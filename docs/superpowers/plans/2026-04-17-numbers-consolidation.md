# Numbers Module Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `/numbers-20` and `/numbers-99` split with a single `/numbers` module covering 0-99, expand weather to include 0 ("nulis laipsnių"), and reset legacy per-user numbers progress on first login.

**Architecture:** One `NumberEngine` instance instead of two. `ALL_ROWS` (with a new row for `number=0`) feeds the consolidated numbers + weather; prices uses a filtered `ALL_ROWS[>=1]`. Session prefix `n20_*` / `n99_*` → `numbers_*` everywhere. `auth.load_progress` explicitly drops legacy fields; `main.py` gets a small `_strip_legacy_number_keys` helper so anonymous cookie sessions also shed the old keys. Old URLs (`/numbers-20`, `/numbers-99`) 301 to `/numbers`.

**Tech Stack:** Python 3.13 (Railway runs 3.12), FastHTML + MonsterUI, sqlite3 via `fastlite`, pytest + ruff, uv toolchain.

**Background reading for engineers:**
- `docs/superpowers/specs/2026-04-17-numbers-consolidation-design.md` — the spec this plan implements.
- `CLAUDE.md` — project overview, commands, deployment.
- Prior adaptive-scheme refactor (`docs/superpowers/plans/2026-04-17-adaptive-scheme-cleanup.md`) for context on the TS plumbing touched here.

**Working directory:** All commands below assume `/Users/jonathan/projects/lithuanianquiz/.worktrees/numbers-consolidation`. The worktree is on branch `numbers-consolidation` tracking `origin/main`.

---

## File structure

Every change lives in existing files. One new helper function (`_strip_legacy_number_keys`) is added inside `main.py`. No new modules.

**Modify:**

- `lithuanian_data.db` — add one row (number=0).
- `number_engine.py` — drop `max_number` constructor parameter.
- `main.py` — delete `number_engine_20`; rename `number_engine_99` → `number_engine` with `ALL_ROWS`; add filtered row-sets for weather (≥0) and prices (≥1); consolidate `_make_number_routes` calls; add `/numbers-20` and `/numbers-99` → `/numbers` redirect handler; rename `n20_*` / `n99_*` session keys → `numbers_*`; add `_strip_legacy_number_keys` helper + call at top of each `_ensure_*_session`; update `_MIX_MODULES`, `_MIX_Q_KEY_BY_MODULE`, and mix transient-key tuple; update `_refresh_cached_questions` mix map; update `age_engine.init_tracking` / `weather_engine.init_tracking` `seed_prefix="n99"` → `"numbers"`.
- `weather_engine.py` — guard: when `negative=True` and sampled `row["number"] == 0`, fall back to the existing `negative_rows` pool (never emit "minus nulis").
- `auth.py` — `load_progress`: stop reading `n20_*` / `n99_*`, start reading `numbers_*`; normalize legacy `mix_modules` to reset. `save_progress`: write `numbers_*` instead of `n20_*` / `n99_*`.
- `ui.py` — `MODULE_NAMES` set update; nav dropdown two items → one; landing-page two cards → one (keep "Start here" badge); `stats_page_content` two sections → one; about page list two entries → one; `number_examples_section` drops `max_number` parameter and the `<=20` branch.
- `tests/test_numbers.py` — fixture drops `max_number=99`; `TestNumberInitTrackingCompact` class renamed and trimmed per spec Section 7.
- `tests/test_weather.py` — add deterministic zero-row correct-answer test + negative-zero exclusion test; update any `seed_prefix="n99"` to `"numbers"`.
- `tests/test_age.py` — `seed_prefix="n99"` → `"numbers"`.
- `tests/test_regressions.py` — update `test_mix_session_initializes_only_one_module_question`, update `test_session_cookie_stays_under_budget_after_module_tour` paths, add four new tests (legacy-field discard, mix_modules legacy reset, redirect smoke, anonymous-session cleanup).
- `FUTURE_MODULES.md` — "Done" list: collapse the two Numbers entries into one.
- `CLAUDE.md` — project-structure line: collapse the two numbers routes into one.
- `LITHUANIAN_INTERFACE_REVIEW_REFERENCE.md` — append a short section listing the new LT forms for native-speaker review.

**Not touched:** `thompson.py`, `time_engine.py`, `age_engine.py` body (only a `seed_prefix` default comment update is needed, see Task 7), `adaptive.py`, `quiz.py`, `i18n.py`.

---

## Task 1: Add `number=0` row to the DB

**Files:**
- Modify: `lithuanian_data.db`

- [ ] **Step 1: Verify row 0 is absent**

Run:
```bash
uv run python -c "
import sqlite3
c = sqlite3.connect('lithuanian_data.db')
row = c.execute('SELECT * FROM numbers WHERE number=0').fetchone()
print('zero row exists' if row else 'zero row absent')
"
```
Expected: `zero row absent`.

- [ ] **Step 2: Check table schema**

Run:
```bash
uv run python -c "
import sqlite3
c = sqlite3.connect('lithuanian_data.db')
print(c.execute(\"SELECT sql FROM sqlite_master WHERE type='table' AND name='numbers'\").fetchone()[0])
"
```
Expected output (for reference):
```
CREATE TABLE [numbers] (
   [number] INTEGER PRIMARY KEY,
   [neoficialiai] TEXT,
   [compound] TEXT,
   [years] TEXT,
   [kokia_kaina] TEXT,
   [kokia_kaina_compound] TEXT,
   [euro_nom] TEXT,
   [cent_nom] TEXT,
   [kiek_kainuoja] TEXT,
   [kiek_kainuoja_compound] TEXT,
   [euro_acc] TEXT,
   [cent_acc] TEXT
)
```

- [ ] **Step 3: Insert the row**

Run:
```bash
uv run python -c "
import sqlite3
c = sqlite3.connect('lithuanian_data.db')
c.execute('''
    INSERT INTO numbers (
        number, neoficialiai, compound, years,
        kokia_kaina, kokia_kaina_compound, euro_nom, cent_nom,
        kiek_kainuoja, kiek_kainuoja_compound, euro_acc, cent_acc
    ) VALUES (
        0, NULL, NULL, NULL,
        'nulis', NULL, 'eurų', 'centų',
        'nulį', NULL, 'eurų', 'centų'
    )
''')
c.commit()
print('inserted')
"
```
Expected: `inserted`.

- [ ] **Step 4: Verify the row**

Run:
```bash
uv run python -c "
import sqlite3
c = sqlite3.connect('lithuanian_data.db')
row = c.execute('SELECT number, kokia_kaina, euro_nom FROM numbers WHERE number=0').fetchone()
print(row)
total = c.execute('SELECT COUNT(*) FROM numbers').fetchone()[0]
print('total rows:', total)
"
```
Expected:
```
(0, 'nulis', 'eurų')
total rows: 100
```

