"""Thompson Sampling adaptive learning engine."""

import random
from typing import Any

import numpy as np

from quiz import EXERCISE_TYPES, ITEMS, number_pattern


def _bump(
    category: dict[str, dict[str, int]],
    key: str,
    is_correct: bool,
) -> None:
    """Create arm if missing, then increment correct/incorrect."""
    if key not in category:
        category[key] = {"correct": 0, "incorrect": 1}
    side = "correct" if is_correct else "incorrect"
    category[key][side] += 1


def _sample_weakest(arms: dict[str, dict[str, int]]) -> str:
    """Thompson-sample and return the arm with the *lowest* draw."""
    samples = {}
    for arm, stats in arms.items():
        alpha = stats["correct"] + 1
        beta_val = stats["incorrect"] + 1
        samples[arm] = np.random.beta(alpha, beta_val)
    return min(samples, key=samples.get)


class AdaptiveLearning:
    """Thompson Sampling–based exercise selector."""

    def __init__(self, exploration_rate: float = 0.2) -> None:
        self.exploration_rate = exploration_rate
        self.adaptation_threshold = 10

    # ------------------------------------------------------------------
    # Session initialisation
    # ------------------------------------------------------------------

    def init_tracking(self, session: dict[str, Any]) -> None:
        """Idempotently set up performance tracking in session."""
        if "performance" in session:
            return
        session["performance"] = {
            "exercise_types": {
                t: {"correct": 0, "incorrect": 1}
                for t in EXERCISE_TYPES
            },
            "number_patterns": {},
            "grammatical_cases": {},
            "combined_arms": {},
            "total_exercises": 0,
        }

    # ------------------------------------------------------------------
    # Update after answer
    # ------------------------------------------------------------------

    def update(
        self,
        session: dict[str, Any],
        exercise_info: dict[str, Any],
        is_correct: bool,
    ) -> None:
        self.init_tracking(session)
        perf = session["performance"]
        perf["total_exercises"] += 1

        _bump(
            perf["exercise_types"],
            exercise_info["exercise_type"],
            is_correct,
        )

        np_ = exercise_info.get("number_pattern")
        if np_:
            _bump(perf["number_patterns"], np_, is_correct)

        gc = exercise_info.get("grammatical_case")
        if gc:
            _bump(perf["grammatical_cases"], gc, is_correct)

        if np_ and gc:
            combined = (
                f"{exercise_info['exercise_type']}_{np_}_{gc}"
            )
            _bump(perf["combined_arms"], combined, is_correct)

    # ------------------------------------------------------------------
    # Exercise selection
    # ------------------------------------------------------------------

    def select_exercise(
        self,
        session: dict[str, Any],
        engine: Any,
    ) -> dict[str, Any]:
        self.init_tracking(session)
        perf = session["performance"]

        if (
            random.random() < self.exploration_rate
            or perf["total_exercises"] < self.adaptation_threshold
        ):
            return self._random_exercise(engine)

        return self._thompson_sample(session, engine)

    def _random_exercise(self, engine: Any) -> dict[str, Any]:
        row = random.choice(engine.rows)
        ex_type = random.choice(EXERCISE_TYPES)
        item = (
            random.choice(ITEMS) if ex_type == "kiek" else None
        )
        gc = "accusative" if ex_type == "kiek" else "nominative"
        return {
            "exercise_type": ex_type,
            "price": f"€{row['number']}",
            "item": item,
            "row": row,
            "grammatical_case": gc,
            "number_pattern": number_pattern(row["number"]),
        }

    def _thompson_sample(
        self,
        session: dict[str, Any],
        engine: Any,
    ) -> dict[str, Any]:
        perf = session["performance"]

        # 1. Weakest exercise type
        ex_type = _sample_weakest(perf["exercise_types"])

        # 2. Weakest number pattern
        if perf["number_patterns"]:
            np_ = _sample_weakest(perf["number_patterns"])
        else:
            np_ = number_pattern(
                random.choice(engine.rows)["number"]
            )

        # 3. Find a row matching the pattern
        matching = [
            r
            for r in engine.rows
            if number_pattern(r["number"]) == np_
        ]
        row = (
            random.choice(matching)
            if matching
            else random.choice(engine.rows)
        )

        item = (
            random.choice(ITEMS) if ex_type == "kiek" else None
        )
        gc = "accusative" if ex_type == "kiek" else "nominative"
        return {
            "exercise_type": ex_type,
            "price": f"€{row['number']}",
            "item": item,
            "row": row,
            "grammatical_case": gc,
            "number_pattern": number_pattern(row["number"]),
        }

    # ------------------------------------------------------------------
    # Weak-area reporting
    # ------------------------------------------------------------------

    def get_weak_areas(
        self, session: dict[str, Any]
    ) -> dict[str, list[dict[str, Any]]]:
        if "performance" not in session:
            return {}

        perf = session["performance"]
        categories = {
            "Exercise Types": "exercise_types",
            "Number Patterns": "number_patterns",
            "Grammatical Cases": "grammatical_cases",
        }
        weak: dict[str, list[dict[str, Any]]] = {}

        for label, key in categories.items():
            cat = perf.get(key, {})
            if not cat:
                continue
            rates: list[tuple[str, float]] = []
            for arm, stats in cat.items():
                total = stats["correct"] + stats["incorrect"]
                if total > 1:
                    rates.append(
                        (arm, stats["correct"] / total)
                    )
            if rates:
                rates.sort(key=lambda x: x[1])
                weak[label] = [
                    {"name": arm, "success_rate": rate}
                    for arm, rate in rates[:3]
                ]

        return weak
