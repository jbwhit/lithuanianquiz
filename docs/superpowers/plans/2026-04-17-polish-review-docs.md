# Polish PR γ — Native-Speaker Review Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a single generator script that emits two review documents — `docs/reviews/exercise-reference.md` (representative, cross-module, ~66 rows) and `docs/reviews/time-reference.md` (exhaustive, 48 rows) — retire `time_reference.py`, and gate both docs with a CI regression test.

**Architecture:** `scripts/generate_exercise_reference.py` imports the engines directly (`NumberEngine`, `AgeEngine`, `WeatherEngine`, `ExerciseEngine`, `TimeEngine`) and calls their existing `format_question` / `correct_answer` methods. Representative mode walks explicit per-module tuple lists; exhaustive time mode iterates all 12 hours × 4 types. Both docs are written to `docs/reviews/` and committed. A single regression test regenerates both in-process and asserts byte equality with the committed outputs.

**Tech Stack:** Python stdlib + existing engine modules. No new deps.

**Background reading:**
- `docs/superpowers/specs/2026-04-17-polish-bucket-design.md` §PR γ — the spec this plan implements.
- `time_reference.py` (current root-level script) — its exhaustive output is what the new time-reference doc replaces.
- Existing `LITHUANIAN_INTERFACE_REVIEW_REFERENCE.md` covers interface chrome (navbar, card labels, modal copy) — untouched by this PR.

**Working directory:** Commands assume `/Users/jonathan/projects/lithuanianquiz/.worktrees/polish-review-docs`. Task 0 creates it.

---

## File structure

**Create:**
- `scripts/generate_exercise_reference.py` — single generator, two outputs.
- `docs/reviews/exercise-reference.md` — committed output, representative.
- `docs/reviews/time-reference.md` — committed output, exhaustive.

**Delete:**
- `time_reference.py` (repo root) — superseded.

**Modify:**
- `CLAUDE.md` — file-structure section references `time_reference.py`; update to point at the generator + doc.
- `HANDOFF.md` — if it mentions `time_reference.py`, update.
- `FUTURE_MODULES.md` — the "Native Speaker Spot Check" section references `time_reference.py`; update.
- `tests/test_regressions.py` — add one test that re-runs the generator and diffs against both committed docs.

---

## Task 0: Worktree setup + context scan

- [ ] **Step 1: Create worktree**

Run:
```bash
cd /Users/jonathan/projects/lithuanianquiz
git fetch origin
git worktree add -b polish-review-docs .worktrees/polish-review-docs origin/main
cd .worktrees/polish-review-docs
```

- [ ] **Step 2: Grep repo-wide for `time_reference` references**

Run: `grep -rn "time_reference" --include="*.md" --include="*.py" . 2>&1 | grep -v ".venv" | grep -v ".worktrees"`
Expected hits: `time_reference.py` itself, `CLAUDE.md`, `HANDOFF.md`, `FUTURE_MODULES.md`. Any hit in another file needs updating in Task 5.

- [ ] **Step 3: Read the existing `time_reference.py`**

Run: `cat time_reference.py`
Note the output format it produces; the new generator's time section should cover the same information (every hour × every time type with correct-answer strings).

---

## Task 1: Generator skeleton + representative exercise tuples

**Files:**
- Create: `scripts/generate_exercise_reference.py`

Start with a script that (a) builds the representative exercises doc in-memory and prints it to stdout, (b) has no side effects yet. Adding file writes happens in Task 2.

- [ ] **Step 1: Create the script**

Write `scripts/generate_exercise_reference.py`:

