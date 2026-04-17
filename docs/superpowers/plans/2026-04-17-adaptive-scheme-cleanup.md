# Adaptive Scheme Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the marginal-TS-plus-uniform-gate-plus-lazy-arms scheme with pre-seeded arm families, symmetric γ-decay, and a pure warmup gate. Delete the write-only `combined_arms` table.

**Architecture:** Thompson Sampling math is unchanged (`Beta(correct+1, incorrect+1)`, argmin). Three structural changes: (1) every arm family is pre-seeded at `init_tracking` from its known taxonomy so `sample_weakest` can never be trapped in a partially-populated dict; (2) `thompson.bump` applies symmetric exponential decay (γ=0.98) to both counts before incrementing, bounding effective sample size at ~50; (3) engines drop the steady-state `random() < exploration_rate` gate and keep only the `total_exercises < adaptation_threshold` warmup gate. `combined_arms` is removed since selection never reads it.

**Tech Stack:** Python 3.13 (Railway runs 3.12), numpy for `Beta` sampling, pytest for tests, ruff for format/lint. No new dependencies.

**Design decisions resolved from the revised review's open questions:**
- `combined_arms`: **delete**. Marginal TS + decay carries the adaptation; joint sampling is a larger change for another day.
- γ tuning: **shared single constant** `DECAY_GAMMA = 0.98` in `thompson.py`.
- Manual "mastered" affordance: **skip** (YAGNI).

**Background reading (for engineers without context):**
- `docs/reviews/2026-04-17-thompson-sampling-review-revised.md` — the review this plan implements
- `docs/reviews/2026-04-17-thompson-sampling-review-response.md` — Codex's corrections that shape the plan
- `CLAUDE.md` — project overview, uv toolchain, deployment

---

## File structure

**Modify:**
- `thompson.py` — add `DECAY_GAMMA`, rewrite `bump` to decay symmetrically, make `sample_weakest` tie-break deterministically.
- `adaptive.py` — pre-seed `number_patterns` and `grammatical_cases` in `init_tracking`; make init idempotent per-family (top up on load); delete `combined_arms` (init + update); remove steady-state gate in `select_exercise`.
- `time_engine.py` — pre-seed `hour_patterns` and `grammatical_cases`; per-family idempotent init; remove steady-state gate and the extra hour-level random branch in `generate`.
- `number_engine.py` — pre-seed `number_patterns`; per-family idempotent init; remove steady-state gate (both the type-selection one and the extra `random() > exploration_rate` pattern-selection one).
- `age_engine.py` — pre-seed `number_patterns` (pronouns already pre-seeded); per-family idempotent init; remove steady-state gate.
- `weather_engine.py` — pre-seed `number_patterns` (sign already pre-seeded); per-family idempotent init; remove steady-state gate.
- Existing tests in `tests/test_adaptive.py`, `tests/test_time.py`, `tests/test_numbers.py`, `tests/test_age.py`, `tests/test_weather.py` — update any that assert exact int counts or check for `combined_arms`.

**Create:**
- `tests/test_thompson.py` — unit tests for `thompson.bump` decay and `sample_weakest` determinism under seed.

**No change:**
- `auth.py` `load_progress` — relies on engine `init_tracking` to top up missing arm families after load, which the per-family idempotent init delivers for free. Nothing to edit directly.
- `main.py` — uses engines through `_ensure_*_session` which always calls `init_tracking`; no changes needed.

---

## Task 1: γ-decay in `thompson.bump`

**Files:**
- Modify: `thompson.py`
- Create: `tests/test_thompson.py`

- [ ] **Step 1: Write failing tests for decay + tie-breaking**

Create `tests/test_thompson.py`:

