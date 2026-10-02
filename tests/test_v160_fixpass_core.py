# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | v1.6.0 FIX PASS: REASONING, TOOLS, PROMPT, CANCEL
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# -----------------------------------------------------------------------------

"""Live-bug fix pass (2026-10-01): answers one step behind / leaking reasoning,
XML tool calls, history poisoning, the system prompt rewrite, /ask/cancel."""

import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_v160_toolloop import ScriptedLLM, _web_plugin, body, drain_kernel, make_server  # noqa: E402

from core_system import settings  # noqa: E402
from core_system.extensions import registry, tools  # noqa: E402
from core_system.memory import chat_ledger as ledger_mod  # noqa: E402
from core_system.prompting.builder import build_full_context  # noqa: E402
from core_system.prompting.constitution import (  # noqa: E402
    build_system_prompt,
    is_storable_answer,
    model_display_name,
    parse_kernel_response,
    split_reasoning,
    stream_visible_body,
    strip_reasoning,
)

XML_CALL = ("I'll search.\n<tool_call>\n<function=web_search>\n<parameter=query>\n"
            "Kid Cudi\n</parameter>\n</function>\n")  # </tool_call> is the stop string


# --------------------------------------------------------------------------- #
# reasoning split
# --------------------------------------------------------------------------- #

def test_quoted_think_tags_inside_reasoning_do_not_leak():
    raw = ("<think>\nThe prompt says reason inside <think></think> then answer after "
           "</think>. Fine.\n</think>\n\nHello! How can I help?")
    assert strip_reasoning(raw) == "Hello! How can I help?"
    reasoning, answer = split_reasoning(raw)
    assert answer == "Hello! How can I help?"
    assert reasoning.startswith("The prompt says") and "<think>" not in reasoning
    assert stream_visible_body(raw) == "Hello! How can I help?"
    assert parse_kernel_response(raw) == ("", "Hello! How can I help?")


def test_preseeded_output_without_opening_tag():
    raw = "user greets me\n</think>\n\nHi there."
    assert strip_reasoning(raw) == "Hi there."
    assert split_reasoning(raw) == ("user greets me", "Hi there.")


def test_unclosed_and_untagged():
    assert strip_reasoning("<think>\nstill going") == ""
    assert split_reasoning("<think>\nstill going") == ("still going", "")
    assert stream_visible_body("<think>\nstill going") == ""
    assert strip_reasoning("plain answer") == "plain answer"
    assert split_reasoning("plain answer") == ("", "plain answer")
    assert stream_visible_body("plain answer") == "plain answer"


def test_stream_hides_a_second_open_think_block():
    # Tool loop: the client accumulates every generation's deltas.
    raw = "<think>\na\n</think>\n\nSearching.<think>\nb"
    assert stream_visible_body(raw) == ""
    assert stream_visible_body(raw + "\n</think>\n\nDone.") == "Done."


# --------------------------------------------------------------------------- #
# builder pre-seed
# --------------------------------------------------------------------------- #

def test_builder_preseeds_think_for_thinking_models_only():
    history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    thinking = build_full_context("", history, "q", "chatml", thinking=True)
    plain = build_full_context("", history, "q", "chatml", thinking=False)
    assert thinking.endswith("<|im_start|>assistant\n<think>\n")
    assert plain.endswith("<|im_start|>assistant\n")
    # Past assistant turns carry the template's empty think block.
    assert "<|im_start|>assistant\n<think>\n\n</think>\n\nhello<|im_end|>" in thinking
    assert "<think>" not in plain


# --------------------------------------------------------------------------- #
# tool calls
# --------------------------------------------------------------------------- #

def test_parse_xml_tool_calls():
    one = "<tool_call>\n<function=web_search>\n<parameter=query>\nKid Cudi\n</parameter>\n</function>\n</tool_call>"
    assert tools.parse_tool_calls(one) == [("web_search", {"query": "Kid Cudi"})]
    many = ("<tool_call>\n<function=f>\n<parameter=a>\nx y\n</parameter>\n<parameter=n>\n3\n</parameter>\n"
            "<parameter=flag>\ntrue\n</parameter>\n<parameter=text>\nline1\nline2\n</parameter>\n</function>\n</tool_call>")
    assert tools.parse_tool_calls(many) == [("f", {"a": "x y", "n": 3, "flag": True, "text": "line1\nline2"})]
    assert tools.parse_tool_calls(XML_CALL) == [("web_search", {"query": "Kid Cudi"})]
    bare = "<function=read_file>\n<parameter=path>\nE:/a.txt\n</parameter>\n</function>"
    assert tools.parse_tool_calls(bare) == [("read_file", {"path": "E:/a.txt"})]


def test_parse_json_tool_calls_still_work_and_malformed_ignored():
    text = ('<tool_call>{"name": "x", "arguments": {"q": 1}}</tool_call>'
            "<tool_call>{not json}</tool_call><tool_call>\n<function=>\n</function></tool_call>")
    assert tools.parse_tool_calls(text) == [("x", {"q": 1})]


