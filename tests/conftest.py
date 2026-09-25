# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | SHARED TEST FIXTURES
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""Shared pytest fixtures.

Collapses helpers that were previously hand-rolled in four separate test
modules (a fake embedder module, a fake vault, the TURBOVEC_NATIVE monkeypatch,
and a recomputed project root), and pins the offline environment that one test
module was silently relying on another to establish.
"""

import os
import sys
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True, scope="session")
def _offline_environment():
    """Guarantee the sovereignty-lock env vars for the whole session.

    core_system/model_fetch.assert_main_process_offline() raises unless
    HF_HUB_OFFLINE and TRANSFORMERS_OFFLINE are "1", and server.py calls it at
    import time. Those variables are normally set as a side effect of importing
    the real `config`, so test_agent3_rag_mtbf.py -- which imports `server`
    against a *fabricated* config module -- only passed when some other test
    module happened to import the real config first. Running that file alone
    failed with RuntimeError from model_fetch.py. Setting them here makes every
    test file runnable on its own.
    """
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


@pytest.fixture
def project_root() -> Path:
    """Repository root. Was recomputed in six separate modules."""
    return PROJECT_ROOT


@pytest.fixture
def fake_embedder(monkeypatch):
    """Install a stub core_system.memory.embedder and return it.

    The real module builds a SentenceTransformer at import time. Four test
    modules each built their own version of this stub.
    """
    module = types.ModuleType("core_system.memory.embedder")
    module.embedder = types.SimpleNamespace(embed_query=lambda query: [0.0] * 384)
    monkeypatch.setitem(sys.modules, "core_system.memory.embedder", module)
    return module


@pytest.fixture
def fake_vault():
    """A vault double matching PersistentVault.search(query_vector, top_k=6).

    Set `.chunks` to control what a search returns; `.calls` records the top_k
    each call was made with, which is what the RAG-depth tests assert on.
    """

    class FakeVault:
        def __init__(self):
            self.chunks = None
            self.calls = []

        def search(self, query_vector, top_k=6):
            self.calls.append(top_k)
            return self.chunks

    return FakeVault()


@pytest.fixture
def no_native_turbovec(monkeypatch):
    """Force the pure-Python index path.

    turbovec is an optional accelerator; turbovec_index latches
    TURBOVEC_NATIVE at import. Three modules patched this by hand.
    """
    from core_system.memory import turbovec_index

    monkeypatch.setattr(turbovec_index, "TURBOVEC_NATIVE", False)
    return turbovec_index
