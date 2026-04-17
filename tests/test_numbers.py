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

    def test_produce_is_strict_for_diacritics_by_default(
        self, engine: NumberEngine
    ) -> None:
        assert engine.check("sesi", "šeši", "produce") is False

    def test_produce_accepts_missing_diacritics_in_tolerant_mode(
        self, engine: NumberEngine
    ) -> None:
        assert engine.check("sesi", "šeši", "produce", diacritic_tolerant=True) is True

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
        # Arms are lazily created via bump; init leaves dicts empty.
        assert session["n99_performance"]["exercise_types"] == {}
        assert session["n99_performance"]["number_patterns"] == {}

    def test_update_increments(self, engine: NumberEngine) -> None:
        session: dict = {}
        engine.init_tracking(session, "n99")
        info = {"exercise_type": "produce", "number_pattern": "single_digit"}
        engine.update(session, "n99", info, True)
        perf = session["n99_performance"]
        assert perf["exercise_types"]["produce"]["correct"] == pytest.approx(1.0)
        assert perf["number_patterns"]["single_digit"]["correct"] == pytest.approx(1.0)
        assert perf["total_exercises"] == 1

    def test_seed_from_prefix_copies_priors(self, engine: NumberEngine) -> None:
        session: dict = {}
        engine.init_tracking(session, "n20")
        info = {"exercise_type": "produce", "number_pattern": "teens"}
        for _ in range(5):
            engine.update(session, "n20", info, False)
        # Now init n99 seeded from n20
        engine.init_tracking(session, "n99", seed_prefix="n20")
        n99_perf = session["n99_performance"]
        assert n99_perf["number_patterns"]["teens"]["incorrect"] > 1
        assert n99_perf["total_exercises"] == 5

    def test_seed_is_deep_copy(self, engine: NumberEngine) -> None:
        session: dict = {}
        engine.init_tracking(session, "n20")
        engine.update(
            session,
            "n20",
            {"exercise_type": "produce", "number_pattern": "teens"},
            True,
        )
        engine.init_tracking(session, "n99", seed_prefix="n20")
        # Mutating n99 shouldn't affect n20
        engine.update(
            session,
            "n99",
            {"exercise_type": "produce", "number_pattern": "teens"},
            True,
        )
        assert session["n20_performance"]["total_exercises"] == 1
        assert session["n99_performance"]["total_exercises"] == 2

    def test_seed_ignored_when_no_source(self, engine: NumberEngine) -> None:
        session: dict = {}
        engine.init_tracking(session, "n99", seed_prefix="n20")
        # Falls back to default priors
        assert session["n99_performance"]["total_exercises"] == 0

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


class TestNumberInitTrackingCompact:
    def test_fresh_n20_session_starts_empty(self) -> None:
        from number_engine import NumberEngine

        session: dict = {}
        engine = NumberEngine(rows=[{"number": n} for n in range(1, 21)], max_number=20)
        engine.init_tracking(session, "n20")
        perf = session["n20_performance"]
        assert perf["exercise_types"] == {}
        assert perf["number_patterns"] == {}

    def test_n20_reachable_patterns_computed_from_rows(self) -> None:
        """The engine exposes which patterns are actually servable; the
        1-20 row set has no compound rows so compound must be absent."""
        from number_engine import NumberEngine

        engine = NumberEngine(rows=[{"number": n} for n in range(1, 21)], max_number=20)
        assert set(engine._reachable_patterns) == {"single_digit", "teens", "decade"}
        assert "compound" not in engine._reachable_patterns

    def test_n99_reachable_patterns_include_all_four(self) -> None:
        from number_engine import NumberEngine

        engine = NumberEngine(
            rows=[{"number": n} for n in range(1, 100)], max_number=99
        )
        assert set(engine._reachable_patterns) == {
            "single_digit",
            "teens",
            "decade",
            "compound",
        }

    def test_legacy_n20_session_strips_unreachable_compound(self) -> None:
        """Legacy sessions persisted with the earlier eager-seed version
        carried an untrainable "compound" arm. It must be stripped so TS
        cannot converge on it."""
        from number_engine import NumberEngine

        session = {
            "n20_performance": {
                "exercise_types": {"produce": {"correct": 1.0, "incorrect": 1.0}},
                "number_patterns": {
                    "compound": {"correct": 0.0, "incorrect": 1.0},
                    "teens": {"correct": 2.0, "incorrect": 1.0},
                },
                "total_exercises": 3,
            }
        }
        engine = NumberEngine(rows=[{"number": n} for n in range(1, 21)], max_number=20)
        engine.init_tracking(session, "n20")
        perf = session["n20_performance"]
        assert "compound" not in perf["number_patterns"]
        # Reachable + touched arm survives.
        assert perf["number_patterns"]["teens"]["correct"] == pytest.approx(2.0)

    def test_seed_prefix_from_n99_drops_unreachable_patterns(self) -> None:
        """n20 seeded from n99's priors must drop n99's compound stats."""
        from number_engine import NumberEngine

        session = {
            "n99_performance": {
                "exercise_types": {
                    "produce": {"correct": 5.0, "incorrect": 1.0},
                },
                "number_patterns": {
                    "single_digit": {"correct": 3.0, "incorrect": 0.5},
                    "compound": {"correct": 4.0, "incorrect": 0.5},
                },
                "total_exercises": 12,
            }
        }
        engine = NumberEngine(rows=[{"number": n} for n in range(1, 21)], max_number=20)
        engine.init_tracking(session, "n20", seed_prefix="n99")
        perf = session["n20_performance"]
        assert "compound" not in perf["number_patterns"]
        # single_digit prior carried over.
        assert perf["number_patterns"]["single_digit"]["correct"] == pytest.approx(3.0)


class TestLocalizedPrompt:
    def test_produce_prompt_lithuanian(
        self, engine: NumberEngine, sample_rows: list[dict]
    ) -> None:
        assert (
            engine.format_question("produce", sample_rows[0], lang="lt")
            == "Kaip pasakyti 5?"
        )

    def test_recognize_prompt_lithuanian(
        self, engine: NumberEngine, sample_rows: list[dict]
    ) -> None:
        assert (
            engine.format_question("recognize", sample_rows[1], lang="lt")
            == "Koks skaičius yra penkiolika?"
        )
