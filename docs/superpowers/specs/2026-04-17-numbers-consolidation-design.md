# Numbers Module Consolidation — Design

**Date:** 2026-04-17
**Scope:** Merge `/numbers-20` and `/numbers-99` into a single `/numbers` module covering 0-99; expand weather module to include 0 ("nulis laipsnių"); reset legacy per-user numbers progress on first login.

---

## Goals

1. Eliminate the `1-20` / `1-99` split. One "Numbers" module, range 0-99.
2. Add the row for `number=0` to the DB so `nulis` is practiceable.
3. Expand weather to serve 0 ("zero degrees" is common and natural Lithuanian). Keep prices filtered to `>= 1` (zero price is unnatural) and age filtered to `>= 2` (unchanged).
4. Reset legacy `n20_*` / `n99_*` user progress and Practice-All priors rather than migrating (zero-user scale, trivial rebuild cost).

## Non-goals

- Schema redesign of `lithuanian_data.db` beyond adding one row.
- Changes to age, time, or prices engines themselves.
- Deploying this refactor in the same PR as library updates or the polish bucket.
- Retaining legacy `n20_*` / `n99_*` fields in the DB across saves (they go away naturally on first re-save per user).

---

## Design

### 1. Data model

Add one row to `lithuanian_data.db::numbers` for `number=0`:

| column | value |
|---|---|
| `number` | `0` |
| `kokia_kaina` | `nulis` |
| `kokia_kaina_compound` | `NULL` |
| `kiek_kainuoja` | `nulį` *(accusative of nulis — native-speaker verify)* |
| `kiek_kainuoja_compound` | `NULL` |
| `euro_nom` | `eurų` *(genitive plural — matches 10+/compound 0 pattern)* |
| `euro_acc` | `eurų` |

Additional columns beyond these may exist in the table; populate with sensible defaults (null/empty) at insert time. The implementer checks the actual schema while coding.

### 2. Row filters per module

| module | before | after |
|---|---|---|
| numbers (consolidated) | `<= 20` or `<= 99` (two NumberEngine instances) | all rows (`0-99`) |
| age | `>= 2` | `>= 2` (unchanged) |
| weather | `>= 1` | `>= 0` |
| prices | all rows | `>= 1` (new explicit filter) |

### 3. Engine & routing

**`main.py`:**
- Delete `rows_20` slice and `number_engine_20` instance.
- Rename `number_engine_99` → `number_engine`; construct with `ALL_ROWS`.
- Collapse the two `_make_number_routes(...)` calls into one:
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
  No `seed_prefix` argument.
- Update `age_engine.init_tracking(..., seed_prefix="n99")` → `seed_prefix="numbers"`. Same for `weather_engine`.
- Construct new filtered row-sets for weather (`>= 0`, i.e. all rows including 0) and prices (`>= 1`).
- Add redirect block:
  ```python
  @rt("/numbers-20")
  @rt("/numbers-99")
  def get_legacy_numbers() -> RedirectResponse:
      return RedirectResponse("/numbers", status_code=301)
  ```

**Session prefix rename** — everywhere `n20_*` or `n99_*` appears in `main.py` (ensure/new_q helpers, cached-question refresh map, mix module map, price session key tuples used for reset), collapse to `numbers_*`.

**`NumberEngine` API:** `_reachable_patterns` automatically covers `{single_digit, teens, decade, compound}` from the 0-99 row-set. Section 4 removes the only current use of `max_number` (it branched `number_examples_section`). **Decision:** drop the `max_number` parameter from `NumberEngine.__init__` in this refactor. The constructor becomes `NumberEngine(rows, adaptation_threshold=10)`. Every existing test and call site that passes `max_number=...` must be updated.

### 4. UI updates (`ui.py`)

- `MODULE_NAMES` set: remove `"numbers-20"`, `"numbers-99"`; add `"numbers"`.
- Nav dropdown (`page_shell` around line 67-68): two `Li(A(...))` entries collapse to one — `Li(A(_txt(lang, "Numbers", "Skaičiai"), href="/numbers"))`.
- Landing-page module cards: the two separate Numbers cards collapse to one. Keep the "Start here" / "Pradėkite čia" badge on the consolidated card (it was on the 1-20 card). Description: EN "Lithuanian number words from 0 to 99." / LT "Skaičių žodžiai nuo 0 iki 99."
- `stats_page_content` (around line 1595-1625): the two `_module_stats_section(...)` calls for `n20_performance` and `n99_performance` become one for `numbers_performance`, titled "Numbers" / "Skaičiai".
- About page module list (around line 1756-1764): two `Strong(...)` entries become one.
- `number_examples_section(max_number, lang)`: simplify. Drop the `max_number` parameter (and the `if max_number <= 20` branch). Show one set of examples covering a simple number and a compound number — the set currently shown for `max_number > 20`. Callers (one call site in `main.py`) lose the argument.

