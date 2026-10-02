# -----------------------------------------------------------------------------
# PERIDOT SETTINGS STORE | Persistent Runtime Preferences (v1.6.0)
# Copyright (C) 2026 uncoalesced
#
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------
# Flat dotted keys in storage/settings.json. Every key must exist in DEFAULTS
# and keep the default's type; a missing or corrupt file degrades to defaults.

import copy
import json
import os
import threading
from pathlib import Path

from config import STORAGE_PATH

from core_system.audit import ghost

DEFAULTS = {
    "extensions.model_invoke": True,
    "web.enabled": False,
    "web.searxng_url": "",
    "allow.folders": [],
    "invocation.idle_unload_s": 300,
    "invocation.review_timeout_s": 120,
    "plugins.approved": {},
    "model.active": "",
    # Computer use (core_system/computer): scaffold only in v1.6.0, off.
    "computer.enabled": False,
    "computer.require_approval": True,
    "computer.allowed_apps": [],
    "computer.max_actions_per_turn": 25,
}

_path = Path(STORAGE_PATH) / "settings.json"
_lock = threading.Lock()
_cache = {"mtime": None, "data": {}}


def _warn(msg):
    try:
        ghost.warning(msg)
    except Exception:
        pass


def set_path(path):
    """Point the store at another file (tests)."""
    global _path
    with _lock:
        _path = Path(path)
        _cache["mtime"] = None
        _cache["data"] = {}


def _load():
    """Return the on-disk dict, re-reading only when mtime changes."""
    try:
        mtime = _path.stat().st_mtime_ns
    except OSError:
        return {}
    if mtime == _cache["mtime"]:
        return _cache["data"]
    try:
        data = json.loads(_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("settings root is not an object")
    except Exception as e:
        _warn(f"[SETTINGS] Unreadable {_path.name}, using defaults: {e}")
        data = {}
    # Drop unknown or mistyped keys so a hand-edited file cannot poison callers.
    data = {k: v for k, v in data.items() if k in DEFAULTS and _type_ok(k, v)}
    _cache["mtime"], _cache["data"] = mtime, data
    return data


def _type_ok(key, value):
    want = type(DEFAULTS[key])
    # bool is a subclass of int; keep them distinct both ways.
    if isinstance(value, bool) != (want is bool):
        return False
    return isinstance(value, want)


def all():  # shadows the builtin by contract; callers use settings.all()
    with _lock:
        merged = copy.deepcopy(DEFAULTS)
        merged.update(copy.deepcopy(_load()))
        return merged


def get(key):
    if key not in DEFAULTS:
        raise ValueError(f"Unknown setting: {key}")
    with _lock:
        return copy.deepcopy(_load().get(key, DEFAULTS[key]))


def update(changes):
    if not isinstance(changes, dict):
        raise ValueError("Settings update must be an object")
    for key, value in changes.items():
        if key not in DEFAULTS:
            raise ValueError(f"Unknown setting: {key}")
        if not _type_ok(key, value):
            raise ValueError(f"Setting {key} expects {type(DEFAULTS[key]).__name__}")
    with _lock:
        data = dict(_load())
        data.update(changes)
        _path.parent.mkdir(parents=True, exist_ok=True)
        tmp = _path.with_suffix(_path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, _path)
        _cache["mtime"] = None  # force a re-read on next access
    return all()
