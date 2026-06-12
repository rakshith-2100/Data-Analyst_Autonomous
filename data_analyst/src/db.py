"""db.py — SQLite persistence for chat sessions and messages.

Lets a person see and resume previous chats across server restarts. Stdlib sqlite3 only;
the database lives at data/app.db (gitignored). Sessions are scoped by a user id.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "app.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id           TEXT PRIMARY KEY,
                user_id      TEXT NOT NULL,
                filename     TEXT,
                csv_path     TEXT,
                profile_json TEXT,
                created_at   TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL,
                text        TEXT,
                images_json TEXT,
                tables_json TEXT,
                code        TEXT,
                created_at  TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
            """
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_session(sid, user_id, filename, csv_path, profile_json) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO sessions(id,user_id,filename,csv_path,profile_json,created_at)"
            " VALUES (?,?,?,?,?,?)",
            (sid, user_id, filename, str(csv_path), json.dumps(profile_json), _now()),
        )


def get_session(sid) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        return dict(row) if row else None


def list_sessions(user_id) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            """
            SELECT s.id, s.filename, s.created_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS message_count,
                   (SELECT m.text FROM messages m
                    WHERE m.session_id = s.id AND m.role = 'user'
                    ORDER BY m.id DESC LIMIT 1) AS last_user_message
            FROM sessions s
            WHERE s.user_id = ?
            ORDER BY s.created_at DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def add_message(session_id, role, text, images=None, tables=None, code=None) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO messages(session_id,role,text,images_json,tables_json,code,created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (session_id, role, text, json.dumps(images or []), json.dumps(tables or []),
             code, _now()),
        )


def get_messages(session_id) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT role,text,images_json,tables_json,code,created_at FROM messages"
            " WHERE session_id=? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
    return [
        {
            "role": r["role"],
            "text": r["text"],
            "images": json.loads(r["images_json"] or "[]"),
            "tables": json.loads(r["tables_json"] or "[]"),
            "code": r["code"] or "",
            "created_at": r["created_at"],
        }
        for r in rows
    ]
