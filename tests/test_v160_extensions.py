# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | v1.6.0 EXTENSIONS TESTS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# -----------------------------------------------------------------------------

"""Registry, tool catalog/dispatch, tool-call parsing, prompt block, slash routing."""

import json
import textwrap

import pytest

from core_system import settings
from core_system.extensions import registry, sandbox, slash, tools
from core_system.prompting.constitution import build_system_prompt


@pytest.fixture
def ext(tmp_path):
    root = tmp_path / "extensions"
    (root / "skills").mkdir(parents=True)
    (root / "plugins").mkdir()
    registry.set_root(root)
    settings.set_path(tmp_path / "settings.json")
    yield root
    settings.set_path(tmp_path / "unused.json")


def _skill(root, name, desc="Does a thing", body="Step 1. Do it."):
    d = root / "skills" / name
    d.mkdir()
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\n{body}\n",
                                encoding="utf-8")
    return d


def _plugin(root, folder, manifest=None, code=None, **overrides):
    d = root / "plugins" / folder
    d.mkdir()
    m = {
        "name": folder, "description": "test plugin", "version": "1.0.0",
        "permissions": {"network": False, "files": "none"},
        "tools": [{"name": f"{folder.replace('-', '_')}_echo", "description": "echo",
                   "parameters": {"type": "object", "properties": {"x": {"type": "string"}}}}],
    }
    m.update(overrides)
    (d / "plugin.json").write_text(json.dumps(manifest or m), encoding="utf-8")
    (d / "main.py").write_text(code or "def noop():\n    return 'x'\n", encoding="utf-8")
    return d


def test_skill_frontmatter_parsed(ext):
    _skill(ext, "summarize", desc="Summarize text", body="Be brief.\nUse bullets.")
    skill = registry.get_skill("summarize")
    assert skill.description == "Summarize text"
    assert skill.body == "Be brief.\nUse bullets."
    assert registry.scan().errors == []


def test_valid_plugin_manifest_parsed(ext):
    _plugin(ext, "echo")
    (p,) = registry.list_plugins()
    assert (p.name, p.version, p.entry) == ("echo", "1.0.0", "main.py")
    assert p.permissions == {"network": False, "files": "none"}
    assert p.tools[0]["name"] == "echo_echo"
    assert len(p.hash) == 64 and p.approved is False


@pytest.mark.parametrize("folder,overrides,reason", [
    ("bad", {"name": "Bad Name"}, "must match folder"),
    ("esc", {"entry": "../x.py"}, "plain .py filename"),
    ("res", {"tools": [{"name": "read_file"}]}, "reserved"),
    ("none", {"tools": []}, "non-empty"),
])
def test_bad_manifests_rejected(ext, folder, overrides, reason):
    _plugin(ext, folder, **overrides)
    reg = registry.scan()
    assert reg.plugins == {}
    assert len(reg.errors) == 1 and reason in reg.errors[0], reg.errors


def test_duplicate_tool_across_plugins_rejected(ext):
    tool = [{"name": "shared", "description": ""}]
    _plugin(ext, "aaa", tools=tool)
    _plugin(ext, "bbb", tools=tool)
    reg = registry.scan()
    assert list(reg.plugins) == ["aaa"]
    assert reg.errors and "already used" in reg.errors[0]


def test_hash_change_drops_approval(ext):
    d = _plugin(ext, "echo")
    assert registry.approve("echo")
    assert registry.list_plugins()[0].approved
    (d / "main.py").write_text("def noop():\n    return 'changed!'\n", encoding="utf-8")
    assert not registry.list_plugins()[0].approved
    assert registry.revoke("echo") and not registry.revoke("echo")


def test_catalog_hides_unapproved_and_includes_use_skill(ext):
    _skill(ext, "summarize")
    _plugin(ext, "echo")
    names = [t["name"] for t in tools.tool_catalog()]
    assert names == ["use_skill"]
    registry.approve("echo")
    cat = tools.tool_catalog(include_files=True)
    assert [t["name"] for t in cat] == ["use_skill", "echo_echo", "read_file", "list_dir", "write_file"]
    assert cat[0]["parameters"]["properties"]["name"]["enum"] == ["summarize"]


