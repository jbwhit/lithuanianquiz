"""Exercise engine for Lithuanian number words — no FastHTML dependency."""

import copy
import random
from typing import Any

from quiz import normalize, number_pattern
from thompson import bump as _bump
from thompson import sample_weakest as _sample_weakest

EXERCISE_TYPES: list[str] = ["produce", "recognize"]


class NumberEngine:
    """Generates number exercises and checks answers with adaptive selection."""

    def __init__(
        self,
        rows: list[dict[str, Any]],
        max_number: int,
        adaptation_threshold: int = 10,
    ) -> None:
        self.rows = rows
        self.max_number = max_number
        self.adaptation_threshold = adaptation_threshold
        # Patterns reachable from this engine's row set. The 1-20 engine,
        # for example, cannot serve "compound" (21+), so we must not seed
        # that arm or TS will converge on an untrainable pattern.
        self._reachable_patterns = sorted({number_pattern(r["number"]) for r in rows})

    def init_tracking(
        self,
        session: dict[str, Any],
        prefix: str,
        seed_prefix: str | None = None,
    ) -> None:
        """Ensure the perf skeleton exists and is compact.

        If seed_prefix is given and the target perf dict doesn't exist yet,
        copy priors from that module first. Arms are created lazily via
        `bump`; the sampler handles missing keys via its cold-start default.
        """
        from thompson import strip_cold_start

        perf_key = f"{prefix}_performance"
        if perf_key not in session:
            seed_key = f"{seed_prefix}_performance" if seed_prefix else None
            if seed_key and seed_key in session:
                session[perf_key] = copy.deepcopy(session[seed_key])
            else:
                session[perf_key] = {
                    "exercise_types": {},
                    "number_patterns": {},
                    "total_exercises": 0,
                }
        perf = session[perf_key]
        perf.setdefault("exercise_types", {})
        perf.setdefault("number_patterns", {})
        perf.setdefault("total_exercises", 0)

        # Drop any persisted number patterns that aren't reachable here
        # (e.g. "compound" in the 1-20 engine, or carried over from n99).
        perf["number_patterns"] = {
            k: v
            for k, v in perf["number_patterns"].items()
            if k in self._reachable_patterns
        }
        # Strip any cold-start arms left over from an eagerly-seeded
        # version of this code.
        strip_cold_start(perf["exercise_types"])
        strip_cold_start(perf["number_patterns"])

    def generate(self, session: dict[str, Any], prefix: str) -> dict[str, Any]:
        """Return an exercise dict using adaptive selection."""
        self.init_tracking(session, prefix)
        perf = session[f"{prefix}_performance"]

        if perf["total_exercises"] < self.adaptation_threshold:
            exercise_type = random.choice(EXERCISE_TYPES)
        else:
            exercise_type = _sample_weakest(
                perf["exercise_types"], list(EXERCISE_TYPES)
            )

        # Weakest reachable pattern; matching is non-empty by construction
        # (only reachable patterns are in _reachable_patterns).
        weak_pattern = _sample_weakest(
            perf["number_patterns"], self._reachable_patterns
        )
        matching = [r for r in self.rows if number_pattern(r["number"]) == weak_pattern]
        row = random.choice(matching) if matching else random.choice(self.rows)

        return {
            "exercise_type": exercise_type,
            "row": row,
            "number_pattern": number_pattern(row["number"]),
        }

    def correct_answer(self, exercise_type: str, row: dict[str, Any]) -> str:
        """Build the correct answer for a number exercise."""
        if exercise_type == "produce":
            parts = [row["kokia_kaina"]]
            if row.get("kokia_kaina_compound"):
                parts.append(row["kokia_kaina_compound"])
            return " ".join(parts)
        # recognize
        return str(row["number"])

    def format_question(
        self, exercise_type: str, row: dict[str, Any], lang: str = "en"
    ) -> str:
        """Format the question text for display."""
        if exercise_type == "produce":
            if lang == "lt":
                return f"Kaip pasakyti {row['number']}?"
            return f"How do you say {row['number']}?"
        # recognize: show the nominative form
        parts = [row["kokia_kaina"]]
        if row.get("kokia_kaina_compound"):
            parts.append(row["kokia_kaina_compound"])
        prompt = "Koks skaičius yra" if lang == "lt" else "What number is"
        return f"{prompt} {' '.join(parts)}?"

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

    def get_weak_areas(
        self, session: dict[str, Any], prefix: str
    ) -> dict[str, list[dict[str, Any]]]:
        """Return weak areas for display in stats panel."""
        perf_key = f"{prefix}_performance"
        if perf_key not in session:
            return {}

        perf = session[perf_key]
        categories = {
            "Exercise Types": "exercise_types",
            "Number Patterns": "number_patterns",
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
