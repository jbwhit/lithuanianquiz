"""Tests for adaptive.py — Thompson Sampling engine."""

from collections import Counter

import pytest

from adaptive import AdaptiveLearning, _bump, _sample_weakest
from quiz import ExerciseEngine

# ------------------------------------------------------------------
# _bump
# ------------------------------------------------------------------


class TestBump:
    def test_creates_arm_if_missing(self) -> None:
        # New arms start at cold-start seed {correct: 0.0, incorrect: 1.0}.
        # After bump(True): correct = 0.0*γ + 1 = 1.0, incorrect = 1.0*γ = 0.98.
        from thompson import DECAY_GAMMA

        cat: dict = {}
        _bump(cat, "foo", True)
        assert cat["foo"]["correct"] == pytest.approx(1.0)
        assert cat["foo"]["incorrect"] == pytest.approx(1.0 * DECAY_GAMMA)

    def test_increments_correct(self) -> None:
        # After bump(True): correct = 5*γ + 1, incorrect = 2*γ.
        from thompson import DECAY_GAMMA

        cat = {"foo": {"correct": 5, "incorrect": 2}}
        _bump(cat, "foo", True)
        assert cat["foo"]["correct"] == pytest.approx(5 * DECAY_GAMMA + 1)

    def test_increments_incorrect(self) -> None:
        # After bump(False): correct = 5*γ, incorrect = 2*γ + 1.
        from thompson import DECAY_GAMMA

        cat = {"foo": {"correct": 5, "incorrect": 2}}
        _bump(cat, "foo", False)
        assert cat["foo"]["incorrect"] == pytest.approx(2 * DECAY_GAMMA + 1)


# ------------------------------------------------------------------
# _sample_weakest
# ------------------------------------------------------------------


class TestSampleWeakest:
    def test_prefers_weak_arm(self) -> None:
        """Over many samples, the weak arm should be picked more often."""
        arms = {
            "strong": {"correct": 50, "incorrect": 1},
            "weak": {"correct": 1, "incorrect": 50},
        }
        counts = Counter(_sample_weakest(arms) for _ in range(500))
        assert counts["weak"] > counts["strong"]


# ------------------------------------------------------------------
# AdaptiveLearning
# ------------------------------------------------------------------

ROWS = [
    {
        "number": n,
        "kokia_kaina": "x",
        "kokia_kaina_compound": None,
        "euro_nom": "euras",
        "kiek_kainuoja": "x",
        "kiek_kainuoja_compound": None,
        "euro_acc": "eurą",
    }
    for n in (1, 5, 15, 20, 25)
]


class TestAdaptiveLearning:
    @pytest.fixture()
    def al(self) -> AdaptiveLearning:
        return AdaptiveLearning()

    def test_init_tracking_idempotent(self, al: AdaptiveLearning) -> None:
        session: dict = {}
        al.init_tracking(session)
        perf1 = session["performance"]
        al.init_tracking(session)
        assert session["performance"] is perf1

    def test_update_increments(self, al: AdaptiveLearning) -> None:
        session: dict = {}
        al.init_tracking(session)
        info = {
            "exercise_type": "kokia",
            "number_pattern": "single_digit",
            "grammatical_case": "nominative",
        }
        al.update(session, info, True)
        et = session["performance"]["exercise_types"]["kokia"]
        assert et["correct"] == pytest.approx(1.0)

    def test_select_exercise_returns_dict(self, al: AdaptiveLearning) -> None:
        engine = ExerciseEngine(ROWS)
        session: dict = {}
        ex = al.select_exercise(session, engine)
        assert "exercise_type" in ex
        assert "row" in ex

    def test_get_weak_areas_empty_without_perf(self, al: AdaptiveLearning) -> None:
        assert al.get_weak_areas({}) == {}

    def test_thompson_convergence(self) -> None:
        """After biased history, Thompson sampling should target weak area."""
        al = AdaptiveLearning()
        engine = ExerciseEngine(ROWS)
        session: dict = {}
        al.init_tracking(session)

        # Simulate strong kokia, weak kiek
        perf = session["performance"]
        perf["exercise_types"]["kokia"] = {
            "correct": 30,
            "incorrect": 2,
        }
        perf["exercise_types"]["kiek"] = {
            "correct": 2,
            "incorrect": 30,
        }
        perf["total_exercises"] = 64

        counts = Counter(
            al.select_exercise(session, engine)["exercise_type"] for _ in range(500)
        )
        assert counts["kiek"] > counts["kokia"]


