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


def test_set_diacritic_mode_route_updates_session_and_redirects() -> None:
    session: dict = {}
    resp = main.get_set_diacritic_mode(session, enabled="1", next_path="/practice-all")

    assert session["diacritic_tolerant"] is True
    assert resp.status_code == 303
    assert resp.headers.get("location") == "/practice-all"


def test_set_diacritic_mode_rejects_non_local_redirects() -> None:
    session: dict = {"diacritic_tolerant": True}
    resp = main.get_set_diacritic_mode(
        session, enabled="0", next_path="https://evil.example"
    )

    assert session["diacritic_tolerant"] is False
    assert resp.status_code == 303
    assert resp.headers.get("location") == "/"


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


def test_post_time_answer_feedback_uses_answered_snapshot(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(main, "_ensure_time_session", lambda _s: None)
    monkeypatch.setattr(
        main.time_engine,
        "correct_answer",
        lambda *_a, **_k: "Ketvirtis septintos.",
    )
    monkeypatch.setattr(main.time_engine, "check", lambda *_a, **_k: False)
    monkeypatch.setattr(main.time_engine, "update", lambda *_a, **_k: None)

    def _fake_new_time_question(session: dict) -> None:
        session["time_exercise_type"] = "quarter_to"
        session["time_hour"] = 8
        session["time_minute"] = 45
        session["time_display"] = "8:45"
        session["time_number_pattern"] = "hour_8"
        session["time_grammatical_case"] = "nominative"
        session["time_current_question"] = "Kiek valandų? (8:45)"

    def _fake_feedback_incorrect(*_a, **kwargs):
        captured["question"] = kwargs.get("question")
        captured["hour"] = kwargs.get("hour")
        captured["exercise_type"] = kwargs.get("exercise_type")
        captured["grammatical_case"] = kwargs.get("grammatical_case")
        return "feedback"

    def _fake_quiz_area(question: str, **_kwargs):
        captured["next_question"] = question
        return "quiz"

    monkeypatch.setattr(main, "_new_time_question", _fake_new_time_question)
    monkeypatch.setattr(main, "feedback_incorrect", _fake_feedback_incorrect)
    monkeypatch.setattr(main, "feedback_correct", lambda *_a, **_k: "ok")
    monkeypatch.setattr(main, "stats_panel", lambda *_a, **_k: "stats")
    monkeypatch.setattr(main, "quiz_area", _fake_quiz_area)

    session = {
        "time_current_question": "Kiek valandų? (6:15)",
        "time_exercise_type": "quarter_past",
        "time_hour": 6,
        "time_minute": 15,
        "time_number_pattern": "hour_6",
        "time_grammatical_case": "genitive",
        "time_history": [],
        "time_correct_count": 0,
        "time_incorrect_count": 0,
    }

    main.post_time_answer(session, user_answer="")

    assert captured["question"] == "Kiek valandų? (6:15)"
    assert captured["hour"] == 6
    assert captured["exercise_type"] == "quarter_past"
    assert captured["grammatical_case"] == "genitive"
    assert captured["next_question"] == "Kiek valandų? (8:45)"
    assert session["time_history"] == [
        {
            "question": "Kiek valandų? (6:15)",
            "answer": "",
            "correct": False,
            "true_answer": "Ketvirtis septintos.",
        }
    ]


def test_post_age_answer_feedback_uses_answered_snapshot(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(main, "_ensure_age_session", lambda _s: None)
    monkeypatch.setattr(
        main.age_engine,
        "correct_answer",
        lambda *_a, **_k: "Jam dveji metai.",
    )
    monkeypatch.setattr(main.age_engine, "check", lambda *_a, **_k: False)
    monkeypatch.setattr(main.age_engine, "update", lambda *_a, **_k: None)

    def _fake_new_age_question(session: dict) -> None:
        session["age_exercise_type"] = "recognize"
        session["age_pronoun"] = "Tau"
        session["age_number_pattern"] = "teen"
        session["age_current_question"] = "How old are you? (19)"

    def _fake_feedback_incorrect(*_a, **kwargs):
        captured["question"] = kwargs.get("question")
        captured["exercise_type"] = kwargs.get("exercise_type")
        captured["number_pattern"] = kwargs.get("number_pattern")
        return "feedback"

    def _fake_quiz_area(question: str, **_kwargs):
        captured["next_question"] = question
        return "quiz"

    monkeypatch.setattr(main, "_new_age_question", _fake_new_age_question)
    monkeypatch.setattr(main, "feedback_incorrect", _fake_feedback_incorrect)
    monkeypatch.setattr(main, "feedback_correct", lambda *_a, **_k: "ok")
    monkeypatch.setattr(main, "stats_panel", lambda *_a, **_k: "stats")
    monkeypatch.setattr(main, "quiz_area", _fake_quiz_area)

    session = {
        "age_current_question": "How old is he? (2)",
        "age_row_id": main.age_rows[0]["number"],
        "age_exercise_type": "produce",
        "age_pronoun": "Jam",
        "age_number_pattern": "single",
        "age_history": [],
        "age_correct_count": 0,
        "age_incorrect_count": 0,
    }

    main.post_age_answer(session, user_answer="blogai")

    assert captured["question"] == "How old is he? (2)"
    assert captured["exercise_type"] == "produce"
    assert captured["number_pattern"] == "single"
    assert captured["next_question"] == "How old are you? (19)"
    assert session["age_history"] == [
        {
            "question": "How old is he? (2)",
            "answer": "blogai",
            "correct": False,
            "true_answer": "Jam dveji metai.",
        }
    ]


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
