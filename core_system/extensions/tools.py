# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.6.0 | MODEL TOOL CATALOG & DISPATCH
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
What the model may call, how calls are written (Qwen3.x <tool_call> XML; the
older JSON form is still parsed), and
where they go: use_skill returns a skill body, plugin tools run in the
sandbox, file tools go to FILE_TOOL_HANDLERS. Unapproved plugins never reach
the catalog and are refused at dispatch.
"""

import json
import re
import time

from core_system import settings
from core_system.extensions import registry, sandbox
from core_system.prompting.constitution import FUNCTION_RE, TOOL_CALL_RE, strip_tool_markup

try:
    from core_system.audit import ghost
except Exception:  # pragma: no cover - audit is optional at import time
    ghost = None

WEB_PLUGIN = "web_search"

FILE_TOOLS = [
    {"name": "read_file", "description": "Read a text file inside an allowed folder.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}},
                    "required": ["path"]}},
    {"name": "list_dir", "description": "List the entries of a directory inside an allowed folder.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}},
                    "required": ["path"]}},
    {"name": "write_file", "description": "Write a text file inside a writable allowed folder.",
     "parameters": {"type": "object",
                    "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                    "required": ["path", "content"]}},
]

# name -> handler(arguments: dict) -> {"ok", "result", "error"}; populated by the file-tools leaf.
FILE_TOOL_HANDLERS: dict = {}

_PARAM_RE = re.compile(r"<parameter=([^>\n]+)>(.*?)(?:</parameter>|(?=<parameter=)|\Z)", re.DOTALL)


def _out(ok, result="", error=""):
    return {"ok": ok, "result": result, "error": error}


def tool_catalog(include_files: bool = False) -> list:
    """Tools the model is offered. web_search's tools are left out while web
    access is off in Settings: offering them only produced calls that dispatch
    then refused."""
    reg = registry.scan()
    catalog = []
    if reg.skills:
        catalog.append({
            "name": "use_skill",
            "description": "Load the instructions of a named skill. Skills: " + "; ".join(
                f"{s.name}: {s.description}" for s in reg.skills.values()),
            "parameters": {"type": "object",
                           "properties": {"name": {"type": "string", "enum": sorted(reg.skills)}},
                           "required": ["name"]},
        })
    web_on = bool(settings.get("web.enabled"))
    for plugin in reg.plugins.values():
        if plugin.approved and (web_on or plugin.name != WEB_PLUGIN):
            catalog.extend(dict(t) for t in plugin.tools)
    if include_files:
        catalog.extend(dict(t) for t in FILE_TOOLS)
    return catalog


def _folder_policy():
    read, write = [], []
    for entry in settings.get("allow.folders"):
        if isinstance(entry, str):
            read.append(entry)
        elif isinstance(entry, dict) and isinstance(entry.get("path"), str):
            read.append(entry["path"])
            if entry.get("write") is True:
                write.append(entry["path"])
    return read, write


def _dispatch(name, arguments, allow_files):
    if not isinstance(arguments, dict):
        return _out(False, error="Tool arguments must be an object.")

    if name == "use_skill":
        skill = registry.get_skill(str(arguments.get("name", "")))
        if skill is None:
            return _out(False, error=f"Unknown skill: {arguments.get('name')!r}")
        return _out(True, skill.body)

    if name in registry.RESERVED_TOOLS:  # file tools
        if not allow_files:
            return _out(False, error="File access is not enabled for this request.")
        handler = FILE_TOOL_HANDLERS.get(name)
        if handler is None:
            return _out(False, error=f"File tool {name!r} is not available.")
        return handler(arguments)

    found = registry.find_tool(name)
    if found is None:
        return _out(False, error=f"Unknown tool: {name!r}")
    plugin, _tool = found
    if not plugin.approved:
        return _out(False, error="Plugin not approved")

    # web_search's network is additionally gated by the Settings toggle.
    if plugin.name == WEB_PLUGIN:
        if not settings.get("web.enabled"):
            return _out(False, error="Web access is disabled in Settings.")
        # searxng_url is a hidden arg (bundled/web_search/main.py): SearXNG
        # requests skip the private-address guard, so only Settings may set it.
        arguments = {k: v for k, v in arguments.items() if k != "searxng_url"}
        searxng = settings.get("web.searxng_url").strip()
        if name == "web_search" and searxng:
            arguments["searxng_url"] = searxng
    network = plugin.permissions["network"]
    read, write = _folder_policy() if plugin.permissions["files"] == "allowlist" else ([], [])
    policy = {"network": network, "read_paths": read, "write_paths": write, "mem_mb": 512}
    r = sandbox.run_tool(plugin.path, plugin.entry, name, arguments, policy)
    return _out(r["ok"], r["result"], r["error"])


def dispatch(name, arguments: dict, *, allow_files: bool = False) -> dict:
    started = time.monotonic()
    try:
        out = _dispatch(name, arguments, allow_files)
    except Exception as e:
        out = _out(False, error=f"Tool {name!r} failed: {e}")
    if ghost is not None:
        try:
            ghost.info(f"[TOOLS] dispatch {name} ok={out['ok']} {time.monotonic() - started:.2f}s")
        except Exception:
            pass
    return out


def render_tools_block(catalog: list) -> str:
    """Tool declaration in the model's own (Qwen3.x GGUF template) format; empty catalog -> ""."""
    if not catalog:
        return ""
    lines = [
        "# Tools",
        "",
        "You have access to the following functions:",
        "",
        "<tools>",
        *(json.dumps(t, ensure_ascii=False) for t in catalog),
        "</tools>",
        "",
        "If you choose to call a function ONLY reply in the following format with NO suffix:",
        "",
        "<tool_call>",
        "<function=example_function_name>",
        "<parameter=example_parameter_1>",
        "value_1",
        "</parameter>",
        "</function>",
        "</tool_call>",
        "",
        "After a tool call, stop and wait for <tool_response>. Never claim to have looked "
        "something up unless a tool_response gave you the result. Call a tool only when it "
        "actually helps; otherwise answer normally.",
    ]
    return "\n".join(lines) + "\n"


def _param_value(raw: str):
    value = raw.strip("\r\n")
    try:
        return json.loads(value)
    except ValueError:
        return value


def _parse_json_call(raw: str):
    try:
        obj = json.loads(raw.strip())
    except ValueError:
        return None
    if not isinstance(obj, dict) or not isinstance(obj.get("name"), str):
        return None
    args = obj.get("arguments", {})
    if args is None:
        args = {}
    return (obj["name"], args) if isinstance(args, dict) else None


def _parse_xml_call(name: str, body: str):
    name = name.strip()
    if not name:
        return None
    return name, {k.strip(): _param_value(v) for k, v in _PARAM_RE.findall(body)}


def parse_tool_calls(text: str) -> list:
    """[(name, arguments)] from tool calls; malformed blocks are skipped.

    Accepts the Qwen3.x XML form (<function=NAME><parameter=K>V</parameter>...)
    and the older JSON form inside <tool_call>, a final unclosed block (when
    </tool_call> is a stop token) and a bare <function=...> without the outer tag.
    """
    calls = []
    text = text or ""
    for raw in TOOL_CALL_RE.findall(text):
        fn = FUNCTION_RE.search(raw)
        call = _parse_xml_call(*fn.groups()) if fn else _parse_json_call(raw)
        if call:
            calls.append(call)
    for name, body in FUNCTION_RE.findall(TOOL_CALL_RE.sub("", text)):
        call = _parse_xml_call(name, body)
        if call:
            calls.append(call)
    return calls


def strip_tool_calls(text: str) -> str:
    return strip_tool_markup(text)