```python
"""Unit tests for the shared Thompson-sampling helpers."""

import random

import numpy as np
import pytest

from thompson import DECAY_GAMMA, bump, sample_weakest


class TestBumpDecay:
    def test_bump_initializes_missing_arm_with_cold_start_seed(self) -> None:
        arms: dict[str, dict[str, float]] = {}
        bump(arms, "new_arm", is_correct=True)
        # After one correct observation on a brand-new arm, with γ-decay of
        # the seed (correct=0, incorrect=1): correct = 0·γ + 1 = 1,
        # incorrect = 1·γ = γ.
        assert arms["new_arm"]["correct"] == pytest.approx(1.0)
        assert arms["new_arm"]["incorrect"] == pytest.approx(DECAY_GAMMA)

    def test_bump_decays_both_counts_before_incrementing(self) -> None:
        arms = {"a": {"correct": 10.0, "incorrect": 4.0}}
        bump(arms, "a", is_correct=True)
        assert arms["a"]["correct"] == pytest.approx(10.0 * DECAY_GAMMA + 1.0)
        assert arms["a"]["incorrect"] == pytest.approx(4.0 * DECAY_GAMMA)

    def test_bump_decays_both_counts_on_incorrect(self) -> None:
        arms = {"a": {"correct": 10.0, "incorrect": 4.0}}
        bump(arms, "a", is_correct=False)
        assert arms["a"]["correct"] == pytest.approx(10.0 * DECAY_GAMMA)
        assert arms["a"]["incorrect"] == pytest.approx(4.0 * DECAY_GAMMA + 1.0)

    def test_bump_bounds_effective_sample_size_under_long_run(self) -> None:
        """ESS should converge to ~1/(1-γ) under a long streak of same outcome."""
        arms: dict[str, dict[str, float]] = {}
        for _ in range(1000):
            bump(arms, "a", is_correct=True)
        ess = arms["a"]["correct"] + arms["a"]["incorrect"]
        # Steady-state ESS is 1/(1-γ). With γ=0.98, that's 50.
        assert ess == pytest.approx(1.0 / (1.0 - DECAY_GAMMA), rel=0.01)


class TestSampleWeakest:
    def test_returns_one_of_the_arms(self) -> None:
        arms = {
            "x": {"correct": 5.0, "incorrect": 1.0},
            "y": {"correct": 1.0, "incorrect": 5.0},
        }
        result = sample_weakest(arms)
        assert result in arms

    def test_heavily_favors_the_weaker_arm(self) -> None:
        """Over many draws, the low-success-rate arm should dominate."""
        np.random.seed(0)
        random.seed(0)
        arms = {
            "strong": {"correct": 20.0, "incorrect": 1.0},
            "weak": {"correct": 1.0, "incorrect": 20.0},
        }
        picks = [sample_weakest(arms) for _ in range(200)]
        assert picks.count("weak") > picks.count("strong") * 5

    def test_ties_do_not_depend_on_dict_insertion_order(self) -> None:
        """With identical posteriors, ties should break via the sampled values,
        not via dict iteration order."""
        np.random.seed(42)
        ab = sample_weakest({"a": {"correct": 1.0, "incorrect": 1.0},
                             "b": {"correct": 1.0, "incorrect": 1.0}})
        np.random.seed(42)
        ba = sample_weakest({"b": {"correct": 1.0, "incorrect": 1.0},
                             "a": {"correct": 1.0, "incorrect": 1.0}})
        # With the same RNG seed and equal posteriors, the chosen arm should
        # be determined by sample values, not by which key is listed first.
        assert ab == ba
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run --extra dev pytest tests/test_thompson.py -v`
Expected: All fail with `ImportError: cannot import name 'DECAY_GAMMA'` or `AssertionError` on existing behavior.

- [ ] **Step 3: Rewrite `thompson.py`**

Replace the contents of `thompson.py` with:

```python
"""Shared Thompson Sampling utilities for adaptive learning."""

from typing import Any

import numpy as np

# Symmetric exponential decay factor applied to both counts before each bump.
# Steady-state effective sample size ≈ 1/(1−γ) = 50 at γ=0.98, which keeps
# adaptation responsive to recent performance while smoothing out single-pull
# noise.
DECAY_GAMMA: float = 0.98

# Cold-start seed for previously-unseen arms. Posterior mean 1/3 deliberately
# nudges selection toward arms the learner has not yet seen.
_SEED_CORRECT: float = 0.0
_SEED_INCORRECT: float = 1.0


def bump(
    category: dict[str, dict[str, float]],
    key: str,
    is_correct: bool,
) -> None:
    """Decay both counts symmetrically, then increment the observed side.

    Creates the arm with the cold-start seed if missing.
    """
    if key not in category:
        category[key] = {"correct": _SEED_CORRECT, "incorrect": _SEED_INCORRECT}
    arm = category[key]
    arm["correct"] *= DECAY_GAMMA
    arm["incorrect"] *= DECAY_GAMMA
    if is_correct:
        arm["correct"] += 1.0
    else:
        arm["incorrect"] += 1.0


def sample_weakest(arms: dict[str, dict[str, float]]) -> str:
    """Thompson-sample and return the arm with the lowest posterior draw.

    Ties break by the sampled value itself (not by dict insertion order).
    """
    samples: dict[str, Any] = {}
    for arm, stats in arms.items():
        alpha = stats["correct"] + 1.0
        beta_val = stats["incorrect"] + 1.0
        samples[arm] = np.random.beta(alpha, beta_val)
    return min(samples, key=lambda k: samples[k])
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `uv run --extra dev pytest tests/test_thompson.py -v`
Expected: All pass.

- [ ] **Step 5: Run the full suite to identify fallout**

Run: `uv run --extra dev pytest 2>&1 | tail -40`
Expected: Some existing tests fail because they assert integer counts like `assert stats["correct"] == 1`. Note the failures — they'll be fixed in Task 2 when we also update pre-seeds.

- [ ] **Step 6: Commit**

```bash
git add thompson.py tests/test_thompson.py
git commit -m "refactor(thompson): add symmetric γ-decay to bump + deterministic tie-breaking

