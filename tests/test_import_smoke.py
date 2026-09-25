# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | IMPORT SMOKE TEST
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""Every first-party module must import cleanly.

This is the cheapest possible guard against a whole class of defect that the
rest of the suite cannot see, because nothing imported the affected modules:

  * core_system/modules/resource_monitor.py did `from enhancedlogger import
    EnhancedLogger`. No top-level `enhancedlogger` module exists, so the module
    raised ImportError on every import. It sat that way undetected because it
    had no importers at all.
  * benchmarking/benchmark_cold_start.py and benchmark_context_scaling.py did
    `from benchmark_utils import ...` behind a sys.path prologue, which broke
    the moment they were imported as package modules.

Each module is imported in a subprocess. A module that calls sys.exit(), aborts
on a missing GPU, or blocks would otherwise take the whole test session with it.
"""

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Not source: vendored, generated, virtualenvs, or data.
SKIP_DIRS = {
    "llama.cpp", "venv", ".venv", "backups", "__pycache__", ".git",
    ".pytest_cache", "models", "logs", "storage", "input", "assets", "docs",
}

# Modules that cannot be imported in a bare test process, with the reason.
# Keep this list SHORT and justified -- it is the escape hatch that lets the
# rest of the check be strict.
EXPECTED_UNIMPORTABLE = {
    # Binds a live GPU (pynvml init + sys.exit on NVMLError), asserts the
    # offline lock, opens SQLite, and loads the embedding model at import.
    # Exercised instead by tests/test_agent3_rag_mtbf.py against stubs.
    "server": "boots the kernel: NVML, SQLite and the embedder at import time",
    # Interactive first-run installer; prompts on stdin.
    "setup": "interactive install wizard",
    # Spawns the server and the Tkinter client as subprocesses.
    "launcher": "process supervisor; spawns server.py and main.py",
    "main": "Tkinter client bootstrap; exits when no server answers /health",
}


def _discover():
    modules = []
    for path in sorted(PROJECT_ROOT.rglob("*.py")):
        rel = path.relative_to(PROJECT_ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if rel.parts[0] == "tests":
            continue
        parts = list(rel.parts)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
            if not parts:
                continue
        else:
            parts[-1] = parts[-1][:-3]
        modules.append(".".join(parts))
    return sorted(set(modules))


ALL_MODULES = _discover()
IMPORTABLE = [m for m in ALL_MODULES if m not in EXPECTED_UNIMPORTABLE]


def test_discovery_found_the_source_tree():
    """Guard the guard: a broken discovery walk would vacuously pass everything."""
    assert len(IMPORTABLE) > 40, f"only discovered {len(IMPORTABLE)} modules"
    for expected in ("config", "core", "ui", "core_system.kernel",
                     "core_system.memory.vault", "core_system.providers",
                     "benchmarking.utils.benchmark_utils"):
        assert expected in IMPORTABLE, f"{expected} missing from discovery"


@pytest.mark.parametrize("module", IMPORTABLE)
def test_module_imports(module):
    proc = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        tail = [ln for ln in proc.stderr.strip().splitlines() if ln.strip()]
        pytest.fail(
            f"`import {module}` failed (exit {proc.returncode}):\n"
            + "\n".join(tail[-12:])
        )


@pytest.mark.parametrize("module", sorted(EXPECTED_UNIMPORTABLE))
def test_excluded_modules_still_exist(module):
    """Keep the exclusion list honest.

    If one of these is deleted or renamed, fail here rather than let the
    exclusion silently cover a module that no longer exists.
    """
    assert module in ALL_MODULES, (
        f"{module} is excluded from the import smoke test but no longer exists; "
        f"remove it from EXPECTED_UNIMPORTABLE ({EXPECTED_UNIMPORTABLE[module]})"
    )