def test_dispatch_use_skill_and_refusals(ext):
    _skill(ext, "summarize", body="Be brief.")
    _plugin(ext, "echo")
    assert tools.dispatch("use_skill", {"name": "summarize"}) == {"ok": True, "result": "Be brief.", "error": ""}
    assert not tools.dispatch("nope", {})["ok"]
    assert tools.dispatch("echo_echo", {})["error"] == "Plugin not approved"
    assert not tools.dispatch("read_file", {"path": "x"})["ok"]


def test_dispatch_runs_plugin_through_sandbox(ext):
    code = textwrap.dedent("""
        def echo_echo(x):
            return "got " + x
    """)
    _plugin(ext, "echo", code=code)
    registry.approve("echo")
    r = tools.dispatch("echo_echo", {"x": "hi"})
    assert r == {"ok": True, "result": "got hi", "error": ""}


def test_web_search_disabled_never_spawns(ext, monkeypatch):
    _plugin(ext, "web_search", tools=[{"name": "web_search", "description": "search"}],
            permissions={"network": True, "files": "none"})
    registry.approve("web_search")

    def boom(*a, **k):
        raise AssertionError("sandbox must not be spawned")

    monkeypatch.setattr(sandbox, "run_tool", boom)
    r = tools.dispatch("web_search", {"q": "x"})
    assert r == {"ok": False, "result": "", "error": "Web access is disabled in Settings."}


def test_policy_from_permissions_and_folders(ext, monkeypatch):
    _plugin(ext, "web_search", tools=[{"name": "web_search", "description": "search"}],
            permissions={"network": True, "files": "allowlist"})
    registry.approve("web_search")
    settings.update({"web.enabled": True,
                     "allow.folders": [{"path": "E:/docs", "write": False}, {"path": "E:/out", "write": True}]})
    seen = {}
    monkeypatch.setattr(sandbox, "run_tool",
                        lambda d, e, t, a, policy, timeout=30.0: seen.update(policy) or
                        {"ok": True, "result": "r", "error": "", "denied": False})
    assert tools.dispatch("web_search", {})["ok"]
    assert seen == {"network": True, "read_paths": ["E:/docs", "E:/out"], "write_paths": ["E:/out"], "mem_mb": 512}


def test_parse_tool_calls():
    text = (
        'a <tool_call>{"name": "x", "arguments": {"q": 1}}</tool_call> b '
        '<tool_call>{not json}</tool_call>'
        '<tool_call>{"name": "y"}</tool_call>'
        '<tool_call>{"arguments": {}}</tool_call>'
        '<tool_call>{"name": "z", "arguments": {"k": "v"}}'  # unclosed tail (stop token)
    )
    assert tools.parse_tool_calls(text) == [("x", {"q": 1}), ("y", {}), ("z", {"k": "v"})]
    assert tools.parse_tool_calls("plain answer") == []
    assert tools.strip_tool_calls('hi <tool_call>{"name": "x"}</tool_call>') == "hi"


def test_build_system_prompt_tools_block():
    block = tools.render_tools_block([{"name": "t", "description": "d", "parameters": {}}])
    assert "<tools>\n{" in block and "<function=example_function_name>" in block
    assert tools.render_tools_block([]) == ""
    for thinking in (False, True):
        with_tools = build_system_prompt(model_format="chatml", thinking=thinking, tools_block=block,
                                         context_str="doc text")
        assert "<tools>" in with_tools
        assert with_tools.index("<tools>") < with_tools.index("Relevant excerpts from the user's documents")
        assert "<tools>" not in build_system_prompt(model_format="chatml", thinking=thinking)


def test_slash_routing(ext):
    _skill(ext, "summarize", desc="Summarize text", body="Be brief.")
    _plugin(ext, "echo")
    assert slash.route("hello") == ("passthrough", "hello")
    assert slash.route("/unknown thing") == ("passthrough", "/unknown thing")
    kind, out = slash.route("/skills")
    assert kind == "local" and "summarize — Summarize text" in out
    kind, out = slash.route("/plugins")
    assert kind == "local" and "echo v1.0.0 [NOT approved]" in out and "network: off" in out
    assert slash.route("/Summarize this paragraph") == (
        "prompt", "[Skill: summarize]\nBe brief.\n\n[Task]\nthis paragraph")
