"""Exercise engine for Lithuanian price quiz — no FastHTML dependency."""

import html
import random
from difflib import SequenceMatcher
from typing import Any

EXERCISE_TYPES: list[str] = ["kokia", "kiek"]
ITEMS: list[str] = [
    "knyga",
    "puodelis",
    "marškinėliai",
    "žurnalas",
    "kepurė",
]


def normalize(answer: str) -> str:
    """Normalize an answer for comparison."""
    s = answer.strip().lower()
    if s.endswith("."):
        s = s[:-1]
    return " ".join(s.split())


def number_pattern(n: int) -> str:
    """Categorize a number for adaptive tracking."""
    if n < 10:
        return "single_digit"
    if n < 20:
        return "teens"
    if n % 10 == 0:
        return "decade"
    return "compound"


def highlight_diff(
    user: str, correct: str, is_correct: bool
) -> tuple[str, str]:
    """Return (user_html, correct_html) with coloured diff spans."""
    if is_correct:
        return (
            f"<span class='text-success font-bold'>"
            f"{html.escape(user)}</span>",
            html.escape(correct),
        )

    user_low = user.lower()
    corr_low = correct.lower()
    sm = SequenceMatcher(None, user_low, corr_low)
    out_u: list[str] = []
    out_c: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        seg_u = html.escape(user[i1:i2])
        seg_c = html.escape(correct[j1:j2])
        if tag == "equal":
            out_u.append(seg_u)
            out_c.append(seg_c)
        elif tag == "replace":
            out_u.append(
                f"<span class='text-error font-bold underline decoration-error/50'>{seg_u}</span>"
            )
            out_c.append(
                f"<span class='text-success font-bold underline decoration-success/50'>{seg_c}</span>"
            )
        elif tag == "delete":
            out_u.append(
                f"<span class='text-error font-bold underline decoration-error/50'>{seg_u}</span>"
            )
        elif tag == "insert":
            out_c.append(
                f"<span class='text-success font-bold underline decoration-success/50'>{seg_c}</span>"
            )
    return "".join(out_u), "".join(out_c)


class ExerciseEngine:
    """Generates exercises and checks answers against the DB rows."""

    def __init__(
        self,
        rows: list[dict[str, Any]],
        adaptive: Any | None = None,
    ) -> None:
        self.rows = rows
        self.by_number: dict[int, dict[str, Any]] = {
            r["number"]: r for r in rows
        }
        self.adaptive = adaptive

    def get_row(self, number: int) -> dict[str, Any]:
        return self.by_number[number]

    def generate(self, session: dict[str, Any]) -> dict[str, Any]:
        """Return an exercise dict using adaptive selection if available."""
        if self.adaptive:
            return self.adaptive.select_exercise(session, self)
        row = random.choice(self.rows)
        ex_type = random.choice(EXERCISE_TYPES)
        item = random.choice(ITEMS) if ex_type == "kiek" else None
        return {
            "exercise_type": ex_type,
            "price": f"€{row['number']}",
            "item": item,
            "row": row,
            "number_pattern": number_pattern(row["number"]),
        }

    def correct_answer(
        self, ex_type: str, row: dict[str, Any]
    ) -> str:
        """Build the correct Lithuanian price phrase."""
        if ex_type == "kokia":
            parts = [row["kokia_kaina"]]
            if row.get("kokia_kaina_compound"):
                parts.append(row["kokia_kaina_compound"])
            parts.append(row["euro_nom"])
        else:
            parts = [row["kiek_kainuoja"]]
            if row.get("kiek_kainuoja_compound"):
                parts.append(row["kiek_kainuoja_compound"])
            parts.append(row["euro_acc"])
        return f"{' '.join(parts)}."

    @staticmethod
    def format_question(
        ex_type: str, price: str, item: str | None
    ) -> str:
        if ex_type == "kokia":
            return f"Kokia kaina? ({price})"
        return f"Kiek kainuoja {item}? ({price})"

    @staticmethod
    def check(user_answer: str, correct_answer: str) -> bool:
        return normalize(user_answer) == normalize(correct_answer)
