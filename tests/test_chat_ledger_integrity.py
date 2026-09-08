# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | CHAT LEDGER INTEGRITY TESTS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# -----------------------------------------------------------------------------

"""
Guards the referential integrity of the chat ledger.

The schema has always declared ON DELETE CASCADE on messages.session_id, but
SQLite ignores foreign keys unless `PRAGMA foreign_keys = ON` is issued on the
connection. It was not, so delete_session() removed the session row and left
every message behind: unreachable through the API, invisible in the UI, and
never reclaimed. "Delete session" did not delete the conversation.

These run against a temp database, never the operator's storage/ ledger.
"""

import sqlite3
from pathlib import Path

import pytest

from core_system.memory import chat_ledger as ledger_mod
from core_system.memory.chat_ledger import ChatLedger


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    """A ChatLedger backed by a throwaway database."""
    monkeypatch.setattr(ledger_mod, "STORAGE_PATH", tmp_path)
    return ChatLedger()


def _message_count(ledger) -> int:
    with sqlite3.connect(ledger.db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]


def test_every_connection_goes_through_connect():
    """
    The pragma is per-connection, so a raw sqlite3.connect anywhere in the
    module is a hole: that method's writes run with foreign keys off again.

    Reads the file from disk rather than via inspect.getsource -- other tests
    in this suite replace core_system.memory.chat_ledger in sys.modules with a
    stub, and inspect resolves through sys.modules.
    """
    source_file = (
        Path(__file__).resolve().parents[1]
        / "core_system" / "memory" / "chat_ledger.py"
    )
    src = source_file.read_text(encoding="utf-8")
    assert src.count("sqlite3.connect(") == 1, (
        "found a raw sqlite3.connect outside _connect(); route it through "
        "_connect() or it silently loses foreign-key enforcement"
    )


def test_connect_actually_turns_foreign_keys_on(ledger):
    with ledger._connect() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_deleting_a_session_cascades_to_its_messages(ledger):
    sid = ledger.create_session("doomed")
    ledger.add_message(sid, "user", "question")
    ledger.add_message(sid, "assistant", "answer")
    assert _message_count(ledger) == 2

    assert ledger.delete_session(sid) is True
    assert _message_count(ledger) == 0, "messages outlived their session"


def test_delete_leaves_other_sessions_untouched(ledger):
    keep = ledger.create_session("keep")
    drop = ledger.create_session("drop")
    ledger.add_message(keep, "user", "keep me")
    ledger.add_message(drop, "user", "drop me")

    ledger.delete_session(drop)

    assert _message_count(ledger) == 1
    assert [m["content"] for m in ledger.get_full_history(keep)] == ["keep me"]


def test_orphans_written_before_enforcement_are_reclaimed(tmp_path, monkeypatch):
    """
    Rows stranded by the old behaviour must be cleared on the next open, once.
    Simulated by inserting a message for a session that does not exist, with
    foreign keys off -- exactly the state the shipped ledger was left in.
    """
    monkeypatch.setattr(ledger_mod, "STORAGE_PATH", tmp_path)
    first = ChatLedger()
    live = first.create_session("live")
    first.add_message(live, "user", "still reachable")

    with sqlite3.connect(first.db_path) as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) "
            "VALUES (?, ?, ?, ?)",
            ("session-that-was-deleted", "user", "stranded", 1.0),
        )
        conn.commit()
    assert _message_count(first) == 2

    ChatLedger()  # reopening runs the reclaim

    assert _message_count(first) == 1, "orphaned row was not reclaimed"
    assert [m["content"] for m in first.get_full_history(live)] == ["still reachable"]


def test_reclaim_is_a_noop_on_a_clean_ledger(ledger):
    sid = ledger.create_session("clean")
    ledger.add_message(sid, "user", "keep")

    ChatLedger()  # second open must not touch anything

    assert _message_count(ledger) == 1
