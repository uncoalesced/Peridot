# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | CHAT LEDGER (peridot.memory)
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Chat Ledger: Persistent multi-session conversational memory.
Stores sessions and messages in SQLite for sovereignty and auditability.
"""

import sqlite3
import uuid
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from config import STORAGE_PATH
from core_system.audit import ghost
from core_system.prompting.constitution import parse_kernel_response


def _drop_empty_assistant_turns(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove assistant turns that carry no actual answer, plus the user turn they
    were replying to, so prompt history stays alternating.

    get_history feeds the prompt builder. Rows written before 2026-08-20 (and
    any that slip through later) can be pure scaffolding -- a bare <think>
    fragment or an [ANALYSIS] block with nothing after [KERNEL_RESPONSE].
    Replaying those as assistant turns demonstrates to the model that an empty
    reply is acceptable, and it obligingly produces more of them. Filtering on
    read neutralises history already sitting in the database without deleting
    anything the user can still see in the transcript view.
    """
    cleaned: List[Dict[str, Any]] = []
    for msg in messages:
        if msg.get("role") == "assistant":
            _analysis, body = parse_kernel_response(msg.get("content", ""))
            if not body:
                if cleaned and cleaned[-1].get("role") == "user":
                    cleaned.pop()
                continue
            msg = {**msg, "content": body}
        cleaned.append(msg)
    return cleaned


class ChatLedger:
    def __init__(self):
        self.db_path = STORAGE_PATH / "chat_ledger.db"
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """
        Open a ledger connection with foreign keys actually enforced.

        SQLite ignores FOREIGN KEY constraints unless this pragma is set, and
        the setting is per-connection, not stored with the database. Without it
        the ON DELETE CASCADE declared on messages.session_id is inert:
        delete_session() dropped the session row and left every one of its
        messages behind, unreachable through the API and invisible in the UI,
        but still on disk. Every connection goes through here so a method added
        later cannot silently reintroduce that.
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize the SQLite database with sessions and messages tables."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")

            # Reclaim rows stranded before the pragma above was set. These
            # belong to sessions the user already chose to delete, so the
            # delete is finishing a job the UI reported as done -- not
            # discarding anything still reachable. Self-limiting: with foreign
            # keys now enforced no new orphans can appear, so this is a no-op
            # on every boot after the first.
            orphaned = conn.execute(
                "DELETE FROM messages "
                "WHERE session_id NOT IN (SELECT session_id FROM sessions)"
            ).rowcount
            conn.commit()

        if orphaned and ghost:
            try:
                ghost.info(
                    f"CHAT_LEDGER | Reclaimed {orphaned} orphaned message(s) "
                    "left by session deletes that predate foreign-key enforcement."
                )
            except Exception:
                pass

    def create_session(self, title: str = "New Session") -> str:
        """Create a new chat session and return its session_id."""
        session_id = str(uuid.uuid4())
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, title, now, now)
            )
            conn.commit()
        if ghost:
            try:
                ghost.info(f"CHAT_LEDGER | Created session {session_id[:8]}: {title}")
            except Exception as e:
                pass
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session metadata by session_id."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent sessions ordered by last update."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0

    def update_session_title(self, session_id: str, title: str) -> bool:
        """Update the title of a session."""
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE session_id = ?",
                (title, time.time(), session_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def add_message(self, session_id: str, role: str, content: str) -> int:
        """Add a message to a session. Returns message ID."""
        now = time.time()
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, role, content, now)
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id)
            )
            conn.commit()
            return cursor.lastrowid

    def get_history(self, session_id: str, limit: int = 6) -> List[Dict[str, Any]]:
        """Get recent conversation history for a session (last N turns = 2*N messages)."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT role, content, timestamp FROM messages
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (session_id, limit * 2)
            )
            rows = cursor.fetchall()

            # De-duplicate consecutive identical messages
            deduped = []
            for row in reversed(rows):
                msg = dict(row)
                if deduped and deduped[-1]['role'] == msg['role'] and deduped[-1]['content'] == msg['content']:
                    continue
                deduped.append(msg)
            return _drop_empty_assistant_turns(deduped)

    def get_full_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get complete conversation history for a session."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT role, content, timestamp FROM messages WHERE session_id = ? ORDER BY timestamp",
                (session_id,)
            )
            rows = cursor.fetchall()
            
            # De-duplicate consecutive identical messages
            deduped = []
            for row in rows:
                msg = dict(row)
                if deduped and deduped[-1]['role'] == msg['role'] and deduped[-1]['content'] == msg['content']:
                    continue
                deduped.append(msg)
            return deduped


# Global singleton instance
_chat_ledger = None

def get_chat_ledger() -> ChatLedger:
    global _chat_ledger
    if _chat_ledger is None:
        _chat_ledger = ChatLedger()
    return _chat_ledger