Decay factor γ=0.98 bounds effective sample size at ~1/(1-γ)=50, keeping the
posterior responsive to current skill instead of dominated by stale early
history. Tie-breaking in sample_weakest now uses the sampled value (via
explicit key lambda) rather than dict insertion order.

Existing engine tests that assert integer counts will fail until task 2
updates their expectations; that's the natural fallout from making counts
time-weighted floats.
"
```

---

## Task 2: Pre-seed all arm families with idempotent per-family init

This is the biggest task. Every engine's `init_tracking` currently returns early if the performance dict exists; we change to *always* ensure each known arm family is present with a complete seed. That handles both fresh sessions and legacy sessions loaded from the DB.

Order matters: do one engine at a time, commit after each, run the full suite between engines so regressions surface narrowly.

**Shared helper we'll introduce:**

A small helper `_ensure_seeded(category, keys)` inside `thompson.py` that adds missing keys with the cold-start seed. Used by every engine.

**Files:**
- Modify: `thompson.py`
- Modify: `adaptive.py`, `time_engine.py`, `number_engine.py`, `age_engine.py`, `weather_engine.py`
- Modify: `tests/test_adaptive.py`, `tests/test_time.py`, `tests/test_numbers.py`, `tests/test_age.py`, `tests/test_weather.py`

### Task 2a: Add `_ensure_seeded` to thompson.py

- [ ] **Step 1: Write the failing test**

Append to `tests/test_thompson.py`:

```python
class TestEnsureSeeded:
    def test_adds_missing_keys_with_cold_start_seed(self) -> None:
        from thompson import _ensure_seeded

        arms: dict[str, dict[str, float]] = {}
        _ensure_seeded(arms, ["a", "b", "c"])
        assert set(arms.keys()) == {"a", "b", "c"}
        for stats in arms.values():
            assert stats["correct"] == pytest.approx(0.0)
            assert stats["incorrect"] == pytest.approx(1.0)

    def test_leaves_existing_arms_untouched(self) -> None:
        from thompson import _ensure_seeded

        arms = {"a": {"correct": 5.0, "incorrect": 2.0}}
        _ensure_seeded(arms, ["a", "b"])
        assert arms["a"] == {"correct": 5.0, "incorrect": 2.0}
        assert arms["b"]["correct"] == pytest.approx(0.0)
        assert arms["b"]["incorrect"] == pytest.approx(1.0)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --extra dev pytest tests/test_thompson.py::TestEnsureSeeded -v`
Expected: `ImportError: cannot import name '_ensure_seeded'`.

- [ ] **Step 3: Add `_ensure_seeded` to thompson.py**

Append to `thompson.py`, just before `def bump`:

```python
def _ensure_seeded(category: dict[str, dict[str, float]], keys: list[str]) -> None:
    """Ensure every key is present with the cold-start seed.

    Idempotent: arms that already exist are left untouched. Used by per-engine
    init_tracking to guarantee full arm coverage on fresh sessions and to
    top up legacy sessions loaded from the DB.
    """
    for key in keys:
        if key not in category:
            category[key] = {
                "correct": _SEED_CORRECT,
                "incorrect": _SEED_INCORRECT,
            }
```

- [ ] **Step 4: Run tests**

Run: `uv run --extra dev pytest tests/test_thompson.py -v`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add thompson.py tests/test_thompson.py
git commit -m "feat(thompson): add _ensure_seeded helper for idempotent arm pre-seeding"
```

### Task 2b: Pre-seed `adaptive.py` (prices)

- [ ] **Step 1: Identify taxonomies**

Known taxonomies for prices:
- `exercise_types`: already seeded from `EXERCISE_TYPES` (`["kokia", "kiek"]`)
- `number_patterns`: `["single_digit", "teens", "decade", "compound"]` (from `quiz.number_pattern`)
- `grammatical_cases`: `["nominative", "accusative"]`

- [ ] **Step 2: Write a failing test for pre-seeding**

Append to `tests/test_adaptive.py` (or add to an existing class near the top):

```python
class TestInitTrackingPreSeeds:
    def test_fresh_session_has_all_arm_families_seeded(self) -> None:
        from adaptive import AdaptiveLearning

        session: dict = {}
        AdaptiveLearning().init_tracking(session)
        perf = session["performance"]

        assert set(perf["exercise_types"].keys()) == {"kokia", "kiek"}
        assert set(perf["number_patterns"].keys()) == {
            "single_digit", "teens", "decade", "compound",
        }
        assert set(perf["grammatical_cases"].keys()) == {
            "nominative", "accusative",
        }
        # No combined_arms in the new scheme.
        assert "combined_arms" not in perf

    def test_legacy_session_gets_missing_families_topped_up(self) -> None:
        from adaptive import AdaptiveLearning

        # Simulate a session loaded from the DB with the old lazy-arm layout.
        session = {
            "performance": {
                "exercise_types": {
                    "kokia": {"correct": 3.0, "incorrect": 1.0},
                    "kiek": {"correct": 2.0, "incorrect": 2.0},
                },
                "number_patterns": {},
                "grammatical_cases": {},
                "total_exercises": 7,
            }
        }
        AdaptiveLearning().init_tracking(session)
        perf = session["performance"]

        # Existing arm stats preserved.
        assert perf["exercise_types"]["kokia"]["correct"] == pytest.approx(3.0)
        assert perf["total_exercises"] == 7
        # Missing families filled in.
        assert set(perf["number_patterns"].keys()) == {
            "single_digit", "teens", "decade", "compound",
        }
        assert set(perf["grammatical_cases"].keys()) == {
            "nominative", "accusative",
        }
```

