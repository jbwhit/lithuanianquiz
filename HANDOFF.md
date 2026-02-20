# Lithuanian Quiz — Project Handoff

Context document for a new Claude Code session. Covers the full conversation
history that built this project from a basic quiz into a deployed, auth-enabled
web app.

---

## 1. Workflow Preferences

- **Auto commit + push + deploy**: When asked to commit, always push immediately
  after and deploy to Railway without asking for confirmation.
- **Plan mode for significant changes**: Uses `/plan` before non-trivial
  implementations. Switches to Opus for planning, back to Sonnet for execution.
  Approves the plan before execution begins.
- **"What's next?" cadence**: Jonathan asks open-ended "what's next?" questions
  and expects a short ranked list of options with rationale, not immediate action.
- **Concise communication**: Short responses preferred. No bullet-point padding.
  Get to the point.
- **End-to-end ownership**: Claude is expected to handle the full cycle —
  code, lint, test, commit, push, deploy, verify. Don't stop halfway.
- **Ask before big UX decisions**: Collapsible vs always-visible, navbar vs
  footer — use `AskUserQuestion` to settle placement/style choices.
- **No over-engineering**: Don't add abstractions, docstrings, or cleanup beyond
  the explicit request.

---

## 2. Tech Stack & Tools

### App
| Layer | Choice |
|---|---|
| Framework | FastHTML (`python-fasthtml>=0.12.1`) |
| UI components | MonsterUI (`monsterui>=1.0.7`) with DaisyUI + Tailwind |
| DB | SQLite via fastlite (`fastlite>=0.1.1`) |
| Auth | `fasthtml.oauth.GoogleAppClient` + custom `QuizOAuth(OAuth)` |
| Adaptive learning | Thompson Sampling (numpy), hand-rolled in `adaptive.py` |
| Env vars | `python-dotenv` — loaded in `auth.py` at module level |

### Dev tooling
| Tool | Usage |
|---|---|
| `uv` | **Only** package manager — never pip/poetry/conda |
| `ruff` | Lint + format (line-length 88). Run: `uv run ruff check .` |
| `pytest` | Tests in `tests/`. Run: `uv run pytest` |
| `railway` CLI | Deploy: `railway up --detach`, status: `railway service status` |
| GoatCounter | Analytics at https://jbwhit.goatcounter.com |

### Project structure
```
main.py          — App init, routes, session helpers
auth.py          — Google OAuth, QuizOAuth, DB helpers (users/user_progress)
quiz.py          — Exercise engine (no FastHTML dependency)
adaptive.py      — Thompson Sampling adaptive selector
ui.py            — All UI as plain functions (no classes)
tests/           — pytest suite (31 tests)
lithuanian_data.db — SQLite: numbers table + users + user_progress
.env             — GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET (gitignored)
.env.example     — committed empty template
```

### Railway setup
- Project: `lithuanianquiz2`, Service: `lithuanian-practice`
- Domain: `https://lithuanian-practice.com`
- Google OAuth redirect URI: `https://lithuanian-practice.com/redirect`
- Env vars set via: `railway variables --set "KEY=value"`
- Link project: `railway link --project lithuanianquiz2`
- Link service: `railway service link lithuanian-practice`
- Config file: `~/.railway/config.json` (has project/service IDs if CLI gets confused)
- Railway runs **Python 3.12** (local is 3.13 — matters for stdlib differences)

---

## 3. Things That Went Well

### FastHTML patterns
- **HTMX partial swaps**: `/answer` returns `(quiz_area(...), oob_stats)` — the
  OOB div has `hx_swap_oob="true"` and matches `id="stats-panel"`. Clean and fast.
- **Session injection**: Unannotated `session` parameter in route handlers —
  FastHTML injects it automatically. Works perfectly.
- **`load_dotenv()` placement**: Called in `auth.py` after imports, before
  module-level `GoogleAppClient(os.environ.get(...))`. Avoids E402 lint errors
  in `main.py` entirely.

### OAuth design
- `QuizOAuth.redir_login()` returns `None` → unauthenticated users can use the
  quiz freely; login is optional for cross-session persistence.
