# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | v1.6.0 MODEL TOOL LOOP TESTS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# -----------------------------------------------------------------------------

"""/ask and /ask/stream tool loop, web pre-search, cache bypass, kernel handshake.

Runs server.py against the test_agent3 stub harness with a scripted LLM.
"""

import importlib
import json
import queue
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_agent3_rag_mtbf import _STUBBED_MODULES, _drop_modules, _install_common_runtime_stubs  # noqa: E402

from core_system import settings  # noqa: E402
from core_system.extensions import registry, sandbox, tools  # noqa: E402
from core_system.invocation import agent  # noqa: E402

CALL = 'Let me look.<tool_call>{"name": "lookup", "arguments": {"q": "x"}}'  # stop string dropped
ANSWER = "[ANALYSIS]\nok\n[KERNEL_RESPONSE]\nThe answer is 42"
CATALOG = [{"name": "lookup", "description": "Look a thing up.",
            "parameters": {"type": "object", "properties": {"q": {"type": "string"}}}}]


class ScriptedLLM:
    """Returns outputs in order (the last one repeats), streaming 4-char chunks."""

    is_loaded = True

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.prompts, self.kwargs = [], []

    def token_count(self, _text):
        return 3

    def generate(self, prompt, **kw):
        self.prompts.append(prompt)
        self.kwargs.append(kw)
        text = self.outputs.pop(0) if len(self.outputs) > 1 else self.outputs[0]
        on_chunk = kw.get("on_chunk")
        if on_chunk:
            for i in range(0, len(text), 4):
                on_chunk(text[i:i + 4])
        return types.SimpleNamespace(text=text, finish_reason="stop", completion_tokens=2, prompt_tokens=3)


def make_server(tmp_path):
    _drop_modules(*_STUBBED_MODULES)
    _install_common_runtime_stubs()
    srv = importlib.import_module("server")
    settings.set_path(tmp_path / "settings.json")
    registry.set_root(tmp_path / "extensions")
    srv.vault = None
    srv.l1_cache = None
    srv.chat_ledger = None
    srv.get_model_format = lambda _p: "chatml"
    srv.kernel.state = srv.KernelState.INFERENCE
    drain_kernel(srv)
    srv.request.json = {"query": "what is it?", "session_id": "s1"}
    srv.request.headers = {"Authorization": f"Bearer {srv.API_KEY}"}
    srv.request.environ = {}
    return srv


def drain_kernel(srv):
    events = []
    while True:
        try:
            events.append(srv.kernel.event_queue.get_nowait())
        except queue.Empty:
            return events


def status(resp):
    return resp[1] if isinstance(resp, tuple) else 200


def body(resp):
    return (resp[0] if isinstance(resp, tuple) else resp).get_json()


@pytest.fixture
def srv(tmp_path):
    old_root = registry.EXTENSIONS_DIR
    yield make_server(tmp_path)
    _drop_modules(*_STUBBED_MODULES)
    registry.set_root(old_root)
    settings.set_path(tmp_path / "unused.json")


@pytest.fixture
def dispatched(monkeypatch):
    """Tools on with a fake catalog; records (name, args, allow_files) per dispatch."""
    seen = []

    def fake_dispatch(name, arguments, *, allow_files=False):
        seen.append((name, arguments, allow_files))
        return {"ok": True, "result": f"result for {name}", "error": ""}

    monkeypatch.setattr(tools, "tool_catalog", lambda include_files=False: [dict(t) for t in CATALOG])
    monkeypatch.setattr(tools, "dispatch", fake_dispatch)
    return seen


def test_tool_call_dispatched_then_answer(srv, dispatched):
    srv.llm = ScriptedLLM(CALL, ANSWER)
    resp = srv.ask()

    assert status(resp) == 200
    assert dispatched == [("lookup", {"q": "x"}, False)]
    assert "The answer is 42" in body(resp)["response"]
    first, second = srv.llm.prompts
    assert "<tools>" in first and '"name": "lookup"' in first
    assert "</tool_call>" in srv.llm.kwargs[0]["stop"]
    turn = second[len(first):]
    assert turn.startswith(CALL + "</tool_call><|im_end|>\n<|im_start|>user\n<tool_response>\n")
    assert json.dumps({"name": "lookup", "result": "result for lookup"}) in turn
    assert turn.endswith("</tool_response><|im_end|>\n<|im_start|>assistant\n")


