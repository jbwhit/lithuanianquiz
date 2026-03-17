# Feedback Flow Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make answer feedback and practice-page follow-up UI always describe the exercise that was just submitted, even after the next question has already been generated.

**Architecture:** Capture an immutable answered snapshot before any route mutates session state for the next exercise, then render feedback/history from that snapshot instead of live session keys. Keep the implementation narrow: stabilize or remove flaky practice-page stats/sidebar sections rather than extending them.

**Tech Stack:** Python 3.13, FastHTML, MonsterUI, pytest, ruff

---

### Task 1: Lock Down The Broken Flow With Regressions

**Files:**
- Modify: `tests/test_regressions.py`
- Test: `tests/test_regressions.py`

**Step 1: Write the failing test**

```python
def test_time_feedback_uses_answered_snapshot(monkeypatch) -> None:
    ...
```

Add focused tests that prove:
- `/time/answer` shows the answered question and answered correct answer after the next question becomes `8:45`
- at least one other module route keeps its answered prompt in feedback/history after generating a new prompt
- mixed practice still uses the answered time hour for grammar hints

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_regressions.py -k "time_feedback or answered_snapshot or practice_all_time_feedback" -v`
Expected: FAIL on the new regression before implementation.

**Step 3: Write minimal implementation**

No production changes yet. Only add the regression coverage.

**Step 4: Run test to verify it fails correctly**

Run: `uv run pytest tests/test_regressions.py -k "time_feedback or answered_snapshot or practice_all_time_feedback" -v`
Expected: FAIL because current handlers still read mutable session state too loosely.

**Step 5: Commit**

```bash
git add tests/test_regressions.py
git commit -m "test: cover feedback snapshot regressions"
```

### Task 2: Introduce Answered Snapshots In The Shared Submit Flow

**Files:**
- Modify: `main.py`
- Modify: `ui.py`
- Test: `tests/test_regressions.py`

**Step 1: Write the failing test**

Use the Task 1 regressions as the active failing tests.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_regressions.py -k "time_feedback or answered_snapshot or practice_all_time_feedback" -v`
Expected: FAIL.

**Step 3: Write minimal implementation**

Implement small shared helpers in `main.py` to:
- capture answered state before `_new_question`, `_new_time_question`, `_new_age_question`, `_new_weather_question`, `_new_number_question`, or `_new_mix_question`
- build a history entry from the frozen snapshot
- pass snapshot-backed metadata into `feedback_correct` / `feedback_incorrect`

Only change `ui.py` if a feedback helper needs a cleaner contract for snapshot-driven rendering.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_regressions.py -k "time_feedback or answered_snapshot or practice_all_time_feedback" -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add main.py ui.py tests/test_regressions.py
git commit -m "fix: freeze answered exercise state for feedback"
```

### Task 3: Remove Or Simplify Flaky Practice-Page Sidebar Pieces

**Files:**
- Modify: `ui.py`
- Modify: `tests/test_ui.py`
- Modify: `tests/test_regressions.py`
- Test: `tests/test_ui.py`

**Step 1: Write the failing test**

Add UI/regression coverage for whichever sidebar behavior is kept on practice pages. If a section is removed, assert the simplified/stable shape instead of the old one.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui.py tests/test_regressions.py -k "stats or history or sidebar" -v`
Expected: FAIL until the practice-page sidebar matches the chosen stable contract.

**Step 3: Write minimal implementation**

Trim practice-page stats/history rendering to the smallest stable set. Prefer:
- keeping simple aggregate counters if they remain correct
- removing weak-area breakdowns or recent-exercise previews from live practice responses if they rely on brittle state coupling

Leave the dedicated `/stats` page intact unless the same shared component must change for correctness.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ui.py tests/test_regressions.py -k "stats or history or sidebar" -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add ui.py tests/test_ui.py tests/test_regressions.py
git commit -m "fix: simplify unstable practice sidebar state"
```

### Task 4: Verify The Full Cleanup

**Files:**
- Modify: `main.py`
- Modify: `ui.py`
- Modify: `tests/test_regressions.py`
- Modify: `tests/test_ui.py`

**Step 1: Run targeted route and UI checks**

Run: `uv run pytest tests/test_regressions.py tests/test_ui.py -v`
Expected: PASS.

**Step 2: Run the full test suite**

Run: `uv run pytest`
Expected: PASS for the full suite.

**Step 3: Run lint**

Run: `uv run ruff check .`
Expected: PASS.

**Step 4: Commit**

```bash
git add main.py ui.py tests/test_regressions.py tests/test_ui.py
git commit -m "fix: clean up practice feedback flow"
```
