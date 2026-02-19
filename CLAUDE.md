# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Adaptive Lithuanian price quiz app built with FastHTML + MonsterUI.

### File structure

- `main.py` — App init, routes, session helpers (~120 lines)
- `quiz.py` — Exercise engine: generation, answer checking, diffs (no FastHTML dependency)
- `adaptive.py` — Thompson Sampling adaptive learning engine
- `ui.py` — UI component functions (plain functions, not classes)
- `tests/test_quiz.py` — Tests for quiz engine
- `tests/test_adaptive.py` — Tests for adaptive learning
- `db_manager.py` — Offline tooling for DB updates (kept as-is)
- `get_csvs.py` — Offline tooling for CSV export (kept as-is)
- `lithuanian_data.db` — 99 rows of Lithuanian number forms (static data)

### Architecture

- **Cookie sessions** via FastHTML's built-in `SessionMiddleware` (no custom session DB)
- **HTMX partial swaps** — `/answer` returns inline feedback + next question + OOB stats update
- **Functions over classes** — UI components are plain functions in `ui.py`
- **Data loaded once** at startup (`ALL_ROWS` from `lithuanian_data.db`)

### Commands

- `uv sync` — install dependencies
- `uv run pytest` — run tests
- `uv run ruff check .` — lint
- `uv run ruff format .` — format
- `uv run python main.py` — start dev server on localhost:5001

## Python Conventions

- Use **uv** exclusively for package management (never pip/poetry/conda)
- **ruff** for formatting (line length 88) and linting; **pytest** for tests
- Type hints on all function signatures
- `pathlib.Path` over `os.path`
- `logging` module over `print`
- Commit and push when a logical chunk of work is completed
