"""Tests for weather_engine.py — Lithuanian temperature expressions."""

import pytest

from weather_engine import WeatherEngine, _degree_form


@pytest.fixture()
def sample_rows() -> list[dict]:
    return [
        {
            "number": 1,
            "kokia_kaina": "vienas",
            "kokia_kaina_compound": None,
            "years": "metai",
        },
        {
            "number": 5,
            "kokia_kaina": "penki",
            "kokia_kaina_compound": None,
            "years": "metai",
        },
        {
            "number": 15,
            "kokia_kaina": "penkiolika",
            "kokia_kaina_compound": None,
            "years": "metų",
        },
        {
            "number": 25,
            "kokia_kaina": "dvidešimt",
            "kokia_kaina_compound": "penki",
            "years": "metai",
        },
        {
            "number": 30,
            "kokia_kaina": "trisdešimt",
            "kokia_kaina_compound": None,
            "years": "metų",
        },
    ]


@pytest.fixture()
def engine(sample_rows: list[dict]) -> WeatherEngine:
    return WeatherEngine(sample_rows)


class TestDegreeForm:
    def test_one(self, sample_rows: list[dict]) -> None:
        assert _degree_form(sample_rows[0]) == "laipsnis"

    def test_single_digit(self, sample_rows: list[dict]) -> None:
        assert _degree_form(sample_rows[1]) == "laipsniai"

    def test_teens(self, sample_rows: list[dict]) -> None:
        assert _degree_form(sample_rows[2]) == "laipsnių"

    def test_compound(self, sample_rows: list[dict]) -> None:
        assert _degree_form(sample_rows[3]) == "laipsniai"

    def test_decade(self, sample_rows: list[dict]) -> None:
        assert _degree_form(sample_rows[4]) == "laipsnių"


class TestCorrectAnswer:
    def test_produce_simple(
        self, engine: WeatherEngine, sample_rows: list[dict]
    ) -> None:
        assert (
            engine.correct_answer("produce", sample_rows[1], negative=False)
            == "penki laipsniai"
        )

    def test_produce_compound(
        self, engine: WeatherEngine, sample_rows: list[dict]
    ) -> None:
        assert (
            engine.correct_answer("produce", sample_rows[3], negative=False)
            == "dvidešimt penki laipsniai"
        )

    def test_produce_negative(
        self, engine: WeatherEngine, sample_rows: list[dict]
    ) -> None:
        assert (
            engine.correct_answer("produce", sample_rows[1], negative=True)
            == "minus penki laipsniai"
        )

    def test_produce_teens(
        self, engine: WeatherEngine, sample_rows: list[dict]
    ) -> None:
        assert (
            engine.correct_answer("produce", sample_rows[2], negative=False)
            == "penkiolika laipsnių"
        )

    def test_recognize_positive(
        self, engine: WeatherEngine, sample_rows: list[dict]
    ) -> None:
        assert engine.correct_answer("recognize", sample_rows[1], negative=False) == "5"

    def test_recognize_negative(
        self, engine: WeatherEngine, sample_rows: list[dict]
    ) -> None:
        assert engine.correct_answer("recognize", sample_rows[1], negative=True) == "-5"


class TestFormatQuestion:
    def test_produce_positive(
        self, engine: WeatherEngine, sample_rows: list[dict]
    ) -> None:
        assert (
            engine.format_question("produce", sample_rows[3], negative=False)
            == "How do you say 25\u00b0C?"
        )

    def test_produce_negative(
        self, engine: WeatherEngine, sample_rows: list[dict]
    ) -> None:
        assert (
            engine.format_question("produce", sample_rows[1], negative=True)
            == "How do you say -5\u00b0C?"
        )

    def test_produce_lithuanian(
        self, engine: WeatherEngine, sample_rows: list[dict]
    ) -> None:
        assert (
            engine.format_question("produce", sample_rows[3], negative=False, lang="lt")
            == "Kaip pasakyti 25\u00b0C?"
        )

    def test_recognize(self, engine: WeatherEngine, sample_rows: list[dict]) -> None:
        assert (
            engine.format_question("recognize", sample_rows[1], negative=True)
            == "minus penki laipsniai"
        )

    def test_recognize_positive(
        self, engine: WeatherEngine, sample_rows: list[dict]
    ) -> None:
        assert (
            engine.format_question("recognize", sample_rows[2], negative=False)
            == "penkiolika laipsnių"
        )


class TestCheck:
    def test_produce_correct(self, engine: WeatherEngine) -> None:
        assert engine.check("penki laipsniai", "penki laipsniai", "produce") is True

    def test_produce_case_insensitive(self, engine: WeatherEngine) -> None:
        assert engine.check("Penki Laipsniai", "penki laipsniai", "produce") is True

    def test_produce_wrong(self, engine: WeatherEngine) -> None:
        assert engine.check("šeši laipsniai", "penki laipsniai", "produce") is False

    def test_recognize_correct(self, engine: WeatherEngine) -> None:
        assert engine.check("-5", "-5", "recognize") is True

    def test_recognize_wrong(self, engine: WeatherEngine) -> None:
        assert engine.check("5", "-5", "recognize") is False

    def test_recognize_strips_whitespace(self, engine: WeatherEngine) -> None:
        assert engine.check(" 15 ", "15", "recognize") is True


