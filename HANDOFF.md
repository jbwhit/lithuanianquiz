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
main.py            — App init, routes, session helpers (prices + time)
auth.py            — Google OAuth, QuizOAuth, DB helpers (users/user_progress)
quiz.py            — Price exercise engine (no FastHTML dependency)
time_engine.py     — Time exercise engine + adaptive (no FastHTML dependency)
adaptive.py        — Thompson Sampling adaptive selector (prices)
ui.py              — All UI as plain functions (no classes)
time_reference.py  — Generates all time expressions for native speaker review
tests/             — pytest suite (77 tests: 31 price, 46 time)
.githooks/         — Pre-commit hook (auto ruff format)
lithuanian_data.db — SQLite: numbers table + users + user_progress
.env               — GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET (gitignored)
.env.example       — committed empty template
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

### Multi-module pattern
- Each module (prices, time) gets its **own engine class** — prices are DB-driven,
  time is algorithmic. No shared base class needed.
- Session keys are namespaced with `time_` prefix for time module — keeps stats
  independent.
- Time has its own Thompson Sampling in `time_engine.py` (not shared with
  `adaptive.py`) since the exercise space is different.
- `save_progress`/`load_progress` in `auth.py` persist both modules to the same
  `user_progress` row as a single JSON blob.

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

### Session cookie size limits (critical)
FastHTML uses Starlette `SessionMiddleware`, which stores the **entire session**
in a signed cookie. Browser cookie limits are roughly ~4KB per cookie. If the
session grows too large, writes become unreliable and users can see stale state
(for example: answer feedback appears to use a previous question/answer).

Symptoms seen in production:
- Happens after enough answers/history accumulate (especially in `practice-all`)
- Current question and correctness checks feel "out of sync"

Mitigations implemented in PR #2:
- Cap module histories in session to last **5** entries (`main.py`)
- Cap loaded/saved persisted histories to last **5** entries (`auth.py`)
- In `practice-all`, keep only active-module transient question keys; drop stale
  per-module question keys before generating the next mix question
- Do **not** eagerly initialize all module sessions inside `/stats`

Debug rule of thumb:
- If answer checking seems stale, inspect session/cookie payload size first
  before debugging engine logic.

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

## 5. Product Vision

**Lithuanian Practice is a small, grammar-aware practice tool for number-centered Lithuanian expression.** It prioritizes correctness, clarity, and repeatable daily use over breadth, gamification, or multimedia features.

### Guiding constraints
- Single-purpose per module, minimal UI, high-quality linguistic feedback
- Every new feature must pass: *"Does this make the app better at focused Lithuanian practice, without making it feel like a bloated language platform?"*
- Prefer a few excellent exercise modes over feature sprawl

### Roadmap (incremental, stay micro)
1. ~~**Time**~~ — **Done.** Whole hours, half past, quarter past, quarter to. See `TIME_MODULE_SPEC.md`.
2. **Dates** — day + month expressions, written/spoken variants
3. **Quantified nouns** — "5 books", "2 cups" — only if it stays minimal

### Architecture note
Each module gets its **own engine class** (not a refactor of `ExerciseEngine`). The price engine is DB-driven; time is algorithmic. Shared layers: routing, session management, UI patterns. Each module has its own adaptive tracking.

---

## 6. Open Questions / Loose Ends

- **Native speaker review of time expressions** — Run `uv run python time_reference.py`
  to generate all 48 time expressions. Key question: is "Pusė trečios" (ordinal
  genitive) or "Pusė trijų" (cardinal genitive) the standard form for half past?
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

---

## Key URLs
| | |
|---|---|
| Live app | https://lithuanian-practice.com |
| GoatCounter | https://jbwhit.goatcounter.com |
| GitHub repo | https://github.com/jbwhit/lithuanianquiz |
| Railway dashboard | https://railway.com/project/87f24bff-8f22-484f-b481-38c83518cd10 |
| Google OAuth credentials | https://console.cloud.google.com → APIs & Services → Credentials |
