"""Google OAuth integration and user progress persistence."""

import json
import logging
import os
from datetime import UTC, datetime
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

_SESSION_HISTORY_LIMIT = 5
log = logging.getLogger(__name__)


def _load_progress_payload(raw: Any, google_id: str) -> dict[str, Any] | None:
    """Parse saved progress JSON and return None when payload is unusable."""
    if not isinstance(raw, str):
        log.warning("Skipping progress load for %s: payload is not a string", google_id)
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("Skipping progress load for %s: invalid JSON payload", google_id)
        return None

    if not isinstance(data, dict):
        log.warning("Skipping progress load for %s: payload is not an object", google_id)
        return None

    return data


def _capped_history(value: Any) -> list[Any]:
    """Return the latest history items when value is a list."""
    if isinstance(value, list):
        return value[-_SESSION_HISTORY_LIMIT:]
    return []


def _is_valid_mix_modules(value: Any) -> bool:
    """Validate persisted mix-module counters before loading."""
    if not isinstance(value, dict) or not value:
        return False
    for stats in value.values():
        if not isinstance(stats, dict):
            return False
        correct = stats.get("correct")
        incorrect = stats.get("incorrect")
        if not isinstance(correct, int) or not isinstance(incorrect, int):
            return False
        if correct < 0 or incorrect < 0:
            return False
    return True


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
    return datetime.now(UTC).isoformat()


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
    if not row:
        return

    data = _load_progress_payload(row[0], google_id)
    if data is None:
        return

    # Price progress
    session["correct_count"] = data.get("correct_count", 0)
    session["incorrect_count"] = data.get("incorrect_count", 0)
    session["history"] = _capped_history(data.get("history"))
    session["performance"] = (
        data["performance"] if isinstance(data.get("performance"), dict) else {}
    )
    # Time progress
    session["time_correct_count"] = data.get("time_correct_count", 0)
    session["time_incorrect_count"] = data.get("time_incorrect_count", 0)
    session["time_history"] = _capped_history(data.get("time_history"))
    session["time_performance"] = (
        data["time_performance"] if isinstance(data.get("time_performance"), dict) else {}
    )
    # Numbers 1-20 progress
    session["n20_correct_count"] = data.get("n20_correct_count", 0)
    session["n20_incorrect_count"] = data.get("n20_incorrect_count", 0)
    session["n20_history"] = _capped_history(data.get("n20_history"))
    session["n20_performance"] = (
        data["n20_performance"] if isinstance(data.get("n20_performance"), dict) else {}
    )
    # Numbers 1-99 progress
    session["n99_correct_count"] = data.get("n99_correct_count", 0)
    session["n99_incorrect_count"] = data.get("n99_incorrect_count", 0)
    session["n99_history"] = _capped_history(data.get("n99_history"))
    session["n99_performance"] = (
        data["n99_performance"] if isinstance(data.get("n99_performance"), dict) else {}
    )
    # Age progress
    session["age_correct_count"] = data.get("age_correct_count", 0)
    session["age_incorrect_count"] = data.get("age_incorrect_count", 0)
    session["age_history"] = _capped_history(data.get("age_history"))
    session["age_performance"] = (
        data["age_performance"] if isinstance(data.get("age_performance"), dict) else {}
    )
    # Weather progress
    session["weather_correct_count"] = data.get("weather_correct_count", 0)
    session["weather_incorrect_count"] = data.get("weather_incorrect_count", 0)
    session["weather_history"] = _capped_history(data.get("weather_history"))
    session["weather_performance"] = (
        data["weather_performance"]
        if isinstance(data.get("weather_performance"), dict)
        else {}
    )
    # Practice-all progress
    session["mix_correct_count"] = data.get("mix_correct_count", 0)
    session["mix_incorrect_count"] = data.get("mix_incorrect_count", 0)
    session["mix_history"] = _capped_history(data.get("mix_history"))
    mix_modules = data.get("mix_modules")
    if _is_valid_mix_modules(mix_modules):
        session["mix_modules"] = mix_modules
    else:
        session.pop("mix_modules", None)


def save_progress(google_id: str, session: dict[str, Any]) -> None:
    """Write session progress state to the DB."""
    data = json.dumps(
        {
            # Price progress
            "correct_count": session.get("correct_count", 0),
            "incorrect_count": session.get("incorrect_count", 0),
            "history": session.get("history", [])[-_SESSION_HISTORY_LIMIT:],
            "performance": session.get("performance", {}),
            # Time progress
            "time_correct_count": session.get("time_correct_count", 0),
            "time_incorrect_count": session.get("time_incorrect_count", 0),
            "time_history": session.get("time_history", [])[-_SESSION_HISTORY_LIMIT:],
            "time_performance": session.get("time_performance", {}),
            # Numbers 1-20 progress
            "n20_correct_count": session.get("n20_correct_count", 0),
            "n20_incorrect_count": session.get("n20_incorrect_count", 0),
            "n20_history": session.get("n20_history", [])[-_SESSION_HISTORY_LIMIT:],
            "n20_performance": session.get("n20_performance", {}),
            # Numbers 1-99 progress
            "n99_correct_count": session.get("n99_correct_count", 0),
            "n99_incorrect_count": session.get("n99_incorrect_count", 0),
            "n99_history": session.get("n99_history", [])[-_SESSION_HISTORY_LIMIT:],
            "n99_performance": session.get("n99_performance", {}),
            # Age progress
            "age_correct_count": session.get("age_correct_count", 0),
            "age_incorrect_count": session.get("age_incorrect_count", 0),
            "age_history": session.get("age_history", [])[-_SESSION_HISTORY_LIMIT:],
            "age_performance": session.get("age_performance", {}),
            # Weather progress
            "weather_correct_count": session.get("weather_correct_count", 0),
            "weather_incorrect_count": session.get("weather_incorrect_count", 0),
            "weather_history": session.get("weather_history", [])[
                -_SESSION_HISTORY_LIMIT:
            ],
            "weather_performance": session.get("weather_performance", {}),
            # Practice-all progress
            "mix_correct_count": session.get("mix_correct_count", 0),
            "mix_incorrect_count": session.get("mix_incorrect_count", 0),
            "mix_history": session.get("mix_history", [])[-_SESSION_HISTORY_LIMIT:],
            "mix_modules": session.get("mix_modules"),
        }
    )
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
