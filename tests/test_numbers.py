"""Tests for number_engine.py — Lithuanian number words."""

import pytest

from number_engine import NumberEngine


@pytest.fixture()
def sample_rows() -> list[dict]:
    return [
        {"number": 5, "kokia_kaina": "penki", "kokia_kaina_compound": None},
        {"number": 15, "kokia_kaina": "penkiolika", "kokia_kaina_compound": None},
        {
            "number": 45,
            "kokia_kaina": "keturiasdešimt",
            "kokia_kaina_compound": "penki",
        },
    ]


@pytest.fixture()
def engine(sample_rows: list[dict]) -> NumberEngine:
    return NumberEngine(sample_rows, max_number=99)


class TestCorrectAnswer:
    def test_produce_simple(
        self, engine: NumberEngine, sample_rows: list[dict]
    ) -> None:
        assert engine.correct_answer("produce", sample_rows[0]) == "penki"

    def test_produce_compound(
        self, engine: NumberEngine, sample_rows: list[dict]
    ) -> None:
        assert (
            engine.correct_answer("produce", sample_rows[2]) == "keturiasdešimt penki"
        )

    def test_recognize(self, engine: NumberEngine, sample_rows: list[dict]) -> None:
        assert engine.correct_answer("recognize", sample_rows[0]) == "5"
        assert engine.correct_answer("recognize", sample_rows[2]) == "45"


class TestCheck:
    def test_produce_correct(self, engine: NumberEngine) -> None:
        assert engine.check("penki", "penki", "produce") is True

    def test_produce_case_insensitive(self, engine: NumberEngine) -> None:
        assert engine.check("Penki", "penki", "produce") is True

    def test_produce_trailing_period(self, engine: NumberEngine) -> None:
        assert engine.check("penki.", "penki", "produce") is True

    def test_produce_wrong(self, engine: NumberEngine) -> None:
        assert engine.check("šeši", "penki", "produce") is False

    def test_recognize_correct(self, engine: NumberEngine) -> None:
        assert engine.check("5", "5", "recognize") is True

    def test_recognize_wrong(self, engine: NumberEngine) -> None:
        assert engine.check("6", "5", "recognize") is False

    def test_recognize_strips_whitespace(self, engine: NumberEngine) -> None:
        assert engine.check(" 5 ", "5", "recognize") is True


class TestGenerate:
    def test_returns_valid_structure(self, engine: NumberEngine) -> None:
        session: dict = {}
        ex = engine.generate(session, "n99")
        assert "exercise_type" in ex
        assert "row" in ex
        assert "number_pattern" in ex
        assert ex["exercise_type"] in ["produce", "recognize"]

    def test_row_from_engine_rows(
        self, engine: NumberEngine, sample_rows: list[dict]
    ) -> None:
        session: dict = {}
        for _ in range(20):
            ex = engine.generate(session, "n99")
            assert ex["row"] in sample_rows


class TestAdaptive:
    def test_init_tracking_idempotent(self, engine: NumberEngine) -> None:
        session: dict = {}
        engine.init_tracking(session, "n99")
        engine.init_tracking(session, "n99")
        assert "n99_performance" in session
        assert len(session["n99_performance"]["exercise_types"]) == 2

    def test_update_increments(self, engine: NumberEngine) -> None:
        session: dict = {}
        engine.init_tracking(session, "n99")
        info = {"exercise_type": "produce", "number_pattern": "single_digit"}
        engine.update(session, "n99", info, True)
        perf = session["n99_performance"]
        assert perf["exercise_types"]["produce"]["correct"] == 1
        assert perf["number_patterns"]["single_digit"]["correct"] == 1
        assert perf["total_exercises"] == 1

    def test_get_weak_areas_empty(self, engine: NumberEngine) -> None:
        assert engine.get_weak_areas({}, "n99") == {}

    def test_get_weak_areas_with_data(self, engine: NumberEngine) -> None:
        session: dict = {}
        engine.init_tracking(session, "n99")
        info = {"exercise_type": "produce", "number_pattern": "single_digit"}
        for _ in range(5):
            engine.update(session, "n99", info, True)
        info2 = {**info, "exercise_type": "recognize"}
        for _ in range(5):
            engine.update(session, "n99", info2, False)
        weak = engine.get_weak_areas(session, "n99")
        assert "Exercise Types" in weak
