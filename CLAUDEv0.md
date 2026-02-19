# CLAUDE.md — Lithuanian Language Learning App

## Project Overview

An adaptive Lithuanian language learning web application that helps users master price-expression grammar (e.g. *kiek kainuoja* / *kokia kaina*) using **Thompson Sampling** to intelligently target each user's weak areas. Built with **FastHTML** + **MonsterUI** + **SQLite** (via fastlite).

This is Jonathan's personal project. The app is currently a functional prototype (monolithic `main.py`) undergoing planned modernization into a modular structure.

---

## Tech Stack

| Layer | Library/Tool |
|---|---|
| Web framework | `python-fasthtml` (Starlette + HTMX + FastTags) |
| UI components | `monsterui` (FrankenUI + Tailwind + DaisyUI) |
| Database | SQLite via `fastlite` |
| Adaptive engine | Thompson Sampling (beta distributions, in-session) |
| Linting | `ruff` (pre-commit hook active) |
| Testing | `pytest` (planned, not yet comprehensive) |

**Key docs are in the project directory:**
- `fasthtml-llms-cts.txt` — FastHTML API reference
- `monsterui-llms-ctx.txt` — MonsterUI component reference

Always read these before making UI or routing changes. They are the canonical source of truth for these libraries.

---

## Running the App

```bash
python main.py           # runs on http://localhost:5001
```

FastHTML uses `serve()` at the bottom of `main.py` — do **not** wrap in `if __name__ == "__main__"`, that's handled internally.

---

## Architecture (Current State)

The app is a **monolithic `main.py`** with these logical sections:

### Classes

**`SessionManager`**
- Manages all session state (exercise history, stats, current exercise)
- Keeps history capped at last 50 entries
- Initializes with default values on first visit

**`DatabaseManager`**
- Wraps fastlite SQLite operations
- Handles exercise retrieval, performance logging
- Tables: exercises, user_performance (per exercise_type, case, number_pattern)

**`AdaptiveLearningService`**
- Implements Thompson Sampling over beta distributions
- Arms = exercise types × grammatical cases × number patterns
- Initialized with α=1, β=1 (one assumed incorrect answer per arm)
- **80% exploitation** (sample lowest-performing arm) / **20% exploration** (random)
- Meaningful adaptation kicks in after ~10 answered questions

**UI Components (static methods on `UIComponents`)**
- `question_card()` — renders exercise with answer form
- `feedback_card()` — shows correct/incorrect with diff highlighting
- `stats_panel()` — performance breakdown by category
- `app_header()` — NavBar with MonsterUI

### Routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Main exercise page |
| POST | `/submit` | Submit answer, return feedback via HTMX |
| GET | `/next` | Load next exercise (HTMX partial) |
| GET | `/stats` | Performance dashboard |

### Session Flow

1. First visit → `SessionManager` initializes, random exercise selected
2. Answer submitted → session updated, feedback rendered as HTMX swap
3. "Next" clicked → `AdaptiveLearningService` selects next exercise
4. Session persists answer history and beta distribution state (α/β per arm)

---

## Exercise Structure

```
Numbers (top category)
└── Exercise Types: kiek_kainuoja, kokia_kaina
    └── Grammatical Cases: accusative, nominative, genitive, ...
        └── Number Patterns: single_digit, decades, special, teens, ...
```

Each exercise has: `question`, `correct_answer`, `exercise_type`, `case`, `number_pattern`

---

## Known Issues / Technical Debt

1. **Debug print statements** still scattered through session management code — remove before production
2. **Nested try/except blocks** in `submit_answer()` — fragile, needs flattening
3. **Session reliability**: there was a workaround using `cookie('session_updated', '1', max_age=1)` + `RedirectResponse` to force session persistence — verify if still needed with current FastHTML version
4. **Monolithic structure**: all logic in one file, makes testing hard

---

## Planned Modernization (5-Phase Plan)

The codebase is slated for a major refactor. Phases:

**Phase 1 — Preparation**
- Backup DB, set up `.gitignore`, create `requirements.txt`
- Tag current working version: `git tag -a v1.0-pre-upgrade`

**Phase 2 — Modular Restructure**
```
project/
├── main.py              # App init + route wiring only
├── config.py            # Constants, DB path, session config
├── models/
│   ├── exercise.py      # Exercise dataclass
│   └── user_stats.py    # Stats dataclass
├── services/
│   ├── adaptive.py      # Thompson Sampling engine
│   ├── session.py       # SessionManager
│   └── database.py      # DatabaseManager
├── ui/
│   ├── components.py    # Reusable FT components
│   └── pages.py         # Full page renders
└── tests/
    ├── test_adaptive.py
    └── test_database.py
```