No new translation strings required; the existing `("Numbers", "Skaičiai")` pair already exists via the nav. The `Lithuanian Numbers` page title is parameterized through `_make_number_routes`, so passing the new title argument is enough.

### 5. Migration (`auth.py`)

**`load_progress` (lines 180-188 / 203-207):**
- Replace the 8 lines that read `n20_*` and `n99_*` from `data` with 4 lines that read `numbers_*`. Do not read the legacy fields at all.
- Before the `_is_valid_mix_modules(mix_modules)` check, normalize legacy Practice-All state:
  ```python
  if isinstance(mix_modules, dict) and (
      "n20" in mix_modules or "n99" in mix_modules
  ):
      mix_modules = None
  ```

**`save_progress` (lines 227-235):**
- Replace the 8 `n20_*` / `n99_*` entries with 4 `numbers_*` entries. The next save per user rewrites their DB row without the legacy fields.

**Also strip legacy keys from anonymous cookie sessions (`main.py`):**

Anonymous users (no OAuth) never go through `auth.load_progress`, so their cookie keeps any `n20_*` / `n99_*` / legacy-`mix_modules` keys forever unless we proactively strip them. Add a shared helper near the other session helpers:

```python
_LEGACY_NUMBER_PREFIXES = ("n20_", "n99_")

def _strip_legacy_number_keys(session: dict[str, Any]) -> None:
    for key in list(session):
        if key.startswith(_LEGACY_NUMBER_PREFIXES):
            del session[key]
    mix_modules = session.get("mix_modules")
    if isinstance(mix_modules, dict) and (
        "n20" in mix_modules or "n99" in mix_modules
    ):
        session.pop("mix_modules", None)
```

Call it at the top of `_ensure_session`, `_ensure_time_session`, `_ensure_age_session`, `_ensure_weather_session`, `_ensure_number_session`, and `_ensure_mix_session`. First call per request cleans the session; becomes a no-op thereafter. Cost: one `startswith` loop over session keys per request, negligible.

This keeps logged-in and anonymous users on the same reset behavior and avoids stale cookie bloat from abandoned legacy keys.

**No DB pruning script.** Legacy keys in the serialized JSON are harmless; they go away naturally on first save-after-upgrade per user.

### 6. Practice-All mode (`main.py`, `_MIX_MODULES` around line 1622)

- Remove `"n20"` and `"n99"` entries from `_MIX_MODULES`, `_MIX_Q_KEY_BY_MODULE`, and the transient-session-keys tuple (around line 1658-1667).
- Add single `"numbers"` entry to each:
  ```python
  "numbers": {
      "ensure": lambda s: _ensure_number_session(s, number_engine, "numbers"),
      "new_q": lambda s: _new_number_question(s, number_engine, "numbers"),
  },
  ```
  and `"numbers": "numbers_current_question"` in `_MIX_Q_KEY_BY_MODULE`, and transient tuple `("numbers_exercise_type", "numbers_row_id", "numbers_number_pattern", "numbers_current_question")`.

`_sample_weakest(mix_modules)` picks up the new taxonomy automatically since it's the virtual sampler over the dict's keys.

### 7. Tests

**Delete / update:**
- `tests/test_numbers.py::TestNumberInitTrackingCompact` — drop `test_n20_reachable_patterns_computed_from_rows`, `test_legacy_n20_session_strips_unreachable_compound`, `test_seed_prefix_from_n99_drops_unreachable_patterns`. Rename `test_n99_reachable_patterns_include_all_four` → `test_numbers_reachable_patterns_include_all_four` (same assertion, different engine name).
- `tests/test_age.py`, `tests/test_weather.py` — replace `seed_prefix="n99"` with `seed_prefix="numbers"` in any test that references it.
- `tests/test_regressions.py::test_mix_session_initializes_only_one_module_question` — remove `n20_current_question` and `n99_current_question` from the expected-keys list; add `numbers_current_question`.
- `tests/test_regressions.py::test_session_cookie_stays_under_budget_after_module_tour` — replace `/numbers-20` and `/numbers-99` in the path tuple with single `/numbers`.

