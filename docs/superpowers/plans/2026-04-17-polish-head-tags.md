# Polish PR α — Head Tags Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the wrong-value default `<title>FastHTML page</title>` with correct per-route, language-aware titles, and add `<meta name="description">` + Open Graph tags.

**Architecture:** `page_shell` gains a `page_title` parameter and returns explicit `Title(...)` and `Meta(...)` FastHTML primitives alongside its body content. FastHTML hoists these into `<head>` automatically. The `fast_app(title=...)` kwarg — silently ignored in 0.13.3 — is removed.

**Tech Stack:** Python 3.13, FastHTML 0.13.3, MonsterUI. No new deps.

**Background reading:**
- `docs/superpowers/specs/2026-04-17-polish-bucket-design.md` §PR α — the spec this plan implements.
- Viewport meta is already emitted by MonsterUI; we do not add one.
- `fasthtml.Titled(...)` emits a visible `<h1>`/`<main>` body wrapper in addition to `<title>` — **do not** use it as a head-only primitive.

**Working directory:** Commands assume `/Users/jonathan/projects/lithuanianquiz/.worktrees/polish-head-tags`. Task 0 creates it.

---

## File structure

**Modify:**
- `ui.py` — `page_shell` gains `page_title` parameter; returns `(Title, Meta×N, Div)` tuple instead of bare `Div`. Adds a module-level constant for the description text.
- `main.py` — every `_render_page(...)` and direct `page_shell(...)` call site passes an explicit `page_title`. `fast_app(title=...)` kwarg removed. The `_not_found` handler gets its own title.
- `tests/test_ui.py` — new assertions for title / meta tags / no-body-h1 regression guard.

**No new files.** No tests delete or rename.

---

## Task 0: Worktree setup

- [ ] **Step 1: Create worktree**

Run (from repo root):
```bash
cd /Users/jonathan/projects/lithuanianquiz
git fetch origin
git worktree add -b polish-head-tags .worktrees/polish-head-tags origin/main
cd .worktrees/polish-head-tags
```

Expected: new branch `polish-head-tags` tracking `origin/main`, worktree at `.worktrees/polish-head-tags`.

- [ ] **Step 2: Confirm baseline**

Run: `uv run --extra dev pytest 2>&1 | tail -3`
Expected: all tests pass (247 at time of writing).

---

## Task 1: Spike — verify FastHTML hoists Title/Meta from the return tuple

Before touching any production code, confirm that FastHTML 0.13.3 hoists `Title(...)` and `Meta(...)` to `<head>` when they're returned alongside body content from a route handler. If not, spec R1 triggers the fallback plan and we escalate.

- [ ] **Step 1: Write the spike as a one-file test script**

Create `/tmp/head_hoist_spike.py`:

```python
"""One-shot spike: does FastHTML hoist Title/Meta to <head>?"""
from starlette.testclient import TestClient
from fasthtml.common import fast_app, Title, Meta, Div

app, rt = fast_app()

@rt("/")
def home():
    return (
        Title("Spike title"),
        Meta(name="description", content="spike description"),
        Div("body content"),
    )

with TestClient(app) as c:
    html = c.get("/").text

print(html)
assert "<title>Spike title</title>" in html, "Title did NOT hoist"
assert '<meta name="description" content="spike description"' in html, "Meta did NOT hoist"
print("\nHOIST OK")
```

- [ ] **Step 2: Run it**

Run: `uv run python /tmp/head_hoist_spike.py 2>&1 | tail -5`
Expected: `HOIST OK` at the end.

If it fails: stop. Escalate — R1 fallback is to use `hdrs=[...]` on `fast_app` with a single static title, which sacrifices per-route titles. Surface this to the plan author rather than improvising.

- [ ] **Step 3: Delete the spike**

Run: `rm /tmp/head_hoist_spike.py`
No commit — spike was throwaway.

---

## Task 2: Add constants and update `page_shell` signature

