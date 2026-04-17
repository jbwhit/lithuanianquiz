"""Thompson Sampling adaptive learning engine."""

import random
from typing import Any

from quiz import EXERCISE_TYPES, ITEMS, number_pattern
from thompson import bump as _bump
from thompson import sample_weakest as _sample_weakest

_NUMBER_PATTERNS = ["single_digit", "teens", "decade", "compound"]
_PRICE_CASES = ["nominative", "accusative"]


class AdaptiveLearning:
    """Thompson Sampling–based exercise selector."""

    def __init__(self) -> None:
        self.adaptation_threshold = 10

    # ------------------------------------------------------------------
    # Session initialisation
    # ------------------------------------------------------------------

    def init_tracking(self, session: dict[str, Any]) -> None:
        """Idempotently ensure every arm family is pre-seeded.

        Runs on every request. Fresh sessions get a complete set of cold-start
        arms; sessions loaded from the DB in the old lazy-arm layout get topped
        up with any arms that used to be created lazily.
        """
        from thompson import _ensure_seeded

        perf = session.setdefault(
            "performance",
            {
                "exercise_types": {},
                "number_patterns": {},
                "grammatical_cases": {},
                "total_exercises": 0,
            },
        )
        perf.setdefault("exercise_types", {})
        perf.setdefault("number_patterns", {})
        perf.setdefault("grammatical_cases", {})
        perf.setdefault("total_exercises", 0)
        # Drop the dead combined_arms table if loaded from a legacy session.
        perf.pop("combined_arms", None)

        _ensure_seeded(perf["exercise_types"], list(EXERCISE_TYPES))
        _ensure_seeded(perf["number_patterns"], _NUMBER_PATTERNS)
        _ensure_seeded(perf["grammatical_cases"], _PRICE_CASES)

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

        if perf["total_exercises"] < self.adaptation_threshold:
            return self._random_exercise(engine)

        return self._thompson_sample(session, engine)

    def _random_exercise(self, engine: Any) -> dict[str, Any]:
        row = random.choice(engine.rows)
        ex_type = random.choice(EXERCISE_TYPES)
        item = random.choice(ITEMS) if ex_type == "kiek" else None
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

        # 2. Weakest number pattern (always pre-seeded, never empty)
        np_ = _sample_weakest(perf["number_patterns"])

        # 3. Find a row matching the pattern
        matching = [r for r in engine.rows if number_pattern(r["number"]) == np_]
        row = random.choice(matching) if matching else random.choice(engine.rows)

        item = random.choice(ITEMS) if ex_type == "kiek" else None
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
                    rates.append((arm, stats["correct"] / total))
            if rates:
                rates.sort(key=lambda x: x[1])
                weak[label] = [
                    {"name": arm, "success_rate": rate} for arm, rate in rates[:3]
                ]

        return weak
