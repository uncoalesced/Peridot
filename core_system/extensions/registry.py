# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.6.0 | EXTENSION REGISTRY
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Discovers user skills and plugins under <BASE_DIR>/extensions.

  extensions/skills/<name>/SKILL.md      frontmatter (name, description) + body
  extensions/plugins/<name>/plugin.json  manifest + entry file, run via sandbox

A plugin is approved only while settings "plugins.approved"[name] equals the
sha256 of its current files, so any edit drops it back to unapproved.
Imports stay light (config, settings, audit): core.py loads this in the UI
process.
"""

import dataclasses
import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

from config import BASE_DIR

from core_system import settings

try:
    from core_system.audit import ghost
except Exception:  # pragma: no cover - audit is optional at import time
    ghost = None

EXTENSIONS_DIR = Path(BASE_DIR) / "extensions"

RESERVED_TOOLS = frozenset({"use_skill", "read_file", "list_dir", "write_file"})
_NAME_RE = re.compile(r"[a-z0-9_-]{1,40}")
_TOOL_RE = re.compile(r"[a-z0-9_]{1,40}")
_FILE_PERMS = ("allowlist", "none")


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path


@dataclass
class Plugin:
    name: str
    description: str
    version: str
    entry: str
    permissions: dict
    tools: list
    path: Path
    hash: str
    approved: bool = False


@dataclass
class Registry:
    skills: dict = field(default_factory=dict)   # name -> Skill
    plugins: dict = field(default_factory=dict)  # name -> Plugin
    errors: list = field(default_factory=list)   # "plugins/<dir>: reason"


_lock = threading.Lock()
_cache = {"key": None, "reg": None}


def _warn(msg):
    if ghost is None:
        return
    try:
        ghost.warning(msg)
    except Exception:
        pass


def set_root(path):
    """Point discovery at another extensions dir (tests)."""
    global EXTENSIONS_DIR
    with _lock:
        EXTENSIONS_DIR = Path(path)
        _cache["key"] = _cache["reg"] = None


# --- parsing -----------------------------------------------------------------

def parse_frontmatter(text):
    """Tiny `key: value` frontmatter reader. Returns (meta, body) or (None, text)."""
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            meta = {}
            for raw in lines[1:i]:
                key, sep, value = raw.partition(":")
                if sep and key.strip():
                    meta[key.strip().lower()] = value.strip().strip("\"'")
            return meta, "\n".join(lines[i + 1:]).strip()
    return None, text


def _load_skill(folder):
    text = (folder / "SKILL.md").read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    if meta is None:
        raise ValueError("SKILL.md has no --- frontmatter")
    name = meta.get("name") or folder.name
    if name != folder.name or not _NAME_RE.fullmatch(name):
        raise ValueError(f"name {name!r} must match folder and [a-z0-9_-]{{1,40}}")
    if not body:
        raise ValueError("SKILL.md body is empty")
    return Skill(name, meta.get("description", ""), body, folder)


def plugin_hash(folder):
    """sha256 over sorted relative paths + bytes of every file (no __pycache__)."""
    folder = Path(folder)
    files = sorted(
        p.relative_to(folder).as_posix()
        for p in folder.rglob("*")
        if p.is_file() and "__pycache__" not in p.relative_to(folder).parts
    )
    h = hashlib.sha256()
    for rel in files:
        data = (folder / rel).read_bytes()
        h.update(f"{rel}\0{len(data)}\0".encode("utf-8"))
        h.update(data)
    return h.hexdigest()


def _load_plugin(folder, taken):
    manifest = json.loads((folder / "plugin.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("plugin.json is not an object")

    name = manifest.get("name")
    if name != folder.name or not isinstance(name, str) or not _NAME_RE.fullmatch(name):
        raise ValueError(f"name {name!r} must match folder and [a-z0-9_-]{{1,40}}")

    entry = manifest.get("entry", "main.py")
    if (not isinstance(entry, str) or not entry.endswith(".py")
            or entry != os.path.basename(entry) or "/" in entry or "\\" in entry
            or entry in (".", "..") or ":" in entry):
        raise ValueError(f"entry {entry!r} must be a plain .py filename inside the plugin folder")
    if not (folder / entry).is_file():
        raise ValueError(f"entry {entry!r} not found")

    perms = manifest.get("permissions", {})
    if not isinstance(perms, dict):
        raise ValueError("permissions must be an object")
    network = perms.get("network", False)
    files = perms.get("files", "none")
    if not isinstance(network, bool) or files not in _FILE_PERMS:
        raise ValueError("permissions need network: bool and files: 'allowlist'|'none'")

    tools = manifest.get("tools")
    if not isinstance(tools, list) or not tools:
        raise ValueError("tools must be a non-empty list")
    clean, seen = [], set()
    for tool in tools:
        tname = tool.get("name") if isinstance(tool, dict) else None
        if not isinstance(tname, str) or not _TOOL_RE.fullmatch(tname):
            raise ValueError(f"tool name {tname!r} must match [a-z0-9_]{{1,40}}")
        if tname in RESERVED_TOOLS:
            raise ValueError(f"tool name {tname!r} is reserved")
        if tname in seen or tname in taken:
            raise ValueError(f"tool name {tname!r} already used by {taken.get(tname, name)!r}")
        params = tool.get("parameters", {"type": "object", "properties": {}})
        if not isinstance(params, dict):
            raise ValueError(f"tool {tname!r} parameters must be a JSON-schema object")
        seen.add(tname)
        clean.append({"name": tname, "description": str(tool.get("description", "")),
                      "parameters": params})

    return Plugin(
        name=name,
        description=str(manifest.get("description", "")),
        version=str(manifest.get("version", "0.0.0")),
        entry=entry,
        permissions={"network": network, "files": files},
        tools=clean,
        path=folder,
        hash=plugin_hash(folder),
    )


# --- scanning ----------------------------------------------------------------

def _subdirs(path):
    try:
        return sorted(p for p in path.iterdir() if p.is_dir() and p.name != "__pycache__")
    except OSError:
        return []


def _signature(root):
    """Cheap change detector: (path, mtime, size) of everything under root."""
    sig = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            try:
                st = os.stat(p)
            except OSError:
                continue
            sig.append((p, st.st_mtime_ns, st.st_size))
    return tuple(sorted(sig))


def _build(root):
    reg = Registry()
    for folder in _subdirs(root / "skills"):
        try:
            skill = _load_skill(folder)
            reg.skills[skill.name] = skill
        except Exception as e:
            reg.errors.append(f"skills/{folder.name}: {e}")

    taken = {}  # tool name -> owning plugin
    for folder in _subdirs(root / "plugins"):
        try:
            plugin = _load_plugin(folder, taken)
        except Exception as e:
            reg.errors.append(f"plugins/{folder.name}: {e}")
            continue
        reg.plugins[plugin.name] = plugin
        for tool in plugin.tools:
            taken[tool["name"]] = plugin.name

    for err in reg.errors:
        _warn(f"[EXTENSIONS] Skipped {err}")
    return reg


def scan(force=False):
    """Return the current Registry; reparses only when files under the root change."""
    with _lock:
        root = EXTENSIONS_DIR
        key = (str(root), _signature(root))
        if force or key != _cache["key"]:
            _cache["key"], _cache["reg"] = key, _build(root)
        reg = _cache["reg"]
    # Approval is read live so approve()/revoke() never wait on a rescan.
    approved = settings.get("plugins.approved")
    plugins = {n: dataclasses.replace(p, approved=approved.get(n) == p.hash)
               for n, p in reg.plugins.items()}
    return Registry(dict(reg.skills), plugins, list(reg.errors))


def rescan(force=True):
    return scan(force=force)


def list_skills():
    return list(scan().skills.values())


def list_plugins():
    return list(scan().plugins.values())


def get_skill(name):
    return scan().skills.get(name)


def find_tool(tool_name):
    """(Plugin, tooldef) for a plugin tool, approved or not; None if unknown."""
    for plugin in scan().plugins.values():
        for tool in plugin.tools:
            if tool["name"] == tool_name:
                return plugin, tool
    return None


def approve(name):
    """Pin the plugin's current hash as approved. False if no such valid plugin."""
    plugin = rescan().plugins.get(name)
    if plugin is None:
        return False
    approved = settings.get("plugins.approved")
    approved[name] = plugin.hash
    settings.update({"plugins.approved": approved})
    return True


def revoke(name):
    approved = settings.get("plugins.approved")
    if approved.pop(name, None) is None:
        return False
    settings.update({"plugins.approved": approved})
    return True
