"""Exercise engine for Lithuanian age expressions — no FastHTML dependency."""

import copy
import random
from typing import Any

from quiz import normalize, number_pattern
from thompson import bump as _bump
from thompson import sample_weakest as _sample_weakest

PRONOUNS: list[dict[str, str]] = [
    {"dative": "Man", "english": "I am"},
    {"dative": "Tau", "english": "You are"},
    {"dative": "Jam", "english": "He is"},
    {"dative": "Jai", "english": "She is"},
]
PRONOUN_DATIVES: list[str] = [p["dative"] for p in PRONOUNS]
EXERCISE_TYPES: list[str] = ["produce", "recognize"]


def _pronoun_by_dative(dative: str) -> dict[str, str]:
    """Look up a pronoun dict by its dative form."""
    for p in PRONOUNS:
        if p["dative"] == dative:
            return p
    msg = f"Unknown pronoun dative: {dative}"
    raise ValueError(msg)


# Collective numerals used with plurale tantum nouns like "metai".
# Only the ones digit changes; decade prefixes stay cardinal.
_COLLECTIVE: dict[str, str] = {
    "vienas": "vieneri",
    "du": "dveji",
    "trys": "treji",
    "keturi": "ketveri",
    "penki": "penkeri",
    "šeši": "šešeri",
    "septyni": "septyneri",
    "aštuoni": "aštuoneri",
    "devyni": "devyneri",
}


def _age_number_word(row: dict[str, Any]) -> str:
    """Build the number word for an age expression.

    Numbers paired with 'metai' (1-9, compounds ending 1-9) require
    collective numerals (dveji, treji, ketveri …) instead of cardinals.
    Numbers paired with 'metų' (10-20, decades) use regular cardinals.
    """
    if row["years"] == "metų":
        # Cardinal form — same as prices
        parts = [row["kokia_kaina"]]
        if row.get("kokia_kaina_compound"):
            parts.append(row["kokia_kaina_compound"])
        return " ".join(parts)

    # metai → need collective numeral for the ones digit
    compound = row.get("kokia_kaina_compound")
    if compound:
        # Compound number (e.g. 22 = "dvidešimt" + "du" → "dvidešimt dveji")
        ones_collective = _COLLECTIVE.get(compound, compound)
        return f"{row['kokia_kaina']} {ones_collective}"
    # Simple number (e.g. 2 = "du" → "dveji")
    return _COLLECTIVE.get(row["kokia_kaina"], row["kokia_kaina"])


class AgeEngine:
    """Generates age exercises and checks answers with adaptive selection."""

    def __init__(
        self,
        rows: list[dict[str, Any]],
        adaptation_threshold: int = 10,
    ) -> None:
        self.rows = rows
        self.adaptation_threshold = adaptation_threshold

    def init_tracking(
        self,
        session: dict[str, Any],
        prefix: str = "age",
        seed_prefix: str | None = None,
    ) -> None:
        """Ensure the age perf skeleton exists and is compact.

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
                    "pronouns": {},
                    "total_exercises": source.get("total_exercises", 0),
                }
            else:
                session[perf_key] = {
                    "exercise_types": {},
                    "number_patterns": {},
                    "pronouns": {},
                    "total_exercises": 0,
                }
        perf = session[perf_key]
        perf.setdefault("exercise_types", {})
        perf.setdefault("number_patterns", {})
        perf.setdefault("pronouns", {})
        perf.setdefault("total_exercises", 0)
        # Reclaim cookie space from eagerly-pre-seeded legacy sessions.
        strip_cold_start(perf["exercise_types"])
        strip_cold_start(perf["number_patterns"])
        strip_cold_start(perf["pronouns"])

    def generate(self, session: dict[str, Any], prefix: str = "age") -> dict[str, Any]:
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

        # Weakest number pattern over the full 4-pattern taxonomy. Matching
        # rows may still be empty for a given pattern; fall back to uniform.
        weak_pattern = _sample_weakest(
            perf["number_patterns"],
            ["single_digit", "teens", "decade", "compound"],
        )
        matching = [r for r in self.rows if number_pattern(r["number"]) == weak_pattern]
        row = random.choice(matching) if matching else random.choice(self.rows)

        # Weakest pronoun over the full 4-pronoun taxonomy.
        weak_pronoun = _sample_weakest(perf["pronouns"], list(PRONOUN_DATIVES))
        pronoun = _pronoun_by_dative(weak_pronoun)

        return {
            "exercise_type": exercise_type,
            "row": row,
            "number_pattern": number_pattern(row["number"]),
            "pronoun": pronoun,
        }

    def correct_answer(
        self, exercise_type: str, row: dict[str, Any], pronoun: dict[str, str]
    ) -> str:
        """Build the correct answer for an age exercise."""
        if exercise_type == "produce":
            return f"{pronoun['dative']} {_age_number_word(row)} {row['years']}."
        # recognize
        return str(row["number"])

    def format_question(
        self,
        exercise_type: str,
        row: dict[str, Any],
        pronoun: dict[str, str],
        lang: str = "en",
    ) -> str:
        """Format the question text for display."""
        if exercise_type == "produce":
            if lang == "lt":
                return f"{pronoun['dative']} yra {row['number']} metų."
            return f"{pronoun['english']} {row['number']} years old."
        # recognize: show the Lithuanian phrase
        return f"{pronoun['dative']} {_age_number_word(row)} {row['years']}."

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

        pn = exercise_info.get("pronoun")
        if pn:
            _bump(perf["pronouns"], pn, is_correct)

    def get_weak_areas(
        self, session: dict[str, Any], prefix: str = "age"
    ) -> dict[str, list[dict[str, Any]]]:
        """Return weak areas for display in stats panel."""
        perf_key = f"{prefix}_performance"
        if perf_key not in session:
            return {}

        perf = session[perf_key]
        categories = {
            "Exercise Types": "exercise_types",
            "Number Patterns": "number_patterns",
            "Pronouns": "pronouns",
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