Add `import pytest` near the top of `tests/test_adaptive.py` if not already present.

- [ ] **Step 3: Run to verify failure**

Run: `uv run --extra dev pytest tests/test_adaptive.py::TestInitTrackingPreSeeds -v`
Expected: Fail on empty `number_patterns`/`grammatical_cases`.

- [ ] **Step 4: Update `adaptive.init_tracking`**

Replace the current `init_tracking` in `adaptive.py` with:

```python
_NUMBER_PATTERNS = ["single_digit", "teens", "decade", "compound"]
_PRICE_CASES = ["nominative", "accusative"]


def init_tracking(self, session: dict[str, Any]) -> None:
    """Idempotently ensure every arm family is pre-seeded.

    Runs on every request. Fresh sessions get a complete set of cold-start
    arms; sessions loaded from the DB in the old lazy-arm layout get topped
    up with any arms that used to be created lazily.
    """
    from thompson import _ensure_seeded

    perf = session.setdefault(
        "performance",
        {
            "exercise_types": {},
            "number_patterns": {},
            "grammatical_cases": {},
            "total_exercises": 0,
        },
    )
    perf.setdefault("exercise_types", {})
    perf.setdefault("number_patterns", {})
    perf.setdefault("grammatical_cases", {})
    perf.setdefault("total_exercises", 0)
    # Drop the dead combined_arms table if loaded from a legacy session.
    perf.pop("combined_arms", None)

    _ensure_seeded(perf["exercise_types"], list(EXERCISE_TYPES))
    _ensure_seeded(perf["number_patterns"], _NUMBER_PATTERNS)
    _ensure_seeded(perf["grammatical_cases"], _PRICE_CASES)
```

Also remove the `combined_arms` write in `update()` (the whole `if np_ and gc:` block). Delete the module-level `# combined_arms` comments if any.

- [ ] **Step 5: Run pre-seed tests**

Run: `uv run --extra dev pytest tests/test_adaptive.py::TestInitTrackingPreSeeds -v`
Expected: All pass.

- [ ] **Step 6: Run full adaptive test file and repair any broken assertions**

Run: `uv run --extra dev pytest tests/test_adaptive.py -v`
Expected: Some pre-existing tests may break because `number_patterns` is no longer empty on a fresh session.

For every failure of the form `assert perf["exercise_types"]["kokia"]["correct"] == N`: update to `== pytest.approx(N)` to tolerate γ-decay (when applicable).

For every failure of the form `assert session["performance"]["exercise_types"]["kokia"]["incorrect"] > 1`: adjust threshold to account for `γ * prior + increments`.

For every failure checking `assert "combined_arms" in perf`: delete the assertion.

- [ ] **Step 7: Commit**

```bash
git add adaptive.py tests/test_adaptive.py
git commit -m "refactor(adaptive): pre-seed all arm families + delete combined_arms

init_tracking now idempotently ensures exercise_types, number_patterns, and
grammatical_cases are fully populated from known taxonomies. The write-only
combined_arms table is removed. This removes the arm-discovery load the
steady-state exploration gate was quietly carrying (gate itself removed in
a later task).
"
```

### Task 2c: Pre-seed `time_engine.py`

- [ ] **Step 1: Identify taxonomies**

- `exercise_types`: `TIME_TYPES` (`["whole_hour", "half_past", "quarter_past", "quarter_to"]`) — already seeded
- `hour_patterns`: `[f"hour_{i}" for i in range(1, 13)]`
- `grammatical_cases`: `["nominative", "genitive"]`

- [ ] **Step 2: Write a failing test for pre-seeding**

Append to `tests/test_time.py`:

```python
class TestTimeInitTrackingPreSeeds:
    def test_fresh_session_has_all_arm_families(self) -> None:
        from time_engine import TimeEngine

        session: dict = {}
        TimeEngine().init_tracking(session)
        perf = session["time_performance"]

        assert set(perf["exercise_types"].keys()) == {
            "whole_hour", "half_past", "quarter_past", "quarter_to",
        }
        assert set(perf["hour_patterns"].keys()) == {
            f"hour_{i}" for i in range(1, 13)
        }
        assert set(perf["grammatical_cases"].keys()) == {"nominative", "genitive"}

    def test_legacy_session_gets_topped_up(self) -> None:
        from time_engine import TimeEngine

        session = {
            "time_performance": {
                "exercise_types": {
                    "whole_hour": {"correct": 2.0, "incorrect": 1.0},
                },
                "hour_patterns": {},
                "grammatical_cases": {},
                "total_exercises": 5,
            }
        }
        TimeEngine().init_tracking(session)
        perf = session["time_performance"]
        assert perf["exercise_types"]["whole_hour"]["correct"] == pytest.approx(2.0)
        assert len(perf["hour_patterns"]) == 12
        assert len(perf["grammatical_cases"]) == 2
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run --extra dev pytest tests/test_time.py::TestTimeInitTrackingPreSeeds -v`
Expected: Fail on empty families.

- [ ] **Step 4: Update `time_engine.init_tracking`**

Replace the current method in `time_engine.py` with:

```python
_HOUR_PATTERNS = [f"hour_{i}" for i in range(1, 13)]
_TIME_CASES = ["nominative", "genitive"]


def init_tracking(self, session: dict[str, Any]) -> None:
    """Idempotently pre-seed every time-module arm family."""
    from thompson import _ensure_seeded

    perf = session.setdefault(
        "time_performance",
        {
            "exercise_types": {},
            "hour_patterns": {},
            "grammatical_cases": {},
            "total_exercises": 0,
        },
    )
    perf.setdefault("exercise_types", {})
    perf.setdefault("hour_patterns", {})
    perf.setdefault("grammatical_cases", {})
    perf.setdefault("total_exercises", 0)

    _ensure_seeded(perf["exercise_types"], list(TIME_TYPES))
    _ensure_seeded(perf["hour_patterns"], _HOUR_PATTERNS)
    _ensure_seeded(perf["grammatical_cases"], _TIME_CASES)
```

- [ ] **Step 5: Run time tests and repair fallout**

Run: `uv run --extra dev pytest tests/test_time.py -v`
Expected: New tests pass. Any pre-existing test asserting `len(perf["hour_patterns"]) == 0` or checking int counts needs updating (use `pytest.approx`, adjust length checks).

- [ ] **Step 6: Commit**

```bash
git add time_engine.py tests/test_time.py
git commit -m "refactor(time_engine): pre-seed hour_patterns + grammatical_cases"
```

### Task 2d: Pre-seed `number_engine.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_numbers.py`:

```python
class TestNumberInitTrackingPreSeeds:
    def test_fresh_session_has_all_arm_families(self) -> None:
        from number_engine import NumberEngine

        session: dict = {}
        # Build a minimal engine with the numbers 1-20 sample rows already in
        # use elsewhere in this test file; the tracking init itself doesn't
        # depend on rows, but the constructor does.
        engine = NumberEngine(rows=[{"number": n} for n in range(1, 21)], max_number=20)
        engine.init_tracking(session, "n20")
        perf = session["n20_performance"]

        assert set(perf["exercise_types"].keys()) == {"produce", "recognize"}
        assert set(perf["number_patterns"].keys()) == {
            "single_digit", "teens", "decade", "compound",
        }

    def test_legacy_session_gets_topped_up(self) -> None:
        from number_engine import NumberEngine

        session = {
            "n20_performance": {
                "exercise_types": {
                    "produce": {"correct": 1.0, "incorrect": 1.0},
                },
                "number_patterns": {},
                "total_exercises": 3,
            }
        }
        engine = NumberEngine(rows=[{"number": n} for n in range(1, 21)], max_number=20)
        engine.init_tracking(session, "n20")
        perf = session["n20_performance"]
        assert perf["exercise_types"]["produce"]["correct"] == pytest.approx(1.0)
        assert len(perf["number_patterns"]) == 4
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --extra dev pytest tests/test_numbers.py::TestNumberInitTrackingPreSeeds -v`
Expected: Fail.

- [ ] **Step 3: Update `number_engine.init_tracking`**

Replace the current method with:

```python
def init_tracking(
    self,
    session: dict[str, Any],
    prefix: str,
    seed_prefix: str | None = None,
) -> None:
    """Idempotently pre-seed every number-module arm family.

    If seed_prefix is given and that module has existing data *and* the
    target perf dict doesn't exist yet, copy its priors first, then ensure
    all arm families are complete.
    """
    from thompson import _ensure_seeded

    perf_key = f"{prefix}_performance"
    if perf_key not in session:
        seed_key = f"{seed_prefix}_performance" if seed_prefix else None
        if seed_key and seed_key in session:
            session[perf_key] = copy.deepcopy(session[seed_key])
        else:
            session[perf_key] = {
                "exercise_types": {},
                "number_patterns": {},
                "total_exercises": 0,
            }
    perf = session[perf_key]
    perf.setdefault("exercise_types", {})
    perf.setdefault("number_patterns", {})
    perf.setdefault("total_exercises", 0)

    _ensure_seeded(perf["exercise_types"], list(EXERCISE_TYPES))
    _ensure_seeded(perf["number_patterns"], ["single_digit", "teens", "decade", "compound"])
```

