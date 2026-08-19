# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.5.4 | ISOLATED MODEL FETCH
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Subprocess-isolated model acquisition.

Sovereignty rule: the Peridot main process runs with HF_HUB_OFFLINE=1 and
TRANSFORMERS_OFFLINE=1 for its entire lifetime and never opens an outbound
connection. huggingface_hub latches those flags at *import* time, so flipping
them inside a live process is unreliable -- the constant has already been read.

Model downloads therefore run in a short-lived child interpreter that is the
only thing in the system ever given HF_HUB_OFFLINE=0. The child exits, the
file lands on disk, and the parent stays air-gapped.

Every call passes through core_system.security.is_model_download_safe first
(Peridot Directive #2: external interaction routes through the security layer).
"""

import os
import sys
import json
import shutil
import logging
import subprocess
from pathlib import Path

from core_system.security import is_model_download_safe, log_event

logger = logging.getLogger("Peridot-ModelFetch")

# The child does exactly one thing: fetch one file into one directory.
# Arguments arrive as a JSON blob on argv to keep the shell out of the picture.
_CHILD_PROGRAM = """
import json, sys
from huggingface_hub import hf_hub_download, snapshot_download
args = json.loads(sys.argv[1])
if args.get("snapshot"):
    path = snapshot_download(
        repo_id=args["repo_id"],
        local_dir=args["dest_dir"],
        allow_patterns=args.get("allow_patterns"),
    )
else:
    path = hf_hub_download(
        repo_id=args["repo_id"],
        filename=args["filename"],
        local_dir=args["dest_dir"],
    )
print(json.dumps({"path": path}))
"""

# sentence-transformers only needs the PyTorch weights and its config/tokeniser
# files; the repos also ship ONNX/OpenVINO/TF variants worth several hundred MB.
SENTENCE_TRANSFORMER_PATTERNS = [
    "*.json", "*.txt", "*.md", "pytorch_model.bin", "model.safetensors",
    "1_Pooling/*", "2_Normalize/*",
]


def _spawn_fetch_child(payload: dict, timeout: int) -> subprocess.CompletedProcess:
    """Run the fetch child with HF_HUB_OFFLINE=0 in its environment only."""
    child_env = dict(os.environ)
    child_env["HF_HUB_OFFLINE"] = "0"
    child_env["TRANSFORMERS_OFFLINE"] = "0"
    child_env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    child_env["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"

    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    return subprocess.run(
        [sys.executable, "-c", _CHILD_PROGRAM, json.dumps(payload)],
        env=child_env,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
        **kwargs,
    )


def download_snapshot(repo_id: str, dest_dir, allow_patterns=None, timeout: int = 3600) -> Path:
    """
    Fetch a whole repo (e.g. the sentence-transformers embedding model) into
    `dest_dir` via the same isolated child process.
    """
    ok, reason = is_model_download_safe(repo_id, "placeholder.bin", Path(dest_dir).parent)
    if not ok:
        raise PermissionError(reason)

    dest = Path(dest_dir).resolve()
    dest.mkdir(parents=True, exist_ok=True)

    log_event("DOWNLOAD_SUBPROCESS", f"Spawning isolated snapshot child for {repo_id}", "INFO")
    logger.info("Isolated snapshot: %s -> %s", repo_id, dest)

    try:
        proc = _spawn_fetch_child({
            "snapshot": True,
            "repo_id": repo_id,
            "dest_dir": str(dest),
            "allow_patterns": allow_patterns,
        }, timeout)
    except subprocess.TimeoutExpired:
        log_event("DOWNLOAD_FAILED", f"{repo_id} snapshot timed out", "WARNING")
        raise RuntimeError(f"Snapshot fetch timed out after {timeout}s.")

    if proc.returncode != 0:
        log_event("DOWNLOAD_FAILED", f"{repo_id} snapshot exit {proc.returncode}", "WARNING")
        raise RuntimeError(f"Snapshot child failed ({proc.returncode}): {proc.stderr.strip()[-500:]}")

    log_event("DOWNLOAD_COMPLETE", f"{repo_id} snapshot -> {dest}", "INFO")
    return dest


def download_model(repo_id: str, filename: str, dest_dir, timeout: int = 7200) -> Path:
    """
    Fetch `filename` from `repo_id` into `dest_dir` via an isolated child process.

    Returns the resulting Path. Raises PermissionError if the security layer
    rejects the request, or RuntimeError if the child fails.
    """
    ok, reason = is_model_download_safe(repo_id, filename, dest_dir)
    if not ok:
        raise PermissionError(reason)

    dest = Path(dest_dir).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / filename
    if target.exists():
        logger.info("Model already present, skipping fetch: %s", target)
        return target

    log_event(
        "DOWNLOAD_SUBPROCESS",
        f"Spawning isolated fetch child for {repo_id}/{filename}",
        "INFO",
    )
    logger.info("Isolated fetch: %s/%s -> %s", repo_id, filename, dest)

    try:
        proc = _spawn_fetch_child({
            "repo_id": repo_id,
            "filename": filename,
            "dest_dir": str(dest),
        }, timeout)
    except subprocess.TimeoutExpired:
        log_event("DOWNLOAD_FAILED", f"{repo_id}/{filename} timed out", "WARNING")
        raise RuntimeError(f"Model fetch timed out after {timeout}s.")

    if proc.returncode != 0:
        log_event("DOWNLOAD_FAILED", f"{repo_id}/{filename} exit {proc.returncode}", "WARNING")
        raise RuntimeError(f"Model fetch child failed ({proc.returncode}): {proc.stderr.strip()[-500:]}")

    # hf_hub_download may land the file under a nested repo path; normalise it.
    try:
        produced = Path(json.loads(proc.stdout.strip().splitlines()[-1])["path"])
    except Exception:
        produced = target

    if produced.exists() and produced != target:
        shutil.move(str(produced), str(target))

    if not target.exists():
        raise RuntimeError(f"Model fetch reported success but {target} is missing.")

    log_event("DOWNLOAD_COMPLETE", f"{repo_id}/{filename} -> {target}", "INFO")
    return target


def assert_main_process_offline() -> None:
    """
    Boot-time guard. Fails loud if something has unset offline mode in the
    parent, which would mean the kernel could silently phone home.
    """
    for var in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        if os.environ.get(var) != "1":
            log_event("SOVEREIGNTY_VIOLATION", f"{var}={os.environ.get(var)!r} in main process", "CRITICAL")
            raise RuntimeError(
                f"Sovereignty violation: {var} must be '1' in the Peridot main process. "
                "Model downloads belong in core_system.model_fetch.download_model()."
            )


if __name__ == "__main__":
    # Operator entry point for acquiring a model after install:
    #   python -m core_system.model_fetch <repo_id> <filename> [dest_dir]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | [FETCH] %(message)s")

    argv = sys.argv[1:]
    snapshot = "--snapshot" in argv
    if snapshot:
        argv.remove("--snapshot")

    models_root = Path(__file__).resolve().parent.parent / "models"

    try:
        if snapshot:
            if len(argv) not in (1, 2):
                raise ValueError
            is_st = "sentence-transformers" in argv[0]
            # Embedding models land under models/embeddings/ -- that is where
            # core_system/memory/embedder.py looks for a vendored copy.
            default_dest = (models_root / "embeddings" if is_st else models_root) / argv[0].split("/")[-1]
            dest = Path(argv[1]) if len(argv) == 2 else default_dest
            patterns = SENTENCE_TRANSFORMER_PATTERNS if is_st else None
            out = download_snapshot(argv[0], dest, allow_patterns=patterns)
        else:
            if len(argv) not in (2, 3):
                raise ValueError
            dest = Path(argv[2]) if len(argv) == 3 else models_root
            out = download_model(argv[0], argv[1], dest)
    except ValueError:
        print("usage: python -m core_system.model_fetch <repo_id> <filename> [dest_dir]")
        print("       python -m core_system.model_fetch --snapshot <repo_id> [dest_dir]")
        sys.exit(2)
    except (PermissionError, RuntimeError) as exc:
        print(f"[FAILED] {exc}")
        sys.exit(1)
    print(f"[OK] {out}")