**Phase 3 — Testing**
- `pytest` unit tests for adaptive algorithm
- Simulation framework: create synthetic user with known weak area, verify Thompson Sampling converges

**Phase 4 — Performance**
- DB query caching
- Session state compression
- Add indexes on `exercise_type`, `case`, `number_pattern`

**Phase 5 — Future Features**
- Google Auth (user accounts replacing anonymous sessions)
- Age / time / year exercise types
- Spaced repetition
- Audio pronunciation

---

## FastHTML Patterns to Follow

```python
# Import
from fasthtml.common import *

# App init with MonsterUI
from monsterui.all import *
app, rt = fast_app(
    hdrs=Theme.green.headers(daisy=True),
    session_cookie="lt_session",
    max_age=86400
)

# Routes — use function name as path (no need to pass path string)
@rt
def index(session): ...  # GET /index

@rt
def submit(session, answer: str): ...  # POST /submit

# HTMX partial return (no full page wrapper needed)
@rt
def next_exercise(session):
    return Div(question_card(...), id="exercise-area")

# Run
serve()
```

**Important FastHTML gotchas:**
- It is NOT FastAPI — don't use Pydantic models or `async def` patterns from FastAPI
- Return FT components directly; FastHTML renders them automatically
- For HTMX swaps, return just the target component — no need for full HTML document
- `Titled()` already wraps in `Container` + sets `<title>` — don't double-wrap

---

## MonsterUI Patterns to Follow

```python
# Theme
Theme.green.headers(daisy=True)   # sets up FrankenUI + Tailwind + DaisyUI

# Cards
Card(CardHeader(...), CardBody(...), cls=(CardT.hover, "shadow-lg"))

# Alerts / feedback
Alert("Correct!", cls=AlertT.success)
Alert("Try again", cls=AlertT.error)

# Typography
P("text", cls=TextT.lead)

# Buttons
Button("Submit", cls=ButtonT.primary)
Button("Next →", hx_get="/next", hx_target="#exercise-area", hx_swap="outerHTML")

# NavBar
NavBar(...)
```

Always check `monsterui-llms-ctx.txt` for current component signatures before using — the API has changed across versions.

---

## Adaptive Algorithm Reference

Thompson Sampling implementation:

```python
# Each "arm" is a (exercise_type, case, number_pattern) tuple
# Beta distribution: Beta(alpha, beta) where:
#   alpha = successes + 1
#   beta  = failures + 1  (initialized to 1 = one assumed failure)

# Selection (exploitation arm):
samples = {arm: np.random.beta(alpha[arm], beta[arm]) for arm in arms}
worst_arm = min(samples, key=samples.get)  # lowest sample = weakest area

# Update after answer:
if correct:
    alpha[arm] += 1
else:
    beta[arm] += 1

# Exploration vs exploitation:
import random
if random.random() < 0.20 or total_answers < 10:
    return random_exercise()
else:
    return exercise_for_arm(worst_arm)
```

---

## Linting & Commits

Pre-commit hooks run `ruff`. Before committing:

```bash
ruff check . --fix     # auto-fix what it can
ruff check .           # verify clean
git add -A && git commit -m "your message"
```

Common ruff gotchas in this codebase:
- Use `from typing import Type, Optional, List` explicitly (don't rely on builtins for older Python)
- Modern union syntax `X | Y` preferred over `Optional[X]`
- Functions with cyclomatic complexity > ~10 will be flagged — break them up

---

## PRD Summary (What Matters for Implementation)

- **MVP scope**: price exercises only (`kiek_kainuoja`, `kokia_kaina`)
- **Auth**: Google Auth (not yet implemented — currently session-only)
- **Success metrics to keep in mind**: 15% accuracy improvement after 10 sessions, algorithm demonstrably converges on user weak areas
- **Rollout order**: prices → ages → time → years
- **Do not expose** the hierarchical exercise system in the UI — users select by topic, not by case/pattern

---

## What's NOT Done Yet (from todo.md)

High priority open items:
- [ ] Database schema for hierarchical tracking (exercise_type + case + number_pattern tables)
- [ ] Google Auth integration
- [ ] Performance visualization / progress dashboard
- [ ] pytest test suite for adaptive algorithm
- [ ] Modular file structure (currently monolithic)
- [ ] `requirements.txt` / proper dependency pinning

---

## Conversation History Notes

Prior conversations in this project have covered:
- Multiple debugging sessions on session management and form submission reliability
- A full library upgrade plan (FastHTML + MonsterUI) with rollback strategy — see branch `upgrade-libraries`
- A pricing/premium feature design (one-time Stripe payment, anonymous user IDs)
- A `db_manager.py` script for database migrations with `ruff`-compliant code

When referencing past work, use `conversation_search` with the project knowledge tool to find specifics.