- [ ] **Step 5: Commit**

```bash
git add lithuanian_data.db
git commit -m "data: add row for number=0 (nulis) to support 0-99 numbers module

Accusative 'nulį' is a spot-check candidate for native-speaker review
(LITHUANIAN_INTERFACE_REVIEW_REFERENCE.md will list the new forms in
a later task). Prices module will be filtered to n>=1 so kiek_kainuoja
for this row is never user-facing in its own right; the field is
populated for schema symmetry only."
```

---

## Task 2: Drop `max_number` from `NumberEngine`

**Files:**
- Modify: `number_engine.py`
- Modify: `tests/test_numbers.py`

- [ ] **Step 1: Write failing test for the new signature**

Open `tests/test_numbers.py` and update the `engine` fixture near the top of the file. Find:

```python
@pytest.fixture()
def engine(sample_rows: list[dict]) -> NumberEngine:
    return NumberEngine(sample_rows, max_number=99)
```

Replace with:

```python
@pytest.fixture()
def engine(sample_rows: list[dict]) -> NumberEngine:
    return NumberEngine(sample_rows)
```

- [ ] **Step 2: Run to see the failure**

Run: `uv run --extra dev pytest tests/test_numbers.py -q 2>&1 | tail -5`
Expected: failures like `TypeError: NumberEngine.__init__() missing 1 required positional argument: 'max_number'`.

- [ ] **Step 3: Update `NumberEngine.__init__`**

Open `number_engine.py`, find the class and replace the current constructor with:

```python
def __init__(
    self,
    rows: list[dict[str, Any]],
    adaptation_threshold: int = 10,
) -> None:
    self.rows = rows
    self.adaptation_threshold = adaptation_threshold
    # Patterns reachable from this engine's row set. Computed from rows so
    # callers can't request a pattern (e.g. "compound") that has no rows.
    self._reachable_patterns = sorted({number_pattern(r["number"]) for r in rows})
```

Delete `self.max_number = max_number` and the `max_number` parameter. Leave the body of `generate`/`init_tracking`/etc. unchanged — nothing else read `max_number`.

- [ ] **Step 4: Run the test**

Run: `uv run --extra dev pytest tests/test_numbers.py -q 2>&1 | tail -5`
Expected: the `NumberEngine` construction passes, but other tests that still reference `max_number` may break. Specifically, check for any remaining occurrences:

```bash
grep -n "max_number" number_engine.py tests/test_numbers.py main.py ui.py
```
Expected: zero hits in any of those files. If hits remain, update the usages: `NumberEngine(rows, max_number=20)` → `NumberEngine(rows)`. No other code reads `.max_number`.

- [ ] **Step 5: Run full suite**

Run: `uv run --extra dev pytest 2>&1 | tail -10`
Expected: failures in `main.py` (from the two `_make_number_routes` calls that pass `number_engine.max_number` into `number_examples_section`) and `ui.py` (the `number_examples_section` signature). These are fixed in Tasks 3 and 7 respectively. Confirm the failures are *only* in those files; if anything else is red, fix before proceeding.

- [ ] **Step 6: Commit**

```bash
git add number_engine.py tests/test_numbers.py
git commit -m "refactor(number_engine): drop unused max_number parameter

Post-consolidation there's a single NumberEngine instance with rows 0-99,
and the only consumer of max_number (ui.number_examples_section) is
being simplified in a following task. Ctor is now
NumberEngine(rows, adaptation_threshold=10)."
```

---

## Task 3: Consolidate engines, row filters, and routes in `main.py`

This is the biggest single-file edit. Split into focused substeps.

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Replace engine construction (top of file)**

Find the current block in `main.py` (around lines 45-60):

```python
ALL_ROWS: list[dict[str, Any]] = list(_db.t["numbers"].rows)

adaptive = AdaptiveLearning(exploration_rate=0.2)
engine = ExerciseEngine(ALL_ROWS, adaptive)
time_engine = TimeEngine()

rows_20 = [r for r in ALL_ROWS if r["number"] <= 20]
number_engine_20 = NumberEngine(rows_20, max_number=20)
number_engine_99 = NumberEngine(ALL_ROWS, max_number=99)

age_rows = [r for r in ALL_ROWS if r["number"] >= 2]
age_engine = AgeEngine(age_rows)

weather_rows = [r for r in ALL_ROWS if r["number"] >= 1]
weather_engine = WeatherEngine(weather_rows)
```

(The `exploration_rate=0.2` was removed in the earlier adaptive-scheme cleanup; if your tree still has it, leave that change alone.) Replace the engine setup with:

```python
ALL_ROWS: list[dict[str, Any]] = list(_db.t["numbers"].rows)

adaptive = AdaptiveLearning()
price_rows = [r for r in ALL_ROWS if r["number"] >= 1]
engine = ExerciseEngine(price_rows, adaptive)
time_engine = TimeEngine()

number_engine = NumberEngine(ALL_ROWS)

age_rows = [r for r in ALL_ROWS if r["number"] >= 2]
age_engine = AgeEngine(age_rows)

weather_rows = [r for r in ALL_ROWS if r["number"] >= 0]
weather_engine = WeatherEngine(weather_rows)
```

- [ ] **Step 2: Verify `ExerciseEngine` accepts a filtered row list**

Run: `grep -n "class ExerciseEngine" quiz.py`, then check the `__init__` signature. It takes `rows` as its first positional argument; passing `price_rows` is fine. If any caller reads `engine.rows`, `engine.rows` is now `price_rows` (99 entries, no zero). This is the intended behavior.

- [ ] **Step 3: Rename session prefixes throughout `main.py`**

Run this to find every occurrence:
```bash
grep -n "\bn20_\|\bn99_\|\"n20\"\|\"n99\"" main.py
```
Expected: dozens of hits across session helpers, mix-module map, etc.

Apply this transformation in `main.py`:
- `n20_` → `numbers_` (string literal) wherever it's a session-key prefix
- `n99_` → `numbers_` similarly
- `"n20"` → `"numbers"` as a dict key (in `_MIX_MODULES`, `_MIX_Q_KEY_BY_MODULE`)
- `"n99"` → `"numbers"` as a dict key

**Concrete surgery for each hit:**

In `_refresh_cached_questions` (the `_MIX_Q_KEY_BY_MODULE` dict around line 296):

Find:
```python
_MIX_Q_KEY_BY_MODULE = {
    "prices": "current_question",
    "time": "time_current_question",
    "n20": "n20_current_question",
    "n99": "n99_current_question",
    "age": "age_current_question",
    "weather": "weather_current_question",
}
```
Replace with:
```python
_MIX_Q_KEY_BY_MODULE = {
    "prices": "current_question",
    "time": "time_current_question",
    "numbers": "numbers_current_question",
    "age": "age_current_question",
    "weather": "weather_current_question",
}
```

