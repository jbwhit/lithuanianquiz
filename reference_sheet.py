"""Generate a reference sheet of ALL Lithuanian expressions used across all six modules.

For a native speaker to quickly scan and validate correctness.

Usage: uv run python reference_sheet.py
"""

import sqlite3
from pathlib import Path

from age_engine import PRONOUNS
from quiz import ExerciseEngine
from time_engine import ORDINALS_GEN, ORDINALS_NOM, _next_hour


def _load_rows() -> list[dict]:
    db = Path("lithuanian_data.db")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM numbers ORDER BY number")]
    conn.close()
    return rows


def _number_word(row: dict) -> str:
    parts = [row["kokia_kaina"]]
    if row.get("kokia_kaina_compound"):
        parts.append(row["kokia_kaina_compound"])
    return " ".join(parts)


def _number_word_acc(row: dict) -> str:
    parts = [row["kiek_kainuoja"]]
    if row.get("kiek_kainuoja_compound"):
        parts.append(row["kiek_kainuoja_compound"])
    return " ".join(parts)


def _degree_form(row: dict) -> str:
    if row["number"] == 1:
        return "laipsnis"
    if row["years"] == "metai":
        return "laipsniai"
    return "laipsnių"


def section(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def subsection(title: str) -> None:
    print(f"\n--- {title} ---\n")


def main() -> None:
    rows = _load_rows()
    rows_20 = [r for r in rows if r["number"] <= 20]

    print("=" * 70)
    print("  LITHUANIAN PRACTICE — COMPLETE REFERENCE SHEET")
    print("  For native speaker verification of all app expressions")
    print("=" * 70)

    # ── MODULE 1 & 2: Numbers (nominative form) ──────────────────────
    section("MODULE: Numbers 1-20 & 1-99  (Nominative number words)")
    print("  The app asks 'How do you say N?' and expects the nominative form.")
    print("  It also asks 'What number is <word>?' for recognition.\n")
    for r in rows:
        word = _number_word(r)
        print(f"  {r['number']:3d}  →  {word}")

    # ── MODULE 3: Age ─────────────────────────────────────────────────
    section("MODULE: Age  (Dative pronoun + number + metai/metų)")
    print("  Pattern: <Pronoun dat.> <number word nom.> <metai|metų>.")
    print("  The years form depends on the number (same rule as prices).\n")
    subsection("Pronouns used")
    for p in PRONOUNS:
        print(f"  {p['english']:12s} → {p['dative']}")

    subsection("Year form (metai vs metų)")
    print("  metai — numbers 1-9, compounds ending 1-9 (21, 32, …)")
    print("  metų  — numbers 10-20, decades (30, 40, …)\n")

    subsection("Full age expressions (one pronoun per number, rotating)")
    print("  Pattern: <Dative> <number word> <metai|metų>.\n")
    for r in rows:
        word = _number_word(r)
        years = r["years"]
        p = PRONOUNS[(r["number"] - 1) % len(PRONOUNS)]
        print(
            f"  {p['english']:12s} {r['number']:3d}  →  {p['dative']} {word} {years}."
        )

    # ── MODULE 4: Weather ─────────────────────────────────────────────
    section("MODULE: Weather  (number + laipsnis/laipsniai/laipsnių)")
    print("  Positive temperatures: 1-99°C")
    print("  Negative temperatures: -1 to -20°C (prefixed with 'minus')\n")

    subsection("Degree form rules")
    print("  1          → laipsnis   (nom. sg.)")
    print("  2-9, x1-x9 → laipsniai  (nom. pl.)")
    print("  10-20, x0  → laipsnių   (gen. pl.)\n")

    subsection("Positive temperatures (1-99°C)")
    for r in rows:
        word = _number_word(r)
        deg = _degree_form(r)
        print(f"  {r['number']:3d}°C  →  {word} {deg}")

    subsection("Negative temperatures (-1 to -20°C)")
    for r in rows_20:
        word = _number_word(r)
        deg = _degree_form(r)
        print(f"  -{r['number']:2d}°C  →  minus {word} {deg}")

    # ── MODULE 5: Prices ──────────────────────────────────────────────
    section("MODULE: Prices  (two question types)")
    print('  "Kokia kaina?" → nominative: <number nom.> <euro nom.>')
    print('  "Kiek kainuoja?" → accusative: <number acc.> <euro acc.>\n')

    engine = ExerciseEngine(rows)

    subsection("Kokia kaina? (Nominative)")
    for r in rows:
        answer = engine.correct_answer("kokia", r)
        print(f"  €{r['number']:3d}  →  {answer}")

    subsection("Kiek kainuoja? (Accusative)")
    for r in rows:
        answer = engine.correct_answer("kiek", r)
        print(f"  €{r['number']:3d}  →  {answer}")

    # ── MODULE 6: Time ────────────────────────────────────────────────
    section("MODULE: Time  (4 time types × 12 hours)")

    subsection("Whole hours (Kelinta valanda?)")
    for h in range(1, 13):
        print(f"  {h:2d}:00  →  {ORDINALS_NOM[h].capitalize()} valanda")

    subsection("Half past (pusė + genitive of NEXT hour)")
    for h in range(1, 13):
        nh = _next_hour(h)
        print(f"  {h:2d}:30  →  Pusė {ORDINALS_GEN[nh]}")

    subsection("Quarter past (ketvirtis + genitive of NEXT hour)")
    for h in range(1, 13):
        nh = _next_hour(h)
        print(f"  {h:2d}:15  →  Ketvirtis {ORDINALS_GEN[nh]}")

    subsection("Quarter to (be ketvirčio + nominative of NEXT hour)")
    for h in range(1, 13):
        nh = _next_hour(h)
        print(f"  {h:2d}:45  →  Be ketvirčio {ORDINALS_NOM[nh]}")

    print(f"\n{'=' * 70}")
    print("  END OF REFERENCE SHEET")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
