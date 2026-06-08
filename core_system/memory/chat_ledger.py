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


class ChatLedger:
    def __init__(self):
        self.db_path = STORAGE_PATH / "chat_ledger.db"
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database with sessions and messages tables."""
        with sqlite3.connect(self.db_path) as conn:
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
            conn.commit()

    def create_session(self, title: str = "New Session") -> str:
        """Create a new chat session and return its session_id."""
        session_id = str(uuid.uuid4())
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, title, now, now)
            )
            conn.commit()
        if ghost:
            try:
                ghost.info(f"CHAT_LEDGER | Created session {session_id[:8]}: {title}")
            except:
                pass
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session metadata by session_id."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent sessions ordered by last update."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0

    def update_session_title(self, session_id: str, title: str) -> bool:
        """Update the title of a session."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE session_id = ?",
                (title, time.time(), session_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def add_message(self, session_id: str, role: str, content: str) -> int:
        """Add a message to a session. Returns message ID."""
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
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
            return deduped

    def get_full_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get complete conversation history for a session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
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