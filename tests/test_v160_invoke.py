# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | v1.6.0 SOVEREIGN INVOCATION TESTS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# -----------------------------------------------------------------------------

"""POST /invoke and the allowlisted file tools (core_system/invocation/filetools.py)."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_agent3_rag_mtbf import _STUBBED_MODULES, _drop_modules  # noqa: E402
from test_v160_toolloop import ScriptedLLM, body, drain_kernel, make_server, status  # noqa: E402

from core_system import settings  # noqa: E402
from core_system.extensions import registry, tools  # noqa: E402
from core_system.invocation import filetools  # noqa: E402


@pytest.fixture
def folders(tmp_path):
    ro, rw, outside = tmp_path / "ro", tmp_path / "rw", tmp_path / "outside"
    for d in (ro, rw, outside):
        d.mkdir()
    (ro / "notes.txt").write_text("alpha beta", encoding="utf-8")
    (outside / "secret.txt").write_text("TOP SECRET", encoding="utf-8")
    settings.set_path(tmp_path / "settings.json")
    settings.update({"allow.folders": [str(ro), {"path": str(rw), "write": True}]})
    yield ro, rw, outside
    settings.set_path(tmp_path / "unused.json")


@pytest.fixture
def srv(tmp_path, folders):
    old_root = registry.EXTENSIONS_DIR
    s = make_server(tmp_path)
    settings.update({"allow.folders": [str(folders[0]), {"path": str(folders[1]), "write": True}]})
    s.request.json = {"task": "tidy my notes", "return_mode": "full"}
    yield s
    _drop_modules(*_STUBBED_MODULES)
    registry.set_root(old_root)


# --------------------------------------------------------------------------- #
# file tools
# --------------------------------------------------------------------------- #

def test_read_file_inside_and_outside(folders):
    ro, _rw, outside = folders
    assert filetools.read_file({"path": str(ro / "notes.txt")}) == {"ok": True, "result": "alpha beta", "error": ""}
    assert filetools.read_file({"path": "notes.txt"})["result"] == "alpha beta"  # relative to a root
    denied = filetools.read_file({"path": str(outside / "secret.txt")})
    assert not denied["ok"] and "TOP SECRET" not in denied["error"]
    assert not filetools.read_file({"path": str(ro / ".." / "outside" / "secret.txt")})["ok"]
    # registered with the dispatcher, and only reachable when files are allowed
    assert tools.dispatch("read_file", {"path": str(ro / "notes.txt")}, allow_files=True)["ok"]
    assert not tools.dispatch("read_file", {"path": str(ro / "notes.txt")})["ok"]


def test_symlink_escape_denied(folders):
    ro, _rw, outside = folders
    link = ro / "link.txt"
    try:
        os.symlink(outside / "secret.txt", link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not permitted here")
    assert not filetools.read_file({"path": str(link)})["ok"]


def test_write_file_respects_write_flag(folders):
    ro, rw, _outside = folders
    assert not filetools.write_file({"path": str(ro / "new.txt"), "content": "x"})["ok"]
    assert not (ro / "new.txt").exists()
    r = filetools.write_file({"path": str(rw / "sub" / "new.txt"), "content": "hello"})
    assert r["ok"]
    assert (rw / "sub" / "new.txt").read_text(encoding="utf-8") == "hello"


def test_list_dir(folders):
    ro, _rw, _outside = folders
    (ro / "sub").mkdir()
    r = filetools.list_dir({"path": str(ro)})
    assert r["ok"] and r["result"] == "notes.txt (10 bytes)\nsub/ [dir]"


# --------------------------------------------------------------------------- #
# /invoke
# --------------------------------------------------------------------------- #

def test_no_allowlist_is_403(srv):
    settings.update({"allow.folders": []})
    resp = srv.invoke()
    assert status(resp) == 403
    assert body(resp)["error"] == srv.NO_FOLDERS_MSG


def test_path_outside_allowlist_is_403(srv, folders):
    srv.request.json = {"task": "read it", "paths": [str(folders[2] / "secret.txt")]}
    resp = srv.invoke()
    assert status(resp) == 403
    assert "secret" not in body(resp)["error"]


def test_bad_request_and_auth(srv):
    srv.request.json = {"return_mode": "full"}
    assert status(srv.invoke()) == 400
    srv.request.json = {"task": "x", "return_mode": "loud"}
    assert status(srv.invoke()) == 400
    srv.request.headers = {}
    assert status(srv.invoke()) == 403


def test_review_mode_writes_and_summarises(srv, folders):
    rw = folders[1]
    target = str(rw / "out.txt").replace("\\", "/")
    srv.llm = ScriptedLLM(
        '<tool_call>{"name": "write_file", "arguments": {"path": "%s", "content": "done"}}' % target,
        "[ANALYSIS]\nx\n[KERNEL_RESPONSE]\nDone.",
        "[ANALYSIS]\nx\n[KERNEL_RESPONSE]\nThe notes were tidied.",
    )
    srv.request.json = {"task": "tidy", "paths": [str(folders[0])], "return_mode": "review"}
    resp = srv.invoke()

    assert status(resp) == 200
    data = body(resp)
    assert data == {"answer": "Done.", "summary": "The notes were tidied.", "action_only": True,
                    "model_used": "unit-test.gguf", "steps": 1}
    assert (rw / "out.txt").read_text(encoding="utf-8") == "done"
    assert "delegated local agent" in srv.llm.prompts[0] and '"name": "write_file"' in srv.llm.prompts[0]
    assert "<result>\nDone.\n</result>" in srv.llm.prompts[-1]
    assert drain_kernel(srv).count("INFERENCE_COMPLETE") == 1


def test_full_mode_has_no_summary(srv):
    srv.llm = ScriptedLLM("[ANALYSIS]\nx\n[KERNEL_RESPONSE]\nYour notes mention alpha and beta.")
    resp = srv.invoke()
    data = body(resp)
    assert data["summary"] == ""
    assert data["answer"] == "Your notes mention alpha and beta."
    assert data["action_only"] is False and data["steps"] == 0
    assert len(srv.llm.prompts) == 1
