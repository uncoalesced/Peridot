# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | v1.6.0 SETTINGS STORE TESTS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# -----------------------------------------------------------------------------

"""
Coverage for core_system/settings.py and the GET/POST /settings routes.

The route tests reuse the stub harness from test_agent3_rag_mtbf.py (fake
config/flask/dotenv) and call the view functions directly. No network.
"""

import importlib
import sys

import pytest

from core_system import settings
from test_agent3_rag_mtbf import _STUBBED_MODULES, _drop_modules, _install_common_runtime_stubs


@pytest.fixture
def store(tmp_path):
    path = tmp_path / "settings.json"
    settings.set_path(path)
    yield path
    settings.set_path(tmp_path / "unused.json")


def test_missing_file_returns_defaults(store):
    assert not store.exists()
    assert settings.all() == settings.DEFAULTS
    assert settings.get("invocation.idle_unload_s") == 300


def test_update_round_trip_persists_and_reloads(store):
    result = settings.update({"web.enabled": True, "allow.folders": ["E:/docs"]})
    assert result["web.enabled"] is True
    assert result["allow.folders"] == ["E:/docs"]
    # Fresh cache: a new set_path forces a cold read from disk.
    settings.set_path(store)
    assert settings.get("web.enabled") is True
    assert settings.get("allow.folders") == ["E:/docs"]
    assert settings.get("model.active") == ""


def test_unknown_key_and_wrong_type_raise(store):
    with pytest.raises(ValueError):
        settings.update({"no.such.key": 1})
    with pytest.raises(ValueError):
        settings.update({"web.enabled": "yes"})
    with pytest.raises(ValueError):
        settings.update({"invocation.idle_unload_s": True})  # bool is not int here
    assert not store.exists()  # rejected updates never touch disk


def test_corrupt_json_falls_back_to_defaults(store):
    store.write_text("{not json", encoding="utf-8")
    assert settings.all() == settings.DEFAULTS


def test_atomic_write_leaves_no_tmp_file(store):
    settings.update({"web.searxng_url": "http://127.0.0.1:8888"})
    assert store.exists()
    assert list(store.parent.glob("*.tmp")) == []


def test_returned_values_are_copies(store):
    settings.get("allow.folders").append("x")
    assert settings.get("allow.folders") == []


@pytest.fixture
def server(tmp_path):
    _drop_modules(*_STUBBED_MODULES)
    _install_common_runtime_stubs()
    env_writes = []
    sys.modules["config"].MODEL_DIR = tmp_path
    sys.modules["config"].ENV_PATH = tmp_path / ".env"
    sys.modules["dotenv"].set_key = lambda path, key, value: env_writes.append((path, key, value))
    srv = importlib.import_module("server")
    srv.settings.set_path(tmp_path / "settings.json")
    srv.request.headers = {"Authorization": f"Bearer {srv.API_KEY}"}
    srv.request.environ = {}
    srv.env_writes = env_writes
    yield srv
    _drop_modules(*_STUBBED_MODULES)


def _status(resp):
    return resp[1] if isinstance(resp, tuple) else 200


def test_route_get_and_post_round_trip(server):
    assert server.get_settings()["web.enabled"] is False
    server.request.json = {"web.enabled": True}
    resp = server.post_settings()
    assert _status(resp) == 200
    assert resp["web.enabled"] is True
    assert "restart_required" not in resp
    assert server.env_writes == []


def test_route_rejects_bad_body_and_requires_auth(server):
    server.request.json = {"web.enabled": "yes"}
    assert _status(server.post_settings()) == 400
    server.request.json = {"bogus": 1}
    assert _status(server.post_settings()) == 400
    server.request.headers = {}
    assert _status(server.get_settings()) == 403


def test_route_model_swap_writes_env(server, tmp_path):
    (tmp_path / "real.gguf").write_bytes(b"")
    server.request.json = {"model.active": "real.gguf"}
    resp = server.post_settings()
    assert _status(resp) == 200
    assert resp["restart_required"] is True
    assert resp["model.active"] == "real.gguf"
    assert server.env_writes == [(str(tmp_path / ".env"), "ACTIVE_MODEL_NAME", "real.gguf")]


@pytest.mark.parametrize("name", ["missing.gguf", "notes.txt", "../real.gguf"])
def test_route_model_swap_rejects_invalid(server, tmp_path, name):
    (tmp_path / "real.gguf").write_bytes(b"")
    (tmp_path / "notes.txt").write_bytes(b"")
    server.request.json = {"model.active": name}
    assert _status(server.post_settings()) == 400
    assert server.env_writes == []
    assert server.settings.get("model.active") == ""