class TestInitTrackingPreSeeds:
    def test_fresh_session_has_all_arm_families_seeded(self) -> None:
        from adaptive import AdaptiveLearning

        session: dict = {}
        AdaptiveLearning().init_tracking(session)
        perf = session["performance"]

        assert set(perf["exercise_types"].keys()) == {"kokia", "kiek"}
        assert set(perf["number_patterns"].keys()) == {
            "single_digit",
            "teens",
            "decade",
            "compound",
        }
        assert set(perf["grammatical_cases"].keys()) == {
            "nominative",
            "accusative",
        }
        # No combined_arms in the new scheme.
        assert "combined_arms" not in perf

    def test_legacy_session_gets_missing_families_topped_up(self) -> None:
        from adaptive import AdaptiveLearning

        # Simulate a session loaded from the DB with the old lazy-arm layout.
        session = {
            "performance": {
                "exercise_types": {
                    "kokia": {"correct": 3.0, "incorrect": 1.0},
                    "kiek": {"correct": 2.0, "incorrect": 2.0},
                },
                "number_patterns": {},
                "grammatical_cases": {},
                "total_exercises": 7,
            }
        }
        AdaptiveLearning().init_tracking(session)
        perf = session["performance"]

        # Existing arm stats preserved.
        assert perf["exercise_types"]["kokia"]["correct"] == pytest.approx(3.0)
        assert perf["total_exercises"] == 7
        # Missing families filled in.
        assert set(perf["number_patterns"].keys()) == {
            "single_digit",
            "teens",
            "decade",
            "compound",
        }
        assert set(perf["grammatical_cases"].keys()) == {
            "nominative",
            "accusative",
        }

    def test_legacy_session_with_combined_arms_drops_it(self) -> None:
        from adaptive import AdaptiveLearning

        session = {
            "performance": {
                "exercise_types": {
                    "kokia": {"correct": 1.0, "incorrect": 1.0},
                    "kiek": {"correct": 1.0, "incorrect": 1.0},
                },
                "number_patterns": {},
                "grammatical_cases": {},
                "combined_arms": {
                    "kokia_teens_nominative": {"correct": 1.0, "incorrect": 0.0}
                },
                "total_exercises": 2,
            }
        }
        AdaptiveLearning().init_tracking(session)
        assert "combined_arms" not in session["performance"]


class TestAdaptiveNoSteadyStateGate:
    def test_post_warmup_always_takes_thompson_path(self, monkeypatch) -> None:
        """After warmup, random() is not consulted for a gate — _thompson_sample
        is always invoked."""
        from adaptive import AdaptiveLearning

        engine = AdaptiveLearning()
        # After warmup, always use Thompson Sampling (no random gate)
        session: dict = {}
        engine.init_tracking(session)
        session["performance"]["total_exercises"] = 999  # past warmup

        called = {"ts": 0, "rand": 0}

        def fake_ts(*_a, **_kw):
            called["ts"] += 1
            return {
                "exercise_type": "kokia",
                "price": "€1",
                "item": None,
                "row": {"number": 1},
                "grammatical_case": "nominative",
                "number_pattern": "single_digit",
            }

        def fake_rand(*_a, **_kw):
            called["rand"] += 1
            return {}

        monkeypatch.setattr(engine, "_thompson_sample", fake_ts)
        monkeypatch.setattr(engine, "_random_exercise", fake_rand)

        class _FakeEngine:
            rows = [{"number": 1}]

        for _ in range(50):
            engine.select_exercise(session, engine=_FakeEngine())
        assert called["ts"] == 50
        assert called["rand"] == 0
