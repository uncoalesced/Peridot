import re
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement


REQUIREMENTS = Path(__file__).resolve().parents[1] / "requirements.txt"


def _canon(name: str) -> str:
    """PEP 503 name normalisation.

    requirements.txt spells some distributions with underscores
    (llama_cpp_python, huggingface_hub) while everything else uses hyphens.
    pip treats those as the same name, so lookups here must too -- a plain
    .lower() silently misses them.
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement_lines():
    for line_number, raw_line in enumerate(REQUIREMENTS.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-", "--")):
            continue
        yield line_number, line


def _parsed_requirements():
    parsed = []
    errors = []
    for line_number, line in _requirement_lines():
        try:
            parsed.append(Requirement(line))
        except InvalidRequirement as exc:
            errors.append(f"line {line_number}: {line!r} ({exc})")
    assert not errors, "Invalid requirement entries:\n" + "\n".join(errors)
    return parsed


def test_requirements_are_valid_pep508_and_do_not_pin_refused_turbovec():
    requirements = _parsed_requirements()
    by_name = {_canon(req.name): req for req in requirements}

    # turbovec replaced faiss as the vector index; faiss must not creep back in.
    assert "faiss-cpu" not in by_name
    # turbovec 0.7.1's API doesn't match turbovec_index.py's native path, which
    # refuses it and uses the numpy fallback -- pinning it installs dead weight.
    assert "turbovec" not in by_name

    # PyPDF2 used to be asserted here, but nothing imports it -- PDF extraction
    # goes through PyMuPDF/fitz (core_system/memory/vault.py) -- so it was
    # dropped when requirements.txt was trimmed to actually-imported packages.
    assert "pypdf2" not in by_name
    assert "pymupdf" in by_name, "PDF ingestion depends on PyMuPDF"

    # These must stay pinned, but assert *that* they are pinned rather than to
    # which version: exact-string assertions here broke on every routine bump
    # and taught no one anything.
    for package in ("pillow", "flask-limiter", "numpy", "llama-cpp-python"):
        specifier = str(by_name[package].specifier)
        assert specifier.startswith("=="), f"{package} must stay exactly pinned"


def test_runtime_requirements_have_no_unimported_extras():
    """Guard the Phase-4 dependency trim.

    requirements.txt is meant to list only packages first-party code actually
    imports (plus explicitly-commented compatibility constraints). These were
    each declared and never imported; they should not silently return.
    """
    by_name = {_canon(req.name) for req in _parsed_requirements()}
    # pyaudio is deliberately absent from this list: speech_recognition's
    # Microphone imports it at runtime, so it is needed despite no direct import.
    for package in ("colorama", "torchaudio", "torchvision",
                    "pip-audit", "cyclonedx-python-lib", "scikit-learn"):
        assert package not in by_name, (
            f"{package} is declared but imported nowhere in first-party code; "
            "dev/audit tooling belongs in pyproject.toml optional-dependencies"
        )


def test_torch_matrix_is_platform_isolated():
    requirements = _parsed_requirements()

    # torchaudio/torchvision were dropped from the matrix: declared but never
    # imported. Only torch keeps the Windows-CUDA / non-Windows-CPU split.
    for package in ("torch",):
        entries = [req for req in requirements if _canon(req.name) == package]
        assert len(entries) == 2, f"expected Windows CUDA and non-Windows CPU entries for {package}"

        windows_entries = [req for req in entries if req.marker and "sys_platform == \"win32\"" in str(req.marker)]
        non_windows_entries = [req for req in entries if req.marker and "sys_platform != \"win32\"" in str(req.marker)]
        assert len(windows_entries) == 1, f"missing Windows-only CUDA marker for {package}"
        assert len(non_windows_entries) == 1, f"missing non-Windows standard marker for {package}"

        windows_entry = windows_entries[0]
        url = str(windows_entry.url or "")
        assert "%2Bcu" in url, f"{package} Windows entry must use a CUDA wheel"
        # download.pytorch.org answers 403 to a raw "+" in the wheel URL.
        assert "+" not in url, f"{package} Windows wheel URL must keep '+' encoded as %2B"

        non_windows_entry = non_windows_entries[0]
        assert not non_windows_entry.url, f"{package} non-Windows entry must use standard package index resolution"
        assert "+cu" not in str(non_windows_entry.specifier), f"{package} non-Windows entry must not pin CUDA wheels"
        assert str(non_windows_entry.specifier).startswith("=="), f"{package} non-Windows entry must stay pinned"
