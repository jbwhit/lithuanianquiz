# Time Module — Implementation Spec

Detailed spec for adding a time-telling practice module to Lithuanian Practice.
Intended as a self-contained brief for Sonnet to implement.

---

## Scope (v1)

Four exercise types, ordered by difficulty:

1. **Whole hours** — `3:00` → `Trečia valanda`
2. **Half past** — `2:30` → `Pusė trečios`
3. **Quarter past** — `1:15` → `Ketvirtis antros`
4. **Quarter to** — `2:45` → `Be ketvirčio trečia`

All use the **conversational 12-hour system** (ordinal feminine forms). No 24-hour
formal clock in v1. No arbitrary minutes (e.g., 3:07) in v1.

---

## Lithuanian Grammar Reference

### Question prompt

**Kiek valandų?** ("What time is it?") — used for all exercise types.

### Whole hours (ordinal feminine nominative)

The answer is a feminine ordinal + `valanda`:

| Hour | Answer |
|------|--------|
| 1:00 | Pirma valanda |
| 2:00 | Antra valanda |
| 3:00 | Trečia valanda |
| 4:00 | Ketvirta valanda |
| 5:00 | Penkta valanda |
| 6:00 | Šešta valanda |
| 7:00 | Septinta valanda |
| 8:00 | Aštunta valanda |
| 9:00 | Devinta valanda |
| 10:00 | Dešimta valanda |
| 11:00 | Vienuolikta valanda |
| 12:00 | Dvylikta valanda |

### Half past (pusė + genitive of NEXT hour's ordinal)

Lithuanian says "half of the next hour":

| Time | Answer | Literal |
|------|--------|---------|
| 12:30 | Pusė pirmos | Half of the first |
| 1:30 | Pusė antros | Half of the second |
| 2:30 | Pusė trečios | Half of the third |
| 3:30 | Pusė ketvirtos | Half of the fourth |
| 4:30 | Pusė penktos | Half of the fifth |
| 5:30 | Pusė šeštos | Half of the sixth |
| 6:30 | Pusė septintos | Half of the seventh |
| 7:30 | Pusė aštuntos | Half of the eighth |
| 8:30 | Pusė devintos | Half of the ninth |
| 9:30 | Pusė dešimtos | Half of the tenth |
| 10:30 | Pusė vienuoliktos | Half of the eleventh |
| 11:30 | Pusė dvyliktos | Half of the twelfth |

### Quarter past (ketvirtis + genitive of NEXT hour's ordinal)

| Time | Answer |
|------|--------|
| 12:15 | Ketvirtis pirmos |
| 1:15 | Ketvirtis antros |
| 2:15 | Ketvirtis trečios |
| etc. | Same genitive pattern as pusė |

### Quarter to (be ketvirčio + nominative of NEXT hour's ordinal)

| Time | Answer |
|------|--------|
| 12:45 | Be ketvirčio pirma |
| 1:45 | Be ketvirčio antra |
| 2:45 | Be ketvirčio trečia |
| etc. | Nominative ordinal of the coming hour |

### Ordinal forms reference (feminine)

| # | Nominative | Genitive |
|---|-----------|----------|
| 1 | pirma | pirmos |
| 2 | antra | antros |
| 3 | trečia | trečios |
| 4 | ketvirta | ketvirtos |
| 5 | penkta | penktos |
| 6 | šešta | šeštos |
| 7 | septinta | septintos |
| 8 | aštunta | aštuntos |
| 9 | devinta | devintos |
| 10 | dešimta | dešimtos |
| 11 | vienuolikta | vienuoliktos |
| 12 | dvylikta | dvyliktos |

---

## Implementation Plan

### 1. New file: `time_engine.py`

A self-contained engine (no FastHTML dependency), mirroring `quiz.py`'s pattern.

```python
class TimeEngine:
    def generate(self, session, adaptive=None) -> dict:
        """Return an exercise dict with time_type, hour, minute, display_time."""
        ...

    def correct_answer(self, time_type: str, hour: int, minute: int) -> str:
        """Build the correct Lithuanian time phrase."""
        ...

    @staticmethod
    def format_question(display_time: str) -> str:
        return f"Kiek valandų? ({display_time})"

    @staticmethod
    def check(user_answer: str, correct_answer: str) -> bool:
        """Reuse quiz.normalize() for comparison."""
        ...
```

Key internals:
- `ORDINALS_NOM` and `ORDINALS_GEN` dicts mapping 1–12 to Lithuanian forms
- `_next_hour(h)` helper: wraps 12 → 1
- Generate random hour (1–12) + type-appropriate minute (0, 15, 30, 45)
- Accept answers with or without trailing period

### 2. New file: `tests/test_time.py`

Test every hour for each exercise type. Use the reference tables above as expected values.

Key test cases:
- All 12 whole hours
- All 12 half-past times
- Boundary: 12:30 → "Pusė pirmos" (wraps to 1)
- Boundary: 12:15 → "Ketvirtis pirmos"
- Boundary: 12:45 → "Be ketvirčio pirma"
- Normalization: trailing period, extra whitespace, case insensitivity

### 3. Modify `main.py`

Add a `/time` route that renders the time practice page. Follow the exact same
pattern as the price quiz `/` route:
- Separate session keys namespaced with `time_` prefix (e.g., `time_history`,
  `time_correct_count`) to keep price and time progress independent
- Same HTMX partial swap pattern: `/time/answer` returns feedback + next question + OOB stats
- Same reset modal pattern at `/time/reset`

### 4. Modify `ui.py`

- Add `time_quiz_area()` and `time_examples_section()` functions
- Reuse `stats_panel()`, `feedback_correct()`, `feedback_incorrect()` as-is
  (they're already generic enough)
- Add a "Time" link to the navbar

### 5. Adaptive learning

The existing `AdaptiveLearning` class tracks by `exercise_type` + `number_pattern`
+ `grammatical_case`. For time exercises:
- `exercise_type`: `"whole_hour"`, `"half_past"`, `"quarter_past"`, `"quarter_to"`
- `number_pattern`: reuse or add `"hour_1"` through `"hour_12"`
- `grammatical_case`: `"nominative"` (whole hours, quarter to) or `"genitive"` (half past, quarter past)

Use the same session-level tracking but under `time_` prefixed keys.

### 6. Navigation

Add module switching to the navbar:
- "Prices" → `/`
- "Time" → `/time`
- Keep the current page highlighted

---

## What NOT to do

- Don't refactor `ExerciseEngine` — it's price-specific and that's fine
- Don't add 24-hour formal time (v2 scope)
- Don't add arbitrary minutes like 3:07 (v2 scope)
- Don't add audio
- Don't change the price quiz behaviour at all

---

## Acceptance criteria

1. All tests pass (`uv run pytest`)
2. Ruff clean (`uv run ruff check . && uv run ruff format --check .`)
3. `/time` page works with the same UX loop as prices
4. Stats are tracked independently from price quiz
5. Navbar allows switching between Prices and Time
6. Adaptive learning works for time exercises
7. Pre-commit hook auto-formats (already set up)

---

## Open question for native speaker review

The research found two patterns for "half past":
- **Ordinal genitive:** `Pusė trečios` (2:30) — standard grammar reference form
- **Cardinal genitive:** `Pusė trijų` (2:30) — seen in some conversational sources

This spec uses the ordinal genitive form. Run `uv run python time_reference.py` to
generate a full reference document for native speaker verification before implementing
answer checking.
