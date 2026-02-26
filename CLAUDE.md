# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Adaptive Lithuanian practice app built with FastHTML + MonsterUI. Six modules: **Numbers 1-20**, **Numbers 1-99**, **Age**, **Weather**, **Prices**, and **Time**.

### File structure

- `main.py` — App init, routes, session helpers (prices + time)
- `auth.py` — Google OAuth client, `QuizOAuth`, DB helpers for user/progress persistence
- `quiz.py` — Price exercise engine: generation, answer checking, diffs (no FastHTML dependency)
- `time_engine.py` — Time exercise engine: algorithmic generation, Thompson Sampling (no FastHTML dependency)
- `number_engine.py` — Number word exercise engine: produce/recognize, Thompson Sampling (no FastHTML dependency)
- `age_engine.py` — Age exercise engine: dative pronouns + number words + metai/metų, Thompson Sampling (no FastHTML dependency)
- `weather_engine.py` — Weather temperature exercise engine: number words + laipsnis/laipsniai/laipsnių, Thompson Sampling (no FastHTML dependency)
- `adaptive.py` — Thompson Sampling adaptive learning engine (prices)
- `ui.py` — UI component functions (plain functions, not classes)
- `time_reference.py` — Standalone script to generate all time expressions for native speaker review
- `tests/test_quiz.py` — Tests for price quiz engine
- `tests/test_time.py` — Tests for time engine + adaptive
- `tests/test_adaptive.py` — Tests for price adaptive learning
- `tests/test_numbers.py` — Tests for number engine
- `tests/test_age.py` — Tests for age engine
- `tests/test_weather.py` — Tests for weather engine
- `db_manager.py` — Offline tooling for DB updates (kept as-is)
- `get_csvs.py` — Offline tooling for CSV export (kept as-is)
- `lithuanian_data.db` — 99 rows of Lithuanian number forms + `users` + `user_progress` tables
- `.githooks/pre-commit` — Auto-formats Python files with ruff on commit
- `.env` — Local secrets (gitignored): `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `.env.example` — Committed template with empty values
- `HANDOFF.md` — Full project context doc for onboarding new sessions
- `TIME_MODULE_SPEC.md` — Implementation spec for the time module

### Architecture

- **Landing page** at `/` with module cards; Numbers at `/numbers-20` & `/numbers-99`, Age at `/age`, Weather at `/weather`, Prices at `/prices`, Time at `/time`
- **Six modules**: Numbers 1-20 (`/numbers-20`), Numbers 1-99 (`/numbers-99`), Age (`/age`), Weather (`/weather`), Prices (`/prices`), Time (`/time`) — each with own engine, adaptive tracking, and session state
- **Google OAuth** via `fasthtml.oauth.GoogleAppClient` + `QuizOAuth(OAuth)` — optional login for cross-session persistence
- **User progress persisted** to `user_progress` table in SQLite (both price and time data, loaded on login, saved on answer/reset)
- **Cookie sessions** via FastHTML's built-in `SessionMiddleware` (no custom session DB)
- **HTMX partial swaps** — `/answer` and `/time/answer` return inline feedback + next question + OOB stats update
- **Functions over classes** — UI components are plain functions in `ui.py`
- **Data loaded once** at startup (`ALL_ROWS` from `lithuanian_data.db` for prices; time is algorithmic)

### Setup

- `git config core.hooksPath .githooks` — enable pre-commit hook (auto-formats Python with ruff)

### Commands

- `uv sync --extra dev` — install dependencies including pytest/ruff (`uv sync` alone removes dev tools)
- `uv run pytest` — run tests
- `uv run ruff check .` — lint
- `uv run ruff format .` — format
- `uv run python main.py` — start dev server on localhost:5001

### Deployment (Railway)

- Project: `lithuanianquiz2`, Service: `lithuanian-practice`
- Domain: `https://lithuanian-practice.com` — **Railway runs Python 3.12** (local is 3.13)
- Link: `railway link --project lithuanianquiz2 && railway service link lithuanian-practice`
- Deploy: `railway up --detach` then poll `railway service status`
- Env vars: `railway variables --set "KEY=value"` (triggers auto-redeploy)
- Analytics: GoatCounter at https://jbwhit.goatcounter.com

## Python Conventions

- Use **uv** exclusively for package management (never pip/poetry/conda)
- **ruff** for formatting (line length 88) and linting; **pytest** for tests
- Type hints on all function signatures
- `pathlib.Path` over `os.path`
- `logging` module over `print`
- Commit and push when a logical chunk of work is completed
