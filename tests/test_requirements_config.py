from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement


REQUIREMENTS = Path(__file__).resolve().parents[1] / "requirements.txt"


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


def test_requirements_are_valid_pep508_and_use_turbovec():
    requirements = _parsed_requirements()
    by_name = {req.name.lower(): req for req in requirements}

    assert "faiss-cpu" not in by_name
    assert str(by_name["turbovec"].specifier) == "==0.7.1"
    assert str(by_name["pillow"].specifier) == "==12.2.0"
    assert str(by_name["pypdf2"].specifier) == "==3.0.1"
    assert str(by_name["flask-limiter"].specifier), "Flask-Limiter must stay pinned"


def test_torch_matrix_is_platform_isolated():
    requirements = _parsed_requirements()

    for package in ("torch", "torchaudio", "torchvision"):
        entries = [req for req in requirements if req.name.lower() == package]
        assert len(entries) == 2, f"expected Windows CUDA and non-Windows CPU entries for {package}"

        windows_entries = [req for req in entries if req.marker and "sys_platform == \"win32\"" in str(req.marker)]
        non_windows_entries = [req for req in entries if req.marker and "sys_platform != \"win32\"" in str(req.marker)]
        assert len(windows_entries) == 1, f"missing Windows-only CUDA marker for {package}"
        assert len(non_windows_entries) == 1, f"missing non-Windows standard marker for {package}"

        windows_entry = windows_entries[0]
        assert "+cu" in str(windows_entry.url or windows_entry.specifier), f"{package} Windows entry must use a CUDA wheel"

        non_windows_entry = non_windows_entries[0]
        assert not non_windows_entry.url, f"{package} non-Windows entry must use standard package index resolution"
        assert "+cu" not in str(non_windows_entry.specifier), f"{package} non-Windows entry must not pin CUDA wheels"
        assert str(non_windows_entry.specifier).startswith("=="), f"{package} non-Windows entry must stay pinned"
