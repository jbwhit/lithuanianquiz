"""Generate a reference document of all Lithuanian time expressions for native speaker review.

Usage: uv run python time_reference.py
"""

from time_engine import ORDINALS_GEN, ORDINALS_NOM, _next_hour


def whole_hour(h: int) -> str:
    """e.g., 3:00 → 'Trečia valanda'"""
    return f"{ORDINALS_NOM[h].capitalize()} valanda"


def half_past(h: int) -> str:
    """e.g., 2:30 → 'Pusė trečios' (half of the next hour)"""
    return f"Pusė {ORDINALS_GEN[_next_hour(h)]}"


def quarter_past(h: int) -> str:
    """e.g., 1:15 → 'Ketvirtis antros' (quarter of the next hour)"""
    return f"Ketvirtis {ORDINALS_GEN[_next_hour(h)]}"


def quarter_to(h: int) -> str:
    """e.g., 2:45 → 'Be ketvirčio trečia' (without a quarter, next hour)"""
    return f"Be ketvirčio {ORDINALS_NOM[_next_hour(h)]}"


def main() -> None:
    print("=" * 60)
    print("LITHUANIAN TIME EXPRESSIONS — REFERENCE DOCUMENT")
    print("For native speaker verification")
    print("=" * 60)

    print("\n## Whole Hours (Kelinta valanda?)\n")
    for h in range(1, 13):
        print(f"  {h:2d}:00  →  {whole_hour(h)}")

    print("\n## Half Past (pusė + genitive of NEXT hour)\n")
    for h in range(1, 13):
        print(f"  {h:2d}:30  →  {half_past(h)}")
    # Also show 12:30 explicitly since it wraps
    print(f"\n  Note: 12:30 wraps → {half_past(12)} (half of the first)")

    print("\n## Quarter Past (ketvirtis + genitive of NEXT hour)\n")
    for h in range(1, 13):
        print(f"  {h:2d}:15  →  {quarter_past(h)}")

    print("\n## Quarter To (be ketvirčio + nominative of NEXT hour)\n")
    for h in range(1, 13):
        print(f"  {h:2d}:45  →  {quarter_to(h)}")

    print("\n" + "=" * 60)
    print("OPEN QUESTION: Is 'Pusė trečios' (ordinal genitive) correct")
    print("for 2:30, or should it be 'Pusė trijų' (cardinal genitive)?")
    print("Some sources show both forms.")
    print("=" * 60)


if __name__ == "__main__":
    main()