In the number-loop inside `_refresh_cached_questions` (around line 325), find:
```python
for prefix, eng in (("n20", number_engine_20), ("n99", number_engine_99)):
```
Replace with:
```python
for prefix, eng in (("numbers", number_engine),):
```

In the stats page call (around line 755-765), find:
```python
n20_stats = _compute_number_stats(session, "n20", number_engine_20)
n99_stats = _compute_number_stats(session, "n99", number_engine_99)
```
Replace with:
```python
numbers_stats = _compute_number_stats(session, "numbers", number_engine)
```
And in the `stats_page_content(...)` call just below, replace:
```python
n20_stats=n20_stats,
n99_stats=n99_stats,
```
with:
```python
numbers_stats=numbers_stats,
```

- [ ] **Step 4: Update age/weather `seed_prefix` references**

Find:
```python
age_engine.init_tracking(session, "age", seed_prefix="n99")
```
(around line 964). Replace with:
```python
age_engine.init_tracking(session, "age", seed_prefix="numbers")
```

Find:
```python
weather_engine.init_tracking(session, "weather", seed_prefix="n99")
```
(around line 1001). Replace with:
```python
weather_engine.init_tracking(session, "weather", seed_prefix="numbers")
```

- [ ] **Step 5: Replace the two `_make_number_routes` calls**

Find (around line 1599-1615):
```python
_make_number_routes(
    number_engine_20,
    "n20",
    "/numbers-20",
    "Lithuanian Numbers 1-20",
    "Learn the basic Lithuanian number words.",
    "numbers-20",
)
_make_number_routes(
    number_engine_99,
    "n99",
    "/numbers-99",
    "Lithuanian Numbers 1-99",
    "All numbers including decades and compounds.",
    "numbers-99",
    seed_prefix="n20",
)
```

Replace with:
```python
_make_number_routes(
    number_engine,
    "numbers",
    "/numbers",
    "Lithuanian Numbers",
    "Lithuanian number words from 0 to 99.",
    "numbers",
)
```

- [ ] **Step 6: Simplify the title/subtitle override inside `_make_number_routes`**

Find the block inside `get_numbers` (around line 1419-1434) that conditionally rewrites the title based on `module_name`:

```python
title_text = title
subtitle_text = subtitle
if module_name == "numbers-20":
    title_text = _t(session, "Lithuanian Numbers 1-20", "Skaiciai 1-20")
    subtitle_text = _t(
        session,
        "Learn the basic Lithuanian number words.",
        "Mokykites kalbeti apie skaicius.",
    )
elif module_name == "numbers-99":
    title_text = _t(session, "Lithuanian Numbers 1-99", "Skaiciai 1-99")
    subtitle_text = _t(
        session,
        "All numbers including decades and compounds.",
        "Visi skaiciai, iskaitant desimtis ir sudetinius.",
    )
```

Replace with:
```python
title_text = _t(session, "Lithuanian Numbers", "Skaičiai")
subtitle_text = _t(
    session,
    "Lithuanian number words from 0 to 99.",
    "Skaičių žodžiai nuo 0 iki 99.",
)
```

The `title` and `subtitle` parameters of `_make_number_routes` are now unused. Drop them from the signature:

Find:
```python
def _make_number_routes(
    engine_inst: NumberEngine,
    prefix: str,
    route_base: str,
    title: str,
    subtitle: str,
    module_name: str,
    seed_prefix: str | None = None,
) -> None:
```
Replace with:
```python
def _make_number_routes(
    engine_inst: NumberEngine,
    prefix: str,
    route_base: str,
    module_name: str,
    seed_prefix: str | None = None,
) -> None:
```

And update the call from step 5 to drop the two positional args:
```python
_make_number_routes(
    number_engine,
    "numbers",
    "/numbers",
    "numbers",
)
```

- [ ] **Step 7: Replace `number_examples_section` call inside routes**

Inside `get_numbers` (around line 1486), find:
```python
number_examples_section(engine_inst.max_number, lang=lang),
```
Replace with:
```python
number_examples_section(lang=lang),
```

(Task 7 will drop the parameter from the `ui.py` side.)

- [ ] **Step 8: Add redirects for the legacy URLs**

Right after the `_make_number_routes(...)` call from step 5, add:

```python
@rt("/numbers-20")
@rt("/numbers-99")
def get_legacy_numbers() -> RedirectResponse:
    return RedirectResponse("/numbers", status_code=301)
```