def test_step_cap_forces_final_answer(srv, dispatched):
    srv.llm = ScriptedLLM(CALL)  # always asks for another tool
    resp = srv.ask()

    assert len(dispatched) == agent.MAX_TOOL_STEPS == 8
    assert agent.TOOL_LIMIT_NOTE in srv.llm.prompts[8]
    assert agent.TOOL_LIMIT_NOTE not in srv.llm.prompts[7]
    assert "<tool_call>" not in body(resp)["response"]


def test_malformed_tool_call_is_text(srv, dispatched):
    srv.llm = ScriptedLLM("Answer: hi <tool_call>{not json}</tool_call>")
    resp = srv.ask()

    assert dispatched == []
    assert len(srv.llm.prompts) == 1
    assert "Answer: hi" in body(resp)["response"]
    assert "<tool_call>" not in body(resp)["response"]


def test_model_invoke_off_means_no_tools(srv, dispatched):
    settings.update({"extensions.model_invoke": False})
    srv.llm = ScriptedLLM(CALL, ANSWER)
    srv.ask()

    assert dispatched == []
    assert len(srv.llm.prompts) == 1
    assert "<tools>" not in srv.llm.prompts[0]
    assert "</tool_call>" not in srv.llm.kwargs[0]["stop"]


def test_web_flag_with_web_disabled_adds_note(srv, dispatched):
    srv.request.json = {"query": "news?", "session_id": "s1", "web": True}
    srv.llm = ScriptedLLM(ANSWER)
    resp = srv.ask()

    assert dispatched == []
    assert body(resp)["notice"] == "Web access is disabled in Settings."
    assert "[SYSTEM NOTE]: Web access is disabled in Settings." in srv.llm.prompts[0]


def test_web_flag_runs_search_first_and_bypasses_cache(srv, dispatched, monkeypatch):
    settings.update({"web.enabled": True})
    monkeypatch.setattr(registry, "scan", lambda force=False: registry.Registry(
        plugins={"web_search": types.SimpleNamespace(approved=True)}))

    class NoCache:
        added = []

        def search(self, _q):
            raise AssertionError("cache lookup must be skipped on web turns")

        def add(self, q, r):
            self.added.append(q)

    srv.l1_cache = NoCache()
    srv.request.json = {"query": "python release?", "session_id": "s1", "web": True}
    srv.llm = ScriptedLLM(ANSWER)
    resp = srv.ask()

    assert status(resp) == 200
    assert dispatched[0] == ("web_search", {"query": "python release?"}, False)
    assert "[WEB SEARCH RESULTS]\nresult for web_search" in srv.llm.prompts[0]
    assert NoCache.added == []
    assert "notice" not in body(resp)


def test_cache_skipped_on_tool_turns_only(srv, dispatched):
    class Cache:
        def __init__(self):
            self.added = []

        def search(self, _q):
            return None

        def add(self, q, r):
            self.added.append(q)

    srv.l1_cache = Cache()
    srv.llm = ScriptedLLM(CALL, ANSWER)
    srv.ask()
    assert srv.l1_cache.added == []

    srv.llm = ScriptedLLM(ANSWER)
    srv.ask()
    assert srv.l1_cache.added == ["what is it?"]


def test_kernel_complete_sent_exactly_once(srv, dispatched, monkeypatch):
    srv.llm = ScriptedLLM(CALL, CALL, ANSWER)
    srv.ask()
    events = drain_kernel(srv)
    assert events.count("PROMPT_RECEIVED") == 1
    assert events.count("INFERENCE_COMPLETE") == 1

    def boom(*_a, **_k):
        raise RuntimeError("tool exploded")

    monkeypatch.setattr(tools, "dispatch", boom)
    srv.llm = ScriptedLLM(CALL, ANSWER)
    assert status(srv.ask()) == 500
    assert drain_kernel(srv).count("INFERENCE_COMPLETE") == 1


