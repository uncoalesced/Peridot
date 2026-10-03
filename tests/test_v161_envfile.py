# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | v1.6.1 .ENV HELPER TESTS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# -----------------------------------------------------------------------------

"""core_system/envfile.py replaced python-dotenv; these pin the behaviour."""

import os

from core_system.envfile import load_env, read_env, set_env_key


def test_read_env_edge_cases(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n"
        "\n"
        "PLAIN=value\n"
        "export EXPORTED=yes\n"
        "DQ=\"double quoted\"\n"
        "SQ='single # not a comment'\n"
        "MISMATCH=\"half'\n"
        "EQ=a=b=c\n"
        "INLINE=val # trailing comment\n"
        "  SPACED  =  padded  \n"
        "EMPTY=\n"
        "no equals sign\n"
        "=novalue\n"
        "BAD KEY=x\n",
        encoding="utf-8",
    )
    assert read_env(env) == {
        "PLAIN": "value",
        "EXPORTED": "yes",
        "DQ": "double quoted",
        "SQ": "single # not a comment",
        "MISMATCH": "\"half'",
        "EQ": "a=b=c",
        "INLINE": "val",
        "SPACED": "padded",
        "EMPTY": "",
    }


def test_read_env_missing_file(tmp_path):
    assert read_env(tmp_path / "nope.env") == {}


def test_set_env_key_replaces_in_place_and_keeps_comments(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# header\nA=1\n\n# about B\nexport B='old'\nC=3\n", encoding="utf-8")
    set_env_key(env, "B", "new")
    assert env.read_text(encoding="utf-8") == "# header\nA=1\n\n# about B\nB=new\nC=3\n"
    assert not list(tmp_path.glob("*.tmp"))


def test_set_env_key_appends_and_creates(tmp_path):
    env = tmp_path / ".env"
    set_env_key(env, "API_KEY", "abc")  # pragma: allowlist secret
    assert env.read_text(encoding="utf-8") == "API_KEY=abc\n"  # pragma: allowlist secret
    set_env_key(env, "MODEL", "x.gguf")
    assert read_env(env) == {"API_KEY": "abc", "MODEL": "x.gguf"}  # pragma: allowlist secret


def test_load_env_respects_existing_environ(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("PERIDOT_T_SET=from_file\nPERIDOT_T_NEW=new\n", encoding="utf-8")
    monkeypatch.setenv("PERIDOT_T_SET", "from_env")
    monkeypatch.delenv("PERIDOT_T_NEW", raising=False)
    load_env(env)
    assert os.environ["PERIDOT_T_SET"] == "from_env"
    assert os.environ["PERIDOT_T_NEW"] == "new"
    load_env(env, override=True)
    assert os.environ["PERIDOT_T_SET"] == "from_file"
