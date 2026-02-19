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
        cat: dict = {}
        _bump(cat, "foo", True)
        assert cat["foo"] == {"correct": 1, "incorrect": 1}

    def test_increments_correct(self) -> None:
        cat = {"foo": {"correct": 5, "incorrect": 2}}
        _bump(cat, "foo", True)
        assert cat["foo"]["correct"] == 6

    def test_increments_incorrect(self) -> None:
        cat = {"foo": {"correct": 5, "incorrect": 2}}
        _bump(cat, "foo", False)
        assert cat["foo"]["incorrect"] == 3


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
        counts = Counter(
            _sample_weakest(arms) for _ in range(500)
        )
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
        return AdaptiveLearning(exploration_rate=0.2)

    def test_init_tracking_idempotent(
        self, al: AdaptiveLearning
    ) -> None:
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
        assert et["correct"] == 1

    def test_select_exercise_returns_dict(
        self, al: AdaptiveLearning
    ) -> None:
        engine = ExerciseEngine(ROWS)
        session: dict = {}
        ex = al.select_exercise(session, engine)
        assert "exercise_type" in ex
        assert "row" in ex

    def test_get_weak_areas_empty_without_perf(
        self, al: AdaptiveLearning
    ) -> None:
        assert al.get_weak_areas({}) == {}

    def test_thompson_convergence(self) -> None:
        """After biased history, Thompson sampling should target weak area."""
        al = AdaptiveLearning(exploration_rate=0.0)
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
            al.select_exercise(session, engine)["exercise_type"]
            for _ in range(500)
        )
        assert counts["kiek"] > counts["kokia"]