```python
"""Generate native-speaker review docs for exercise content.

Produces two Markdown files under docs/reviews/:

* exercise-reference.md — representative exercises across every module,
  grouped by taxonomy branch. ~66 rows total. For cross-module review.
* time-reference.md — exhaustive enumeration of all 48 time expressions
  (12 hours × 4 types). Replaces the retired time_reference.py.

Run from the repo root:

    uv run python scripts/generate_exercise_reference.py

Both output files are overwritten. The committed copies are gated by
tests/test_regressions.py::test_exercise_reference_docs_in_sync.
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

# Make the repo root importable so the engine modules resolve.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from fastlite import database  # noqa: E402

from age_engine import PRONOUNS as AGE_PRONOUNS  # noqa: E402
from age_engine import AgeEngine  # noqa: E402
from number_engine import NumberEngine  # noqa: E402
from quiz import ExerciseEngine  # noqa: E402
from time_engine import TIME_TYPES, TimeEngine  # noqa: E402
from weather_engine import WeatherEngine  # noqa: E402

# ---------------------------------------------------------------------
# Row loading
# ---------------------------------------------------------------------

_DB_PATH = _REPO_ROOT / "lithuanian_data.db"


def _load_rows() -> list[dict]:
    db = database(str(_DB_PATH))
    return list(db.t["numbers"].rows)


def _row(rows: list[dict], n: int) -> dict:
    for r in rows:
        if r["number"] == n:
            return r
    msg = f"no row for number={n} in lithuanian_data.db"
    raise LookupError(msg)


# ---------------------------------------------------------------------
# Representative tuples — edit these to add / refine review coverage
# ---------------------------------------------------------------------
# Numbers: (exercise_type, number)
_NUMBERS_REP = [
    # single_digit
    ("produce", 0),
    ("produce", 5),
    ("recognize", 7),
    # teens
    ("produce", 13),
    ("recognize", 19),
    # decade
    ("produce", 20),
    ("recognize", 50),
    # compound
    ("produce", 21),
    ("produce", 45),
    ("recognize", 99),
]

# Age: (exercise_type, number, pronoun_dative)
_AGE_REP = [
    # single-digit + metai/metų boundary (5 takes metų)
    ("produce", 2, "Man"),   # dveji metai
    ("produce", 5, "Tau"),   # penkeri metai
    ("produce", 9, "Jam"),   # devyneri metai
    # teens (always metų)
    ("produce", 15, "Jai"),
    # decade
    ("produce", 20, "Man"),
    # compound-collective (21 metai — dvidešimt vieneri)
    ("produce", 21, "Tau"),
    ("produce", 22, "Jam"),  # dvidešimt dveji
    ("produce", 45, "Jai"),
    # recognize
    ("recognize", 10, "Man"),
    ("recognize", 33, "Tau"),
]

# Weather: (exercise_type, number, negative)
_WEATHER_REP = [
    # zero
    ("produce", 0, False),
    # positive single-digit
    ("produce", 5, False),
    # positive teens (genitive plural)
    ("produce", 15, False),
    # positive compound
    ("produce", 25, False),
    # negative (bounded to 1-20)
    ("produce", 1, True),
    ("produce", 10, True),
    ("produce", 15, True),
    # recognize
    ("recognize", 7, False),
    ("recognize", 12, True),
]

# Prices: (exercise_type in {"kokia", "kiek"}, number, item)
# "item" only matters for "kiek" exercises (shown in the prompt).
_PRICES_REP = [
    # kokia — nominative
    ("kokia", 1, None),
    ("kokia", 5, None),
    ("kokia", 15, None),
    ("kokia", 21, None),
    ("kokia", 45, None),
    ("kokia", 99, None),
    # kiek — accusative (compound ones digit declines)
    ("kiek", 1, "knyga"),
    ("kiek", 5, "knyga"),
    ("kiek", 15, "knyga"),
    ("kiek", 21, "knyga"),
    ("kiek", 45, "knyga"),
]


# ---------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------

def _md_table(rows: list[tuple[str, str, str]]) -> str:
    """Return a Markdown table given rows of (exercise, prompt, correct)."""
    out = ["| Exercise | Prompt | Correct answer |", "|---|---|---|"]
    for ex, prompt, correct in rows:
        out.append(f"| {ex} | {prompt} | {correct} |")
    return "\n".join(out)


def _pronoun_dict(dative: str) -> dict[str, str]:
    for p in AGE_PRONOUNS:
        if p["dative"] == dative:
            return p
    msg = f"unknown pronoun dative: {dative!r}"
    raise LookupError(msg)


# ---------------------------------------------------------------------
# Build the representative doc
# ---------------------------------------------------------------------

def _build_exercise_reference(rows: list[dict]) -> str:
    today = _dt.date.today().isoformat()
    out = [
        f"<!-- Generated by scripts/generate_exercise_reference.py on {today}. "
        f"Do not edit by hand. -->",
        "",
        "# Exercise Reference — for Native-Speaker Review",
        "",
        "Representative exercises across every module, grouped by taxonomy "
        "branch. Each row shows the prompt the learner sees and the exact "
        "Lithuanian answer the app accepts. Review for correctness / "
        "naturalness — flag anything that reads wrong.",
        "",
    ]

    # ---- Numbers
    num_engine = NumberEngine(rows)
    out += ["## Numbers (/numbers)", ""]
    out += [
        "Range 0–99. Two exercise types: `produce` (say the number in "
        "Lithuanian) and `recognize` (identify the number from its "
        "Lithuanian form).",
        "",
    ]
    num_rows: list[tuple[str, str, str]] = []
    for ex_type, n in _NUMBERS_REP:
        row = _row(rows, n)
        prompt = num_engine.format_question(ex_type, row, lang="en")
        correct = num_engine.correct_answer(ex_type, row)
        num_rows.append((ex_type, prompt, correct))
    out += [_md_table(num_rows), ""]

    # ---- Age
    age_rows_src = [r for r in rows if r["number"] >= 2]
    age_engine = AgeEngine(age_rows_src)
    out += ["## Age (/age)", ""]
    out += [
        "Ages 2–99 with dative pronouns (Man, Tau, Jam, Jai). Numbers 1–9 "
        "and compound ones-digits 1–9 pair with collective numerals "
        "(dveji, treji, …) and the noun `metai`; 10–19 and round tens "
        "use cardinal numerals with the noun `metų`.",
        "",
    ]
    age_rows: list[tuple[str, str, str]] = []
    for ex_type, n, dative in _AGE_REP:
        row = _row(rows, n)
        pronoun = _pronoun_dict(dative)
        prompt = age_engine.format_question(ex_type, row, pronoun, lang="en")
        correct = age_engine.correct_answer(ex_type, row, pronoun)
        age_rows.append((ex_type, prompt, correct))
    out += [_md_table(age_rows), ""]

    # ---- Weather
    weather_rows_src = [r for r in rows if r["number"] >= 0]
    weather_engine = WeatherEngine(weather_rows_src)
    out += ["## Weather (/weather)", ""]
    out += [
        "Temperatures from –20 °C to +99 °C. `produce` prompts say "
        "'How do you say … °C?'; `recognize` prompts show a Lithuanian "
        "phrase and ask for the numeric answer. Negative is prefixed "
        "with 'minus'; the degree word inflects (laipsnis / laipsniai / "
        "laipsnių).",
        "",
    ]
    weather_rows: list[tuple[str, str, str]] = []
    for ex_type, n, negative in _WEATHER_REP:
        row = _row(rows, n)
        prompt = weather_engine.format_question(
            ex_type, row, negative=negative, lang="en"
        )
        correct = weather_engine.correct_answer(ex_type, row, negative=negative)
        weather_rows.append((ex_type, prompt, correct))
    out += [_md_table(weather_rows), ""]

    # ---- Prices
    price_rows_src = [r for r in rows if r["number"] >= 1]
    # ExerciseEngine only needs rows + an AdaptiveLearning for generate(),
    # but here we call format_question / correct_answer directly so a stub
    # is fine.
    from adaptive import AdaptiveLearning
    price_engine = ExerciseEngine(price_rows_src, AdaptiveLearning())
    out += ["## Prices (/prices)", ""]
    out += [
        "Two cases: `kokia` (nominative — stating the price directly) and "
        "`kiek` (accusative — saying what something costs, where the "
        "number word declines).",
        "",
    ]
    price_rows: list[tuple[str, str, str]] = []
    for ex_type, n, item in _PRICES_REP:
        row = _row(rows, n)
        price_str = f"€{n}"
        prompt = price_engine.format_question(ex_type, price_str, item)
        correct = price_engine.correct_answer(ex_type, row)
        price_rows.append((ex_type, prompt, correct))
    out += [_md_table(price_rows), ""]

    # ---- Time (brief preview; exhaustive file is separate)
    out += ["## Time (/time)", ""]
    out += [
        "Representative samples below; the full 48-expression enumeration "
        "(every hour × every time type) is in `docs/reviews/time-reference.md`.",
        "",
    ]
    time_engine = TimeEngine()
    time_rows: list[tuple[str, str, str]] = []
    for time_type in TIME_TYPES:
        for hour in (1, 6, 12):  # covers wraparound for quarter_to/half_past/quarter_past
            display = f"{hour}:{{:02d}}".format(
                {"whole_hour": 0, "quarter_past": 15, "half_past": 30, "quarter_to": 45}[time_type]
            )
            prompt = time_engine.format_question(display)
            minute = {"whole_hour": 0, "quarter_past": 15, "half_past": 30, "quarter_to": 45}[time_type]
            correct = time_engine.correct_answer(time_type, hour, minute)
            time_rows.append((time_type, prompt, correct))
    out += [_md_table(time_rows), ""]

    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------
# Build the exhaustive time doc
# ---------------------------------------------------------------------

def _build_time_reference() -> str:
    today = _dt.date.today().isoformat()
    time_engine = TimeEngine()
    out = [
        f"<!-- Generated by scripts/generate_exercise_reference.py on {today}. "
        f"Do not edit by hand. -->",
        "",
        "# Time Reference — Exhaustive",
        "",
        "Every time expression the `/time` module can produce: 12 hours × "
        "4 time types = 48 entries. Replaces the retired "
        "`time_reference.py`.",
        "",
    ]

    type_labels = {
        "whole_hour": "Whole hour (nominative + valanda)",
        "quarter_past": "Quarter past (ketvirtis + genitive of next hour)",
        "half_past": "Half past (pusė + genitive of next hour)",
        "quarter_to": "Quarter to (be ketvirčio + nominative of next hour)",
    }
    type_minutes = {
        "whole_hour": 0,
        "quarter_past": 15,
        "half_past": 30,
        "quarter_to": 45,
    }

    for time_type in TIME_TYPES:
        out += [f"## {type_labels[time_type]}", ""]
        rows: list[tuple[str, str, str]] = []
        minute = type_minutes[time_type]
        for hour in range(1, 13):
            display = f"{hour}:{minute:02d}"
            prompt = time_engine.format_question(display)
            correct = time_engine.correct_answer(time_type, hour, minute)
            rows.append((f"hour={hour}", prompt, correct))
        out += [
            "| Hour | Prompt | Correct answer |",
            "|---|---|---|",
        ]
        for h_label, prompt, correct in rows:
            out.append(f"| {h_label} | {prompt} | {correct} |")
        out += [""]

    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------

def main() -> None:
    rows = _load_rows()
    exercise_doc = _build_exercise_reference(rows)
    time_doc = _build_time_reference()

    reviews_dir = _REPO_ROOT / "docs" / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    (reviews_dir / "exercise-reference.md").write_text(exercise_doc)
    (reviews_dir / "time-reference.md").write_text(time_doc)

    print(f"wrote {reviews_dir / 'exercise-reference.md'}")
    print(f"wrote {reviews_dir / 'time-reference.md'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the generator**

Run: `uv run python scripts/generate_exercise_reference.py`
Expected:
```
wrote /Users/jonathan/projects/lithuanianquiz/.worktrees/polish-review-docs/docs/reviews/exercise-reference.md
wrote /Users/jonathan/projects/lithuanianquiz/.worktrees/polish-review-docs/docs/reviews/time-reference.md
```

If the run errors, the most likely cause is an engine-signature mismatch (e.g. `format_question` takes a different parameter set for a module). Fix the relevant `_build_*` call to match the real signature.

- [ ] **Step 3: Eyeball the output**

Run: `head -40 docs/reviews/exercise-reference.md && echo --- && head -20 docs/reviews/time-reference.md`
Expected: each doc starts with its header comment, an H1, an intro paragraph, and the first module/time-type section. Skim for anything that looks obviously wrong (empty tables, missing columns, stray "{").

- [ ] **Step 4: Commit the generator + both docs**

```bash
git add scripts/generate_exercise_reference.py docs/reviews/exercise-reference.md docs/reviews/time-reference.md
git commit -m "feat(scripts): add exercise-reference generator + native-speaker docs

