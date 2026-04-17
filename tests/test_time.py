"""Tests for time_engine.py — Lithuanian time expressions."""

import pytest

from time_engine import TimeEngine, _next_hour, time_pattern

# ------------------------------------------------------------------
# _next_hour
# ------------------------------------------------------------------


class TestNextHour:
    def test_normal(self) -> None:
        assert _next_hour(1) == 2
        assert _next_hour(5) == 6
        assert _next_hour(11) == 12

    def test_wrap(self) -> None:
        assert _next_hour(12) == 1


# ------------------------------------------------------------------
# time_pattern
# ------------------------------------------------------------------


class TestTimePattern:
    def test_returns_hour_prefix(self) -> None:
        for h in range(1, 13):
            assert time_pattern(h) == f"hour_{h}"


# ------------------------------------------------------------------
# TimeEngine — correct_answer
# ------------------------------------------------------------------


class TestWholeHour:
    @pytest.fixture()
    def engine(self) -> TimeEngine:
        return TimeEngine()

    @pytest.mark.parametrize(
        ("hour", "expected"),
        [
            (1, "Pirma valanda."),
            (2, "Antra valanda."),
            (3, "Trečia valanda."),
            (4, "Ketvirta valanda."),
            (5, "Penkta valanda."),
            (6, "Šešta valanda."),
            (7, "Septinta valanda."),
            (8, "Aštunta valanda."),
            (9, "Devinta valanda."),
            (10, "Dešimta valanda."),
            (11, "Vienuolikta valanda."),
            (12, "Dvylikta valanda."),
        ],
    )
    def test_all_hours(self, engine: TimeEngine, hour: int, expected: str) -> None:
        assert engine.correct_answer("whole_hour", hour, 0) == expected


class TestHalfPast:
    @pytest.fixture()
    def engine(self) -> TimeEngine:
        return TimeEngine()

    @pytest.mark.parametrize(
        ("hour", "expected"),
        [
            (1, "Pusė antros."),
            (2, "Pusė trečios."),
            (3, "Pusė ketvirtos."),
            (4, "Pusė penktos."),
            (5, "Pusė šeštos."),
            (6, "Pusė septintos."),
            (7, "Pusė aštuntos."),
            (8, "Pusė devintos."),
            (9, "Pusė dešimtos."),
            (10, "Pusė vienuoliktos."),
            (11, "Pusė dvyliktos."),
            (12, "Pusė pirmos."),
        ],
    )
    def test_all_hours(self, engine: TimeEngine, hour: int, expected: str) -> None:
        assert engine.correct_answer("half_past", hour, 30) == expected


class TestQuarterPast:
    @pytest.fixture()
    def engine(self) -> TimeEngine:
        return TimeEngine()

    @pytest.mark.parametrize(
        ("hour", "expected"),
        [
            (1, "Ketvirtis antros."),
            (2, "Ketvirtis trečios."),
            (6, "Ketvirtis septintos."),
            (12, "Ketvirtis pirmos."),
        ],
    )
    def test_selected_hours(self, engine: TimeEngine, hour: int, expected: str) -> None:
        assert engine.correct_answer("quarter_past", hour, 15) == expected


class TestQuarterTo:
    @pytest.fixture()
    def engine(self) -> TimeEngine:
        return TimeEngine()

    @pytest.mark.parametrize(
        ("hour", "expected"),
        [
            (1, "Be ketvirčio antra."),
            (2, "Be ketvirčio trečia."),
            (5, "Be ketvirčio šešta."),
            (11, "Be ketvirčio dvylikta."),
            (12, "Be ketvirčio pirma."),
        ],
    )
    def test_selected_hours(self, engine: TimeEngine, hour: int, expected: str) -> None:
        assert engine.correct_answer("quarter_to", hour, 45) == expected


# ------------------------------------------------------------------
# TimeEngine — format_question, check, generate
# ------------------------------------------------------------------


