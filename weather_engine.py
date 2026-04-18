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

    - number == 0 → laipsnių (gen. pl., same as 10-19/decades)
    - number == 1 → laipsnis (nom. sg.)
    - years == "metai" (2-9, compounds ending 2-9) → laipsniai (nom. pl.)
    - years == "metų" (10-19, decades) → laipsnių (gen. pl.)
    """
    if row["number"] == 0:
        return "laipsnių"
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
        adaptation_threshold: int = 10,
    ) -> None:
        self.rows = rows
        # Negative temperatures only for numbers 1-20 (never zero, never 21+)
        self.negative_rows = [r for r in rows if 1 <= r["number"] <= 20]
        self.adaptation_threshold = adaptation_threshold

    def init_tracking(
        self,
        session: dict[str, Any],
        prefix: str = "weather",
        seed_prefix: str | None = None,
    ) -> None:
        """Ensure the weather perf skeleton exists and is compact.

        Arms are created lazily via `bump`; the sampler handles missing
        keys via its cold-start default. The seed_prefix branch still
        copies priors from a sibling module when the target is absent.
        """
        from thompson import strip_cold_start

        perf_key = f"{prefix}_performance"
        if perf_key not in session:
            seed_key = f"{seed_prefix}_performance" if seed_prefix else None
            if seed_key and seed_key in session:
                source = session[seed_key]
                session[perf_key] = {
                    "exercise_types": copy.deepcopy(source.get("exercise_types", {})),
                    "number_patterns": copy.deepcopy(source.get("number_patterns", {})),
                    "sign": {},
                    "total_exercises": source.get("total_exercises", 0),
                }
            else:
                session[perf_key] = {
                    "exercise_types": {},
                    "number_patterns": {},
                    "sign": {},
                    "total_exercises": 0,
                }
        perf = session[perf_key]
        perf.setdefault("exercise_types", {})
        perf.setdefault("number_patterns", {})
        perf.setdefault("sign", {})
        perf.setdefault("total_exercises", 0)
        # Reclaim cookie space from eagerly-pre-seeded legacy sessions.
        strip_cold_start(perf["exercise_types"])
        strip_cold_start(perf["number_patterns"])
        strip_cold_start(perf["sign"])

    def generate(
        self, session: dict[str, Any], prefix: str = "weather"
    ) -> dict[str, Any]:
        """Return an exercise dict using adaptive selection."""
        self.init_tracking(session, prefix)
        perf = session[f"{prefix}_performance"]

        warmup = perf["total_exercises"] < self.adaptation_threshold

        # Pick exercise type
        if warmup:
            exercise_type = random.choice(EXERCISE_TYPES)
        else:
            exercise_type = _sample_weakest(
                perf["exercise_types"], list(EXERCISE_TYPES)
            )

        # Weakest number pattern over the full 4-pattern taxonomy.
        weak_pattern = _sample_weakest(
            perf["number_patterns"],
            ["single_digit", "teens", "decade", "compound"],
        )
        matching = [r for r in self.rows if number_pattern(r["number"]) == weak_pattern]
        row = random.choice(matching) if matching else random.choice(self.rows)

        # Weakest sign over the full taxonomy.
        weak_sign = _sample_weakest(perf["sign"], list(SIGN_TYPES))
        negative = weak_sign == "negative"

        # If negative, constrain to numbers 1-20 (never emit 'minus nulis',
        # never emit 'minus 21+').
        if negative and (row["number"] == 0 or row["number"] > 20):
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

    def check(
        self,
        user_answer: str,
        correct_answer: str,
        exercise_type: str,
        *,
        diacritic_tolerant: bool = False,
    ) -> bool:
        """Check whether the user's answer is correct."""
        if exercise_type == "recognize":
            return user_answer.strip() == correct_answer
        return normalize(user_answer, fold_diacritics=diacritic_tolerant) == normalize(
            correct_answer, fold_diacritics=diacritic_tolerant
        )

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