**Files:**
- Modify: `ui.py` — add constants at module level, add `page_title` param, emit head tuple.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ui.py` (before any existing class, after imports):

```python
class TestPageShellHeadTags:
    def test_page_shell_emits_title(self) -> None:
        html = _render(page_shell("body", page_title="Numbers — Lithuanian Practice"))
        assert "<title>Numbers — Lithuanian Practice</title>" in html

    def test_page_shell_emits_description_meta(self) -> None:
        html = _render(page_shell("body", page_title="Lithuanian Practice"))
        assert '<meta name="description"' in html
        assert "Adaptive Lithuanian practice" in html

    def test_page_shell_emits_og_tags(self) -> None:
        html = _render(page_shell("body", page_title="Lithuanian Practice"))
        assert '<meta property="og:title" content="Lithuanian Practice"' in html
        assert '<meta property="og:description"' in html
        assert '<meta property="og:type" content="website"' in html
        assert '<meta property="og:url" content="https://lithuanian-practice.com/"' in html

    def test_page_shell_does_not_inject_body_h1(self) -> None:
        """Regression guard: using Titled(...) would add a stray body <h1>/<main>
        wrapper. Using explicit Title()/Meta() must not."""
        html = _render(page_shell("body", page_title="Lithuanian Practice"))
        # No <main class="container"> wrapper around body content, and body
        # does not start with the page_title text as an <h1>.
        assert '<main class="container">' not in html
        assert "<h1>Lithuanian Practice</h1>" not in html
```

- [ ] **Step 2: Run to confirm failures**

Run: `uv run --extra dev pytest tests/test_ui.py::TestPageShellHeadTags -v 2>&1 | tail -15`
Expected: all four fail. Most likely error: `TypeError: page_shell() got an unexpected keyword argument 'page_title'`.

- [ ] **Step 3: Add module-level constants at the top of `ui.py`**

Just below the existing imports in `ui.py`, add:

```python
# Site metadata shared across every page.
_DESCRIPTION_META = (
    "Adaptive Lithuanian practice: numbers, age, weather, prices, and time. "
    "Type the answer in Lithuanian; the site adapts to your weak spots."
)
_OG_URL = "https://lithuanian-practice.com/"
```

- [ ] **Step 4: Update `page_shell` signature and return**

Find the `page_shell` function in `ui.py` (near the top, after `_txt` / `_is_lt`). Its current signature looks roughly like:

```python
def page_shell(
    *content: Any,
    user_name: str | None = None,
    active_module: str | None = None,
    lang: str = "en",
    diacritic_tolerant: bool = False,
    current_path: str = "/",
) -> Div:
```

Add `page_title: str = "Lithuanian Practice"` as a kwarg. Change the return type annotation to `tuple[Any, ...]`.

Replace the current `return Div(nav, *content, cls="min-h-screen px-4")` at the end with:

```python
head = (
    Title(page_title),
    Meta(name="description", content=_DESCRIPTION_META),
    Meta(property="og:title", content="Lithuanian Practice"),
    Meta(property="og:description", content=_DESCRIPTION_META),
    Meta(property="og:type", content="website"),
    Meta(property="og:url", content=_OG_URL),
)
body = Div(nav, *content, cls="min-h-screen px-4")
return (*head, body)
```

Make sure `Title` and `Meta` are imported — they come from `fasthtml.common` which is already star-imported at the top.

- [ ] **Step 5: Run the new tests**

Run: `uv run --extra dev pytest tests/test_ui.py::TestPageShellHeadTags -v 2>&1 | tail -10`
Expected: all four pass.

- [ ] **Step 6: Run the full suite**

Run: `uv run --extra dev pytest 2>&1 | tail -10`
Expected: all pass. If any existing test that renders `page_shell(...)` breaks because it now gets a tuple instead of a `Div`, note which tests failed — the test helper `_render` in `tests/test_ui.py` uses `to_xml` which handles tuples fine, but other tests that index into the return value or type-check against `Div` will need adjustment. Fix them in place by adjusting the assertion to match the new tuple shape.

- [ ] **Step 7: Commit**

```bash
git add ui.py tests/test_ui.py
git commit -m "feat(ui): page_shell emits <title> + description/OG meta tags

page_shell gains a page_title parameter and returns a tuple of
(Title, Meta, ..., Div) instead of a bare Div. FastHTML 0.13.3 hoists
Title/Meta siblings of body content into <head> automatically.

Deliberately does NOT use fasthtml.Titled(...) — that primitive also
emits a visible <main class='container'><h1> body wrapper, which
would be a layout regression.

Per-route title plumbing in main.py follows in a later task.
"
```

---

## Task 3: Thread `page_title` through `_render_page` in `main.py`

`_render_page` is the helper that wraps `page_shell` for most routes. Give it a `page_title` param so every caller can specify the page title.

**Files:**
- Modify: `main.py` — `_render_page` signature and body.

- [ ] **Step 1: Update `_render_page`**

Find in `main.py`:

```python
def _render_page(
    session: dict[str, Any],
    *content: Any,
    active_module: str | None = None,
    current_path: str = "/",
) -> Any:
    lang = _ui_lang(session)
    return page_shell(
        *content,
        user_name=session.get("user_name"),
        active_module=active_module,
        lang=lang,
        diacritic_tolerant=_is_diacritic_tolerant(session),
        current_path=current_path,
    )