class TestTimeAdaptive:
    @pytest.fixture()
    def engine(self) -> TimeEngine:
        return TimeEngine()

    def test_init_tracking_idempotent(self, engine: TimeEngine) -> None:
        session: dict = {}
        engine.init_tracking(session)
        engine.init_tracking(session)
        assert "time_performance" in session
        # Arms are created lazily on bump; init leaves the families empty.
        assert session["time_performance"]["exercise_types"] == {}
        assert session["time_performance"]["hour_patterns"] == {}

    def test_update_increments(self, engine: TimeEngine) -> None:
        session: dict = {}
        engine.init_tracking(session)
        info = {
            "exercise_type": "whole_hour",
            "number_pattern": "hour_3",
            "grammatical_case": "nominative",
        }
        engine.update(session, info, True)
        perf = session["time_performance"]
        assert perf["exercise_types"]["whole_hour"]["correct"] == pytest.approx(1.0)
        assert perf["hour_patterns"]["hour_3"]["correct"] == pytest.approx(1.0)
        assert perf["total_exercises"] == 1

    def test_get_weak_areas_empty_without_perf(self, engine: TimeEngine) -> None:
        assert engine.get_weak_areas({}) == {}

    def test_get_weak_areas_returns_categories(self, engine: TimeEngine) -> None:
        session: dict = {}
        engine.init_tracking(session)
        info = {
            "exercise_type": "whole_hour",
            "number_pattern": "hour_1",
            "grammatical_case": "nominative",
        }
        # Add enough data for weak areas to show
        for _ in range(5):
            engine.update(session, info, True)
        info2 = {**info, "exercise_type": "half_past", "grammatical_case": "genitive"}
        for _ in range(5):
            engine.update(session, info2, False)
        weak = engine.get_weak_areas(session)
        assert "Exercise Types" in weak


class TestTimeEngineBasics:
    @pytest.fixture()
    def engine(self) -> TimeEngine:
        return TimeEngine()

    def test_format_question(self, engine: TimeEngine) -> None:
        assert engine.format_question("3:00") == "Kiek valandų? (3:00)"

    def test_check_correct(self, engine: TimeEngine) -> None:
        assert engine.check("Pirma valanda.", "Pirma valanda.") is True

    def test_check_case_insensitive(self, engine: TimeEngine) -> None:
        assert engine.check("pirma valanda", "Pirma valanda.") is True

    def test_check_is_strict_for_diacritics_by_default(
        self, engine: TimeEngine
    ) -> None:
        assert engine.check("Puse antros.", "Pusė antros.") is False

    def test_check_accepts_missing_diacritics_in_tolerant_mode(
        self, engine: TimeEngine
    ) -> None:
        assert (
            engine.check(
                "Puse antros.",
                "Pusė antros.",
                diacritic_tolerant=True,
            )
            is True
        )

    def test_check_incorrect(self, engine: TimeEngine) -> None:
        assert engine.check("Antra valanda.", "Pirma valanda.") is False

    def test_generate_returns_dict(self, engine: TimeEngine) -> None:
        ex = engine.generate({})
        assert "exercise_type" in ex
        assert "hour" in ex
        assert "minute" in ex
        assert "display_time" in ex
        assert "number_pattern" in ex
        assert "grammatical_case" in ex
        assert ex["exercise_type"] in [
            "whole_hour",
            "half_past",
            "quarter_past",
            "quarter_to",
        ]

    def test_generate_minute_matches_type(self, engine: TimeEngine) -> None:
        for _ in range(50):
            ex = engine.generate({})
            if ex["exercise_type"] == "whole_hour":
                assert ex["minute"] == 0
            elif ex["exercise_type"] == "half_past":
                assert ex["minute"] == 30
            elif ex["exercise_type"] == "quarter_past":
                assert ex["minute"] == 15
            elif ex["exercise_type"] == "quarter_to":
                assert ex["minute"] == 45


class TestTimeInitTrackingCompact:
    def test_fresh_session_has_empty_arm_dicts(self) -> None:
        from time_engine import TimeEngine

        session: dict = {}
        TimeEngine().init_tracking(session)
        perf = session["time_performance"]

        assert perf["exercise_types"] == {}
        assert perf["hour_patterns"] == {}
        assert perf["grammatical_cases"] == {}

    def test_legacy_cold_start_arms_stripped(self) -> None:
        """Earlier versions pre-seeded all 12 hour_patterns. In a cookie-
        backed session that's significant bloat; strip on load."""
        from time_engine import TimeEngine

        session = {
            "time_performance": {
                "exercise_types": {
                    "whole_hour": {"correct": 2.0, "incorrect": 1.0},  # touched
                    "half_past": {"correct": 0.0, "incorrect": 1.0},  # cold
                },
                "hour_patterns": {
                    f"hour_{i}": {"correct": 0.0, "incorrect": 1.0}
                    for i in range(1, 13)
                },
                "grammatical_cases": {
                    "nominative": {"correct": 0.0, "incorrect": 1.0},
                    "genitive": {"correct": 0.0, "incorrect": 1.0},
                },
                "total_exercises": 5,
            }
        }
        TimeEngine().init_tracking(session)
        perf = session["time_performance"]
        assert set(perf["exercise_types"].keys()) == {"whole_hour"}
        assert perf["hour_patterns"] == {}
        assert perf["grammatical_cases"] == {}
