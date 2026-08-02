# Production Bug Fixes (fable review) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix five production bugs found by an independent deep-dive review (fable model, empirically reproduced against a sandboxed copy of the app/DB): two logged-in-user data-loss paths, a Lithuanian grammar bug, a broken adaptive-learning persistence check, and an open redirect.

**Architecture:** Each bug is fixed in place with the smallest correct change — no refactors, no new abstractions. Every fix ships with a regression test that fails before the fix and passes after, following the existing test patterns in `tests/test_regressions.py` and `tests/test_weather.py`.

**Tech Stack:** Python 3.13 (local) / 3.12 (Railway), FastHTML + MonsterUI, SQLite via `fastlite`, pytest, `starlette.testclient.TestClient` for route-level regression tests.

## Global Constraints

- Do not fix anything beyond the 5 bugs listed below — other findings from the review (OAuth CSRF `state`, prices-module stale-row 500, Railway volume/secret-key verification) are explicitly out of scope for this plan.
- Run `uv run pytest` after every task; all existing tests must keep passing.
- Before every commit, run `uv run ruff format .` and `uv run ruff check .` — both must be clean (the repo's pre-commit hook enforces this, but run it explicitly since these steps assume no hook is installed in the execution environment).
- Commit after each task individually — do not batch multiple tasks into one commit.
- Follow existing code style: type hints on all new/changed function signatures, docstrings only where the *why* isn't obvious from the code.

---

### Task 1: Hydrate DB progress before saving in `/set-language` and `/set-diacritic-mode`

**Bug:** Both routes call `save_progress(session["auth"], session)` without first calling `_hydrate_progress_if_logged_in(session)`. For a logged-in user, the cookie session has already had all DB-authoritative keys stripped by the `_compact_logged_in_session` after-hook (see `main.py:130-146`), so `save_progress` persists an empty/zeroed payload over the real DB row — wiping all progress. Reproduced live: one GET to `/set-language?lang=lt` zeroed a seeded 42-correct row.

**Files:**
- Modify: `main.py:677-703`
- Test: `tests/test_regressions.py`

**Interfaces:**
- Consumes: `main._hydrate_progress_if_logged_in(session: dict[str, Any]) -> None` (already defined at `main.py:231-243`, idempotent — a session that already has `"performance"` is treated as already hydrated).
- Consumes: `auth.save_progress`, `auth.load_progress` (existing signatures, unchanged by this task).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_regressions.py` (near the existing `test_set_language_*` / `test_set_diacritic_mode_*` tests, e.g. after line 700):

```python
def test_set_language_does_not_wipe_db_progress_for_logged_in_user(
    monkeypatch,
) -> None:
    """Regression: /set-language must hydrate DB progress into the session
    before calling save_progress, or it persists the stripped (cookie-only)
    session over real DB data — wiping all progress."""
    db = _SQLiteDB()
    monkeypatch.setattr(auth, "_db", db)

    auth.save_progress(
        "user-hydrate-lang",
        {
            "correct_count": 42,
            "incorrect_count": 7,
            "performance": {"kokia": {"correct": 40.0, "incorrect": 6.0}},
        },
    )

    class _Req:
        headers = {"referer": "/prices"}

    # Simulates the cookie a logged-in user actually carries: DB-authoritative
    # keys already stripped by _compact_logged_in_session.
    session: dict = {"auth": "user-hydrate-lang", "user_name": "Test User"}
    main.get_set_language(_Req(), session, lang="lt")

    reloaded: dict = {}
    auth.load_progress("user-hydrate-lang", reloaded)
    assert reloaded["correct_count"] == 42
    assert reloaded["incorrect_count"] == 7


def test_set_diacritic_mode_does_not_wipe_db_progress_for_logged_in_user(
    monkeypatch,
) -> None:
    """Same bug as /set-language, for /set-diacritic-mode."""
    db = _SQLiteDB()
    monkeypatch.setattr(auth, "_db", db)

    auth.save_progress(
        "user-hydrate-diacritic",
        {"correct_count": 12, "incorrect_count": 3},
    )

    session: dict = {"auth": "user-hydrate-diacritic"}
    main.get_set_diacritic_mode(session, enabled="1", next_path="/prices")

    reloaded: dict = {}
    auth.load_progress("user-hydrate-diacritic", reloaded)
    assert reloaded["correct_count"] == 12
    assert reloaded["incorrect_count"] == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_regressions.py -k "does_not_wipe_db_progress" -v`
Expected: both FAIL — `reloaded["correct_count"]` is `0`, not `42`/`12`.

- [ ] **Step 3: Implement the fix**

In `main.py`, change lines 677-703 from:

```python
@rt("/set-language")
def get_set_language(req, session, lang: str = "en") -> Any:
    session[UI_LANGUAGE_KEY] = normalize_ui_lang(lang)
    _refresh_cached_questions(session)
    if session.get("auth"):
        save_progress(session["auth"], session)
    referer = req.headers.get("referer", "/")
    from urllib.parse import urlparse

    parsed = urlparse(referer)
    redirect_to = parsed.path if parsed.path else "/"
    if parsed.query:
        redirect_to = f"{redirect_to}?{parsed.query}"
    if not redirect_to.startswith("/"):
        redirect_to = "/"
    return RedirectResponse(redirect_to, status_code=303)


@rt("/set-diacritic-mode")
def get_set_diacritic_mode(session, enabled: str = "0", next_path: str = "/") -> Any:
    session[_DIACRITIC_MODE_KEY] = enabled == "1"
    if session.get("auth"):
        save_progress(session["auth"], session)
    safe_next = (
        next_path if isinstance(next_path, str) and next_path.startswith("/") else "/"
    )
    return RedirectResponse(safe_next, status_code=303)
```

to:

```python
@rt("/set-language")
def get_set_language(req, session, lang: str = "en") -> Any:
    _hydrate_progress_if_logged_in(session)
    session[UI_LANGUAGE_KEY] = normalize_ui_lang(lang)
    _refresh_cached_questions(session)
    if session.get("auth"):
        save_progress(session["auth"], session)
    referer = req.headers.get("referer", "/")
    from urllib.parse import urlparse

    parsed = urlparse(referer)
    redirect_to = parsed.path if parsed.path else "/"
    if parsed.query:
        redirect_to = f"{redirect_to}?{parsed.query}"
    if not redirect_to.startswith("/"):
        redirect_to = "/"
    return RedirectResponse(redirect_to, status_code=303)


@rt("/set-diacritic-mode")
def get_set_diacritic_mode(session, enabled: str = "0", next_path: str = "/") -> Any:
    _hydrate_progress_if_logged_in(session)
    session[_DIACRITIC_MODE_KEY] = enabled == "1"
    if session.get("auth"):
        save_progress(session["auth"], session)
    safe_next = (
        next_path if isinstance(next_path, str) and next_path.startswith("/") else "/"
    )
    return RedirectResponse(safe_next, status_code=303)
```

(Only the two `_hydrate_progress_if_logged_in(session)` lines are new. The redirect-safety lines below `safe_next = (...)` and `if not redirect_to.startswith("/")` are touched again in Task 5 — leave them as-is here.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_regressions.py -k "does_not_wipe_db_progress" -v`
Expected: both PASS.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest`
Expected: all tests pass (no regressions in the existing `/set-language` / `/set-diacritic-mode` tests).

- [ ] **Step 6: Format, lint, commit**

```bash
uv run ruff format .
uv run ruff check .
git add main.py tests/test_regressions.py
git commit -m "fix: hydrate DB progress before save in /set-language and /set-diacritic-mode

Both routes called save_progress() without hydrating first, so for
logged-in users (whose cookie has DB-authoritative keys stripped) it
persisted an empty payload over real progress — wiping it on every
language or diacritic-mode toggle."
```

---

### Task 2: Persist progress on first-time OAuth login

**Bug:** `QuizOAuth.get_auth` (`auth.py:264-275`) calls `load_progress(ident, session)` but never `save_progress`. For a brand-new user (no existing DB row), `load_progress` no-ops. The framework sets `session["auth"]` before the redirect response is built, so the after-hook (`_compact_logged_in_session`) strips the (still-anonymous, never-saved) progress from the outgoing cookie. Net effect: a user who practices anonymously and then logs in for the first time loses everything at that exact moment.

**Files:**
- Modify: `tests/test_regressions.py:13-32` (`_SQLiteDB` fixture — add a `users` table)
- Modify: `auth.py:155-207` (`load_progress` — add a boolean return value)
- Modify: `auth.py:264-275` (`QuizOAuth.get_auth`)
- Test: `tests/test_regressions.py`

**Interfaces:**
- Produces: `auth.load_progress(google_id: str, session: dict[str, Any]) -> bool` — return type changes from `None` to `bool`: `True` if a valid DB row was found and merged into `session`. `False` covers *both* "no row yet" (new user) *and* "row exists but is unusable" (corrupt JSON/shape) — in both cases the current session is treated as authoritative and the caller may save it back, self-healing a corrupted row. All 12 existing call sites ignore the return value already, so this is backward compatible.

**Note on the `_SQLiteDB` test fixture:** `QuizOAuth.get_auth` calls `upsert_user()` first, which does `INSERT INTO users (...)`. The shared `_SQLiteDB` helper (`tests/test_regressions.py:13-32`, used by every test in this file) only creates `user_progress`, so calling `get_auth` against it currently raises `OperationalError: no such table: users`. Step 1 below adds a `users` table to that shared fixture — a one-time change that doesn't affect any other test in the file (they don't touch `users`).

- [ ] **Step 1: Write the failing tests**

First, add a `users` table to the shared `_SQLiteDB` fixture in `tests/test_regressions.py` (around line 13-27), so it matches the real schema from `auth.init_db_tables()`. Change:

```python
class _SQLiteDB:
    """Minimal DB wrapper compatible with auth.py's _db usage."""

    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            """
            CREATE TABLE user_progress (
                google_id TEXT PRIMARY KEY,
                data TEXT,
                updated_at TEXT
            )
            """
        )
        self.conn.commit()