def test_stream_emits_tool_events_and_hides_markup(srv, dispatched, monkeypatch):
    srv.llm = ScriptedLLM(CALL, ANSWER)
    events = [json.loads(line) for line in srv.ask_stream().body]

    deltas = "".join(e["delta"] for e in events if "delta" in e)
    assert "Let me look." in deltas and "The answer is 42" in deltas
    assert "<tool" not in deltas and "lookup" not in deltas
    assert [e for e in events if "tool" in e] == [
        {"tool": "lookup", "status": "start"}, {"tool": "lookup", "status": "ok"}]
    assert sum(1 for e in events if e.get("done")) == 1
    assert events[-1]["status"] == 200

    monkeypatch.setattr(tools, "dispatch", lambda name, arguments, *, allow_files=False:
                        {"ok": False, "result": "", "error": "nope"})
    srv.llm = ScriptedLLM(CALL, ANSWER)
    events = [json.loads(line) for line in srv.ask_stream().body]
    assert [e for e in events if "tool" in e][-1] == {"tool": "lookup", "status": "error", "error": "nope"}


def test_markup_filter_holds_partial_prefix():
    out = []
    f = agent.MarkupFilter(out.append)
    for piece in ("Hello <", "to", "ol_call>{secret}"):
        f(piece)
    f.flush()
    assert "".join(out) == "Hello "

    out.clear()
    f = agent.MarkupFilter(out.append)
    for piece in ("a <to", "p> b <t"):
        f(piece)
    f.flush()
    assert "".join(out) == "a <top> b <t"


def test_skill_turn_not_duplicated_in_history(srv):
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "/summarize this text"},
    ]
    srv.chat_ledger = types.SimpleNamespace(get_history=lambda session_id, limit=6: [dict(m) for m in history])
    captured = {}

    def fake_build(**kwargs):
        captured["history"] = list(kwargs["chat_history"])
        return "p"

    srv.build_full_context = fake_build
    srv.request.json = {"query": "[Skill: summarize]\nBe brief.\n\n[Task]\nthis text", "session_id": "s1"}
    srv.llm = ScriptedLLM(ANSWER)
    srv.ask()
    assert [m["content"] for m in captured["history"]] == ["hi", "hello"]


# --------------------------------------------------------------------------- #
# dispatch argument hygiene (searxng_url)
# --------------------------------------------------------------------------- #

def _web_plugin(root):
    d = root / "plugins" / "web_search"
    d.mkdir(parents=True)
    (d / "plugin.json").write_text(json.dumps({
        "name": "web_search", "permissions": {"network": True, "files": "none"},
        "tools": [{"name": "web_search", "description": "s"}, {"name": "web_fetch", "description": "f"}],
    }), encoding="utf-8")
    (d / "main.py").write_text("def web_search(query):\n    return query\n", encoding="utf-8")
    registry.set_root(root)
    registry.approve("web_search")


def test_dispatch_strips_and_injects_searxng_url(tmp_path, monkeypatch):
    old_root = registry.EXTENSIONS_DIR
    settings.set_path(tmp_path / "settings.json")
    try:
        _web_plugin(tmp_path / "extensions")
        seen = []
        monkeypatch.setattr(sandbox, "run_tool", lambda d, e, t, a, policy, timeout=30.0:
                            seen.append((t, dict(a))) or {"ok": True, "result": "r", "error": "", "denied": False})
        settings.update({"web.enabled": True})

        tools.dispatch("web_search", {"query": "x", "searxng_url": "http://10.0.0.1/evil"})
        assert seen[-1] == ("web_search", {"query": "x"})

        settings.update({"web.searxng_url": "http://127.0.0.1:8888"})
        tools.dispatch("web_search", {"query": "x", "searxng_url": "http://10.0.0.1/evil"})
        assert seen[-1] == ("web_search", {"query": "x", "searxng_url": "http://127.0.0.1:8888"})

        tools.dispatch("web_fetch", {"url": "https://a.example", "searxng_url": "http://10.0.0.1"})
        assert seen[-1] == ("web_fetch", {"url": "https://a.example"})
    finally:
        registry.set_root(old_root)
        settings.set_path(tmp_path / "unused.json")
