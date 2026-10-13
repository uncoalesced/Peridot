# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | .ENV FILE HELPERS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""Minimal .env reader/writer (replaces python-dotenv as of v1.6.1).

Stdlib-only and side-effect free, so launcher/scripts/benchmarks can use it
without importing config. Supports KEY=VALUE, `export KEY=VALUE`, # comments,
matching '...' / "..." quotes, and ` # comment` after an unquoted value.
ponytail: no ${VAR} interpolation, escape sequences or multi-line values --
Peridot's .env never used them; add if a key ever needs one.
"""

import os
import shutil
from pathlib import Path


def _parse_line(line: str):
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[len("export "):].lstrip()
    key, sep, value = line.partition("=")
    key = key.strip()
    if not sep or not key or not key.replace("_", "").replace(".", "").isalnum():
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1]
    else:
        value = value.split(" #", 1)[0].rstrip()
    return key, value


def read_env(path) -> dict:
    """Parse a .env file into a dict; missing file -> {}. Malformed lines are skipped."""
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return {}
    return dict(kv for kv in map(_parse_line, text.splitlines()) if kv)


def load_env(path, override: bool = False) -> None:
    """Copy a .env file into os.environ; existing variables win unless override."""
    for key, value in read_env(path).items():
        if override or key not in os.environ:
            os.environ[key] = value


def set_env_key(path, key: str, value: str) -> None:
    """Set KEY=value in a .env file, keeping every other line, comment and order.

    Written to a temp file then os.replace()d so a crash mid-write cannot
    truncate .env (it holds API_KEY); the original file's mode is kept.
    """
    path = Path(path)
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        lines = []
    new_line = f"{key}={value}"
    hits = [i for i, line in enumerate(lines) if (_parse_line(line) or (None,))[0] == key]
    for i in hits:
        lines[i] = new_line
    if not hits:
        lines.append(new_line)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if path.exists():
        shutil.copymode(path, tmp)
    os.replace(tmp, path)