def test_strip_tool_calls_removes_both_forms():
    assert tools.strip_tool_calls("Hi " + XML_CALL) == "Hi I'll search."
    assert tools.strip_tool_calls('A <tool_call>{"name": "x"}</tool_call> B') == "A  B"
    assert tools.strip_tool_calls("x <function=f>\n<parameter=a>\n1\n</parameter>\n</function>") == "x"


@pytest.fixture
def ext(tmp_path):
    old_root = registry.EXTENSIONS_DIR
    settings.set_path(tmp_path / "settings.json")
    _web_plugin(tmp_path / "extensions")
    yield
    registry.set_root(old_root)
    settings.set_path(tmp_path / "unused.json")


def test_tool_catalog_hides_web_tools_when_web_disabled(ext):
    assert [t["name"] for t in tools.tool_catalog()] == []
    settings.update({"web.enabled": True})
    assert [t["name"] for t in tools.tool_catalog()] == ["web_search", "web_fetch"]


def test_render_tools_block_teaches_xml():
    block = tools.render_tools_block([{"name": "web_search", "description": "s", "parameters": {}}])
    assert "<tools>\n{" in block and "</tools>" in block
    assert "<function=example_function_name>" in block and "<parameter=" in block
    assert "Never claim to have looked something up" in block
    assert '"arguments"' not in block


# --------------------------------------------------------------------------- #
# storable answers & history poisoning
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("text,ok", [
    ("", False),
    ("   ", False),
    ("Let me look that up.", False),
    ("One moment.", False),
    ("Let me check.", False),
    ('{"name": "web_search", "arguments": {"query": "x"}}', False),
    (XML_CALL.replace("I'll search.", ""), False),
    ("<think>\nonly reasoning", False),
    ("[ANALYSIS]\nx\n\n[KERNEL_RESPONSE]\n", False),
    ("Hello! How can I help?", True),
    ("Let me look that up. Kid Cudi's latest album is Free (2025).", True),
    ('{"a": 1}', True),
])
def test_is_storable_answer(text, ok):
    assert is_storable_answer(text) is ok


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger_mod, "STORAGE_PATH", tmp_path)
    return ledger_mod.ChatLedger()


def test_get_history_drops_poisoned_turns_and_never_returns_reasoning(ledger):
    sid = ledger.create_session("t")
    for role, content in [
        ("user", "Look up Kid Cudi"), ("assistant", "Let me look that up."),
        ("user", "go ahead"), ("assistant", '{"name": "web_search", "arguments": {"query": "Kid Cudi"}}'),
        ("user", "hi"),
    ]:
        ledger.add_message(sid, role, content)
    ledger.add_message(sid, "assistant", "Hello! How can I help?", reasoning="greeting")
    history = ledger.get_history(sid)
    assert [m["content"] for m in history] == ["hi", "Hello! How can I help?"]
    assert all("reasoning" not in m for m in history)
    assert ledger.get_full_history(sid)[-1]["reasoning"] == "greeting"


def test_reasoning_column_migrates_old_database(tmp_path, monkeypatch):
    import sqlite3
    monkeypatch.setattr(ledger_mod, "STORAGE_PATH", tmp_path)
    with sqlite3.connect(tmp_path / "chat_ledger.db") as conn:
        conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,"
                     " role TEXT NOT NULL, content TEXT NOT NULL, timestamp REAL NOT NULL)")
    led = ledger_mod.ChatLedger()
    sid = led.create_session("t")
    led.add_message(sid, "assistant", "x", reasoning="r")
    assert led.get_full_history(sid)[0]["reasoning"] == "r"


# --------------------------------------------------------------------------- #
# system prompt
# --------------------------------------------------------------------------- #

def test_model_display_name():
    assert model_display_name("Qwen3.8-27B-UD-IQ1_S.gguf") == "Qwen3.8-27B"
    assert model_display_name("Qwen2.5-14B-Instruct-Q4_K_M.gguf") == "Qwen2.5-14B-Instruct"
    assert model_display_name("Meta-Llama-3-8B-Instruct.Q4_K_M.gguf") == "Meta-Llama-3-8B-Instruct"
    assert model_display_name("Meta-Llama-3.1-8B-Instruct-IQ3_m-imat.gguf") == "Meta-Llama-3.1-8B-Instruct"
    assert model_display_name("") == ""


def test_system_prompt_is_honest_and_not_lobotomized():
    for thinking in (False, True):
        prompt = build_system_prompt(model_format="chatml", thinking=thinking,
                                     model_name="Qwen3.8-27B-UD-IQ1_S.gguf")
        assert "Qwen3.8-27B" in prompt and date.today().isoformat() in prompt
        assert "<think>" not in prompt and "</think>" not in prompt
        for banned in ("ROOT OVERRIDE", "ANTI-PATTERN", "SECURED KERNEL VAULT", "factual data",
                       "[ANALYSIS]", "Relevant excerpts"):
            assert banned not in prompt, banned
        assert "You have no tools this turn" in prompt
        assert "Web access is off" in prompt