class TestGenerate:
    def test_returns_valid_structure(self, engine: WeatherEngine) -> None:
        session: dict = {}
        ex = engine.generate(session, "weather")
        assert "exercise_type" in ex
        assert "row" in ex
        assert "number_pattern" in ex
        assert "negative" in ex
        assert ex["exercise_type"] in ["produce", "recognize"]
        assert isinstance(ex["negative"], bool)

    def test_row_from_engine_rows(
        self, engine: WeatherEngine, sample_rows: list[dict]
    ) -> None:
        session: dict = {}
        for _ in range(20):
            ex = engine.generate(session, "weather")
            assert ex["row"] in sample_rows

    def test_negative_constrained_to_20(self) -> None:
        """Negative exercises should only use numbers <= 20."""
        rows = [
            {
                "number": 5,
                "kokia_kaina": "penki",
                "kokia_kaina_compound": None,
                "years": "metai",
            },
            {
                "number": 35,
                "kokia_kaina": "trisdešimt",
                "kokia_kaina_compound": "penki",
                "years": "metai",
            },
        ]
        eng = WeatherEngine(rows)
        for _ in range(30):
            ex = eng.generate({}, "weather")
            if ex["negative"]:
                assert ex["row"]["number"] <= 20


class TestAdaptive:
    def test_init_tracking_idempotent(self, engine: WeatherEngine) -> None:
        session: dict = {}
        engine.init_tracking(session, "weather")
        engine.init_tracking(session, "weather")
        assert "weather_performance" in session
        assert len(session["weather_performance"]["exercise_types"]) == 2
        assert len(session["weather_performance"]["sign"]) == 2

    def test_update_increments(self, engine: WeatherEngine) -> None:
        session: dict = {}
        engine.init_tracking(session, "weather")
        info = {
            "exercise_type": "produce",
            "number_pattern": "single_digit",
            "sign": "positive",
        }
        engine.update(session, "weather", info, True)
        perf = session["weather_performance"]
        assert perf["exercise_types"]["produce"]["correct"] == 1
        assert perf["number_patterns"]["single_digit"]["correct"] == 1
        assert perf["sign"]["positive"]["correct"] == 1
        assert perf["total_exercises"] == 1

    def test_seed_from_n99(self, engine: WeatherEngine) -> None:
        session: dict = {
            "n99_performance": {
                "exercise_types": {
                    "produce": {"correct": 5, "incorrect": 2},
                    "recognize": {"correct": 3, "incorrect": 4},
                },
                "number_patterns": {
                    "teens": {"correct": 1, "incorrect": 5},
                },
                "total_exercises": 14,
            }
        }
        engine.init_tracking(session, "weather", seed_prefix="n99")
        perf = session["weather_performance"]
        assert perf["exercise_types"]["produce"]["correct"] == 5
        assert perf["number_patterns"]["teens"]["incorrect"] == 5
        # sign initialized fresh
        assert perf["sign"]["positive"]["correct"] == 0
        assert perf["total_exercises"] == 14

    def test_seed_is_deep_copy(self, engine: WeatherEngine) -> None:
        session: dict = {
            "n99_performance": {
                "exercise_types": {
                    "produce": {"correct": 1, "incorrect": 1},
                    "recognize": {"correct": 1, "incorrect": 1},
                },
                "number_patterns": {},
                "total_exercises": 2,
            }
        }
        engine.init_tracking(session, "weather", seed_prefix="n99")
        engine.update(
            session,
            "weather",
            {"exercise_type": "produce", "number_pattern": "teens", "sign": "positive"},
            True,
        )
        assert session["n99_performance"]["total_exercises"] == 2
        assert session["weather_performance"]["total_exercises"] == 3

    def test_get_weak_areas_empty(self, engine: WeatherEngine) -> None:
        assert engine.get_weak_areas({}, "weather") == {}

    def test_get_weak_areas_with_data(self, engine: WeatherEngine) -> None:
        session: dict = {}
        engine.init_tracking(session, "weather")
        info = {
            "exercise_type": "produce",
            "number_pattern": "single_digit",
            "sign": "positive",
        }
        for _ in range(5):
            engine.update(session, "weather", info, True)
        info2 = {**info, "exercise_type": "recognize", "sign": "negative"}
        for _ in range(5):
            engine.update(session, "weather", info2, False)
        weak = engine.get_weak_areas(session, "weather")
        assert "Exercise Types" in weak
        assert "Sign" in weak
