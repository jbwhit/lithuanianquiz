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
        "ui_lang": "lt",
        "diacritic_tolerant": True,
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
    assert loaded_session["ui_lang"] == "lt"
    assert loaded_session["diacritic_tolerant"] is True


def test_load_progress_defaults_diacritic_mode_to_strict(monkeypatch) -> None:
    db = _SQLiteDB()
    monkeypatch.setattr(auth, "_db", db)

    data = json.dumps({"mix_history": []})
    db.execute(
        """
        INSERT INTO user_progress (google_id, data, updated_at)
        VALUES (?, ?, ?)
        """,
        ["user-0", data, "2026-03-02T00:00:00+00:00"],
    )

    loaded_session: dict = {}
    auth.load_progress("user-0", loaded_session)
    assert loaded_session["diacritic_tolerant"] is False


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


def test_mix_session_initializes_only_one_module_question() -> None:
    session: dict = {}
    main._ensure_mix_session(session)

    module_q_keys = [
        "current_question",
        "time_current_question",
        "n20_current_question",
        "n99_current_question",
        "age_current_question",
        "weather_current_question",
    ]
    present = [k for k in module_q_keys if k in session]

    assert len(present) == 1
    assert "mix_current_question" in session


def test_price_history_capped_to_limit() -> None:
    session: dict = {}
    main._ensure_session(session)
    for _ in range(12):
        main.post(session, user_answer="x")
    assert len(session["history"]) == 5


def test_mix_history_capped_to_limit() -> None:
    session: dict = {}
    main._ensure_mix_session(session)
    for _ in range(12):
        main.post_practice_all_answer(session, user_answer="x")
    assert len(session["mix_history"]) == 5


def test_load_progress_caps_oversized_histories(monkeypatch) -> None:
    db = _SQLiteDB()
    monkeypatch.setattr(auth, "_db", db)

    long = [{"question": f"Q{i}", "correct": bool(i % 2)} for i in range(20)]
    data = json.dumps(
        {
            "history": long,
            "time_history": long,
            "n20_history": long,
            "n99_history": long,
            "age_history": long,
            "weather_history": long,
            "mix_history": long,
        }
    )
    db.execute(
        """
        INSERT INTO user_progress (google_id, data, updated_at)
        VALUES (?, ?, ?)
        """,
        ["user-3", data, "2026-03-02T00:00:00+00:00"],
    )

    loaded_session: dict = {}
    auth.load_progress("user-3", loaded_session)

    assert len(loaded_session["history"]) == 5
    assert len(loaded_session["time_history"]) == 5
    assert len(loaded_session["n20_history"]) == 5
    assert len(loaded_session["n99_history"]) == 5
    assert len(loaded_session["age_history"]) == 5
    assert len(loaded_session["weather_history"]) == 5
    assert len(loaded_session["mix_history"]) == 5


def test_load_progress_skips_invalid_json_without_clobbering_session(
    monkeypatch,
) -> None:
    db = _SQLiteDB()
    monkeypatch.setattr(auth, "_db", db)

    db.execute(
        """
        INSERT INTO user_progress (google_id, data, updated_at)
        VALUES (?, ?, ?)
        """,
        ["user-4", "{not json", "2026-03-02T00:00:00+00:00"],
    )

    loaded_session = {"mix_modules": {"time": {"correct": 1, "incorrect": 1}}}
    auth.load_progress("user-4", loaded_session)

    assert loaded_session == {"mix_modules": {"time": {"correct": 1, "incorrect": 1}}}


def test_load_progress_drops_invalid_mix_modules(monkeypatch) -> None:
    db = _SQLiteDB()
    monkeypatch.setattr(auth, "_db", db)

    data = json.dumps(
        {
            "mix_correct_count": 1,
            "mix_incorrect_count": 2,
            "mix_history": [],
            "mix_modules": {
                "time": {"correct": 3},
            },
        }
    )
    db.execute(
        """
        INSERT INTO user_progress (google_id, data, updated_at)
        VALUES (?, ?, ?)
        """,
        ["user-5", data, "2026-03-02T00:00:00+00:00"],
    )

    loaded_session = {"mix_modules": {"prices": {"correct": 9, "incorrect": 1}}}
    auth.load_progress("user-5", loaded_session)

    assert loaded_session["mix_correct_count"] == 1
    assert loaded_session["mix_incorrect_count"] == 2
    assert "mix_modules" not in loaded_session


def test_append_history_entry_resets_non_list_history() -> None:
    session = {"history": "bad-data"}
    main._append_history_entry(
        session,
        "history",
        {"question": "Q", "answer": "A", "correct": False, "true_answer": "T"},
    )

    assert isinstance(session["history"], list)
    assert len(session["history"]) == 1


def test_set_language_updates_session_and_redirects_to_referrer() -> None:
    class _Req:
        headers = {"referer": "https://example.com/time?from=header"}

    session: dict = {}
    response = main.get_set_language(_Req(), session, lang="lt")

    assert session["ui_lang"] == "lt"
    assert response.status_code == 303
    assert response.headers["location"] == "/time?from=header"


def test_set_language_sanitizes_bad_input() -> None:
    class _Req:
        headers = {"referer": "javascript:alert(1)"}

    session: dict = {}
    response = main.get_set_language(_Req(), session, lang="fr")

    assert session["ui_lang"] == "en"
    assert response.headers["location"] == "/"


def test_set_diacritic_mode_route_updates_session_and_redirects() -> None:
    session: dict = {}
    response = main.get_set_diacritic_mode(
        session, enabled="1", next_path="/practice-all"
    )

    assert session["diacritic_tolerant"] is True
    assert response.status_code == 303
    assert response.headers.get("location") == "/practice-all"


def test_set_diacritic_mode_rejects_non_local_redirects() -> None:
    session: dict = {"diacritic_tolerant": True}
    response = main.get_set_diacritic_mode(
        session, enabled="0", next_path="https://evil.example"
    )

    assert session["diacritic_tolerant"] is False
    assert response.status_code == 303
    assert response.headers.get("location") == "/"
