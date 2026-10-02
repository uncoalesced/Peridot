"""v1.6.0 plugin sandbox: child-process tool runner with audit-hook policy."""

import sys
import textwrap

import pytest

from core_system.extensions.sandbox import run_tool

POLICY = {"network": False, "read_paths": [], "write_paths": [], "mem_mb": 512}


def _plugin(tmp_path, body: str):
    d = tmp_path / "plugin"
    d.mkdir()
    (d / "main.py").write_text(textwrap.dedent(body), encoding="utf-8")
    return d


def _run(plugin_dir, args=None, policy=None, timeout=30.0):
    return run_tool(plugin_dir, "main.py", "tool", args or {}, policy or POLICY, timeout=timeout)


def test_happy_path(tmp_path):
    d = _plugin(tmp_path, """
        import json, math
        def tool(x, y):
            return json.dumps({"sum": x + y, "pi": round(math.pi, 2)})
    """)
    r = _run(d, {"x": 2, "y": 3})
    assert r["ok"], r
    assert r["result"] == '{"sum": 5, "pi": 3.14}'
    assert not r["denied"]


def test_read_outside_allowlist_denied(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("hunter2")
    d = _plugin(tmp_path, """
        def tool(p):
            return open(p).read()
    """)
    r = _run(d, {"p": str(secret)})
    assert not r["ok"] and r["denied"], r


def test_read_inside_read_paths_ok(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("hello")
    d = _plugin(tmp_path, """
        def tool(p):
            return open(p).read()
    """)
    r = _run(d, {"p": str(data / "a.txt")}, dict(POLICY, read_paths=[str(data)]))
    assert r["ok"] and r["result"] == "hello", r


def test_write_into_read_only_path_denied(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    d = _plugin(tmp_path, """
        def tool(p):
            with open(p, "w") as f:
                f.write("x")
    """)
    r = _run(d, {"p": str(data / "new.txt")}, dict(POLICY, read_paths=[str(data)]))
    assert not r["ok"] and r["denied"], r
    assert not (data / "new.txt").exists()


def test_write_into_write_paths_ok(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    d = _plugin(tmp_path, """
        import os
        def tool(p):
            os.mkdir(os.path.join(p, "sub"))
            with open(os.path.join(p, "sub", "f.txt"), "w") as f:
                f.write("written")
            return "done"
    """)
    r = _run(d, {"p": str(out)}, dict(POLICY, write_paths=[str(out)]))
    assert r["ok"], r
    assert (out / "sub" / "f.txt").read_text() == "written"


def test_network_denied(tmp_path):
    d = _plugin(tmp_path, """
        import socket
        def tool():
            socket.create_connection(("127.0.0.1", 9), timeout=1)
            return "connected"
    """)
    r = _run(d)
    assert not r["ok"] and r["denied"], r


def test_subprocess_denied(tmp_path):
    cmd = ["cmd", "/c", "echo"] if sys.platform == "win32" else ["true"]
    d = _plugin(tmp_path, f"""
        import subprocess
        def tool():
            subprocess.run({cmd!r})
            return "spawned"
    """)
    r = _run(d)
    assert not r["ok"] and r["denied"], r


def test_swallowed_denial_still_flagged(tmp_path):
    d = _plugin(tmp_path, """
        import os
        def tool():
            try:
                os.system("echo hi")
            except OSError:
                pass
            return "sneaky"
    """)
    r = _run(d)
    assert r["denied"], r


def test_entry_escape_rejected(tmp_path):
    d = _plugin(tmp_path, "def tool():\n    return 1\n")
    r = run_tool(d, "../evil.py", "tool", {}, POLICY)
    assert not r["ok"] and "escapes" in r["error"]


def test_infinite_loop_times_out(tmp_path):
    d = _plugin(tmp_path, """
        def tool():
            while True:
                pass
    """)
    r = _run(d, timeout=2)
    assert r == {"ok": False, "result": "", "error": "timeout", "denied": False}


@pytest.mark.skipif(sys.platform != "win32", reason="Job Object memory limit is Windows-only")
def test_memory_limit(tmp_path):
    d = _plugin(tmp_path, """
        def tool():
            buf = bytearray(800 * 1024 * 1024)
            return str(len(buf))
    """)
    r = _run(d, policy=dict(POLICY, mem_mb=256))
    assert not r["ok"], r