One script (scripts/generate_exercise_reference.py) emits two docs:

* docs/reviews/exercise-reference.md — representative exercises
  across all five modules, grouped by taxonomy branch (~66 rows)
* docs/reviews/time-reference.md — exhaustive enumeration of all 48
  time expressions (replaces time_reference.py, deleted in a later
  commit)

Generator imports engines directly and calls their existing
format_question / correct_answer methods. Representative-mode tuples
live at the top of the script so coverage is easy to extend when a
reviewer asks for more examples.
"
```

---

## Task 2: Regression test — committed docs must stay in sync with generator

**Files:**
- Modify: `tests/test_regressions.py` — add one test that re-runs the generator and diffs against both committed docs.

- [ ] **Step 1: Write the test**

Append to `tests/test_regressions.py`:

```python
def test_exercise_reference_docs_in_sync(tmp_path, monkeypatch) -> None:
    """The committed native-speaker review docs must byte-match what the
    generator currently produces (modulo the date line at the top). If
    an engine changes output, CI fails until someone regenerates."""
    import importlib.util
    import re
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    generator_path = repo_root / "scripts" / "generate_exercise_reference.py"

    # Load the generator module without running its __main__.
    spec = importlib.util.spec_from_file_location("_gen", generator_path)
    assert spec is not None and spec.loader is not None
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)

    # Point the generator at the real DB + reviews dir, but write to tmp.
    monkeypatch.setattr(gen, "_REPO_ROOT", repo_root)
    reviews_tmp = tmp_path / "reviews"
    reviews_tmp.mkdir()

    # Patch the output dir used by gen.main(); cleanest is to just call
    # the builders directly.
    rows = gen._load_rows()
    fresh_exercise = gen._build_exercise_reference(rows)
    fresh_time = gen._build_time_reference()

    committed_exercise = (repo_root / "docs" / "reviews" / "exercise-reference.md").read_text()
    committed_time = (repo_root / "docs" / "reviews" / "time-reference.md").read_text()

    # Strip the date line (format: "<!-- Generated … on YYYY-MM-DD. …-->")
    date_re = re.compile(r"<!-- Generated.*?-->")

    def _strip(s: str) -> str:
        return date_re.sub("<!-- GEN -->", s, count=1)

    assert _strip(fresh_exercise) == _strip(committed_exercise), (
        "docs/reviews/exercise-reference.md is out of date. Run "
        "`uv run python scripts/generate_exercise_reference.py` to refresh."
    )
    assert _strip(fresh_time) == _strip(committed_time), (
        "docs/reviews/time-reference.md is out of date. Run "
        "`uv run python scripts/generate_exercise_reference.py` to refresh."
    )
