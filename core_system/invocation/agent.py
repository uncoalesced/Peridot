# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.6.0 | MODEL TOOL LOOP
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
The generate -> <tool_call> -> dispatch -> <tool_response> -> generate loop,
shared by /ask, /ask/stream and /invoke (server.py). Generation itself stays
in server.py; this module only needs a generate(prompt, tag) callable.
"""

import json
import time

from core_system.extensions import tools
from core_system.invocation import filetools  # noqa: F401 - registers the file tool handlers
from core_system.prompting.builder import THINK_SEED
from core_system.prompting.constitution import get_chat_template

try:
    from core_system.audit import ghost
except Exception:  # pragma: no cover - audit is optional at import time
    ghost = None

MAX_TOOL_STEPS = 8
TOOL_LIMIT_NOTE = "Tool limit reached; answer now without tools."
TOOL_CALL_OPEN, TOOL_CALL_CLOSE = "<tool_call>", "</tool_call>"
RESULT_CAP = 8000  # chars of one tool result fed back to the model


def tool_turn(model_format, content, thinking=False):
    """Close the assistant turn, add a user turn holding content, reopen the assistant.

    Matches the Qwen3.x GGUF template: tool results go back as a user turn of
    <tool_response> blocks, and a thinking model's new assistant turn is
    pre-seeded with "<think>\\n" like the first one (builder.THINK_SEED).
    """
    tmpl = get_chat_template(model_format)
    if model_format == "mistral":
        return f"</s>{tmpl['user_start']}{content}{tmpl['assistant_start']}"
    # chatml / llama3: assistant_start already opens with the end-of-turn token.
    end = tmpl["stop_tokens"][0] + "\n"
    seed = THINK_SEED if thinking and model_format == "chatml" else ""
    return f"{end}{tmpl['user_start']}{content}{tmpl['assistant_start']}{seed}"


def dispatch(name, arguments, emit=None, allow_files=False):
    """tools.dispatch plus the stream's {"tool", "status"} events."""
    if emit:
        emit({"tool": name, "status": "start"})
    out = tools.dispatch(name, arguments, allow_files=allow_files)
    if emit:
        emit({"tool": name, "status": "ok"} if out["ok"]
             else {"tool": name, "status": "error", "error": str(out["error"])[:200]})
    return out


def run_tool_loop(prompt, generate, model_format, *, allowed=None, allow_files=False,
                  emit=None, max_steps=MAX_TOOL_STEPS, thinking=False, first=None):
    """Generate; while the output calls tools, run them and generate again.

    Returns (output, prompt, calls): the last generation, the prompt it ran
    on, and [{"name", "ok", "ms"}] for every dispatched call. Calls to names
    outside `allowed` get an error result without dispatch. After max_steps
    calls the model is told to answer without tools and generates once more;
    any tool markup left in that output is the caller's to strip.
    first: an output already generated on `prompt` (resuming after a retry).
    """
    calls = []
    output = first if first is not None else generate(prompt, "primary")
    while len(calls) < max_steps:
        found = tools.parse_tool_calls(output.text)
        if not found:
            break
        text = output.text
        if text.rfind(TOOL_CALL_OPEN) > text.rfind(TOOL_CALL_CLOSE):
            text += TOOL_CALL_CLOSE  # llama.cpp leaves the matched stop string out
        responses = []
        for name, args in found[: max_steps - len(calls)]:
            started = time.monotonic()
            if allowed is not None and name not in allowed:
                out = {"ok": False, "result": "", "error": f"Unknown tool: {name!r}"}
            else:
                out = dispatch(name, args, emit, allow_files)
            calls.append({"name": name, "ok": out["ok"],
                          "ms": int((time.monotonic() - started) * 1000)})
            payload = ({"name": name, "result": str(out["result"])[:RESULT_CAP]} if out["ok"]
                       else {"name": name, "error": str(out["error"])[:RESULT_CAP]})
            responses.append(f"<tool_response>\n{json.dumps(payload, ensure_ascii=False)}\n</tool_response>")
        content = "\n".join(responses)
        if len(calls) >= max_steps:
            content += "\n" + TOOL_LIMIT_NOTE
        prompt += text + tool_turn(model_format, content, thinking)
        output = generate(prompt, f"tool_step_{len(calls)}")

    if calls and ghost is not None:
        try:
            ghost.info(f"[TOOLS] turn: {len(calls)} call(s): " + ", ".join(
                f"{c['name']} ok={c['ok']} {c['ms']}ms" for c in calls))
        except Exception:
            pass
    return output, prompt, calls


class MarkupFilter:
    """Delta sink wrapper that hides everything from <tool_call> (or a bare
    <function=) onward.

    A tail that could still become a marker is held back until the next
    chunk decides it; flush() releases it at the end of a generation.
    """

    MARKERS = (TOOL_CALL_OPEN, "<function=")

    def __init__(self, sink):
        self.sink, self.buf, self.closed = sink, "", False

    def __call__(self, chunk):
        if self.closed:
            return
        self.buf += chunk
        i = min((j for j in (self.buf.find(m) for m in self.MARKERS) if j >= 0), default=-1)
        if i >= 0:
            out, self.buf, self.closed = self.buf[:i], "", True
        else:
            keep = next((k for k in range(min(len(TOOL_CALL_OPEN) - 1, len(self.buf)), 0, -1)
                         if any(m.startswith(self.buf[-k:]) for m in self.MARKERS)), 0)
            out, self.buf = self.buf[:len(self.buf) - keep], self.buf[len(self.buf) - keep:]
        if out:
            self.sink(out)

    def flush(self):
        if not self.closed and self.buf:
            self.sink(self.buf)
        self.buf = ""
