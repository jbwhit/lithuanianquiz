"""Exercise engine for Lithuanian time expressions — no FastHTML dependency."""

import random
from typing import Any

from quiz import normalize
from thompson import bump as _bump
from thompson import sample_weakest as _sample_weakest

TIME_TYPES: list[str] = ["whole_hour", "half_past", "quarter_past", "quarter_to"]

# Feminine ordinal forms for hours 1-12
ORDINALS_NOM: dict[int, str] = {
    1: "pirma",
    2: "antra",
    3: "trečia",
    4: "ketvirta",
    5: "penkta",
    6: "šešta",
    7: "septinta",
    8: "aštunta",
    9: "devinta",
    10: "dešimta",
    11: "vienuolikta",
    12: "dvylikta",
}

ORDINALS_GEN: dict[int, str] = {
    1: "pirmos",
    2: "antros",
    3: "trečios",
    4: "ketvirtos",
    5: "penktos",
    6: "šeštos",
    7: "septintos",
    8: "aštuntos",
    9: "devintos",
    10: "dešimtos",
    11: "vienuoliktos",
    12: "dvyliktos",
}

# Map time types to the minute value they produce
_TIME_TYPE_MINUTES: dict[str, int] = {
    "whole_hour": 0,
    "quarter_past": 15,
    "half_past": 30,
    "quarter_to": 45,
}


def _next_hour(h: int) -> int:
    """Wrap 12 → 1."""
    return h % 12 + 1


def time_pattern(hour: int) -> str:
    """Categorize an hour for adaptive tracking."""
    return f"hour_{hour}"


class TimeEngine:
    """Generates time exercises and checks answers with adaptive selection."""

    def __init__(
        self, exploration_rate: float = 0.2, adaptation_threshold: int = 10
    ) -> None:
        self.exploration_rate = exploration_rate
        self.adaptation_threshold = adaptation_threshold

    def init_tracking(self, session: dict[str, Any]) -> None:
        """Idempotently set up time performance tracking in session."""
        if "time_performance" in session:
            return
        session["time_performance"] = {
            "exercise_types": {t: {"correct": 0, "incorrect": 1} for t in TIME_TYPES},
            "hour_patterns": {},
            "grammatical_cases": {},
            "total_exercises": 0,
        }

    def update(
        self,
        session: dict[str, Any],
        exercise_info: dict[str, Any],
        is_correct: bool,
    ) -> None:
        """Update time performance tracking after an answer."""
        self.init_tracking(session)
        perf = session["time_performance"]
        perf["total_exercises"] += 1

        _bump(perf["exercise_types"], exercise_info["exercise_type"], is_correct)

        hp = exercise_info.get("number_pattern")
        if hp:
            _bump(perf["hour_patterns"], hp, is_correct)

        gc = exercise_info.get("grammatical_case")
        if gc:
            _bump(perf["grammatical_cases"], gc, is_correct)

    def get_weak_areas(
        self, session: dict[str, Any]
    ) -> dict[str, list[dict[str, Any]]]:
        """Return weak areas for display in stats panel."""
        if "time_performance" not in session:
            return {}

        perf = session["time_performance"]
        categories = {
            "Exercise Types": "exercise_types",
            "Hour Patterns": "hour_patterns",
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

    def generate(self, session: dict[str, Any]) -> dict[str, Any]:
        """Return an exercise dict using adaptive selection."""
        self.init_tracking(session)
        perf = session["time_performance"]

        if (
            random.random() < self.exploration_rate
            or perf["total_exercises"] < self.adaptation_threshold
        ):
            time_type = random.choice(TIME_TYPES)
        else:
            time_type = _sample_weakest(perf["exercise_types"])

        # Adaptively pick hour if we have data
        if perf["hour_patterns"] and random.random() > self.exploration_rate:
            weak_hour_key = _sample_weakest(perf["hour_patterns"])
            # Extract hour number from "hour_N"
            hour = int(weak_hour_key.split("_")[1])
        else:
            hour = random.randint(1, 12)

        minute = _TIME_TYPE_MINUTES[time_type]
        return {
            "exercise_type": time_type,
            "hour": hour,
            "minute": minute,
            "display_time": f"{hour}:{minute:02d}",
            "number_pattern": time_pattern(hour),
            "grammatical_case": self._case_for_type(time_type),
        }

    @staticmethod
    def _case_for_type(time_type: str) -> str:
        """Determine grammatical case for a time exercise type."""
        if time_type in ("half_past", "quarter_past"):
            return "genitive"
        return "nominative"

    def correct_answer(self, time_type: str, hour: int, minute: int) -> str:
        """Build the correct Lithuanian time phrase."""
        if time_type == "whole_hour":
            return f"{ORDINALS_NOM[hour].capitalize()} valanda."
        elif time_type == "half_past":
            return f"Pusė {ORDINALS_GEN[_next_hour(hour)]}."
        elif time_type == "quarter_past":
            return f"Ketvirtis {ORDINALS_GEN[_next_hour(hour)]}."
        elif time_type == "quarter_to":
            return f"Be ketvirčio {ORDINALS_NOM[_next_hour(hour)]}."
        msg = f"Unknown time type: {time_type}"
        raise ValueError(msg)

    @staticmethod
    def format_question(display_time: str) -> str:
        return f"Kiek valandų? ({display_time})"

    @staticmethod
    def check(
        user_answer: str, correct_answer: str, *, diacritic_tolerant: bool = False
    ) -> bool:
        return normalize(user_answer, fold_diacritics=diacritic_tolerant) == normalize(
            correct_answer, fold_diacritics=diacritic_tolerant
        )
