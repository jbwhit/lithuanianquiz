"""Exercise engine for Lithuanian time expressions — no FastHTML dependency."""

import random
from typing import Any

from quiz import normalize

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
    """Generates time exercises and checks answers."""

    def __init__(self, adaptive: Any | None = None) -> None:
        self.adaptive = adaptive

    def generate(self, session: dict[str, Any]) -> dict[str, Any]:
        """Return an exercise dict with time_type, hour, minute, display_time."""
        time_type = random.choice(TIME_TYPES)
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
    def check(user_answer: str, correct_answer: str) -> bool:
        return normalize(user_answer) == normalize(correct_answer)
