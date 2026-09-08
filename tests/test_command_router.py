# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | COMMAND ROUTER TESTS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# -----------------------------------------------------------------------------

"""
Covers the two router defects found in the v1.5.4 maintainability audit:

  * `vault` passed the raw query string to PersistentVault.search(), which
    takes an embedding. It raised on every invocation, and route()'s catch-all
    turned that into a generic "command failed" -- so a command advertised in
    `help` had never once worked.
  * `clear` assigned to core.chat_memory, an attribute PeridotCore no longer
    has, then reported that memory had been cleared.

Everything is stubbed; no model, no GPU, no database.
"""

import sys
import types

import pytest

from core_system.command_router import CommandRouter


class _FakeVault:
    """Records what search() was handed, and by whom."""

    def __init__(self, chunks=None):
        self.chunks = chunks
        self.received = None

    def search(self, query_vector, top_k=6):
        # Mirrors the real signature: a text query must never arrive here.
        assert not isinstance(query_vector, str), (
            "vault.search() received raw text; it takes an embedding vector"
        )
        self.received = query_vector
        return self.chunks


class _FakeCore:
    def __init__(self, vault):
        self.ui = None
        self.vault = vault
        self.isolated_prompts = []

    def _ask_ai_isolated(self, prompt):
        self.isolated_prompts.append(prompt)
        return "answer"


@pytest.fixture
def fake_embedder(monkeypatch):
    """Stub core_system.memory.embedder so no sentence-transformers load."""
    module = types.ModuleType("core_system.memory.embedder")
    module.embedder = types.SimpleNamespace(
        embed_query=lambda text: [0.5, 0.25, 0.125]
    )
    monkeypatch.setitem(sys.modules, "core_system.memory.embedder", module)
    return module


def test_vault_embeds_the_query_before_searching(fake_embedder):
    vault = _FakeVault(chunks=["chunk one", "chunk two"])
    router = CommandRouter(core=_FakeCore(vault))

    result = router.route("vault", "tell me about mitochondria")

    assert vault.received == [0.5, 0.25, 0.125], "query was not embedded"
    assert result == "answer"


def test_vault_joins_chunks_instead_of_interpolating_a_list(fake_embedder):
    vault = _FakeVault(chunks=["alpha", "beta"])
    core = _FakeCore(vault)
    CommandRouter(core=core).route("vault", "query")

    prompt = core.isolated_prompts[0]
    assert "alpha" in prompt and "beta" in prompt
    assert "['alpha'" not in prompt, "a Python list repr leaked into the prompt"


def test_vault_reports_a_miss_rather_than_failing(fake_embedder):
    router = CommandRouter(core=_FakeCore(_FakeVault(chunks=None)))
    assert "No matching records" in router.route("vault", "query")


def test_vault_without_args_asks_for_a_query():
    router = CommandRouter(core=_FakeCore(_FakeVault()))
    assert "specify" in router.route("vault").lower()


def test_vault_degrades_when_the_embedder_is_offline(monkeypatch):
    """A dead embedder must not surface as a generic command failure."""
    broken = types.ModuleType("core_system.memory.embedder")

    def _explode(_text):
        raise RuntimeError("no offline embedding model")

    broken.embedder = types.SimpleNamespace(embed_query=_explode)
    monkeypatch.setitem(sys.modules, "core_system.memory.embedder", broken)

    result = CommandRouter(core=_FakeCore(_FakeVault())).route("vault", "query")
    assert "unavailable" in result.lower()


def test_clear_does_not_claim_to_have_cleared_memory():
    result = CommandRouter(core=_FakeCore(_FakeVault())).route("clear")
    assert "memory" not in result.lower() or "unchanged" in result.lower()


def test_clear_no_longer_writes_a_phantom_attribute():
    core = _FakeCore(_FakeVault())
    CommandRouter(core=core).route("clear")
    assert not hasattr(core, "chat_memory"), (
        "clear resurrected core.chat_memory, which nothing reads"
    )


def test_help_does_not_advertise_clearing_history():
    help_text = CommandRouter(core=_FakeCore(_FakeVault())).route("help")
    assert "clear chat history" not in help_text.lower()


def test_unknown_command_is_reported_not_raised():
    result = CommandRouter(core=_FakeCore(_FakeVault())).route("nonsense")
    assert "Unknown command" in result