```

to:

```python
class _SQLiteDB:
    """Minimal DB wrapper compatible with auth.py's _db usage."""

    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            """
            CREATE TABLE user_progress (
                google_id TEXT PRIMARY KEY,
                data TEXT,
                updated_at TEXT
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE users (
                google_id TEXT PRIMARY KEY,
                email TEXT,
                name TEXT,
                created_at TEXT,
                last_login TEXT
            )
            """
        )
        self.conn.commit()
```

Then add to `tests/test_regressions.py`:

```python
def test_get_auth_persists_anonymous_progress_for_new_user(monkeypatch) -> None:
    """Regression: a brand-new user's anonymous (cookie-only) progress must
    be saved to the DB on first login. load_progress no-ops when there's no
    existing DB row, so without an explicit save the progress is discarded
    the moment the post-login response strips it from the cookie."""
    db = _SQLiteDB()
    monkeypatch.setattr(auth, "_db", db)

    session: dict = {
        "correct_count": 15,
        "incorrect_count": 4,
        "performance": {"kokia": {"correct": 10.0, "incorrect": 3.0}},
    }
    info = {"email": "new@example.com", "name": "New User"}
    main.oauth.get_auth(info, "new-user-id", session, state=None)

    reloaded: dict = {}
    auth.load_progress("new-user-id", reloaded)
    assert reloaded["correct_count"] == 15
    assert reloaded["incorrect_count"] == 4