**New:**
- `test_load_progress_discards_legacy_n20_n99_fields` — insert a DB row with `n20_correct_count=5`, `n99_performance={...}`, etc. After `load_progress`, session has no keys starting with `n20_` or `n99_`.
- `test_load_progress_resets_mix_modules_with_legacy_keys` — DB row with `mix_modules={"n20": {...}, "age": {...}}` → loaded session has no `mix_modules` key.
- `test_legacy_numbers_routes_redirect` — TestClient GET on `/numbers-20` returns `301` with `location: /numbers`; same for `/numbers-99`.
- `test_weather_engine_correct_answer_for_zero_row` — deterministic unit-seam test. Construct a minimal `WeatherEngine(rows=[{"number": 0, "kokia_kaina": "nulis", ...}])` and call `engine.correct_answer(row=<zero_row>, negative=False, exercise_type="produce")` directly. Assert the output contains `"nulis"` and the genitive-plural degree form (`"laipsnių"`). No RNG, no `generate()`, no adaptive sampling involved.
- `test_weather_engine_excludes_negative_zero` — after adding the R3 guard, assert `generate` never returns `{row.number: 0, negative: True}`: either by inspecting the code path directly, or by forcing the sampler (via seed + priors) into states where `negative=True` is most likely and verifying row 0 is avoided in those cases.

**Not touched:** `tests/test_thompson.py`, `tests/test_time.py`, `tests/test_age.py` (beyond seed_prefix rename), `tests/test_quiz.py`, `tests/test_ui.py` — no API changes reach them.

### 8. Native-speaker spot-check

Append a short section to `LITHUANIAN_INTERFACE_REVIEW_REFERENCE.md` listing:
- `nulis` (nominative)
- `nulį` (accusative)
- `nulis eurų` (zero euros, genitive plural — for prices, even though prices won't serve 0 directly; useful for completeness)
- `nulis laipsnių` (zero degrees, weather produce form)
- `Kaip pasakyti 0?` (question prompt variants already covered by existing format_question logic)

Send to jbagd before merge (non-blocking if response doesn't arrive in time — we can fix the DB row post-merge with a one-line UPDATE).

### 9. Doc updates

- `FUTURE_MODULES.md`: strip the `Numbers 1-20` / `Numbers 1-99` entries from the "Done" list; replace with single "Numbers 0-99". Remove any stale references elsewhere in that file.
- `CLAUDE.md` project structure section: remove the "Numbers 1-20 (`/numbers-20`), Numbers 1-99 (`/numbers-99`)" line; replace with single "Numbers (`/numbers`)".

---

## Risks and mitigations

**R1. Existing logged-in user loses their numbers-specific priors.** Acceptance: hobby-scale (~6 visits/week), TS rebuild in ~10-20 exercises. Noted in Section 5. No mitigation needed.

**R2. `nulį` (accusative of nulis) is wrong.** Likelihood: non-zero — I inferred from pattern, not from a dictionary. Mitigation: native-speaker spot-check before merge; the DB row is a single `UPDATE` if wrong. Impact if unnoticed: the prices module never serves row 0 (filter `>= 1`) so this field is never consulted — it's a completeness-only value. If weather is what uses it via some edge case I'm missing, the "produce" answer for `0°` is "nulis laipsnių" (uses `kokia_kaina` + genitive plural, not `kiek_kainuoja`) — so `kiek_kainuoja` for row 0 is never user-facing. Low impact.

**R3. Weather with `negative=True` and `number=0` is nonsensical** ("minus zero degrees"). Look at `weather_engine.generate` — the `negative` flag is sampled from the sign taxonomy, and the row is sampled separately. If `negative=True` and `row["number"]==0` both fire, the output is "minus nulis laipsnių." Mitigation: in `weather_engine.generate`, skip the `negative=True` branch when `row["number"]==0`, similar to the existing `negative and row["number"] > 20` guard (which constrains to `negative_rows` for small-enough numbers). Small, contained change.

**R4. Someone has the old `/numbers-99` URL bookmarked.** Handled by the 301 redirect block.

---

## Success criteria

- Navigating to `/numbers`, `/numbers-20`, `/numbers-99` all end with the user on the consolidated page (latter two via 301).
- `/prices` GET shows no row for 0.
- `/weather` GET can serve the 0 row; "nulis laipsnių" appears in the correct-answer text when that row is picked for a non-negative produce exercise.
- Full test suite green, including the new redirect and legacy-cleanup regressions.
- Session cookie size after a full module tour stays under the existing 4 KB regression guard.
- No `n20_*` or `n99_*` keys appear in any serialized session after one save-cycle per user.