Confirm `RedirectResponse` is already imported in `main.py` (it should be; it's used by `/set-language` and `/set-diacritic-mode`).

- [ ] **Step 9: Update `_MIX_MODULES` and mix transient-key tuples**

Find (around line 1622):
```python
_MIX_MODULES = {
    "n20": {
        "ensure": lambda s: _ensure_number_session(s, number_engine_20, "n20"),
        "new_q": lambda s: _new_number_question(s, number_engine_20, "n20"),
    },
    "n99": {
        "ensure": lambda s: _ensure_number_session(
            s, number_engine_99, "n99", seed_prefix="n20"
        ),
        "new_q": lambda s: _new_number_question(s, number_engine_99, "n99"),
    },
    ...
```
Replace the `n20` and `n99` blocks with a single `numbers` block:
```python
_MIX_MODULES = {
    "numbers": {
        "ensure": lambda s: _ensure_number_session(s, number_engine, "numbers"),
        "new_q": lambda s: _new_number_question(s, number_engine, "numbers"),
    },
    ...
```
(Preserve the other entries — age, weather, prices, time — unchanged.)

Find the transient-keys tuple (around line 1658):
```python
"n20": (
    "n20_exercise_type",
    "n20_row_id",
    "n20_number_pattern",
    "n20_current_question",
),
"n99": (
    "n99_exercise_type",
    "n99_row_id",
    "n99_number_pattern",
    "n99_current_question",
),
```
Replace with:
```python
"numbers": (
    "numbers_exercise_type",
    "numbers_row_id",
    "numbers_number_pattern",
    "numbers_current_question",
),
```

- [ ] **Step 10: Sanity-check that no `n20` / `n99` / `number_engine_20` / `number_engine_99` remains**

Run:
```bash
grep -n "n20\|n99\|number_engine_20\|number_engine_99\|numbers-20\|numbers-99" main.py
```
Expected output: **empty** (no matches). If anything matches other than test-data comments, track it down and fix it.

- [ ] **Step 11: Import-check**

Run: `uv run python -c "import main"` — expected: no errors (the app module should load cleanly).

If errors, the most likely cause is a missed session-key rename; re-run the grep from Step 10.

- [ ] **Step 12: Commit**

```bash
git add main.py
git commit -m "refactor(main): consolidate numbers modules into single /numbers

- Single NumberEngine instance over ALL_ROWS (0-99).
- New row filters: prices n>=1 (skip zero-price), weather n>=0 (allow
  'nulis laipsnių').
- Session prefix renames n20_*/n99_* -> numbers_* throughout helpers,
  mix module map, refresh map, reset key tuples.
- Age/weather seed_prefix rewired to 'numbers'.
- _make_number_routes simplified: dropped title/subtitle params (now
  hardcoded inside the GET handler with the consolidated copy).
- Legacy URLs /numbers-20 and /numbers-99 301 -> /numbers."
```

---

## Task 4: `_strip_legacy_number_keys` helper + call sites

Anonymous users never hit `auth.load_progress`, so their cookie keeps old `n20_*` / `n99_*` keys forever unless we strip them on each request. Add one helper, call it from every `_ensure_*_session`.

**Files:**
- Modify: `main.py`
- Modify: `tests/test_regressions.py`

- [ ] **Step 1: Write the failing test**

Open `tests/test_regressions.py` and append this test at the bottom (before the final blank line):

```python
def test_ensure_session_strips_legacy_number_keys() -> None:
    """Anonymous users never hit auth.load_progress, so session-helper calls
    must strip legacy n20_/n99_ keys to avoid permanent cookie bloat."""
    session: dict = {
        "n20_correct_count": 5,
        "n20_performance": {"exercise_types": {"produce": {"correct": 3.0, "incorrect": 1.0}}},
        "n99_current_question": "How do you say 42?",
        "mix_modules": {
            "n20": {"correct": 3, "incorrect": 2},
            "age": {"correct": 1, "incorrect": 1},
        },
    }
    main._ensure_session(session)

    assert not any(k.startswith("n20_") for k in session)
    assert not any(k.startswith("n99_") for k in session)
    # mix_modules with any legacy key triggers a full reset.
    assert "mix_modules" not in session
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --extra dev pytest tests/test_regressions.py::test_ensure_session_strips_legacy_number_keys -v`
Expected: FAIL. Most likely assertion: `n20_correct_count` still present in session.

- [ ] **Step 3: Add the helper in `main.py`**

Near the top of the session-helpers section (right after `_is_diacritic_tolerant`, before `_check_kwargs`), add:

```python
_LEGACY_NUMBER_PREFIXES = ("n20_", "n99_")


def _strip_legacy_number_keys(session: dict[str, Any]) -> None:
    """Remove pre-consolidation n20_/n99_ session keys.

    Anonymous users (no OAuth) never flow through auth.load_progress, so
    their cookie would keep these keys forever otherwise. First call per
    request cleans the session; subsequent calls in the same request are
    no-ops.
    """
    for key in list(session):
        if key.startswith(_LEGACY_NUMBER_PREFIXES):
            del session[key]
    mix_modules = session.get("mix_modules")
    if isinstance(mix_modules, dict) and (
        "n20" in mix_modules or "n99" in mix_modules
    ):
        session.pop("mix_modules", None)
```

- [ ] **Step 4: Invoke the helper from every `_ensure_*_session`**

Find each of these functions in `main.py` and add `_strip_legacy_number_keys(session)` as the **first** body statement:

- `_ensure_session` (around line 310)
- `_ensure_time_session` (around line 408)
- `_ensure_age_session` (around line 959)
- `_ensure_weather_session` (around line 996)
- `_ensure_number_session` (around line 435)
- `_ensure_mix_session` (grep `def _ensure_mix_session` to find it)

For example, `_ensure_session` becomes:

```python
def _ensure_session(session: dict[str, Any]) -> None:
    _strip_legacy_number_keys(session)
    session.setdefault("correct_count", 0)
    # ... rest unchanged
```

Apply the same one-line addition to all six functions.

- [ ] **Step 5: Re-run the new test**

Run: `uv run --extra dev pytest tests/test_regressions.py::test_ensure_session_strips_legacy_number_keys -v`
Expected: PASS.

- [ ] **Step 6: Run full suite**

Run: `uv run --extra dev pytest 2>&1 | tail -10`
Expected: same failure set as before (ui.py / auth.py are still broken because Tasks 6 and 7 haven't run yet). The new test passes cleanly.

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_regressions.py
git commit -m "feat(main): strip legacy n20_/n99_ session keys in ensure helpers

Anonymous users (no OAuth) never hit auth.load_progress, so without
this any n20_*/n99_* cookies from the pre-consolidation era would sit
in the session indefinitely. _strip_legacy_number_keys runs as the
first statement of every _ensure_*_session, cleaning the session once
per request and becoming a no-op thereafter. mix_modules with any
legacy key triggers a full reset to match the auth.load_progress
normalization planned in the next task."
```

---

## Task 5: `auth.py` — migrate load/save to new prefix

**Files:**
- Modify: `auth.py`
- Modify: `tests/test_regressions.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_regressions.py`:

```python
def test_load_progress_discards_legacy_n20_n99_fields(monkeypatch) -> None:
    """load_progress must not write n20_*/n99_* fields into session;
    legacy DB rows carry them but we treat them as cold-start data."""
    db = _SQLiteDB()
    monkeypatch.setattr(auth, "_db", db)

    data = json.dumps(
        {
            "n20_correct_count": 5,
            "n20_incorrect_count": 3,
            "n20_history": [{"question": "Q", "correct": True}],
            "n20_performance": {"exercise_types": {"produce": {"correct": 5, "incorrect": 3}}},
            "n99_correct_count": 10,
            "n99_performance": {"exercise_types": {}},
            "numbers_correct_count": 2,  # maybe also present from a post-migration save
        }
    )
    db.execute(
        """INSERT INTO user_progress (google_id, data, updated_at)
           VALUES (?, ?, ?)""",
        ["legacy-user", data, "2026-04-17T00:00:00+00:00"],
    )

    session: dict = {}
    auth.load_progress("legacy-user", session)

    assert not any(k.startswith("n20_") for k in session)
    assert not any(k.startswith("n99_") for k in session)
    # The new-prefix fields should be loaded.
    assert session["numbers_correct_count"] == 2


def test_load_progress_resets_mix_modules_with_legacy_keys(monkeypatch) -> None:
    """A mix_modules dict containing n20 or n99 keys is treated as legacy
    and reset; _is_valid_mix_modules is not asked to validate it."""
    db = _SQLiteDB()
    monkeypatch.setattr(auth, "_db", db)

    data = json.dumps(
        {
            "mix_modules": {
                "n20": {"correct": 3, "incorrect": 2},
                "age": {"correct": 1, "incorrect": 1},
            },
        }
    )
    db.execute(
        """INSERT INTO user_progress (google_id, data, updated_at)
           VALUES (?, ?, ?)""",
        ["legacy-mix", data, "2026-04-17T00:00:00+00:00"],
    )

    session: dict = {}
    auth.load_progress("legacy-mix", session)

    assert "mix_modules" not in session
```

- [ ] **Step 2: Run to verify failures**

Run: `uv run --extra dev pytest tests/test_regressions.py::test_load_progress_discards_legacy_n20_n99_fields tests/test_regressions.py::test_load_progress_resets_mix_modules_with_legacy_keys -v`
Expected: both FAIL.

- [ ] **Step 3: Update `load_progress`**

In `auth.py`, find the block (around lines 180-188):

```python
# Numbers 1-20 progress
session["n20_correct_count"] = data.get("n20_correct_count", 0)
session["n20_incorrect_count"] = data.get("n20_incorrect_count", 0)
session["n20_history"] = _capped_history(data.get("n20_history"))
session["n20_performance"] = _get_perf_dict(data, "n20_performance")
# Numbers 1-99 progress
session["n99_correct_count"] = data.get("n99_correct_count", 0)
session["n99_incorrect_count"] = data.get("n99_incorrect_count", 0)
session["n99_history"] = _capped_history(data.get("n99_history"))
session["n99_performance"] = _get_perf_dict(data, "n99_performance")
```

Replace with:

```python
# Numbers progress (consolidated 0-99)
session["numbers_correct_count"] = data.get("numbers_correct_count", 0)
session["numbers_incorrect_count"] = data.get("numbers_incorrect_count", 0)
session["numbers_history"] = _capped_history(data.get("numbers_history"))
session["numbers_performance"] = _get_perf_dict(data, "numbers_performance")
```

In the same function, find the `mix_modules` handling (around line 203):

```python
mix_modules = data.get("mix_modules")
if _is_valid_mix_modules(mix_modules):
    session["mix_modules"] = mix_modules
else:
    session.pop("mix_modules", None)
```

Replace with:

```python
mix_modules = data.get("mix_modules")
if isinstance(mix_modules, dict) and (
    "n20" in mix_modules or "n99" in mix_modules
):
    mix_modules = None  # legacy layout — reset
if _is_valid_mix_modules(mix_modules):
    session["mix_modules"] = mix_modules
else:
    session.pop("mix_modules", None)
```

- [ ] **Step 4: Update `save_progress`**

Find the block (around lines 227-235):

```python
"n20_correct_count": session.get("n20_correct_count", 0),
"n20_incorrect_count": session.get("n20_incorrect_count", 0),
"n20_history": session.get("n20_history", [])[-_SESSION_HISTORY_LIMIT:],
"n20_performance": session.get("n20_performance", {}),
"n99_correct_count": session.get("n99_correct_count", 0),
"n99_incorrect_count": session.get("n99_incorrect_count", 0),
"n99_history": session.get("n99_history", [])[-_SESSION_HISTORY_LIMIT:],
"n99_performance": session.get("n99_performance", {}),
```

Replace with:

```python
"numbers_correct_count": session.get("numbers_correct_count", 0),
"numbers_incorrect_count": session.get("numbers_incorrect_count", 0),
"numbers_history": session.get("numbers_history", [])[-_SESSION_HISTORY_LIMIT:],
"numbers_performance": session.get("numbers_performance", {}),
```

- [ ] **Step 5: Sanity-grep for leftover n20/n99 in auth.py**

Run: `grep -n "n20\|n99" auth.py`
Expected: only the `_is_valid_mix_modules` normalization that references them as strings inside the `in mix_modules` check. Anything else is a missed edit.

- [ ] **Step 6: Run the new tests + existing auth tests**

Run: `uv run --extra dev pytest tests/test_regressions.py -k "load_progress or save_progress" -v 2>&1 | tail -20`
Expected: new tests pass. Existing `test_save_and_load_progress_persists_mix_fields` passes (it uses generic mix_modules keys).

- [ ] **Step 7: Commit**

```bash
git add auth.py tests/test_regressions.py
git commit -m "feat(auth): migrate progress load/save to consolidated numbers_* prefix

- load_progress no longer reads n20_*/n99_* from the DB payload; it
  reads numbers_* instead. Legacy fields in persisted JSON become dead
  data until the user's next save overwrites them.
- save_progress writes numbers_* only; the legacy fields stop being
  written on the next save per user.
- mix_modules with any legacy key ('n20' or 'n99') is treated as a
  legacy layout and reset, matching the anonymous-session cleanup in
  _strip_legacy_number_keys."
```

---

## Task 6: Guard weather engine against negative-zero (R3 mitigation)

**Files:**
- Modify: `weather_engine.py`
- Modify: `tests/test_weather.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_weather.py` (use existing imports at the top — `WeatherEngine`, `pytest`, etc.):

```python
class TestWeatherZeroRow:
    def test_correct_answer_for_zero_row_positive(self) -> None:
        """Zero-row produce answer uses 'nulis' + genitive plural 'laipsnių'."""
        from weather_engine import WeatherEngine

        zero_row = {
            "number": 0,
            "kokia_kaina": "nulis",
            "kokia_kaina_compound": None,
        }
        engine = WeatherEngine(rows=[zero_row])
        answer = engine.correct_answer("produce", zero_row, negative=False)
        assert answer == "nulis laipsnių"

    def test_generate_never_emits_negative_zero(self, monkeypatch) -> None:
        """Even if the sign sampler would pick 'negative' and the row
        sampler would pick row 0, generate() must fall back to the
        negative_rows pool (same guard as n>20)."""
        from weather_engine import WeatherEngine

        zero_row = {
            "number": 0,
            "kokia_kaina": "nulis",
            "kokia_kaina_compound": None,
        }
        normal_row = {
            "number": 5,
            "kokia_kaina": "penki",
            "kokia_kaina_compound": None,
        }
        engine = WeatherEngine(rows=[zero_row, normal_row])

        # Force sampler decisions: negative=True, initial row=zero_row.
        monkeypatch.setattr(
            "weather_engine._sample_weakest",
            lambda tracked, full_keys=None: (
                "negative" if full_keys and "negative" in full_keys
                else "produce" if full_keys and "produce" in full_keys
                else "single_digit"
            ),
        )
        import random as _r
        monkeypatch.setattr(_r, "choice", lambda seq: seq[0])

        session: dict = {}
        for _ in range(10):
            ex = engine.generate(session)
            if ex["negative"]:
                assert ex["row"]["number"] != 0, (
                    "weather must never emit 'minus nulis' — negative zero"
                )
```

- [ ] **Step 2: Run to verify failures**

Run: `uv run --extra dev pytest tests/test_weather.py::TestWeatherZeroRow -v 2>&1 | tail -15`
Expected: both FAIL. First one because of wrong `correct_answer` output (the zero row's `kokia_kaina` won't be in the test fixture yet — but since we built the row ourselves in the test, this should work; more likely the genitive-plural form picker returns "laipsnis" or "laipsniai" for n=0). Second FAIL because there's no guard yet.

- [ ] **Step 3: Inspect `_degree_form` in `weather_engine.py`**

Run: `grep -n "_degree_form\|_number_word" weather_engine.py`
Then read that function. It likely dispatches on `row["number"]` to return one of `"laipsnis"` / `"laipsniai"` / `"laipsnių"`. Confirm it treats `n=0` as `"laipsnių"` (genitive plural, like `n=10`). If it doesn't already, update it:

```python
def _degree_form(row: dict[str, Any]) -> str:
    n = row["number"]
    if n == 1 or (n > 20 and n % 10 == 1):
        return "laipsnis"
    if n == 0 or n >= 10 and n < 20 or n % 10 == 0:
        return "laipsnių"
    return "laipsniai"
```

(Exact logic depends on what's there already — if n=0 already falls through to "laipsnių" because of `n >= 10 and n < 20`, no change needed. If not, add the `n == 0` check.)

- [ ] **Step 4: Add the negative-zero guard in `generate`**

Find in `weather_engine.py` (around line 121-123):

```python
# If negative, constrain to numbers 1-20
if negative and row["number"] > 20:
    row = random.choice(self.negative_rows)
```

Replace with:

```python
# If negative, constrain to numbers 1-20 (never emit minus zero, never
# emit minus 21+).
if negative and (row["number"] == 0 or row["number"] > 20):
    row = random.choice(self.negative_rows)
```

Also check that `self.negative_rows` excludes number 0. Find the constructor (around line 30):

```python
self.negative_rows = [r for r in rows if 1 <= r["number"] <= 20]
```

If the filter is currently `r["number"] <= 20` without a `>= 1` guard, tighten it. If the filter is already `1 <= r["number"] <= 20`, no change.

- [ ] **Step 5: Re-run the tests**

Run: `uv run --extra dev pytest tests/test_weather.py::TestWeatherZeroRow -v 2>&1 | tail -10`
Expected: both PASS.

- [ ] **Step 6: Commit**

```bash
git add weather_engine.py tests/test_weather.py
git commit -m "fix(weather_engine): guard against emitting 'minus nulis'

With row 0 now in the weather engine's row set (supporting 'nulis
laipsnių' for zero degrees), the existing negative-constrainment guard
(row.number > 20 -> pick from negative_rows) also needs to cover
row.number == 0. Add the condition and pin the negative_rows filter to
1 <= n <= 20 explicitly."
```

---

## Task 7: UI updates

**Files:**
- Modify: `ui.py`
- Modify: `tests/test_ui.py` (only if existing tests break)

- [ ] **Step 1: Update `MODULE_NAMES`**

Find (top of `ui.py`, around line 17-25):

```python
MODULE_NAMES = {
    "numbers-20",
    "numbers-99",
    "age",
    "weather",
    "prices",
    "time",
    "practice-all",
}
```
Replace with:
```python
MODULE_NAMES = {
    "numbers",
    "age",
    "weather",
    "prices",
    "time",
    "practice-all",
}
```

- [ ] **Step 2: Collapse the nav dropdown**

Find (around line 67-68):
```python
Li(A(_txt(lang, "Numbers 1-20", "Skaiciai 1-20"), href="/numbers-20")),
Li(A(_txt(lang, "Numbers 1-99", "Skaiciai 1-99"), href="/numbers-99")),
```
Replace with one line:
```python
Li(A(_txt(lang, "Numbers", "Skaičiai"), href="/numbers")),
```

- [ ] **Step 3: Collapse the landing-page module cards**

Find the two Numbers cards in `landing_page_content` (around line 270-295). The exact structure varies — look for the pair of `_module_card(...)` calls with `"/numbers-20"` and `"/numbers-99"` hrefs. Replace both with a single card:

```python
_module_card(
    "🔢",
    _txt(lang, "Numbers", "Skaičiai"),
    _txt(
        lang,
        "Lithuanian number words from 0 to 99.",
        "Skaičių žodžiai nuo 0 iki 99.",
    ),
    "/numbers",
    "border-t-primary",
    badge=_txt(lang, "Start here", "Pradekite cia"),
),
```

The emoji, border color, and badge should match whatever the existing 1-20 card uses (it currently has the "Start here" badge). If the existing cards use different emojis/borders, copy from the 1-20 card.

- [ ] **Step 4: Collapse the stats page sections**

Find in `stats_page_content` (around line 1595-1625) the two sections for `n20_performance` and `n99_performance`. Each is a call like:

```python
_module_stats_section(
    _txt(lang, "Numbers 1-20", "Skaiciai 1-20"),
    stats.n20_stats,  # or the parameter name used
    n20_stats is None,  # or some skip check
    lang,
),
_module_stats_section(
    _txt(lang, "Numbers 1-99", "Skaiciai 1-99"),
    stats.n99_stats,
    n99_stats is None,
    lang,
),
```

Replace both with a single section:

```python
_module_stats_section(
    _txt(lang, "Numbers", "Skaičiai"),
    numbers_stats,
    numbers_stats is None,
    lang,
),
```

Also update the `stats_page_content` function signature. Find it (around line 1570-1590) and change the parameter names:
- Drop `n20_stats`, `n99_stats` parameters.
- Add `numbers_stats` parameter.

The caller in `main.py` was updated in Task 3 Step 3 to pass `numbers_stats=numbers_stats`.

- [ ] **Step 5: Collapse the about-page module list**

Find in `about_page_content` (around line 1755-1770) the list of module entries. Two consecutive items for the numbers modules become one:

Find something like:
```python
Strong(_txt(lang, "Numbers 1-20", "Skaiciai 1-20")),
" — ",
_txt(lang, "...", "..."),
```
(and a similar block for 1-99). Replace both with:
```python
Strong(_txt(lang, "Numbers", "Skaičiai")),
" — ",
_txt(
    lang,
    "Lithuanian number words from 0 to 99.",
    "Skaičių žodžiai nuo 0 iki 99.",
),
```

(Wrap each as `Li(...)` if the existing structure is a list.)

- [ ] **Step 6: Simplify `number_examples_section`**

Find the function (should be around line 480-530):

```python
def number_examples_section(max_number: int, lang: str = "en") -> ...:
    if max_number <= 20:
        # small-number examples
        ...
    else:
        # compound examples
        ...
```

Drop the parameter and the branch. Show one set covering a small number and a compound number (the union of what the current `> 20` branch shows). The new signature and body:

```python
def number_examples_section(lang: str = "en") -> Details:
    """Collapsible example pairs for the consolidated Numbers module."""
    # Body: show one simple example (e.g. "penki" for 5) and one compound
    # example (e.g. "dvidešimt vienas" for 21). Keep whatever HTML shape
    # the existing > 20 branch produced; just drop the if/else.
    return Details(...)
```

The implementer copies the current `else` branch body into the new function body, replacing `max_number` references as needed (there shouldn't be any).

- [ ] **Step 7: Run full test suite**

Run: `uv run --extra dev pytest 2>&1 | tail -15`
Expected: most tests pass. If `test_ui.py::test_landing_page_shows_all_modules` or similar breaks because it counted the two numbers cards, update the assertion to expect one. Fix any ui-test breakage in place.

- [ ] **Step 8: Run ruff**

Run: `uv run --extra dev ruff check . && uv run --extra dev ruff format --check .`
Expected: clean. If format complains, `uv run --extra dev ruff format .` and stage the result.

- [ ] **Step 9: Commit**

```bash
git add ui.py tests/
git commit -m "refactor(ui): collapse numbers 1-20/1-99 into single 'Numbers' UI

Nav dropdown, landing-page card, stats page section, and about-page
entry all collapse from two items to one. number_examples_section
drops the max_number parameter; shows one simple + one compound
example covering the 0-99 range."
```

---

## Task 8: Update existing tests for renamed prefixes

Most of the cleanup rides on the earlier tasks. This task handles the specific renames that weren't covered by the TDD tests above.

**Files:**
- Modify: `tests/test_numbers.py`
- Modify: `tests/test_age.py`
- Modify: `tests/test_weather.py`
- Modify: `tests/test_regressions.py`

- [ ] **Step 1: `tests/test_numbers.py` — trim `TestNumberInitTrackingCompact`**

Find the class (around line 169) and delete these methods:
- `test_n20_reachable_patterns_computed_from_rows`
- `test_legacy_n20_session_strips_unreachable_compound`
- `test_seed_prefix_from_n99_drops_unreachable_patterns`

Rename:
- `test_n99_reachable_patterns_include_all_four` → `test_numbers_reachable_patterns_include_all_four`

Update the surviving method to reference `"numbers"` prefix instead of `"n99"`:

```python
def test_numbers_reachable_patterns_include_all_four(self) -> None:
    from number_engine import NumberEngine

    engine = NumberEngine(rows=[{"number": n} for n in range(0, 100)])
    assert set(engine._reachable_patterns) == {
        "single_digit", "teens", "decade", "compound",
    }
```

Drop `test_fresh_n20_session_starts_empty` if it assumes the two-engine layout; otherwise keep and rename.

- [ ] **Step 2: `tests/test_age.py` — rename `seed_prefix`**

Run: `grep -n 'seed_prefix="n99"' tests/test_age.py`
For each hit, change `"n99"` → `"numbers"`. If tests construct a `session` dict with an `n99_performance` key to feed into age's `seed_prefix`, rename that key to `numbers_performance` as well.

- [ ] **Step 3: `tests/test_weather.py` — same rename**

Run: `grep -n 'seed_prefix="n99"\|n99_performance' tests/test_weather.py`
Apply the same rename as step 2.

- [ ] **Step 4: `tests/test_regressions.py` — mix keys**

Find `test_mix_session_initializes_only_one_module_question` (around line 286) and update the `module_q_keys` list. Current:

```python
module_q_keys = [
    "current_question",
    "time_current_question",
    "n20_current_question",
    "n99_current_question",
    "age_current_question",
    "weather_current_question",
]
```
Replace with:
```python
module_q_keys = [
    "current_question",
    "time_current_question",
    "numbers_current_question",
    "age_current_question",
    "weather_current_question",
]
```

Find `test_session_cookie_stays_under_budget_after_module_tour` (around line 81-106). Update the path tuple:

```python
for path in (
    "/numbers-20",
    "/numbers-99",
    ...
):
```
Replace with:
```python
for path in (
    "/numbers",
    ...
):
```
(Keep `/age`, `/weather`, `/time`, `/prices` unchanged.)

- [ ] **Step 5: Run full suite**

Run: `uv run --extra dev pytest 2>&1 | tail -10`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add tests/
git commit -m "test: rename n20/n99 references to numbers after consolidation

Drops the n20-specific reachability tests (no longer meaningful), renames
the surviving n99 reachability test, updates seed_prefix='n99' to
seed_prefix='numbers' in age/weather tests, and updates the mix-module
session-key list + cookie-tour path list."
```

---

## Task 9: Redirect smoke test + doc updates

**Files:**
- Modify: `tests/test_regressions.py`
- Modify: `FUTURE_MODULES.md`
- Modify: `CLAUDE.md`
- Modify: `LITHUANIAN_INTERFACE_REVIEW_REFERENCE.md`

- [ ] **Step 1: Write the redirect regression test**

Append to `tests/test_regressions.py`:

```python
def test_legacy_numbers_routes_redirect_to_new_url() -> None:
    """Old /numbers-20 and /numbers-99 URLs must 301 to /numbers so
    bookmarks and any external links keep working."""
    from starlette.testclient import TestClient

    with TestClient(main.app, follow_redirects=False) as client:
        for legacy in ("/numbers-20", "/numbers-99"):
            resp = client.get(legacy)
            assert resp.status_code == 301, (
                f"{legacy} returned {resp.status_code}, expected 301"
            )
            assert resp.headers["location"] == "/numbers", (
                f"{legacy} redirected to {resp.headers.get('location')!r}, "
                f"expected '/numbers'"
            )
```

- [ ] **Step 2: Run it**

Run: `uv run --extra dev pytest tests/test_regressions.py::test_legacy_numbers_routes_redirect_to_new_url -v`
Expected: PASS (the redirect handler was added in Task 3 Step 8).

- [ ] **Step 3: Update `FUTURE_MODULES.md`**

Find the "Done" list at the bottom. Remove these two lines:
```
- ~~**Numbers 1-20**~~ — Implemented.
- ~~**Numbers 1-99**~~ — Implemented.
```
Replace with:
```
- ~~**Numbers 0-99**~~ — Implemented. Consolidated from earlier 1-20 / 1-99 split.
```

- [ ] **Step 4: Update `CLAUDE.md`**

Find the project-structure line in `CLAUDE.md` (around line 28-30):

```
- **Six modules**: Numbers 1-20 (`/numbers-20`), Numbers 1-99 (`/numbers-99`), Age (`/age`), Weather (`/weather`), Prices (`/prices`), Time (`/time`) — each with own engine, adaptive tracking, and session state
```
Replace with:
```
- **Five modules**: Numbers (`/numbers`, 0-99), Age (`/age`), Weather (`/weather`), Prices (`/prices`), Time (`/time`) — each with own engine, adaptive tracking, and session state
```

Also check the landing-page description line earlier in the same file:
```
- **Landing page** at `/` with module cards; Numbers at `/numbers-20` & `/numbers-99`, ...
```
Replace with:
```
- **Landing page** at `/` with module cards; Numbers at `/numbers`, ...
```

- [ ] **Step 5: Append native-speaker addendum**

Append to `LITHUANIAN_INTERFACE_REVIEW_REFERENCE.md`:

```
---

## Added for 0-99 consolidation (2026-04-17)

**DB row for `number=0`** — please spot-check these forms:

- `nulis` (nominative; "Kaip pasakyti 0?" → "nulis")
- `nulį` (accusative; Kokia price answer for €0, not user-facing because prices filter to n≥1)
- `nulis eurų` (zero euros; genitive plural; prices completeness only)
- `nulis laipsnių` (zero degrees; used in weather produce answers)

If any form is off, please flag and we'll update the DB row via a one-line `UPDATE`.
```

- [ ] **Step 6: Run full suite + ruff**

Run: `uv run --extra dev pytest && uv run --extra dev ruff check . && uv run --extra dev ruff format --check .`
Expected: all green, lint clean.

- [ ] **Step 7: Commit**

```bash
git add tests/test_regressions.py FUTURE_MODULES.md CLAUDE.md LITHUANIAN_INTERFACE_REVIEW_REFERENCE.md
git commit -m "docs+test: redirect regression + doc updates for consolidation

- New regression test confirms /numbers-20 and /numbers-99 both 301
  to /numbers (TestClient-driven so FastHTML's route machinery is
  exercised end-to-end, same pattern as the earlier set-language
  redirect test).
- FUTURE_MODULES.md: Numbers entries in 'Done' collapsed.
- CLAUDE.md: module count/routes updated.
- LITHUANIAN_INTERFACE_REVIEW_REFERENCE.md: addendum listing the new
  zero-row forms for native-speaker review."
```

---

## Task 10: End-to-end smoke + deploy

**Files:**
- None modified (integration verification + deploy).

- [ ] **Step 1: Local smoke — every engine initializes cleanly**

Run:
```bash
uv run python -c "
import main
session = {}
main._ensure_session(session)
main._ensure_time_session(session)
main._ensure_age_session(session)
main._ensure_weather_session(session)
main._ensure_number_session(session, main.number_engine, 'numbers')
for key in ('performance', 'time_performance', 'age_performance',
            'weather_performance', 'numbers_performance'):
    perf = session[key]
    summary = {k: (len(v) if isinstance(v, dict) else v) for k, v in perf.items()}
    print(key, summary)
    assert 'combined_arms' not in perf
assert not any(k.startswith('n20_') or k.startswith('n99_') for k in session)
print('ok')
"
```
Expected: each perf dict prints its skeleton, no `n20_*` / `n99_*` keys, exits with `ok`.

- [ ] **Step 2: Local smoke — weather can produce zero-degree answer**

Run:
```bash
uv run python -c "
import main
zero_row = next(r for r in main.weather_rows if r['number'] == 0)
ans = main.weather_engine.correct_answer('produce', zero_row, negative=False)
print(repr(ans))
assert ans == 'nulis laipsnių', f'unexpected: {ans!r}'
print('ok')
"
```
Expected: `'nulis laipsnių'`, then `ok`.

- [ ] **Step 3: Local smoke — cookie-tour under budget**

Run:
```bash
uv run python -c "
from starlette.testclient import TestClient
import main
max_size = 0
with TestClient(main.app) as c:
    for path in ('/numbers', '/age', '/weather', '/time', '/prices'):
        r = c.get(path)
        assert r.status_code == 200
        sc = r.headers.get('set-cookie', '')
        max_size = max(max_size, len(sc))
        print(f'{path:14s} len={len(sc)}')
print(f'max={max_size}')
assert max_size < 4000
"
```
Expected: max under 4000 bytes.

- [ ] **Step 4: Push the branch and open a PR**

```bash
git push -u origin numbers-consolidation
gh pr create --base main --head numbers-consolidation \
  --title "refactor: consolidate /numbers-20 + /numbers-99 into /numbers (0-99)" \
  --body "$(cat <<'EOF'
## Summary

Implements docs/superpowers/specs/2026-04-17-numbers-consolidation-design.md.

- Single /numbers module covering 0-99 (adds DB row for 'nulis').
- Weather now serves zero degrees ('nulis laipsnių'); negative-zero
  guarded.
- Prices filtered to n>=1 (no 'zero euros' exercises).
- Legacy /numbers-20 and /numbers-99 URLs 301 -> /numbers.
- Legacy n20_*/n99_* session keys dropped on load (both OAuth and
  anonymous paths) without migration; TS priors rebuild in ~10-20
  exercises.

## Test plan

- [x] Full pytest suite green locally
- [x] ruff check + format clean
- [x] Local smoke on every engine init_tracking
- [x] Local smoke on zero-degree weather answer
- [x] Local cookie-tour under 4 KB
- [ ] Native-speaker spot-check on 'nulis'/'nulį'/'nulis laipsnių' (non-blocking; see LITHUANIAN_INTERFACE_REVIEW_REFERENCE.md addendum)
- [ ] Railway deploy + production smoke on /numbers, /numbers-20 redirect, weather 0°

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
Expected: PR URL printed.

- [ ] **Step 5: Wait for LGTM, merge, deploy**

After approval:
```bash
gh pr merge <pr-number> --squash
cd /Users/jonathan/projects/lithuanianquiz
git checkout main
git pull --ff-only origin main
git worktree remove .worktrees/numbers-consolidation
git branch -d numbers-consolidation
git push origin --delete numbers-consolidation
railway up --detach
```
Poll `railway service status` until `SUCCESS`.

- [ ] **Step 6: Production smoke**

```bash
curl -sS -o /dev/null -w "HTTP %{http_code}\n" https://lithuanian-practice.com/
curl -sS -I https://lithuanian-practice.com/numbers-20 | grep -iE "HTTP|location"
curl -sS -I https://lithuanian-practice.com/numbers-99 | grep -iE "HTTP|location"
```
Expected: `HTTP 200` on `/`, `HTTP/2 301` with `location: /numbers` on both legacy paths.

---

## Self-review notes

**Spec coverage:**
- Spec §1 data model → Task 1.
- Spec §2 row filters → Task 3 (engine block rewrite).
- Spec §3 engine/routing → Task 3.
- Spec §4 UI updates → Task 7.
- Spec §5 migration (auth + anon) → Tasks 5 and 4.
- Spec §6 practice-all → Task 3 (mix dict rewrite).
- Spec §7 tests → Tasks 4, 5, 6, 8, 9.
- Spec §8 native-speaker spot-check → Task 9 Step 5.
- Spec §9 doc updates → Task 9 Steps 3-4.
- Spec risks R1, R2 → accepted; no mitigation task. R3 → Task 6. R4 → Task 3 Step 8 + Task 9 Step 1.

**Placeholder scan:** no TBD/TODO/"similar to task N"/"fill in" left. Each code block is concrete.

**Type consistency:** `NumberEngine(rows, adaptation_threshold=10)` used consistently across Tasks 2, 3, 8. `_strip_legacy_number_keys(session)` signature consistent across Task 4. Session prefix `numbers_*` used consistently across Tasks 3, 4, 5, 7, 8. Mix key `"numbers"` consistent across Task 3 Step 9 and Task 8 Step 4.
