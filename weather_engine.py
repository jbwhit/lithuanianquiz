"""Exercise engine for Lithuanian weather temperature expressions — no FastHTML dependency."""

import copy
import random
from typing import Any

from quiz import normalize, number_pattern
from thompson import bump as _bump
from thompson import sample_weakest as _sample_weakest

EXERCISE_TYPES: list[str] = ["produce", "recognize"]
SIGN_TYPES: list[str] = ["positive", "negative"]


def _degree_form(row: dict[str, Any]) -> str:
    """Pick laipsnis/laipsniai/laipsnių based on same rule as years column.

    - number == 1 → laipsnis (nom. sg.)
    - years == "metai" (2-9, compounds ending 2-9) → laipsniai (nom. pl.)
    - years == "metų" (10-19, decades) → laipsnių (gen. pl.)
    """
    if row["number"] == 1:
        return "laipsnis"
    if row["years"] == "metai":
        return "laipsniai"
    return "laipsnių"


def _number_word(row: dict[str, Any]) -> str:
    """Build the full number word from a DB row (nominative/informal form)."""
    parts = [row["kokia_kaina"]]
    if row.get("kokia_kaina_compound"):
        parts.append(row["kokia_kaina_compound"])
    return " ".join(parts)


class WeatherEngine:
    """Generates weather temperature exercises with adaptive selection."""

    def __init__(
        self,
        rows: list[dict[str, Any]],
        exploration_rate: float = 0.2,
        adaptation_threshold: int = 10,
    ) -> None:
        self.rows = rows
        # Negative temperatures only for numbers 1-20
        self.negative_rows = [r for r in rows if r["number"] <= 20]
        self.exploration_rate = exploration_rate
        self.adaptation_threshold = adaptation_threshold

    def init_tracking(
        self,
        session: dict[str, Any],
        prefix: str = "weather",
        seed_prefix: str | None = None,
    ) -> None:
        """Idempotently set up weather performance tracking in session.

        If seed_prefix is given and that module has existing performance data,
        copy exercise_types and number_patterns priors from it.
        """
        perf_key = f"{prefix}_performance"
        if perf_key in session:
            return
        seed_key = f"{seed_prefix}_performance" if seed_prefix else None
        if seed_key and seed_key in session:
            source = session[seed_key]
            session[perf_key] = {
                "exercise_types": copy.deepcopy(source.get("exercise_types", {})),
                "number_patterns": copy.deepcopy(source.get("number_patterns", {})),
                "sign": {s: {"correct": 0, "incorrect": 1} for s in SIGN_TYPES},
                "total_exercises": source.get("total_exercises", 0),
            }
        else:
            session[perf_key] = {
                "exercise_types": {
                    t: {"correct": 0, "incorrect": 1} for t in EXERCISE_TYPES
                },
                "number_patterns": {},
                "sign": {s: {"correct": 0, "incorrect": 1} for s in SIGN_TYPES},
                "total_exercises": 0,
            }

    def generate(
        self, session: dict[str, Any], prefix: str = "weather"
    ) -> dict[str, Any]:
        """Return an exercise dict using adaptive selection."""
        self.init_tracking(session, prefix)
        perf = session[f"{prefix}_performance"]

        exploring = (
            random.random() < self.exploration_rate
            or perf["total_exercises"] < self.adaptation_threshold
        )

        # Pick exercise type
        if exploring:
            exercise_type = random.choice(EXERCISE_TYPES)
        else:
            exercise_type = _sample_weakest(perf["exercise_types"])

        # Pick row (number) adaptively
        if perf["number_patterns"] and not exploring:
            weak_pattern = _sample_weakest(perf["number_patterns"])
            matching = [
                r for r in self.rows if number_pattern(r["number"]) == weak_pattern
            ]
            row = random.choice(matching) if matching else random.choice(self.rows)
        else:
            row = random.choice(self.rows)

        # Pick sign adaptively
        if not exploring:
            weak_sign = _sample_weakest(perf["sign"])
            negative = weak_sign == "negative"
        else:
            negative = random.choice([True, False])

        # If negative, constrain to numbers 1-20
        if negative and row["number"] > 20:
            row = random.choice(self.negative_rows)

        return {
            "exercise_type": exercise_type,
            "row": row,
            "number_pattern": number_pattern(row["number"]),
            "negative": negative,
        }

    def correct_answer(
        self, exercise_type: str, row: dict[str, Any], negative: bool
    ) -> str:
        """Build the correct answer for a weather exercise."""
        if exercise_type == "produce":
            prefix = "minus " if negative else ""
            return f"{prefix}{_number_word(row)} {_degree_form(row)}"
        # recognize
        sign = "-" if negative else ""
        return f"{sign}{row['number']}"

    def format_question(
        self,
        exercise_type: str,
        row: dict[str, Any],
        negative: bool,
        lang: str = "en",
    ) -> str:
        """Format the question text for display."""
        if exercise_type == "produce":
            sign = "-" if negative else ""
            if lang == "lt":
                return f"Kaip pasakyti {sign}{row['number']}\u00b0C?"
            return f"How do you say {sign}{row['number']}\u00b0C?"
        # recognize: show the Lithuanian phrase
        prefix = "minus " if negative else ""
        return f"{prefix}{_number_word(row)} {_degree_form(row)}"

    def check(self, user_answer: str, correct_answer: str, exercise_type: str) -> bool:
        """Check whether the user's answer is correct."""
        if exercise_type == "recognize":
            return user_answer.strip() == correct_answer
        return normalize(user_answer) == normalize(correct_answer)

    def update(
        self,
        session: dict[str, Any],
        prefix: str,
        exercise_info: dict[str, Any],
        is_correct: bool,
    ) -> None:
        """Update performance tracking after an answer."""
        self.init_tracking(session, prefix)
        perf = session[f"{prefix}_performance"]
        perf["total_exercises"] += 1

        _bump(perf["exercise_types"], exercise_info["exercise_type"], is_correct)

        np = exercise_info.get("number_pattern")
        if np:
            _bump(perf["number_patterns"], np, is_correct)

        sign = exercise_info.get("sign")
        if sign:
            _bump(perf["sign"], sign, is_correct)

    def get_weak_areas(
        self, session: dict[str, Any], prefix: str = "weather"
    ) -> dict[str, list[dict[str, Any]]]:
        """Return weak areas for display in stats panel."""
        perf_key = f"{prefix}_performance"
        if perf_key not in session:
            return {}

        perf = session[perf_key]
        categories = {
            "Exercise Types": "exercise_types",
            "Number Patterns": "number_patterns",
            "Sign": "sign",
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
