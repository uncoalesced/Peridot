# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | SHARED TEST FIXTURES
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""Shared pytest fixtures.

Pins the offline environment that one test module was silently relying on
another to establish.
"""

import os

import pytest


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


_UI = {}


@pytest.fixture(scope="session")
def peridot_ui():
    """One withdrawn PeridotUI for the whole session.

    Tcl on Windows cannot initialise a second interpreter in the same process
    (tcl_findLibrary), so every live UI test shares this window; each test
    module swaps in its own fake core via `app.core`.
    """
    import tkinter as tk

    if "app" not in _UI:
        import ui
        try:
            _UI["app"] = ui.PeridotUI(core=None)
        except tk.TclError as e:
            _UI["app"] = e
        else:
            _UI["app"].root.withdraw()
    if isinstance(_UI["app"], Exception):
        pytest.skip(f"no display: {_UI['app']}")
    return _UI["app"]