```

- [ ] **Step 2: Run the test**

Run: `uv run --extra dev pytest tests/test_regressions.py::test_exercise_reference_docs_in_sync -v`
Expected: PASS (the committed docs were just regenerated in Task 1).

- [ ] **Step 3: Intentionally break it and reverify**

Edit `docs/reviews/exercise-reference.md` — change one number in a table row (e.g. `| 5 |` → `| 55 |`). Save.

Run: `uv run --extra dev pytest tests/test_regressions.py::test_exercise_reference_docs_in_sync -v 2>&1 | tail -10`
Expected: FAIL with the "out of date" message.

Revert the edit: `git checkout docs/reviews/exercise-reference.md` — the test goes back to PASS.

- [ ] **Step 4: Full suite**

Run: `uv run --extra dev pytest 2>&1 | tail -5`
Expected: all pass.

- [ ] **Step 5: Commit the test**

```bash
git add tests/test_regressions.py
git commit -m "test: regenerate-and-diff guard for exercise-reference docs

Asserts docs/reviews/exercise-reference.md and time-reference.md
byte-match the generator's current output (minus the date line in
the header comment). If an engine changes output, CI fails until
someone runs `uv run python scripts/generate_exercise_reference.py`."
```

---

## Task 3: Retire `time_reference.py` and update doc references

**Files:**
- Delete: `time_reference.py`
- Modify: `CLAUDE.md`, `HANDOFF.md`, `FUTURE_MODULES.md`

- [ ] **Step 1: Delete `time_reference.py`**

Run: `git rm time_reference.py`

- [ ] **Step 2: Update `CLAUDE.md`**

Find the file-structure line:
```
- `time_reference.py` — Standalone script to generate all time expressions for native speaker review
```

Replace with:
```
- `scripts/generate_exercise_reference.py` — Generates `docs/reviews/exercise-reference.md` (representative, cross-module) and `docs/reviews/time-reference.md` (exhaustive) for native-speaker review
```

- [ ] **Step 3: Update `HANDOFF.md`**

Run: `grep -n time_reference HANDOFF.md`
If any hits: update to reference `scripts/generate_exercise_reference.py` + the two doc paths. If no hits, skip.

- [ ] **Step 4: Update `FUTURE_MODULES.md`**

Find the "Native Speaker Spot Check" section. Replace:
```
Generate a document with all exercise types and their correct answers for native speaker review. Similar to `time_reference.py` but covering all modules. ...
```

With (preserving the "Done" / "not Done" status of the section as-is — it was an open item; now it's done):
```
~~**Native Speaker Spot Check**~~ — Implemented. `scripts/generate_exercise_reference.py` produces two review docs: representative cross-module `docs/reviews/exercise-reference.md` (~66 rows) and exhaustive `docs/reviews/time-reference.md` (48 rows).
```

If the section is under a "Done" header, adjust to match the existing style. If it's under "Open Questions" or similar, move it to the "Done" section.

- [ ] **Step 5: Regenerate docs to pick up the new date header (if date changed)**

Run: `uv run python scripts/generate_exercise_reference.py`
Regenerate after the above edits so the committed docs' date lines are fresh. The sync test strips the date so this is cosmetic only.

If the regeneration produces no diff (same day), skip the regenerate.

- [ ] **Step 6: Run full suite + ruff**

Run: `uv run --extra dev pytest && uv run --extra dev ruff check . && uv run --extra dev ruff format --check .`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: retire time_reference.py, update repo doc pointers

time_reference.py deleted; its exhaustive output is now produced by
scripts/generate_exercise_reference.py into docs/reviews/time-reference.md.
CLAUDE.md, HANDOFF.md, and FUTURE_MODULES.md references updated to
point at the new generator + output paths."
```

