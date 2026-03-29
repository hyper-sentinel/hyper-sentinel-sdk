"""
Sentinel Session Memory — SQLite-backed conversation persistence.

Stores chat sessions in ~/.sentinel/memory.db so users can resume
past conversations, review history, and maintain context across restarts.
"""

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


MEMORY_DIR = Path.home() / ".sentinel"
MEMORY_DB = MEMORY_DIR / "memory.db"


def _get_db() -> sqlite3.Connection:
    """Get or create the memory database."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(MEMORY_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT,
            provider TEXT,
            model TEXT,
            created_at REAL,
            updated_at REAL,
            message_count INTEGER DEFAULT 0,
            tool_calls INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp REAL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)
    conn.commit()
    return conn


def create_session(provider: str, model: str) -> str:
    """Create a new chat session. Returns session ID."""
    session_id = str(uuid.uuid4())[:8]
    now = time.time()
    conn = _get_db()
    conn.execute(
        "INSERT INTO sessions (id, title, provider, model, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, "New session", provider, model, now, now),
    )
    conn.commit()
    conn.close()
    return session_id


def save_message(session_id: str, role: str, content: Any) -> None:
    """Save a message to the session."""
    conn = _get_db()
    # Serialize content (Anthropic uses list of blocks)
    if isinstance(content, (list, dict)):
        content_str = json.dumps(content)
    else:
        content_str = str(content)

    conn.execute(
        "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, role, content_str, time.time()),
    )
    conn.execute(
        "UPDATE sessions SET updated_at = ?, message_count = message_count + 1 WHERE id = ?",
        (time.time(), session_id),
    )
    conn.commit()
    conn.close()


def update_session_title(session_id: str, title: str) -> None:
    """Update session title (auto-generated from first user message)."""
    conn = _get_db()
    conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (title[:80], session_id))
    conn.commit()
    conn.close()


def update_session_stats(session_id: str, tool_calls: int) -> None:
    """Update session stats."""
    conn = _get_db()
    conn.execute(
        "UPDATE sessions SET tool_calls = ?, updated_at = ? WHERE id = ?",
        (tool_calls, time.time(), session_id),
    )
    conn.commit()
    conn.close()


def load_session(session_id: str) -> tuple[dict | None, list[dict]]:
    """Load a session and its messages. Returns (session_info, messages)."""
    conn = _get_db()
    cur = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None, []

    session = {
        "id": row[0], "title": row[1], "provider": row[2], "model": row[3],
        "created_at": row[4], "updated_at": row[5],
        "message_count": row[6], "tool_calls": row[7],
    }

    cur = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
        (session_id,),
    )
    messages = []
    for r, c in cur.fetchall():
        try:
            content = json.loads(c)
        except (json.JSONDecodeError, TypeError):
            content = c
        messages.append({"role": r, "content": content})

    conn.close()
    return session, messages


def list_sessions(limit: int = 10) -> list[dict]:
    """List recent sessions."""
    conn = _get_db()
    cur = conn.execute(
        "SELECT id, title, provider, model, created_at, updated_at, message_count, tool_calls "
        "FROM sessions ORDER BY updated_at DESC LIMIT ?",
        (limit,),
    )
    sessions = []
    for row in cur.fetchall():
        sessions.append({
            "id": row[0], "title": row[1], "provider": row[2], "model": row[3],
            "created_at": row[4], "updated_at": row[5],
            "message_count": row[6], "tool_calls": row[7],
        })
    conn.close()
    return sessions


def delete_session(session_id: str) -> bool:
    """Delete a session and its messages."""
    conn = _get_db()
    conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted
