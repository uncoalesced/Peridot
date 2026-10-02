# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.6.0 | INVOCATION FILE TOOLS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
read_file / list_dir / write_file for the model, confined to the Settings
"allow.folders" allowlist ({path, write} dicts; plain strings are read-only).

Every path is resolved (symlinks followed, ".." collapsed) before the
containment check, so a link or traversal that lands outside a root is
refused. Errors never carry file contents. Importing this module registers
the handlers in tools.FILE_TOOL_HANDLERS.
"""

import os
from pathlib import Path

from core_system.extensions import tools
from core_system.security import is_file_safe, log_event

MAX_READ = 200 * 1024
MAX_ENTRIES = 500
MAX_WRITE = 1024 * 1024
DENIED = "Path is outside the folders allowlisted for Sovereign Invocation."


def _out(ok, result="", error=""):
    return {"ok": ok, "result": result, "error": error}


def allowed_roots():
    """[(resolved root Path, writable)] from the allow.folders setting."""
    read, write = tools._folder_policy()
    roots = []
    for path in read:
        if not path.strip():
            continue
        try:
            roots.append((Path(path).expanduser().resolve(), path in write))
        except (OSError, RuntimeError):
            continue
    return roots


def _inside(path, root):
    a, b = os.path.normcase(str(path)), os.path.normcase(str(root))
    try:
        return os.path.commonpath([a, b]) == b
    except ValueError:  # different drives
        return False


def resolve(raw, write=False, tool="invoke"):
    """Resolved Path when raw sits inside an allowlisted (writable, if write) root, else None.

    Relative paths are tried against each root. Denials go to the security log.
    """
    if isinstance(raw, str) and raw.strip() and "\x00" not in raw:
        roots = allowed_roots()
        raw_path = Path(raw).expanduser()
        for root, writable in roots:
            if write and not writable:
                continue
            try:
                p = (raw_path if raw_path.is_absolute() else root / raw_path).resolve()
            except (OSError, RuntimeError):
                continue
            if _inside(p, root) and is_file_safe(str(p))[0]:
                return p
    log_event("INVOKE_DENIED", f"{tool} {'write' if write else 'read'} {str(raw)[:200]!r}", "WARNING")
    return None


def read_file(arguments):
    p = resolve(arguments.get("path"), tool="read_file")
    if p is None:
        return _out(False, error=DENIED)
    if not p.is_file():
        return _out(False, error="Not a file.")
    try:
        if p.suffix.lower() == ".pdf":
            try:
                import fitz
            except ImportError:
                return _out(False, error="PDF support (PyMuPDF) is not installed.")
            with fitz.open(str(p)) as doc:
                text = "\n".join(page.get_text() for page in doc)
            raw_len = len(text)
            text = text[:MAX_READ]
        else:
            with open(p, "rb") as f:
                raw = f.read(MAX_READ + 1)
            if b"\x00" in raw[:8192]:
                return _out(False, error="Binary file; only text and PDF files can be read.")
            raw_len = len(raw)
            text = raw[:MAX_READ].decode("utf-8", errors="replace")
    except Exception as e:
        return _out(False, error=f"Could not read file ({type(e).__name__}).")
    if raw_len > MAX_READ:
        text += "\n[truncated at 200KB]"
    return _out(True, text)


def list_dir(arguments):
    p = resolve(arguments.get("path"), tool="list_dir")
    if p is None:
        return _out(False, error=DENIED)
    if not p.is_dir():
        return _out(False, error="Not a directory.")
    try:
        entries = sorted(os.scandir(p), key=lambda e: e.name.lower())
        lines = []
        for e in entries[:MAX_ENTRIES]:
            if e.is_dir():
                lines.append(f"{e.name}/ [dir]")
            else:
                lines.append(f"{e.name} ({e.stat().st_size} bytes)")
    except Exception as e:
        return _out(False, error=f"Could not list directory ({type(e).__name__}).")
    if len(entries) > MAX_ENTRIES:
        lines.append(f"... {len(entries) - MAX_ENTRIES} more entries")
    return _out(True, "\n".join(lines) or "(empty)")


def write_file(arguments):
    content = arguments.get("content")
    if not isinstance(content, str):
        return _out(False, error="'content' must be a string.")
    if len(content) > MAX_WRITE:
        return _out(False, error="Content too large (max 1MB).")
    p = resolve(arguments.get("path"), write=True, tool="write_file")
    if p is None:
        return _out(False, error="Path is outside the writable folders allowlisted for Sovereign Invocation.")
    if p.is_dir():
        return _out(False, error="Path is a directory.")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(content)
    except Exception as e:
        return _out(False, error=f"Could not write file ({type(e).__name__}).")
    return _out(True, f"Wrote {len(content)} characters to {p.name}.")


tools.FILE_TOOL_HANDLERS.update(read_file=read_file, list_dir=list_dir, write_file=write_file)