- [ ] **Step 4: Run tests**

Run: `uv run --extra dev pytest tests/test_numbers.py -v`
Expected: All pass after any approx updates.

- [ ] **Step 5: Commit**

```bash
git add number_engine.py tests/test_numbers.py
git commit -m "refactor(number_engine): pre-seed number_patterns"
```

### Task 2e: Pre-seed `age_engine.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_age.py`:

```python
class TestAgeInitTrackingPreSeeds:
    def test_fresh_session_has_all_arm_families(self) -> None:
        from age_engine import AgeEngine, PRONOUN_DATIVES

        session: dict = {}
        engine = AgeEngine(rows=[{"number": n, "years": "metai"} for n in range(2, 21)])
        engine.init_tracking(session, "age")
        perf = session["age_performance"]

        assert set(perf["exercise_types"].keys()) == {"produce", "recognize"}
        assert set(perf["number_patterns"].keys()) == {
            "single_digit", "teens", "decade", "compound",
        }
        assert set(perf["pronouns"].keys()) == set(PRONOUN_DATIVES)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --extra dev pytest tests/test_age.py::TestAgeInitTrackingPreSeeds -v`

- [ ] **Step 3: Update `age_engine.init_tracking`**

Replace with:

```python
def init_tracking(
    self,
    session: dict[str, Any],
    prefix: str = "age",
    seed_prefix: str | None = None,
) -> None:
    """Idempotently pre-seed every age-module arm family."""
    from thompson import _ensure_seeded

    perf_key = f"{prefix}_performance"
    if perf_key not in session:
        seed_key = f"{seed_prefix}_performance" if seed_prefix else None
        if seed_key and seed_key in session:
            source = session[seed_key]
            session[perf_key] = {
                "exercise_types": copy.deepcopy(source.get("exercise_types", {})),
                "number_patterns": copy.deepcopy(source.get("number_patterns", {})),
                "pronouns": {},
                "total_exercises": source.get("total_exercises", 0),
            }
        else:
            session[perf_key] = {
                "exercise_types": {},
                "number_patterns": {},
                "pronouns": {},
                "total_exercises": 0,
            }
    perf = session[perf_key]
    perf.setdefault("exercise_types", {})
    perf.setdefault("number_patterns", {})
    perf.setdefault("pronouns", {})
    perf.setdefault("total_exercises", 0)

    _ensure_seeded(perf["exercise_types"], list(EXERCISE_TYPES))
    _ensure_seeded(perf["number_patterns"], ["single_digit", "teens", "decade", "compound"])
    _ensure_seeded(perf["pronouns"], list(PRONOUN_DATIVES))
```

- [ ] **Step 4: Run tests, repair fallout**

Run: `uv run --extra dev pytest tests/test_age.py -v`
Expected: Pass after approx updates. Note any test asserting specific integer counts — switch to `pytest.approx`.

- [ ] **Step 5: Commit**

```bash
git add age_engine.py tests/test_age.py
git commit -m "refactor(age_engine): pre-seed number_patterns (pronouns already seeded)"
```

### Task 2f: Pre-seed `weather_engine.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_weather.py`:

```python
class TestWeatherInitTrackingPreSeeds:
    def test_fresh_session_has_all_arm_families(self) -> None:
        from weather_engine import SIGN_TYPES, WeatherEngine

        session: dict = {}
        engine = WeatherEngine(
            rows=[{"number": n, "kokia_kaina": "x"} for n in range(1, 21)]
        )
        engine.init_tracking(session, "weather")
        perf = session["weather_performance"]

        assert set(perf["exercise_types"].keys()) == {"produce", "recognize"}
        assert set(perf["number_patterns"].keys()) == {
            "single_digit", "teens", "decade", "compound",
        }
        assert set(perf["sign"].keys()) == set(SIGN_TYPES)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --extra dev pytest tests/test_weather.py::TestWeatherInitTrackingPreSeeds -v`

- [ ] **Step 3: Update `weather_engine.init_tracking`**

Replace with:

```python
def init_tracking(
    self,
    session: dict[str, Any],
    prefix: str = "weather",
    seed_prefix: str | None = None,
) -> None:
    """Idempotently pre-seed every weather-module arm family."""
    from thompson import _ensure_seeded

    perf_key = f"{prefix}_performance"
    if perf_key not in session:
        seed_key = f"{seed_prefix}_performance" if seed_prefix else None
        if seed_key and seed_key in session:
            source = session[seed_key]
            session[perf_key] = {
                "exercise_types": copy.deepcopy(source.get("exercise_types", {})),
                "number_patterns": copy.deepcopy(source.get("number_patterns", {})),
                "sign": {},
                "total_exercises": source.get("total_exercises", 0),
            }
        else:
            session[perf_key] = {
                "exercise_types": {},
                "number_patterns": {},
                "sign": {},
                "total_exercises": 0,
            }
    perf = session[perf_key]
    perf.setdefault("exercise_types", {})
    perf.setdefault("number_patterns", {})
    perf.setdefault("sign", {})
    perf.setdefault("total_exercises", 0)

    _ensure_seeded(perf["exercise_types"], list(EXERCISE_TYPES))
    _ensure_seeded(perf["number_patterns"], ["single_digit", "teens", "decade", "compound"])
    _ensure_seeded(perf["sign"], list(SIGN_TYPES))
```

- [ ] **Step 4: Run tests, repair fallout**

Run: `uv run --extra dev pytest tests/test_weather.py -v`

- [ ] **Step 5: Commit**

```bash
git add weather_engine.py tests/test_weather.py
git commit -m "refactor(weather_engine): pre-seed number_patterns (sign already seeded)"
```

### Task 2g: Full-suite verification after all engines pre-seed

- [ ] **Step 1: Run the full suite**

Run: `uv run --extra dev pytest 2>&1 | tail -30`
Expected: All pass. If anything is still red, fix in place (most likely candidate: assertions on integer counts in regression or UI tests).

- [ ] **Step 2: Ruff check + format**

Run: `uv run --extra dev ruff check . && uv run --extra dev ruff format --check .`
Expected: Clean.

- [ ] **Step 3: Commit any cleanup**

```bash
git add -A
git commit -m "refactor: post-preseed test cleanup" --allow-empty
```

---

## Task 3: Drop the steady-state uniform-random gate

With every arm now pre-seeded, `sample_weakest` can never be trapped, so the steady-state gate can come out. The warmup gate (`total_exercises < adaptation_threshold`) stays.

**Files:**
- Modify: `adaptive.py`, `time_engine.py`, `number_engine.py`, `age_engine.py`, `weather_engine.py`
- Modify: tests as needed

- [ ] **Step 1: Write a failing test against the new invariant**

Append to `tests/test_adaptive.py`:

```python
class TestAdaptiveNoSteadyStateGate:
    def test_post_warmup_always_takes_thompson_path(self, monkeypatch) -> None:
        """After warmup, random() is not consulted for a gate — _thompson_sample
        is always invoked."""
        from adaptive import AdaptiveLearning

        engine = AdaptiveLearning(exploration_rate=0.9)  # huge rate, would usually explore
        session: dict = {"performance": {"total_exercises": 999}}
        engine.init_tracking(session)

        called = {"ts": False, "rand": False}
        monkeypatch.setattr(engine, "_thompson_sample",
                            lambda *a, **kw: called.update(ts=True) or {"exercise_type": "kokia", "price": "€1", "item": None, "row": {"number": 1}, "grammatical_case": "nominative", "number_pattern": "single_digit"})
        monkeypatch.setattr(engine, "_random_exercise",
                            lambda *a, **kw: called.update(rand=True) or {})

        for _ in range(50):
            engine.select_exercise(session, engine=_FakeEngine())
        assert called["ts"] is True
        assert called["rand"] is False


class _FakeEngine:
    rows = [{"number": 1}]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --extra dev pytest tests/test_adaptive.py::TestAdaptiveNoSteadyStateGate -v`
Expected: Fails because `_random_exercise` is called ~45/50 times.

- [ ] **Step 3: Remove the gate in `adaptive.select_exercise`**

Find:
```python
if (
    random.random() < self.exploration_rate
    or perf["total_exercises"] < self.adaptation_threshold
):
    return self._random_exercise(engine)
```

Replace with:
```python
if perf["total_exercises"] < self.adaptation_threshold:
    return self._random_exercise(engine)
```

- [ ] **Step 4: Run the new test and full adaptive suite**

Run: `uv run --extra dev pytest tests/test_adaptive.py -v`
Expected: Pass.

- [ ] **Step 5: Repeat for each other engine**

In each of `time_engine.py`, `number_engine.py`, `age_engine.py`, `weather_engine.py`, replace the same pattern in `generate`:

```python
if (
    random.random() < self.exploration_rate
    or perf["total_exercises"] < self.adaptation_threshold
):
```

with:

```python
if perf["total_exercises"] < self.adaptation_threshold:
```

Additionally in `time_engine.generate`, find the hour-level extra-random branch:

```python
if perf["hour_patterns"] and random.random() > self.exploration_rate:
    weak_hour_key = _sample_weakest(perf["hour_patterns"])
    hour = int(weak_hour_key.split("_")[1])
else:
    hour = random.randint(1, 12)
```

Replace with (now that `hour_patterns` is always pre-seeded):

```python
weak_hour_key = _sample_weakest(perf["hour_patterns"])
hour = int(weak_hour_key.split("_")[1])
```