```

Replace with:

```python
def _render_page(
    session: dict[str, Any],
    *content: Any,
    page_title: str,
    active_module: str | None = None,
    current_path: str = "/",
) -> Any:
    lang = _ui_lang(session)
    return page_shell(
        *content,
        page_title=page_title,
        user_name=session.get("user_name"),
        active_module=active_module,
        lang=lang,
        diacritic_tolerant=_is_diacritic_tolerant(session),
        current_path=current_path,
    )
```

`page_title` is now required (no default) so every call site must pass one. This intentionally fails any route that forgets.

- [ ] **Step 2: Run to see the breakage**

Run: `uv run python -c "import main" 2>&1 | tail -5`
Expected: `TypeError: _render_page() missing 1 required keyword-only argument: 'page_title'` somewhere, since some call sites don't pass it yet.

Run: `uv run --extra dev pytest 2>&1 | tail -15`
Note the failures — these guide Task 4.

---

## Task 4: Pass `page_title` at every call site in `main.py`

Add a language-aware title builder and thread it through every route.

**Files:**
- Modify: `main.py` — add `_page_title` helper, update every `_render_page` call, update direct `page_shell` calls.

- [ ] **Step 1: Add the title builder helper**

Near the other session helpers in `main.py` (after `_t`, before `_render_page`), add:

```python
def _page_title(session: dict[str, Any], en_page: str | None, lt_page: str | None) -> str:
    """Build a language-aware page title.

    Landing and other root-level pages pass (None, None) to get just
    'Lithuanian Practice' / 'Praktika'. Sub-pages pass a module/page name
    in EN and LT and get 'Page — Lithuanian Practice' / 'Page — Praktika'.
    """
    lang = _ui_lang(session)
    root = _t(session, "Lithuanian Practice", "Praktika")
    if en_page is None:
        return root
    page = en_page if lang == "en" else (lt_page or en_page)
    return f"{page} — {root}"