def test_get_auth_self_heals_corrupted_progress_row(monkeypatch) -> None:
    """A row that exists but fails to parse (corrupt JSON) must be treated
    the same as "no row" — the anonymous session is saved over it, rather
    than leaving the corrupted row stuck forever (load_progress silently
    no-ops on it on every future login too)."""
    db = _SQLiteDB()
    monkeypatch.setattr(auth, "_db", db)
    db.execute(
        "INSERT INTO user_progress (google_id, data, updated_at) VALUES (?, ?, ?)",
        ["user-corrupt", "{not json", "2026-03-02T00:00:00+00:00"],
    )

    session: dict = {"correct_count": 8, "incorrect_count": 1}
    info = {"email": "healed@example.com", "name": "Healed User"}
    main.oauth.get_auth(info, "user-corrupt", session, state=None)

    reloaded: dict = {}
    auth.load_progress("user-corrupt", reloaded)
    assert reloaded["correct_count"] == 8
    assert reloaded["incorrect_count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_regressions.py -k "test_get_auth_persists_anonymous_progress_for_new_user or test_get_auth_self_heals_corrupted_progress_row" -v`
Expected: both FAIL with `KeyError: 'correct_count'` — no DB row was ever written by `get_auth`, so `load_progress` no-ops and `reloaded` stays `{}`. (Confirm this is the failure — not an `OperationalError: no such table: users` — which is exactly why the `users` table was added to `_SQLiteDB` first.)

- [ ] **Step 3: Implement the fix**

In `auth.py`, change the `load_progress` signature and both early returns (lines 155-165):

```python
def load_progress(google_id: str, session: dict[str, Any]) -> bool:
    """Merge saved DB progress into the session.

    Returns True if a valid DB row was found and merged into `session`.
    Returns False both when there's no row yet (new user) and when an
    existing row is unusable (corrupt JSON / wrong shape) — in both cases
    the caller should treat the current session as authoritative and may
    save it back, which self-heals a corrupted row.
    """
    row = _db.execute(
        "SELECT data FROM user_progress WHERE google_id = ?", [google_id]
    ).fetchone()
    if not row:
        return False

    data = _load_progress_payload(row[0], google_id)
    if data is None:
        return False
```

and add `return True` as the last line of the function (after the existing `session[UI_LANGUAGE_KEY] = normalize_ui_lang(data.get(UI_LANGUAGE_KEY))` line, i.e. new line 207).

Then change `get_auth` (lines 264-275) from:

```python
    def get_auth(
        self, info: Any, ident: str, session: Any, state: Any
    ) -> RedirectResponse:
        upsert_user(ident, info.get("email", ""), info.get("name", ""))
        load_progress(ident, session)
        session["user_name"] = info.get("name", "")
        session["user_email"] = info.get("email", "")
        return RedirectResponse("/", status_code=303)
```

to:

```python
    def get_auth(
        self, info: Any, ident: str, session: Any, state: Any
    ) -> RedirectResponse:
        upsert_user(ident, info.get("email", ""), info.get("name", ""))
        had_progress = load_progress(ident, session)
        if not had_progress:
            save_progress(ident, session)
        session["user_name"] = info.get("name", "")
        session["user_email"] = info.get("email", "")
        return RedirectResponse("/", status_code=303)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_regressions.py -k "test_get_auth_persists_anonymous_progress_for_new_user or test_get_auth_self_heals_corrupted_progress_row" -v`
Expected: both PASS.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest`
Expected: all tests pass.

- [ ] **Step 6: Format, lint, commit**

```bash
uv run ruff format .
uv run ruff check .
git add auth.py tests/test_regressions.py
git commit -m "fix: persist anonymous progress on first OAuth login

load_progress no-ops for a new user (no DB row yet), and get_auth
never called save_progress, so a first-time login discarded all
progress accumulated while browsing anonymously. A corrupt existing
row is treated the same way (self-heals instead of staying stuck)."
```

---

### Task 3: Fix weather grammar for temperatures ending in 1 (21, 31, ... 91)

**Bug:** `_degree_form` (`weather_engine.py:15-29`) picks `laipsniai` whenever `row["years"] == "metai"`, but that column encodes *age* grammar (collective years), not the cardinal-noun agreement `laipsnis/laipsniai/laipsnių` needs. The DB's own `euro_nom` column shows the correct rule: numbers ending in 1 (except 11) take the nominative singular noun. So 21 → `euro_nom = "euras"` (singular) but `_degree_form` currently returns `laipsniai` (plural) for the same row, producing "dvidešimt vienas laipsniai" instead of the correct "dvidešimt vienas laipsnis". Confirmed live via `WeatherEngine.correct_answer("produce", row21, False)`.

**Files:**
- Modify: `weather_engine.py:15-29`
- Test: `tests/test_weather.py`

**Interfaces:**
- No signature changes — `_degree_form(row: dict[str, Any]) -> str` keeps its existing shape; only the internal logic changes.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_weather.py`, inside the existing `class TestDegreeForm:` (after `test_decade`, currently ending at line 63):

```python
    def test_eleven_is_exception_not_singular(self) -> None:
        assert _degree_form({"number": 11, "years": "metų"}) == "laipsnių"

    def test_twenty_one_is_singular(self) -> None:
        assert _degree_form({"number": 21, "years": "metai"}) == "laipsnis"

    def test_thirty_one_is_singular(self) -> None:
        assert _degree_form({"number": 31, "years": "metai"}) == "laipsnis"

    def test_ninety_one_is_singular(self) -> None:
        assert _degree_form({"number": 91, "years": "metai"}) == "laipsnis"
```

Also add a row for 21 to the `sample_rows` fixture (currently `tests/test_weather.py:9-41`, 5 rows) as a new 6th entry:

```python
        {
            "number": 21,
            "kokia_kaina": "dvidešimt",
            "kokia_kaina_compound": "vienas",
            "years": "metai",
        },
```

and add an engine-level test inside `class TestCorrectAnswer:` (after `test_produce_compound`, currently ending at line 81):

```python
    def test_produce_compound_ending_in_one_is_singular(
        self, engine: WeatherEngine, sample_rows: list[dict]
    ) -> None:
        assert (
            engine.correct_answer("produce", sample_rows[5], negative=False)
            == "dvidešimt vienas laipsnis"
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_weather.py -k "twenty_one or thirty_one or ninety_one or eleven_is_exception or ending_in_one" -v`
Expected: the three `*_is_singular` tests and `test_produce_compound_ending_in_one_is_singular` FAIL (current code returns `"laipsniai"` for 21/31/91). `test_eleven_is_exception_not_singular` already PASSES (11's `years` is `"metų"`, not `"metai"`) — that's fine, it documents the boundary case the fix must not break.

- [ ] **Step 3: Implement the fix**

In `weather_engine.py`, change lines 15-29 from:

```python
def _degree_form(row: dict[str, Any]) -> str:
    """Pick laipsnis/laipsniai/laipsnių based on same rule as years column.

    - number == 0 → laipsnių (gen. pl., same as 10-19/decades)
    - number == 1 → laipsnis (nom. sg.)
    - years == "metai" (2-9, compounds ending 2-9) → laipsniai (nom. pl.)
    - years == "metų" (10-19, decades) → laipsnių (gen. pl.)
    """
    if row["number"] == 0:
        return "laipsnių"
    if row["number"] == 1:
        return "laipsnis"
    if row["years"] == "metai":
        return "laipsniai"
    return "laipsnių"
```

to:

```python
def _degree_form(row: dict[str, Any]) -> str:
    """Pick laipsnis/laipsniai/laipsnių to match Lithuanian cardinal-noun
    agreement — the same rule the DB already encodes in `euro_nom`:

    - number == 0 → laipsnių (gen. pl.)
    - number % 100 == 11 → laipsnių (gen. pl.) — the "11" exception
    - number % 10 == 1 → laipsnis (nom. sg.) — includes 21, 31, ... 91
    - years == "metai" (other 2-9-ending numbers/compounds) → laipsniai (nom. pl.)
    - years == "metų" (10-19, decades) → laipsnių (gen. pl.)
    """
    number = row["number"]
    if number == 0:
        return "laipsnių"
    if number % 100 == 11:
        return "laipsnių"
    if number % 10 == 1:
        return "laipsnis"
    if row["years"] == "metai":
        return "laipsniai"
    return "laipsnių"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_weather.py -v`
Expected: all PASS, including the pre-existing `test_one`, `test_single_digit`, `test_teens`, `test_compound`, `test_decade` (unchanged behavior for those cases).

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest`
Expected: all tests pass.

- [ ] **Step 6: Format, lint, commit**

```bash
uv run ruff format .
uv run ruff check .
git add weather_engine.py tests/test_weather.py
git commit -m "fix: correct weather degree-word grammar for X1 temperatures

_degree_form used the years column (age-collective grammar) to choose
laipsnis/laipsniai/laipsnių, but 21/31/.../91 need the singular form
laipsnis, not laipsniai — the DB's own euro_nom column already shows
the correct number%10==1 (except 11) rule."
```

---

### Task 4: Accept decayed float counts in the mix-modules session validator

**Bug:** `_is_valid_mix_modules` (`auth.py:99-112`) requires `isinstance(correct, int)` and `isinstance(incorrect, int)`. But `thompson.bump` (`thompson.py:19-36`) gamma-decays both counts (`arm["correct"] *= DECAY_GAMMA`) before incrementing, turning them into floats after the very first answer in Practice-All. So `load_progress` (`auth.py:198-204`) discards `mix_modules` on every hydrate for any user who has answered at least one Practice-All question — the adaptive weighting resets constantly and never learns for logged-in users.

**Files:**
- Modify: `auth.py:99-112` (add `import math` to the module's existing imports too)
- Test: `tests/test_regressions.py`

**Interfaces:**
- No signature changes — `_is_valid_mix_modules(value: Any) -> bool` keeps its existing shape.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_regressions.py` (near `test_save_and_load_progress_persists_mix_fields`, e.g. after line 78). The first test drives the counters through the real `thompson.bump` (the actual producer), not hand-typed floats, so it can't drift from what production code actually generates:

```python
def test_save_and_load_progress_persists_bumped_mix_counts(monkeypatch) -> None:
    """Regression: after the first thompson.bump() call, mix_modules counts
    are floats (gamma-decayed), not ints. _is_valid_mix_modules must accept
    them or the adaptive weighting silently resets on every hydrate."""
    from thompson import bump

    db = _SQLiteDB()
    monkeypatch.setattr(auth, "_db", db)

    mix_modules = {}
    bump(mix_modules, "time", is_correct=True)
    bump(mix_modules, "prices", is_correct=False)
    assert isinstance(mix_modules["time"]["correct"], float)  # sanity: real bump() output

    auth.save_progress("user-float-mix", {"mix_modules": mix_modules})

    loaded_session: dict = {}
    auth.load_progress("user-float-mix", loaded_session)

    assert loaded_session["mix_modules"] == mix_modules


def test_is_valid_mix_modules_rejects_non_finite_and_bool_counts() -> None:
    """A fail-closed validator must reject NaN/Infinity (Python's json
    module happily round-trips them, and they'd otherwise feed straight
    into Thompson sampling) and bool (an int subclass that isn't a valid
    counter)."""
    base = {"correct": 1.0, "incorrect": 1.0}
    for bad_correct in (float("nan"), float("inf"), float("-inf"), True):
        value = {"time": {**base, "correct": bad_correct}}
        assert auth._is_valid_mix_modules(value) is False


def test_is_valid_mix_modules_rejects_oversized_integers() -> None:
    """JSON integers have no size limit, so a corrupted/crafted payload
    could contain one too large to convert to float. math.isfinite()
    raises OverflowError on that instead of returning False — the
    validator must catch it and fail closed, not crash the caller."""
    value = {"time": {"correct": 10**400, "incorrect": 1}}
    assert auth._is_valid_mix_modules(value) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_regressions.py -k "test_save_and_load_progress_persists_bumped_mix_counts or test_is_valid_mix_modules_rejects_non_finite_and_bool_counts or test_is_valid_mix_modules_rejects_oversized_integers" -v`
Expected: `test_save_and_load_progress_persists_bumped_mix_counts` FAILs (`reloaded["mix_modules"]` raises `KeyError` — the current code never populates it since `_is_valid_mix_modules` rejects the bumped float counters). `test_is_valid_mix_modules_rejects_non_finite_and_bool_counts` FAILs on the `True` case specifically (current code's `isinstance(correct, int)` accepts `bool`); it currently *passes* on the `nan`/`inf` cases only because those are still floats being rejected by the pre-existing `isinstance(correct, int)` check — that's a false-positive pass for the wrong reason, which Step 3 will correct to a real (finite-check-based) rejection for all four cases at once. `test_is_valid_mix_modules_rejects_oversized_integers` FAILs too, but for a different reason: `10**400` is a plain Python int, and the current `isinstance(correct, int)` check accepts *any* int with no magnitude limit, so the validator returns `True` (not the crash you might expect) — the assertion `is False` fails. Step 3 must reject it without ever raising `OverflowError`.

- [ ] **Step 3: Implement the fix**

In `auth.py`, add `import math` near the top with the other standard-library imports (`import json`, `import logging`, `import os`), then change lines 99-112 from:

```python
def _is_valid_mix_modules(value: Any) -> bool:
    """Validate persisted mix-module counters before loading."""
    if not isinstance(value, dict) or not value:
        return False
    for stats in value.values():
        if not isinstance(stats, dict):
            return False
        correct = stats.get("correct")
        incorrect = stats.get("incorrect")
        if not isinstance(correct, int) or not isinstance(incorrect, int):
            return False
        if correct < 0 or incorrect < 0:
            return False
    return True
```

to:

```python
def _is_valid_mix_modules(value: Any) -> bool:
    """Validate persisted mix-module counters before loading.

    Counters are ints only until the first thompson.bump() call, which
    gamma-decays them into floats — both types must be accepted (but not
    bool, an int subclass, and not NaN/Infinity, which json round-trips
    happily but would corrupt Thompson sampling) or every post-bump save
    gets silently dropped on the next load.
    """
    if not isinstance(value, dict) or not value:
        return False
    for stats in value.values():
        if not isinstance(stats, dict):
            return False
        correct = stats.get("correct")
        incorrect = stats.get("incorrect")
        if isinstance(correct, bool) or isinstance(incorrect, bool):
            return False
        if not isinstance(correct, (int, float)) or not isinstance(
            incorrect, (int, float)
        ):
            return False
        try:
            if not math.isfinite(correct) or not math.isfinite(incorrect):
                return False
        except OverflowError:
            # A JSON integer with no size limit (e.g. 10**400) can't be
            # converted to float — treat it as invalid, don't crash.
            return False
        if correct < 0 or incorrect < 0:
            return False
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_regressions.py -k "test_save_and_load_progress_persists_bumped_mix_counts or test_is_valid_mix_modules_rejects_non_finite_and_bool_counts or test_is_valid_mix_modules_rejects_oversized_integers" -v`
Expected: all three PASS.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest`
Expected: all tests pass — in particular, `test_load_progress_drops_invalid_mix_modules` (`tests/test_regressions.py:597`) must still fail-closed for genuinely invalid data (it uses `{"correct": 3}` with no `incorrect` key, which stays invalid under the new check too).

- [ ] **Step 6: Format, lint, commit**

```bash
uv run ruff format .
uv run ruff check .
git add auth.py tests/test_regressions.py
git commit -m "fix: accept decayed float counts in mix-modules session validator

_is_valid_mix_modules required int counters, but thompson.bump()
produces floats after the first answer — Practice-All's adaptive
weighting was silently discarded on every hydrate for logged-in
users. Also fail-closed on bool and non-finite (NaN/Infinity) counts."
```

---

### Task 5: Reject protocol-relative (`//`) redirect targets

**Bug:** Both `/set-language` and `/set-diacritic-mode` treat any path starting with `/` as safe, but a path starting with `//` (or `/\`) is protocol-relative — browsers resolve `Location: //evil.example/phish` to `https://evil.example/phish`, not a same-origin path. Confirmed live: `next_path="//evil.example/phish"` passes the current `startswith("/")` check in `/set-diacritic-mode`, and a referer like `https://evil.com//phish.example/x` produces the same unsafe path via `urlparse` in `/set-language`.

**Files:**
- Modify: `main.py:170-172` (add a helper next to `_is_diacritic_tolerant`)
- Modify: `main.py:677-703` (both routes, post-Task-1 versions)
- Test: `tests/test_regressions.py`

**Interfaces:**
- Produces: `main._is_safe_local_redirect(path: Any) -> bool` — used by both `/set-language` and `/set-diacritic-mode`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_regressions.py` (near `test_set_language_route_returns_303_over_http` / `test_set_diacritic_mode_rejects_non_local_redirects`):

```python
def test_set_language_rejects_protocol_relative_redirect() -> None:
    class _Req:
        headers = {"referer": "https://evil.com//phish.example/x"}

    session: dict = {}
    response = main.get_set_language(_Req(), session, lang="lt")

    assert response.headers["location"] == "/"


def test_set_diacritic_mode_rejects_protocol_relative_redirect() -> None:
    session: dict = {}
    response = main.get_set_diacritic_mode(
        session, enabled="1", next_path="//evil.example/phish"
    )

    assert response.headers["location"] == "/"


def test_set_diacritic_mode_rejects_backslash_protocol_relative_redirect() -> None:
    """Some browsers treat a leading /\\ the same as // (protocol-relative)."""
    session: dict = {}
    response = main.get_set_diacritic_mode(
        session, enabled="1", next_path="/\\evil.example"
    )

    assert response.headers["location"] == "/"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_regressions.py -k protocol_relative_redirect -v`

(Note: `-k rejects_protocol_relative_redirect` would silently skip the backslash test — `"rejects_protocol_relative_redirect"` isn't a contiguous substring of `"rejects_backslash_protocol_relative_redirect"`. Use `-k protocol_relative_redirect`, which matches all three.)

Expected: all three FAIL — `location` is `"//phish.example/x"` and `"//evil.example/phish"` for the first two. For the third, Starlette percent-encodes the backslash in the `Location` header, so the actual pre-fix value is `"/%5Cevil.example"`, not the raw `"/\\evil.example"` — the test's assertion (`== "/"`) doesn't care about the exact pre-fix value, only that it's wrong, so this doesn't change the test itself.

- [ ] **Step 3: Implement the fix**

In `main.py`, add a helper right after `_is_diacritic_tolerant` (after line 172):

```python
def _is_safe_local_redirect(path: Any) -> bool:
    """True if `path` is a same-origin, path-only redirect target.

    A leading `//` (or `/\\`) is protocol-relative — browsers resolve
    `Location: //evil.example/x` to `https://evil.example/x`, not a
    same-origin path, so `path.startswith("/")` alone isn't enough.
    """
    return (
        isinstance(path, str)
        and path.startswith("/")
        and not path.startswith("//")
        and not path.startswith("/\\")
    )
```

Then in the two routes (post-Task-1 versions from `main.py:677-703`), replace the redirect-safety checks:

`/set-language` — change:

```python
    if not redirect_to.startswith("/"):
        redirect_to = "/"
```

to:

```python
    if not _is_safe_local_redirect(redirect_to):
        redirect_to = "/"
```

`/set-diacritic-mode` — change:

```python
    safe_next = (
        next_path if isinstance(next_path, str) and next_path.startswith("/") else "/"
    )
```

to:

```python
    safe_next = next_path if _is_safe_local_redirect(next_path) else "/"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_regressions.py -k protocol_relative_redirect -v`
Expected: all three PASS.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest`
Expected: all tests pass — in particular `test_set_language_sanitizes_bad_input`, `test_set_language_route_returns_303_over_http`, and `test_set_diacritic_mode_rejects_non_local_redirects` must still pass unchanged.

- [ ] **Step 6: Format, lint, commit**

```bash
uv run ruff format .
uv run ruff check .
git add main.py tests/test_regressions.py
git commit -m "fix: reject protocol-relative (//) redirect targets

startswith(\"/\") treated //evil.example/x as a safe same-origin path,
but browsers resolve a leading // as protocol-relative — an open
redirect in /set-language and /set-diacritic-mode."
```

---

## Out of scope (tracked separately, not part of this plan)

- OAuth login-CSRF (no `state` param validation) — `auth.py:264-275` / `fasthtml.oauth`.
- Prices module 500 on stale `row_id` cookie — `main.py:800-807`, `quiz.py:103-104`.
- Verifying a Railway volume backs `lithuanian_data.db` in production, and that `LQ_SECRET_KEY` is actually set (both require live Railway CLI access, not a code change).
- `get_home()` (`main.py:706-707`) and `get_stats()` (`main.py:895-896`) compute `lang`/stats without calling `_hydrate_progress_if_logged_in` first, so they can render the default language or empty stats for a logged-in user even after Tasks 1-2 fix the underlying data loss (found by Codex xhigh review, round 1, as an adjacent issue — doesn't invalidate these 5 fixes but should be fixed in a follow-up).