Same pattern in `number_engine.generate`, `age_engine.generate`, `weather_engine.generate` for the pattern-selection extra-random branch — drop the `and random.random() > self.exploration_rate` half.

- [ ] **Step 6: Full suite + ruff**

Run: `uv run --extra dev pytest && uv run --extra dev ruff check .`
Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add adaptive.py time_engine.py number_engine.py age_engine.py weather_engine.py tests/
git commit -m "refactor: drop steady-state exploration gate + extra per-dimension gates

With all arm families now pre-seeded, sample_weakest can never be trapped
by a partially-populated dict, so the uniform-random gate is no longer
carrying arm-discovery load. The warmup gate (total_exercises <
adaptation_threshold) stays. Time/number/age/weather also drop the extra
random() > exploration_rate gate on their secondary dimension (hour or
number_pattern).
"
```

---

## Task 4: Remove `exploration_rate` from engine constructors

With no call site using it, it's dead code.

**Files:**
- Modify: `adaptive.py`, `time_engine.py`, `number_engine.py`, `age_engine.py`, `weather_engine.py`
- Modify: `main.py` if any instantiation passes `exploration_rate=...`

- [ ] **Step 1: Grep for call sites**

Run: `Grep(pattern="exploration_rate", path=".")`
Note every hit. Confirm nothing outside `__init__` reads it after Task 3.

- [ ] **Step 2: Remove from each engine's `__init__`**

In each engine, change:
```python
def __init__(self, ... exploration_rate: float = 0.2, adaptation_threshold: int = 10) -> None:
    self.exploration_rate = exploration_rate
    self.adaptation_threshold = adaptation_threshold
```

To:
```python
def __init__(self, ... adaptation_threshold: int = 10) -> None:
    self.adaptation_threshold = adaptation_threshold
```

- [ ] **Step 3: Update `main.py`**

Find any `AdaptiveLearning(exploration_rate=...)` or similar and remove that kwarg. Keep defaults.

- [ ] **Step 4: Full suite**

Run: `uv run --extra dev pytest`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove now-unused exploration_rate from engine constructors"
```

---

## Task 5: Deploy verification

- [ ] **Step 1: Run the full suite one last time**

Run: `uv run --extra dev pytest && uv run --extra dev ruff check . && uv run --extra dev ruff format --check .`

- [ ] **Step 2: Smoke test locally**

Run: `uv run python -c "
import main
session = {}
main._ensure_session(session)
main._ensure_time_session(session)
main._ensure_age_session(session)
main._ensure_weather_session(session)
main._ensure_number_session(session, main.number_engine_99, 'n99')
for key in ('performance', 'time_performance', 'age_performance', 'weather_performance', 'n99_performance'):
    perf = session[key]
    print(key, {k: len(v) if isinstance(v, dict) else v for k, v in perf.items()})
    assert 'combined_arms' not in perf
print('ok')
"`
Expected: Each perf dict prints complete family sizes (no zeros), no `combined_arms` anywhere, exits with `ok`.

- [ ] **Step 3: Push**

```bash
git push
```

- [ ] **Step 4: Deploy to Railway**

```bash
railway up --detach
```

Monitor: `railway service status` until `SUCCESS`.

- [ ] **Step 5: Production smoke test**

```bash
curl -sS -o /dev/null -w "HTTP %{http_code}\n" https://lithuanian-practice.com/
curl -sS -I "https://lithuanian-practice.com/set-language?lang=lt" | grep -E "HTTP|location"
```
Expected: `HTTP 200` on `/`, `HTTP/2 303` with a proper path in `location` for `/set-language`.

- [ ] **Step 6: Final commit of any post-deploy fixes**

If anything breaks in production, fix, redeploy, and note in a follow-up commit. Otherwise, done.

---

## Self-review pass

**Spec coverage:**
- Pre-seed every arm family → Task 2 (a–f covers every engine).
- Symmetric γ-decay → Task 1.
- Delete `combined_arms` → Task 2b (in the adaptive update).
- Drop steady-state gate → Task 3.
- Remove newly-unused `exploration_rate` → Task 4.
- Deploy/verify → Task 5.

**Placeholder scan:** No "TBD" / "handle edge cases" / "similar to task N" anywhere. Every code step has concrete code.

**Type consistency:**
- `DECAY_GAMMA: float` defined in Task 1, used by `bump` only (not surfaced to engines).
- `_ensure_seeded(category, keys)` signature defined in Task 2a, called with `list[str]` in every engine — consistent.
- `thompson.bump` / `thompson.sample_weakest` now operate on `dict[str, dict[str, float]]` — all tests use `pytest.approx` for assertions on count values.

**Open risk:** existing test files may have assertions on integer counts I haven't eyeballed. Each task includes a "repair fallout" step that runs the relevant test file and updates assertions to `pytest.approx`. Task 2g is the belt-and-suspenders catch-all after all pre-seeds land.
