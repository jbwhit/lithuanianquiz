"""Tests for age_engine.py — Lithuanian age expressions."""

import pytest

from age_engine import PRONOUNS, AgeEngine


@pytest.fixture()
def sample_rows() -> list[dict]:
    return [
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
def engine(sample_rows: list[dict]) -> AgeEngine:
    return AgeEngine(sample_rows)


JAM = {"dative": "Jam", "english": "He is"}
JAI = {"dative": "Jai", "english": "She is"}
MAN = {"dative": "Man", "english": "I am"}


class TestCorrectAnswer:
    def test_produce_simple(self, engine: AgeEngine, sample_rows: list[dict]) -> None:
        assert (
            engine.correct_answer("produce", sample_rows[0], JAM)
            == "Jam penkeri metai."
        )

    def test_produce_compound(self, engine: AgeEngine, sample_rows: list[dict]) -> None:
        assert (
            engine.correct_answer("produce", sample_rows[2], JAI)
            == "Jai dvidešimt penkeri metai."
        )

    def test_produce_decade(self, engine: AgeEngine, sample_rows: list[dict]) -> None:
        assert (
            engine.correct_answer("produce", sample_rows[3], MAN)
            == "Man trisdešimt metų."
        )

    def test_recognize(self, engine: AgeEngine, sample_rows: list[dict]) -> None:
        assert engine.correct_answer("recognize", sample_rows[0], JAM) == "5"
        assert engine.correct_answer("recognize", sample_rows[2], JAI) == "25"


class TestFormatQuestion:
    def test_produce(self, engine: AgeEngine, sample_rows: list[dict]) -> None:
        assert (
            engine.format_question("produce", sample_rows[0], JAM)
            == "He is 5 years old."
        )

    def test_produce_she(self, engine: AgeEngine, sample_rows: list[dict]) -> None:
        assert (
            engine.format_question("produce", sample_rows[2], JAI)
            == "She is 25 years old."
        )

    def test_recognize(self, engine: AgeEngine, sample_rows: list[dict]) -> None:
        assert (
            engine.format_question("recognize", sample_rows[0], JAM)
            == "Jam penkeri metai."
        )

    def test_produce_lithuanian_prompt(
        self, engine: AgeEngine, sample_rows: list[dict]
    ) -> None:
        assert (
            engine.format_question("produce", sample_rows[0], JAM, lang="lt")
            == "Jam yra 5 metų."
        )


class TestCheck:
    def test_produce_correct(self, engine: AgeEngine) -> None:
        assert (
            engine.check("Jam penkeri metai.", "Jam penkeri metai.", "produce") is True
        )

    def test_produce_case_insensitive(self, engine: AgeEngine) -> None:
        assert (
            engine.check("jam penkeri metai.", "Jam penkeri metai.", "produce") is True
        )

    def test_produce_is_strict_for_diacritics_by_default(
        self, engine: AgeEngine
    ) -> None:
        assert engine.check("Jam sesi metai.", "Jam šeši metai.", "produce") is False

    def test_produce_accepts_missing_diacritics_in_tolerant_mode(
        self, engine: AgeEngine
    ) -> None:
        assert (
            engine.check(
                "Jam sesi metai.",
                "Jam šeši metai.",
                "produce",
                diacritic_tolerant=True,
            )
            is True
        )

    def test_produce_wrong(self, engine: AgeEngine) -> None:
        assert engine.check("Jam šeši metai.", "Jam penkeri metai.", "produce") is False

    def test_recognize_correct(self, engine: AgeEngine) -> None:
        assert engine.check("25", "25", "recognize") is True

    def test_recognize_wrong(self, engine: AgeEngine) -> None:
        assert engine.check("26", "25", "recognize") is False

    def test_recognize_strips_whitespace(self, engine: AgeEngine) -> None:
        assert engine.check(" 25 ", "25", "recognize") is True


class TestGenerate:
    def test_returns_valid_structure(self, engine: AgeEngine) -> None:
        session: dict = {}
        ex = engine.generate(session, "age")
        assert "exercise_type" in ex
        assert "row" in ex
        assert "number_pattern" in ex
        assert "pronoun" in ex
        assert ex["exercise_type"] in ["produce", "recognize"]
        assert ex["pronoun"] in PRONOUNS

    def test_row_from_engine_rows(
        self, engine: AgeEngine, sample_rows: list[dict]
    ) -> None:
        session: dict = {}
        for _ in range(20):
            ex = engine.generate(session, "age")
            assert ex["row"] in sample_rows


class TestAdaptive:
    def test_init_tracking_idempotent(self, engine: AgeEngine) -> None:
        session: dict = {}
        engine.init_tracking(session, "age")
        engine.init_tracking(session, "age")
        assert "age_performance" in session
        # Arms are created lazily via bump; init_tracking only ensures
        # the skeleton exists.
        assert session["age_performance"]["exercise_types"] == {}
        assert session["age_performance"]["pronouns"] == {}
        assert session["age_performance"]["number_patterns"] == {}

    def test_update_increments(self, engine: AgeEngine) -> None:
        session: dict = {}
        engine.init_tracking(session, "age")
        info = {
            "exercise_type": "produce",
            "number_pattern": "single_digit",
            "pronoun": "Jam",
        }
        engine.update(session, "age", info, True)
        perf = session["age_performance"]
        assert perf["exercise_types"]["produce"]["correct"] == pytest.approx(1.0)
        assert perf["number_patterns"]["single_digit"]["correct"] == pytest.approx(1.0)
        assert perf["pronouns"]["Jam"]["correct"] == pytest.approx(1.0)
        assert perf["total_exercises"] == 1

    def test_seed_from_numbers(self, engine: AgeEngine) -> None:
        session: dict = {
            "numbers_performance": {
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
        engine.init_tracking(session, "age", seed_prefix="numbers")
        perf = session["age_performance"]
        # exercise_types and number_patterns seeded from numbers
        assert perf["exercise_types"]["produce"]["correct"] == 5
        assert perf["number_patterns"]["teens"]["incorrect"] == 5
        # pronouns are lazily created; init_tracking leaves them empty.
        assert perf["pronouns"] == {}
        assert perf["total_exercises"] == 14

    def test_seed_is_deep_copy(self, engine: AgeEngine) -> None:
        session: dict = {
            "numbers_performance": {
                "exercise_types": {
                    "produce": {"correct": 1, "incorrect": 1},
                    "recognize": {"correct": 1, "incorrect": 1},
                },
                "number_patterns": {},
                "total_exercises": 2,
            }
        }
        engine.init_tracking(session, "age", seed_prefix="numbers")
        engine.update(
            session,
            "age",
            {"exercise_type": "produce", "number_pattern": "teens", "pronoun": "Man"},
            True,
        )
        # Mutating age shouldn't affect numbers
        assert session["numbers_performance"]["total_exercises"] == 2
        assert session["age_performance"]["total_exercises"] == 3

    def test_get_weak_areas_empty(self, engine: AgeEngine) -> None:
        assert engine.get_weak_areas({}, "age") == {}

    def test_get_weak_areas_with_data(self, engine: AgeEngine) -> None:
        session: dict = {}
        engine.init_tracking(session, "age")
        info = {
            "exercise_type": "produce",
            "number_pattern": "single_digit",
            "pronoun": "Jam",
        }
        for _ in range(5):
            engine.update(session, "age", info, True)
        info2 = {**info, "exercise_type": "recognize", "pronoun": "Jai"}
        for _ in range(5):
            engine.update(session, "age", info2, False)
        weak = engine.get_weak_areas(session, "age")
        assert "Exercise Types" in weak
        assert "Pronouns" in weak


class TestAgeInitTrackingCompact:
    def test_fresh_session_has_empty_arm_dicts(self) -> None:
        from age_engine import AgeEngine

        session: dict = {}
        engine = AgeEngine(rows=[{"number": n, "years": "metai"} for n in range(2, 21)])
        engine.init_tracking(session, "age")
        perf = session["age_performance"]

        # Arms are created lazily via bump to keep session cookies small.
        assert perf["exercise_types"] == {}
        assert perf["number_patterns"] == {}
        assert perf["pronouns"] == {}

    def test_legacy_session_with_cold_start_arms_gets_stripped(self) -> None:
        """Earlier versions of this branch eagerly pre-seeded every arm
        family with cold-start values. Those persist into cookies.
        init_tracking must strip untouched arms to reclaim the space."""
        from age_engine import AgeEngine

        session = {
            "age_performance": {
                "exercise_types": {
                    "produce": {"correct": 0.0, "incorrect": 1.0},  # cold-start
                    "recognize": {"correct": 2.0, "incorrect": 0.5},  # touched
                },
                "number_patterns": {
                    "single_digit": {"correct": 0.0, "incorrect": 1.0},
                    "teens": {"correct": 3.0, "incorrect": 1.0},
                },
                "pronouns": {
                    "Man": {"correct": 0.0, "incorrect": 1.0},
                    "Jam": {"correct": 0.0, "incorrect": 1.0},
                },
                "total_exercises": 5,
            }
        }
        engine = AgeEngine(rows=[{"number": n, "years": "metai"} for n in range(2, 21)])
        engine.init_tracking(session, "age")
        perf = session["age_performance"]
        assert set(perf["exercise_types"].keys()) == {"recognize"}
        assert set(perf["number_patterns"].keys()) == {"teens"}
        assert perf["pronouns"] == {}