```

- [ ] **Step 2: Grep every `_render_page(` call**

Run: `grep -n "_render_page(" main.py`
Note every hit. Each one needs a `page_title=_page_title(session, ...)` argument.

- [ ] **Step 3: Update each `_render_page` call**

Apply these per route. If a route name isn't listed here, use the same pattern: `page_title=_page_title(session, "<EN name>", "<LT name>")`.

| Route | EN page-name | LT page-name |
|---|---|---|
| `get_home` (`/`) | `None` | `None` |
| `get_about` (`/about`) | `"About"` | `"Apie"` |
| `get_stats` (`/stats`) | `"Stats"` | `"Statistika"` |
| `get_numbers` (`/numbers`, inside `_make_number_routes`) | `"Numbers"` | `"Skaičiai"` |
| `get_time` (`/time`) | `"Time"` | `"Laikas"` |
| `get_age` (`/age`) | `"Age"` | `"Amžius"` |
| `get_weather` (`/weather`) | `"Weather"` | `"Oras"` |
| prices route (`/prices`) | `"Prices"` | `"Kainos"` |
| practice-all route (`/practice-all`) | `"Practice All"` | `"Bendra praktika"` |
| `get_login` (`/login`) | `"Log in"` | `"Prisijungti"` |

Example for `get_home`:

```python
return _render_page(
    session,
    landing_page_content(lang=lang),
    page_title=_page_title(session, None, None),
    active_module="home",
    current_path="/",
)
```

Example for a module route:

```python
return _render_page(
    session,
    main_content,
    page_title=_page_title(session, "Age", "Amžius"),
    active_module="age",
    current_path="/age",
)
```

- [ ] **Step 4: Update the `_not_found` handler**

Find `_not_found` near the top of `main.py`. It calls `page_shell(...)` directly with exception context. Add `page_title=...` to that call:

```python
return page_shell(
    Container(...),
    page_title=tr(
        lang, "Page not found — Lithuanian Practice", "Puslapis nerastas — Praktika"
    ),
    user_name=session.get("user_name"),
    lang=lang,
    diacritic_tolerant=_is_diacritic_tolerant(session),
    current_path=req.url.path if req else "/",
)
```

Note: `_not_found` uses `tr(...)` directly because it's outside a normal session-keyed flow.

- [ ] **Step 5: Remove `fast_app(title=...)`**

Find:
```python
app, rt = fast_app(
    hdrs=[*Theme.green.headers(daisy=True), _custom_css, _favicon, _goatcounter],
    secret_key=os.environ.get("LQ_SECRET_KEY") or secrets.token_urlsafe(32),
    title="Lithuanian Price Quiz",
    exception_handlers={404: _not_found},
)
```

Remove the `title="Lithuanian Price Quiz",` line.

- [ ] **Step 6: Run `import main` and full suite**

Run: `uv run python -c "import main" 2>&1 | tail -3`
Expected: no error.

Run: `uv run --extra dev pytest 2>&1 | tail -10`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add main.py
git commit -m "feat(main): per-route, language-aware page titles

Every _render_page call now passes an explicit page_title built via a
new _page_title(session, en_page, lt_page) helper that returns
'<Page> — Lithuanian Practice' (or LT equivalent) for sub-pages and
just 'Lithuanian Practice' / 'Praktika' for the landing page.

The silently-ignored fast_app(title='Lithuanian Price Quiz') kwarg
is dropped; FastHTML 0.13.3 wasn't honoring it anyway.

_not_found handler gets a dedicated 'Page not found — Lithuanian
Practice' title.
"
```

---

## Task 5: Per-route title regression tests

Add tests that render each route through TestClient and assert the correct `<title>` appears in the response HTML.

**Files:**
- Modify: `tests/test_ui.py` — new tests for end-to-end title rendering.

- [ ] **Step 1: Write the tests**

Append to `tests/test_ui.py`:

```python
class TestRouteTitles:
    def _title_of(self, path: str, accept_lang: str = "en") -> str:
        from starlette.testclient import TestClient
        import main

        with TestClient(main.app, follow_redirects=False) as c:
            if accept_lang == "lt":
                # Flip session language via /set-language first.
                c.get("/set-language?lang=lt")
            r = c.get(path)
            import re

            m = re.search(r"<title>([^<]*)</title>", r.text)
            assert m, f"no <title> found on {path}"
            return m.group(1)

    def test_home_title_en(self) -> None:
        assert self._title_of("/") == "Lithuanian Practice"

    def test_home_title_lt(self) -> None:
        assert self._title_of("/", accept_lang="lt") == "Praktika"

    def test_numbers_title_en(self) -> None:
        assert self._title_of("/numbers") == "Numbers — Lithuanian Practice"

    def test_numbers_title_lt(self) -> None:
        assert self._title_of("/numbers", accept_lang="lt") == "Skaičiai — Praktika"

    def test_age_title_en(self) -> None:
        assert self._title_of("/age") == "Age — Lithuanian Practice"

    def test_weather_title_en(self) -> None:
        assert self._title_of("/weather") == "Weather — Lithuanian Practice"

    def test_time_title_en(self) -> None:
        assert self._title_of("/time") == "Time — Lithuanian Practice"

    def test_prices_title_en(self) -> None:
        assert self._title_of("/prices") == "Prices — Lithuanian Practice"

    def test_stats_title_en(self) -> None:
        assert self._title_of("/stats") == "Stats — Lithuanian Practice"

    def test_about_title_en(self) -> None:
        assert self._title_of("/about") == "About — Lithuanian Practice"

    def test_login_title_en(self) -> None:
        # /login redirects to / when a session is authed; fresh TestClient
        # starts anonymous, so this should render the login page title.
        assert self._title_of("/login") == "Log in — Lithuanian Practice"

    def test_not_found_title_en(self) -> None:
        assert self._title_of("/nonexistent") == "Page not found — Lithuanian Practice"
```

- [ ] **Step 2: Run**

Run: `uv run --extra dev pytest tests/test_ui.py::TestRouteTitles -v 2>&1 | tail -25`
Expected: all pass.

- [ ] **Step 3: Full suite + ruff**

Run: `uv run --extra dev pytest && uv run --extra dev ruff check . && uv run --extra dev ruff format --check .`
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add tests/test_ui.py
git commit -m "test(ui): end-to-end assertions for per-route page titles

Renders each route through Starlette TestClient and asserts the
<title> string matches the per-route, language-aware expectation.
Covers all five modules plus home / stats / about / login / 404,
in both EN and LT where relevant."
```

---

## Task 6: Local smoke + PR

- [ ] **Step 1: Local smoke — title value on home**

Run:
```bash
uv run python -c "
from starlette.testclient import TestClient
import main
with TestClient(main.app) as c:
    import re
    t = re.search(r'<title>([^<]*)</title>', c.get('/').text).group(1)
    print('home:', t)
    t = re.search(r'<title>([^<]*)</title>', c.get('/numbers').text).group(1)
    print('numbers:', t)
    # Meta assertions
    html = c.get('/').text
    assert '<meta name=\"description\"' in html
    assert 'og:title' in html and 'Lithuanian Practice' in html
    assert 'og:description' in html
    assert 'og:type' in html
    assert 'og:url' in html
    print('meta tags: OK')
"
```

Expected:
```
home: Lithuanian Practice
numbers: Numbers — Lithuanian Practice
meta tags: OK
```

- [ ] **Step 2: Push**

Run:
```bash
git push -u origin polish-head-tags
```

- [ ] **Step 3: Open PR**

Run:
```bash
gh pr create --base main --head polish-head-tags \
  --title "feat: per-route page titles + description/OG meta (polish α)" \
  --body "$(cat <<'EOF'
## Summary

Implements spec §PR α of `docs/superpowers/specs/2026-04-17-polish-bucket-design.md`.

- Replaces the default `<title>FastHTML page</title>` with correct, per-route, language-aware titles (e.g. `Numbers — Lithuanian Practice`, `Skaičiai — Praktika`).
- Adds `<meta name=\"description\">` and Open Graph tags (`og:title`, `og:description`, `og:type`, `og:url`) to every page.
- Uses explicit `Title(...)` / `Meta(...)` FastHTML primitives in \`page_shell\`'s return tuple (hoists to \`<head>\` automatically). Deliberately avoids `Titled(...)` — it would emit a visible \`<h1>\`/\`<main>\` body wrapper.
- Removes the \`fast_app(title=\"Lithuanian Price Quiz\")\` kwarg, which FastHTML 0.13.3 was silently ignoring anyway.
- Viewport meta untouched — already emitted by MonsterUI.

## Test plan

- [x] All existing tests pass
- [x] New \`TestPageShellHeadTags\` assertions hold
- [x] New \`TestRouteTitles\` parametrised end-to-end assertions hold for every route in both EN and LT
- [x] No-body-h1 regression guard (catches accidental \`Titled(...)\` fallback)
- [ ] Production smoke: curl / and verify correct title/meta in HTML

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Wait for CI, merge when green, deploy**

Wait for `gh pr checks <pr-number>` to pass. Then:
```bash
gh pr merge <pr-number> --squash
cd /Users/jonathan/projects/lithuanianquiz
git checkout main
git pull --ff-only origin main
git worktree remove .worktrees/polish-head-tags
git branch -d polish-head-tags
git push origin --delete polish-head-tags
railway up --detach
```

Poll `railway service status` until `SUCCESS`.

- [ ] **Step 5: Production smoke**

Run:
```bash
curl -sS https://lithuanian-practice.com/ | grep -oE "<title[^<]*</title>" | head -1
curl -sS https://lithuanian-practice.com/ | grep -oE "<meta name=\"description\"[^>]*>"
curl -sS https://lithuanian-practice.com/numbers | grep -oE "<title[^<]*</title>"
```

Expected:
```
<title>Lithuanian Practice</title>
<meta name="description" content="Adaptive Lithuanian practice: ...">
<title>Numbers — Lithuanian Practice</title>
```

---

## Self-review notes

**Spec coverage:**
- Per-route titles with EN/LT variants → Task 4 Step 3 table + Task 5 tests.
- Description + OG tags → Task 2 constants + `page_shell` return.
- `_not_found` title → Task 4 Step 4.
- `fast_app(title=...)` removed → Task 4 Step 5.
- No `Titled(...)` → Task 2 Step 4 uses explicit `Title()`/`Meta()`; Task 2 Step 1 includes the no-body-h1 regression test.
- Viewport not modified → no task (already emitted by MonsterUI).

**Placeholder scan:** no TBD / "similar to task N" / "fill in details" — every step has concrete code.

**Type consistency:** `page_shell(...page_title: str = ...)` signature used consistently in Task 2, Task 4, Task 5. `_render_page(...page_title: str)` (no default, required) used consistently in Task 3, Task 4. `_page_title(session, en_page, lt_page)` signature used consistently in Task 4 Step 1 definition and all Step 3 call-site examples.