---

## Task 4: PR

- [ ] **Step 1: Push**

```bash
git push -u origin polish-review-docs
```

- [ ] **Step 2: Open PR**

Run:
```bash
gh pr create --base main --head polish-review-docs \
  --title "feat: native-speaker review docs generator (polish γ)" \
  --body "$(cat <<'EOF'
## Summary

Implements spec §PR γ of `docs/superpowers/specs/2026-04-17-polish-bucket-design.md`.

- New generator: `scripts/generate_exercise_reference.py` emits two docs under `docs/reviews/`.
  - `exercise-reference.md` — representative exercises across all five modules, grouped by taxonomy branch (~66 rows). For cross-module review by a native speaker.
  - `time-reference.md` — exhaustive enumeration of every time expression (12 hours × 4 types = 48 rows). Replaces `time_reference.py`.
- Retires `time_reference.py`. Doc references in `CLAUDE.md`, `HANDOFF.md`, `FUTURE_MODULES.md` updated.
- Regression test guards both docs against drift: if an engine changes output, CI fails until someone re-runs the generator.

Representative-mode exercises are stored as explicit tuples at the top of the generator so coverage is easy to extend when a reviewer asks for more examples.

## Test plan

- [x] `uv run python scripts/generate_exercise_reference.py` produces two docs that match committed copies.
- [x] `tests/test_regressions.py::test_exercise_reference_docs_in_sync` passes.
- [x] Full suite + ruff clean.
- [ ] CI green.
- [ ] Post-merge: ping jbagd with the two doc links for native-speaker review.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Wait for CI, merge**

No deploy step — γ is doc-only; no runtime change.

```bash
gh pr merge <pr-number> --squash
cd /Users/jonathan/projects/lithuanianquiz
git checkout main
git pull --ff-only origin main
git worktree remove .worktrees/polish-review-docs
git branch -d polish-review-docs
git push origin --delete polish-review-docs
```

---

## Self-review notes

**Spec coverage:**
- Two output docs, representative + exhaustive time → Tasks 1, 2.
- Generator imports engines directly → Task 1 script.
- Representative tuples per module → Task 1 `_NUMBERS_REP`, `_AGE_REP`, `_WEATHER_REP`, `_PRICES_REP`.
- Exhaustive time iteration → Task 1 `_build_time_reference`.
- Date-header on each doc → Task 1 `_build_exercise_reference` / `_build_time_reference`.
- Regen-and-diff test → Task 2.
- `time_reference.py` deletion → Task 3 Step 1.
- Repo doc updates → Task 3 Steps 2-4.

**Placeholder scan:** no TBD / "similar to task N" — every step has concrete code or commands.

**Type consistency:** `_build_exercise_reference(rows)` and `_build_time_reference()` signatures used consistently in Task 1 (definition), Task 2 (test invokes them), Task 3 Step 5 (regenerate). `_row(rows, n)` helper signature consistent across all module builders.

**Known caveat:** the `age_engine.format_question(..., pronoun, lang="en")` call in `_AGE_REP` passes a pronoun dict obtained from `_pronoun_dict`. Verify during implementation that the real `age_engine.format_question` signature matches; if it doesn't, adjust the call.
