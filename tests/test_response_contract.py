# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | RESPONSE CONTRACT TESTS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# -----------------------------------------------------------------------------

"""
Regression tests for the [ANALYSIS]/[KERNEL_RESPONSE] parser.

Every raw string below was pulled verbatim out of storage/chat_ledger.db on
2026-08-20. They are the actual outputs that produced the run of blank replies:
the model emitted the response header and stopped, the old code wrapped that in
more scaffolding and called it a success, and the result was written back to the
ledger where it got replayed as an assistant turn on the next request.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core_system.memory.chat_ledger import _drop_empty_assistant_turns
from core_system.prompting.constitution import (
    format_kernel_response,
    parse_kernel_response,
    strip_reasoning,
)

# Observed failures: all of these must parse to an empty body.
EMPTY_OUTPUTS = [
    "<think>\n\n</think>\n\n[ANALYSIS]\n- Context State: Bypassed.\n"
    "- Domain: General (Business/Technology)\n\n[KERNEL_RESPONSE]",
    "[ANALYSIS]\nEnforced kernel formatting fallback.\n\n[KERNEL_RESPONSE]\n<think>\n\n</think>",
    "[ANALYSIS]\nEnforced kernel formatting fallback.\n\n[KERNEL_RESPONSE]\n<think>",
    "[ANALYSIS]\nEnforced kernel formatting fallback.\n\n[KERNEL_RESPONSE]\n",
    "<think>",
    "",
]


def test_degenerate_outputs_parse_to_empty_body():
    for raw in EMPTY_OUTPUTS:
        _analysis, body = parse_kernel_response(raw)
        assert body == "", f"expected empty body for {raw!r}, got {body!r}"


def test_real_answer_survives_parsing():
    raw = (
        "<think>\nThe user is asking about entanglement. Let me reason.\n</think>\n\n"
        "[ANALYSIS]\n- Domain: Physics\n\n[KERNEL_RESPONSE]\nEntangled particles share a state."
    )
    analysis, body = parse_kernel_response(raw)
    assert body == "Entangled particles share a state."
    assert "Domain: Physics" in analysis
    assert "<think>" not in analysis and "<think>" not in body


def test_answer_without_kernel_header_is_kept():
    analysis, body = parse_kernel_response("Plain answer, no scaffolding.")
    assert analysis == ""
    assert body == "Plain answer, no scaffolding."


def test_unclosed_think_block_drops_the_tail():
    # Generation cut off inside the reasoning block: none of it is an answer.
    assert strip_reasoning("<think>\nstill reasoning when we ran out") == ""
    assert strip_reasoning("prefix <think>a</think> suffix") == "prefix  suffix"


def test_format_round_trips():
    analysis, body = parse_kernel_response(format_kernel_response("Notes", "The answer."))
    assert analysis == "Notes"
    assert body == "The answer."


def test_poisoned_history_is_filtered_with_its_user_turn():
    history = [
        {"role": "user", "content": "Tell me about Bosnia"},
        {"role": "assistant", "content": EMPTY_OUTPUTS[1]},
        {"role": "user", "content": "Explain entanglement"},
        {"role": "assistant", "content": "[ANALYSIS]\nx\n\n[KERNEL_RESPONSE]\nA real answer."},
    ]
    cleaned = _drop_empty_assistant_turns(history)
    assert cleaned == [
        {"role": "user", "content": "Explain entanglement"},
        {"role": "assistant", "content": "A real answer."},
    ], cleaned


def test_clean_history_passes_through_untouched():
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    assert _drop_empty_assistant_turns(history) == history


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("\nAll response-contract tests passed.")
