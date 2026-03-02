"""Regression tests for previously identified bugs."""

import json
import sqlite3

import auth
import main


class _SQLiteDB:
    """Minimal DB wrapper compatible with auth.py's _db usage."""

    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            """
            CREATE TABLE user_progress (
                google_id TEXT PRIMARY KEY,
                data TEXT,
                updated_at TEXT
            )
            """
        )
        self.conn.commit()

    def execute(self, sql: str, params: list[str] | None = None):
        cur = self.conn.execute(sql, params or [])
        self.conn.commit()
        return cur


def test_save_and_load_progress_persists_mix_fields(monkeypatch) -> None:
    db = _SQLiteDB()
    monkeypatch.setattr(auth, "_db", db)

    saved_session = {
        "mix_correct_count": 4,
        "mix_incorrect_count": 2,
        "mix_history": [{"question": "Q1", "correct": True}],
        "mix_modules": {
            "time": {"correct": 3, "incorrect": 1},
            "prices": {"correct": 1, "incorrect": 2},
        },
    }
    auth.save_progress("user-1", saved_session)

    loaded_session: dict = {}
    auth.load_progress("user-1", loaded_session)

    assert loaded_session["mix_correct_count"] == 4
    assert loaded_session["mix_incorrect_count"] == 2
    assert loaded_session["mix_history"] == [{"question": "Q1", "correct": True}]
    assert loaded_session["mix_modules"] == {
        "time": {"correct": 3, "incorrect": 1},
        "prices": {"correct": 1, "incorrect": 2},
    }


def test_load_progress_skips_missing_mix_modules(monkeypatch) -> None:
    db = _SQLiteDB()
    monkeypatch.setattr(auth, "_db", db)

    data = json.dumps(
        {
            "mix_correct_count": 1,
            "mix_incorrect_count": 0,
            "mix_history": [],
        }
    )
    db.execute(
        """
        INSERT INTO user_progress (google_id, data, updated_at)
        VALUES (?, ?, ?)
        """,
        ["user-2", data, "2026-03-02T00:00:00+00:00"],
    )

    loaded_session: dict = {}
    auth.load_progress("user-2", loaded_session)

    assert loaded_session["mix_correct_count"] == 1
    assert loaded_session["mix_incorrect_count"] == 0
    assert loaded_session["mix_history"] == []
    assert "mix_modules" not in loaded_session


def test_practice_all_time_feedback_uses_answered_hour(monkeypatch) -> None:
    captured: dict = {}

    monkeypatch.setattr(main, "_ensure_mix_session", lambda _s: None)
    monkeypatch.setattr(
        main,
        "_check_mix_answer",
        lambda _s, _a: (
            False,
            "Pusė antros.",
            {
                "exercise_type": "half_past",
                "number_pattern": "hour_1",
                "grammatical_case": "genitive",
            },
            None,
        ),
    )

    def _fake_new_mix_question(session: dict) -> None:
        session["mix_current_module"] = "time"
        session["mix_current_question"] = "Kiek valandų? (7:30)"
        session["time_hour"] = 7

    monkeypatch.setattr(main, "_new_mix_question", _fake_new_mix_question)
    monkeypatch.setattr(
        main,
        "feedback_incorrect",
        lambda *_a, **kwargs: captured.setdefault("hour", kwargs.get("hour")),
    )
    monkeypatch.setattr(main, "feedback_correct", lambda *_a, **_k: "ok")
    monkeypatch.setattr(main, "stats_panel", lambda *_a, **_k: "stats")
    monkeypatch.setattr(main, "quiz_area", lambda *_a, **_k: "quiz")

    session = {
        "mix_current_module": "time",
        "mix_current_question": "Kiek valandų? (1:30)",
        "mix_history": [],
        "mix_correct_count": 0,
        "mix_incorrect_count": 0,
        "mix_modules": {"time": {"correct": 0, "incorrect": 1}},
        "time_hour": 1,
    }

    main.post_practice_all_answer(session, user_answer="bad answer")

    assert captured["hour"] == 1
