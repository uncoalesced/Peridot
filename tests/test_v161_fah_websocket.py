# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | v1.6.1 F@H WEBSOCKET CLIENT TEST
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# -----------------------------------------------------------------------------

"""server.send_fah_command speaks RFC 6455 by hand since websocket-client was dropped."""

import importlib
import json
import socket
import threading

import pytest

from test_agent3_rag_mtbf import _STUBBED_MODULES, _drop_modules, _install_common_runtime_stubs


@pytest.fixture
def server():
    _drop_modules(*_STUBBED_MODULES)
    _install_common_runtime_stubs()
    yield importlib.import_module("server")
    _drop_modules(*_STUBBED_MODULES)


def _recv_frame(conn):
    head = conn.recv(2)
    length = head[1] & 0x7F
    mask = conn.recv(4)
    data = b""
    while len(data) < length:
        data += conn.recv(length - len(data))
    return head[0] & 0x0F, bytes(b ^ mask[i % 4] for i, b in enumerate(data))


def test_send_fah_command_sends_masked_text_frame(server, monkeypatch):
    listener = socket.create_server(("127.0.0.1", 0))
    monkeypatch.setattr(server, "FAH_WS_PORT", listener.getsockname()[1])
    monkeypatch.setattr(server, "fah_listening", lambda: True)
    got = {}

    def fake_fah():
        conn, _ = listener.accept()
        with conn:
            req = b""
            while b"\r\n\r\n" not in req:
                req += conn.recv(1024)
            got["request"] = req
            conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                         b"Connection: Upgrade\r\nSec-WebSocket-Accept: x\r\n\r\n")
            got["frames"] = [_recv_frame(conn), _recv_frame(conn)]

    t = threading.Thread(target=fake_fah)
    t.start()
    assert server.send_fah_command("pause") is True
    t.join(5)
    listener.close()

    assert got["request"].startswith(b"GET /api/websocket HTTP/1.1\r\n")
    assert b"Sec-WebSocket-Version: 13" in got["request"]
    (op1, data1), (op2, _) = got["frames"]
    assert op1 == 0x1 and json.loads(data1) == {"cmd": "state", "state": "pause"}
    assert op2 == 0x8


def test_send_fah_command_false_when_not_listening(server, monkeypatch):
    monkeypatch.setattr(server, "fah_listening", lambda: False)
    assert server.send_fah_command("fold") is False
