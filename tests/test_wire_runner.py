# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | AGENT-WIRE INTEGRATION TESTS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

from core_system import settings
from core_system.extensions import registry, tools, wire_runner


def test_wire_runner_availability():
    """Verify wire_runner can detect or report binary availability."""
    path = wire_runner.get_wire_path(force_refresh=True)
    if path is not None:
        assert path.is_file()
        assert wire_runner.is_wire_available() is True


def test_wire_dispatch_validation():
    """Test parameter validation on dispatch_wire_tool."""
    # Empty queries should return user-friendly errors
    res = wire_runner.dispatch_wire_tool("web_search", {"query": ""})
    assert res["ok"] is True
    assert "query must be a non-empty string" in res["result"]

    res = wire_runner.dispatch_wire_tool("web_fetch", {"url": ""})
    assert res["ok"] is True
    assert "url must be a non-empty string" in res["result"]

    res = wire_runner.dispatch_wire_tool("wire_research", {"topic": ""})
    assert res["ok"] is True
    assert "topic must be a non-empty string" in res["result"]

    res = wire_runner.dispatch_wire_tool("wire_cite", {"text": ""})
    assert res["ok"] is True
    assert "text must be a non-empty string" in res["result"]

    res = wire_runner.dispatch_wire_tool("unknown_tool", {})
    assert res["ok"] is False
    assert "Unsupported" in res["error"]


def test_wire_mocked_execution(monkeypatch):
    """Test command assembly and execution with mocked run_wire."""
    calls = []

    def fake_run_wire(args, timeout=35.0, input_text=None):
        calls.append((args, timeout, input_text))
        return {"ok": True, "result": "mocked wire result", "error": ""}

    monkeypatch.setattr(wire_runner, "run_wire", fake_run_wire)

    # Search
    res = wire_runner.dispatch_wire_tool("web_search", {"query": "peridot local ai", "n": 3})
    assert res["ok"] is True
    assert calls[-1][0] == ["search", "peridot local ai", "--profile", "local", "--limit", "3"]

    # Read / Fetch
    res = wire_runner.dispatch_wire_tool("web_fetch", {"url": "https://example.com/article"})
    assert res["ok"] is True
    assert calls[-1][0] == ["read", "https://example.com/article", "--profile", "local"]

    # Research
    res = wire_runner.dispatch_wire_tool("wire_research", {"topic": "quantum computing", "days": 7})
    assert res["ok"] is True
    assert calls[-1][0] == ["research", "quantum computing", "--days", "7", "--depth", "quick", "--profile", "local"]

    # Cite
    res = wire_runner.dispatch_wire_tool("wire_cite", {"text": "According to https://example.com this is true."})
    assert res["ok"] is True
    assert calls[-1][0] == ["cite", "-"]
    assert calls[-1][2] == "According to https://example.com this is true."


def test_tools_dispatch_gated_by_web_enabled(tmp_path):
    """Test that web tools are strictly blocked when web.enabled is False."""
    settings.update({"web.enabled": False})
    out = tools.dispatch("web_search", {"query": "test"})
    assert out["ok"] is False
    assert "Web access is disabled in Settings" in out["error"]


def test_tools_dispatch_routes_to_wire(monkeypatch):
    """Test that tools.dispatch calls wire_runner when web is enabled and wire is available."""
    settings.update({"web.enabled": True})
    registry.approve("web_search")

    called = []
    monkeypatch.setattr(wire_runner, "is_wire_available", lambda: True)
    monkeypatch.setattr(wire_runner, "dispatch_wire_tool",
                        lambda name, args: called.append((name, args)) or {"ok": True, "result": "wire-out", "error": ""})

    out = tools.dispatch("web_search", {"query": "hello world"})
    assert out["ok"] is True
    assert out["result"] == "wire-out"
    assert len(called) == 1
    assert called[0][0] == "web_search"
    assert called[0][1]["query"] == "hello world"

    # Reset web.enabled to default False for airgap
    settings.update({"web.enabled": False})
