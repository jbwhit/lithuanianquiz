"""Google OAuth integration and user progress persistence."""

import json
import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

from fasthtml.common import RedirectResponse
from fasthtml.oauth import GoogleAppClient, OAuth
from fastlite import database

load_dotenv()

_db = database("lithuanian_data.db")

auth_client = GoogleAppClient(
    os.environ.get("GOOGLE_CLIENT_ID", "test"),
    os.environ.get("GOOGLE_CLIENT_SECRET", "test"),
)


def init_db_tables() -> None:
    """Create users and user_progress tables if they don't exist."""
    _db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            google_id TEXT PRIMARY KEY,
            email TEXT,
            name TEXT,
            created_at TEXT,
            last_login TEXT
        )
    """)
    _db.execute("""
        CREATE TABLE IF NOT EXISTS user_progress (
            google_id TEXT PRIMARY KEY,
            data TEXT,
            updated_at TEXT
        )
    """)


def _now() -> str:
    return datetime.now(datetime.UTC).isoformat()


def upsert_user(google_id: str, email: str, name: str) -> None:
    """Insert or update a user record."""
    now = _now()
    _db.execute(
        """
        INSERT INTO users (google_id, email, name, created_at, last_login)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(google_id) DO UPDATE SET
            email = excluded.email,
            name = excluded.name,
            last_login = excluded.last_login
        """,
        [google_id, email, name, now, now],
    )


def load_progress(google_id: str, session: dict[str, Any]) -> None:
    """Merge saved DB progress into the session."""
    row = _db.execute(
        "SELECT data FROM user_progress WHERE google_id = ?", [google_id]
    ).fetchone()
    if row:
        data = json.loads(row[0])
        session["correct_count"] = data.get("correct_count", 0)
        session["incorrect_count"] = data.get("incorrect_count", 0)
        session["history"] = data.get("history", [])
        session["performance"] = data.get("performance", {})


def save_progress(google_id: str, session: dict[str, Any]) -> None:
    """Write session progress state to the DB."""
    data = json.dumps({
        "correct_count": session.get("correct_count", 0),
        "incorrect_count": session.get("incorrect_count", 0),
        "history": session.get("history", []),
        "performance": session.get("performance", {}),
    })
    now = _now()
    _db.execute(
        """
        INSERT INTO user_progress (google_id, data, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(google_id) DO UPDATE SET
            data = excluded.data,
            updated_at = excluded.updated_at
        """,
        [google_id, data, now],
    )


class QuizOAuth(OAuth):
    def redir_login(self, session: Any) -> None:
        return None  # No gate — unauthenticated users can use the quiz freely

    def get_auth(
        self, info: Any, ident: str, session: Any, state: Any
    ) -> RedirectResponse:
        upsert_user(ident, info.get("email", ""), info.get("name", ""))
        load_progress(ident, session)
        session["user_name"] = info.get("name", "")
        session["user_email"] = info.get("email", "")
        return RedirectResponse("/", status_code=303)

    def logout(self, session: Any) -> RedirectResponse:
        session.pop("user_name", None)
        session.pop("user_email", None)
        return RedirectResponse("/", status_code=303)