def test_system_prompt_lists_tools_web_and_documents():
    prompt = build_system_prompt(context_str="[SOURCE: Vault_Chunk_0]: notes",
                                 capabilities={"tools": ["web_search", "web_fetch"], "web": True})
    assert "Tools available this turn: web_search, web_fetch" in prompt
    assert "no tools" not in prompt and "Web access is on" in prompt
    assert "Relevant excerpts from the user's documents:\n[SOURCE: Vault_Chunk_0]: notes" in prompt


# --------------------------------------------------------------------------- #
# server: thinking turns, retry, cancel, health
# --------------------------------------------------------------------------- #

@pytest.fixture
def srv(tmp_path):
    old_root = registry.EXTENSIONS_DIR
    server = make_server(tmp_path)
    yield server
    from test_agent3_rag_mtbf import _STUBBED_MODULES, _drop_modules
    _drop_modules(*_STUBBED_MODULES)
    registry.set_root(old_root)
    settings.set_path(tmp_path / "unused.json")


def test_thinking_turn_preseeds_and_returns_reasoning(srv):
    srv.MODEL_THINKS = True
    srv.llm = ScriptedLLM("I should greet; the rules mention </think> tags.\n</think>\n\nHello!")
    events = [json.loads(line) for line in srv.ask_stream().body]

    assert srv.llm.prompts[0].endswith("<|im_start|>assistant\n<think>\n")
    deltas = "".join(e["delta"] for e in events if "delta" in e)
    assert deltas.startswith("<think>\n") and stream_visible_body(deltas) == "Hello!"
    done = events[-1]
    assert parse_kernel_response(done["response"])[1] == "Hello!"
    assert done["reasoning"].startswith("I should greet") and done["cancelled"] is False


def test_retry_never_returns_bare_tool_json(srv):
    srv.MODEL_THINKS = True
    srv.llm = ScriptedLLM("\n</think>\n\n", '{"name": "web_search", "arguments": {"query": "x"}}\n')
    resp = body(srv.ask())

    retry_prompt = srv.llm.prompts[1]
    assert retry_prompt.endswith("<think>\n\n</think>\n\n") and "[ANALYSIS]" not in retry_prompt[-80:]
    answer = parse_kernel_response(resp["response"])[1]
    assert '"name"' not in answer and "web_search" not in answer
    assert answer.startswith("[KERNEL FAULT]")  # core.py never stores these


def test_retry_tool_call_goes_back_to_the_tool_loop(srv, monkeypatch):
    seen = []
    monkeypatch.setattr(tools, "tool_catalog", lambda include_files=False: [
        {"name": "web_search", "description": "s", "parameters": {}}])
    monkeypatch.setattr(tools, "dispatch", lambda name, arguments, *, allow_files=False:
                        seen.append((name, arguments)) or {"ok": True, "result": "Free (2025)", "error": ""})
    srv.MODEL_THINKS = True
    srv.llm = ScriptedLLM("\n</think>\n\nLet me look that up.", XML_CALL,
                          "ok\n</think>\n\nHis latest album is Free (2025).")
    resp = body(srv.ask())

    assert seen == [("web_search", {"query": "Kid Cudi"})]
    assert parse_kernel_response(resp["response"])[1] == "His latest album is Free (2025)."
    assert "<tool_response>" in srv.llm.prompts[2] and srv.llm.prompts[2].endswith("assistant\n<think>\n")


class CancellingLLM:
    """Streams 'tok0 tok1 ...'; calls /ask/cancel after the third chunk."""

    is_loaded = True

    def __init__(self, srv):
        self.srv, self.sent, self.cancel_reply = srv, [], None

    def token_count(self, _text):
        return 3

    def generate(self, prompt, **kw):
        for i in range(50):
            if i == 3:
                self.cancel_reply = self.srv.ask_cancel()
            kw["on_chunk"](f"tok{i} ")
            self.sent.append(i)
        raise AssertionError("generation was not cancelled")


def test_cancel_stops_generation_with_partial_answer(srv):
    srv.llm = CancellingLLM(srv)
    events = [json.loads(line) for line in srv.ask_stream().body]

    assert srv.llm.cancel_reply[0]["cancelled"] is True
    assert srv.llm.sent == [0, 1, 2]
    done = events[-1]
    assert done["done"] and done["status"] == 200 and done["cancelled"] is True
    assert parse_kernel_response(done["response"])[1] == "tok0 tok1 tok2"
    assert drain_kernel(srv).count("INFERENCE_COMPLETE") == 1

    # The flag is cleared for the next request, and cancelling when idle is a no-op.
    srv.llm = ScriptedLLM("fine")
    assert body(srv.ask())["cancelled"] is False
    assert srv.ask_cancel()[0]["cancelled"] is False


def test_health_reports_model(srv):
    srv.llm = ScriptedLLM("x")
    resp = srv.health_check()
    assert resp[0]["model"] == "unit-test.gguf" and resp[1] == 200