- `QuizOAuth.logout()` returns `RedirectResponse("/")` directly — doesn't call
  `redir_login()`, so logout goes home rather than breaking.
- `get_auth()` returns `RedirectResponse("/", status_code=303)` — correct; not
  `True` (which would produce a blank 200 response).
- Auth keys (`auth`, `user_name`, `user_email`) are preserved across reset by
  saving them before clearing the session and restoring after.

### UX
- Emoji favicon (`🇱🇹`) via inline SVG data URI — no image file needed.
- `autocomplete="off"` on the answer input stops browser from suggesting
  previous Lithuanian answers.
- `<details>`/`<summary>` for collapsible examples — native browser behaviour,
  zero JS needed.

---

## 4. Things to Avoid / Watch Out For

### FastHTML session injection
**Never** annotate `session` in route handlers:
```python
def get(session) -> Any:          # ✅ FastHTML injects correctly
def get(session: dict) -> Any:    # ❌ treated as a form field → 400 error
```
Helper functions *outside* route handlers can use `session: dict[str, Any]` fine.

Source: `fasthtml/core.py` line ~181:
```python
if anno is empty:
    if 'session'.startswith(arg.lower()): return req.scope.get('session', {})
```

### Python 3.12 vs 3.13 — `datetime.UTC`
Railway runs Python 3.12. After `from datetime import datetime`, `datetime.UTC`
raises `AttributeError` — it's a module-level attribute, not a class attribute.

```python
from datetime import UTC, datetime   # ✅
datetime.now(UTC)

from datetime import datetime        # ❌ after ruff UP017 auto-fix
datetime.now(datetime.UTC)           # AttributeError on Py 3.12
```

Ruff's `UP017` auto-fix gets this wrong when the import is `from datetime import datetime`.
Add `from datetime import UTC, datetime` and use `UTC` directly.

### DaisyUI alert contrast
`bg-error/10` and `bg-success/10` are nearly invisible on the green theme.
Use `bg-error/20` + `border-2 border-error/40` instead. Drop `alert alert-error`
DaisyUI classes — they fight custom opacity.

### Railway CLI quirks
- `railway link` is non-interactive in CI mode — use `--project` flag.
- `railway service link <name>` must be run separately after `railway link`.
- `railway variables --set` triggers an automatic redeploy.
- `railway up --detach` uploads and starts build; poll with `railway service status`.
- If service is `null` in `~/.railway/config.json`, query the GraphQL API or
  use `railway service link <service-name>` to reconnect.
- `uv sync` without `--extra dev` removes pytest/ruff — always use
  `uv sync --extra dev` locally.

### OAuth `skip` list
`OAuth.__init__` defaults `skip=['/redirect', '/error', '/login']` — these paths
bypass the `before` hook. Don't put routes that need auth in this list.

---

## 5. Open Questions / Loose Ends

- **`/error` route is unhandled** — if OAuth fails (e.g. user denies consent),
  they land on `/error` which returns a 404. A simple friendly page with a
  "Try again" link would polish this.
- **Mobile UX untested** — the layout hasn't been checked on a phone. The stats
  panel in particular (4-column grid) may be cramped.
- **Spellcheck on answer input** — `autocomplete="off"` was added, but
  `spellcheck="false"` and `autocorrect="off"` (Safari) might also help avoid
  autocorrect mangling Lithuanian words on mobile.
- **More vocabulary** — currently 99 number rows and 5 items (knyga, puodelis,
  marškinėliai, žurnalas, kepurė). Could expand price ranges or add cent values.
- **`/about` page has a "Back to Practice" button but no link from the home page
  to About** beyond the navbar — fine as-is but worth noting.
- **GoatCounter** just added — no baseline data yet. Check https://jbwhit.goatcounter.com
  after a week to see if traffic is real.

---

## Key URLs
| | |
|---|---|
| Live app | https://lithuanian-practice.com |
| GoatCounter | https://jbwhit.goatcounter.com |
| GitHub repo | https://github.com/jbwhit/lithuanianquiz |
| Railway dashboard | https://railway.com/project/87f24bff-8f22-484f-b481-38c83518cd10 |
| Google OAuth credentials | https://console.cloud.google.com → APIs & Services → Credentials |
