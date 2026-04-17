# Thompson Sampling review — revised

**Author:** Claude Opus 4.7 (1M context), 2026-04-17
**Status:** Review only — no code changes. Revision of `2026-04-17-thompson-sampling-review.md` incorporating Codex's corrections in `2026-04-17-thompson-sampling-review-response.md`.
**Scope:** `thompson.py`, `adaptive.py` (prices), `time_engine.py`, `age_engine.py`, `weather_engine.py`, `number_engine.py`.

## What changed from v1

Four technical errors in the original review, each caught by Codex:

1. "Drop the steady-state 20% random gate" was wrong for the *current* code. Three of the arm families (`number_patterns`, `grammatical_cases`, `hour_patterns`) are lazy — created on first observation, not pre-seeded. The gate carries arm-discovery load, not just exploration.
2. "Decay only the opposing count" does not bound effective sample size. On a long correct streak, `α` grows without bound and the posterior collapses at mean 1. The rule needs to be symmetric decay or a real sliding window.
3. "`Beta(101,101)` can't update" is imprecise. The posterior does update — each observation shifts the mean by `1/(α+β+1)`. The correct language is high inertia / slow adaptation, not impossibility.
4. "Fresh arms initialize to `Beta(1, 2)`" treats a mixed regime as uniform. `exercise_types`, `pronouns`, `sign` are pre-seeded. `number_patterns`, `hour_patterns`, `grammatical_cases`, `combined_arms` start empty and only enter the table via `bump()`.

The three headline recommendations still stand, but two of them gain a precondition or a corrected rule.

---

## TL;DR

`thompson.sample_weakest` is a legitimate TS formulation over the reward "incorrectness" = `1 − p`. The issues are structural in the surrounding code:

1. **`combined_arms` is write-only.** Decide: wire it in or delete it.
2. **No forgetting.** Add either **symmetric decay** on both counts or a **sliding window** per arm.
3. **Steady-state 20% uniform gate + lazy arms.** Either pre-seed every arm family up front and then drop the gate, or keep the gate and document that it's doing arm discovery, not generic exploration.

---

## What the sampler does

### `thompson.sample_weakest(arms)`

For each arm, draw `θ_i ~ Beta(correct+1, incorrect+1)`, return `argmin`. Equivalent to standard TS over `1 − p`. ✓

### Per-module wrapping

Every engine follows the same shape:

```python
if random.random() < exploration_rate or total_exercises < adaptation_threshold:
    return self._random_exercise(...)
return self._thompson_sample(...)
```

`_thompson_sample` calls `sample_weakest` **once per tracked dimension** (type, pattern, pronoun/hour/sign) and assembles an exercise.

---

## Issues

### 1. Dimensions are sampled independently, then stitched

Each dimension has its own posterior; no joint selection. Real weakness is joint — a student can be fine on `kiek × single_digit` and bad on `kokia × compound`.

`adaptive.py` populates a `combined_arms` table keyed by `f"{type}_{pattern}_{case}"` on every `update()`, but **nothing ever reads it for selection**. Write-only. Either:

- wire it into `_thompson_sample` (one TS draw over the joint table), or
- delete it and stop pretending joint adaptation is recorded.

Sparsity caveat: 4 types × 4 patterns × 3 cases = 48 arms in the prices module; with a few hundred pulls per session, many arms stay near the prior. The symmetric-decay scheme in §2 helps here by keeping effective sample size bounded.

### 2. No forgetting — counts only accumulate

`α, β` only grow. Two real consequences:

- Old struggle on "teens" dominates new evidence indefinitely; mastery registers slowly.
- After many observations the posterior has very high inertia: each new pull moves the mean by `1/(α+β+1)`. Not frozen, but slow enough that a skilled student stays stuck seeing categories they've already learned.

Two sound remedies:

- **Symmetric exponential decay.** On each update for an arm:
  ```
  correct ← γ · correct + [is_correct]
  incorrect ← γ · incorrect + [not is_correct]
  ```
  Effective sample size at steady state is `~1/(1−γ)`. With `γ = 0.98` that's ≈ 50 — responsive but not noisy.
- **Sliding window.** Keep last N outcomes per arm, recompute counts. Easier to reason about, heavier on state.

**State-size consideration.** The app uses FastHTML's cookie-backed `SessionMiddleware`, and `HANDOFF.md` flags session size as a production risk. Decay stores two floats per arm — cheap. A 30-outcome window per arm across ~40 arms is ~150 bytes — also fine. Neither is alarming, but decay is materially smaller and I'd default to it.

### 3. Steady-state uniform gate exists because arms are lazy

`number_patterns`, `grammatical_cases`, `hour_patterns` all initialize as `{}`. Entries appear only when `bump()` observes an outcome. `sample_weakest` can only pick from existing keys. Without the 20% uniform gate firing periodically, a module can get trapped in whatever subset of arms happened to appear during warmup.

So the gate is **not** redundant in the current implementation — it's the only generic mechanism for arm discovery after warmup.

That makes the design smell not the gate itself but the **lazy-arm pattern**. Every arm space in this app is enumerable from a known taxonomy:

- prices: `TIME_TYPES` / `EXERCISE_TYPES` / number-pattern → `{single_digit, teens, decade, compound}` / case → `{nominative, accusative}`
- time: `TIME_TYPES` / hour → `{1..12}` / case → `{nominative, genitive}`
- age: `EXERCISE_TYPES` / number-pattern / pronoun
- weather: `EXERCISE_TYPES` / number-pattern / sign
- numbers: `EXERCISE_TYPES` / number-pattern

Pre-seeding every dimension at `init_tracking` (with the same `{0, 1}` cold-start seed already used for the already-pre-seeded families) removes arm-discovery load from the gate. Once that's done, the steady-state gate can be dropped safely and TS alone handles exploration.

Time engine's extra `random() > exploration_rate` on the hour dimension falls out for the same reason: hours 1–12 are enumerable.

### 4. Cold-start prior is a mixed regime worth making uniform

Currently:

- **Pre-seeded** at init with `{correct: 0, incorrect: 1}` (posterior mean 1/3): `exercise_types`, `age_engine.pronouns`, `weather_engine.sign`.
- **Lazy** — created via `bump()` with the same `{0, 1}` seed on first observation: `number_patterns`, `hour_patterns`, `grammatical_cases`, `combined_arms`.

The `{0, 1}` seed is an intentional cold-start nudge (new arms look weak, get picked first). The asymmetry across families is what makes the gate load-bearing. Pre-seeding all families unifies the regime and is a prerequisite for dropping the gate.

### 5. Within a sampled pattern, row is uniform

After TS picks `pattern = teens`, `_thompson_sample` does `random.choice(matching)`. No per-row adaptation — if 13 and 14 are genuinely harder than 10, the system can't find it. Fine for small stable categories; a nested TS on rows within pattern is the natural next step if finer targeting is wanted.

### 6. Cross-module prior seeding is informative, not calibrated

`age_engine.init_tracking(seed_prefix="n99")` deep-copies `exercise_types`, `number_patterns`, and `total_exercises` from numbers. The "produce" arm means different things in each module (say-a-number vs. dative+number+metai agreement), so the priors are informative but not calibrated.

This is a legitimate UX choice — skip re-learning obvious number-pattern difficulty from scratch — trading perfect calibration for a warmer start. Worth a one-line comment at the seed site; not a bug.

---

## Smaller observations

- `_sample_weakest` breaks ties by `dict` insertion order (CPython-defined). Use `key=lambda k: samples[k]` for explicitness, or randomize ties.
- `get_weak_areas` requires `total > 1` before reporting a rate — correctly avoids reporting pure prior noise as "weakness."
- `bump` creates missing arms asymmetrically with `{0, 1}`. Consistent with the pre-seed choice, but after pre-seeding all arms the lazy path should only fire for genuinely unexpected keys (new taxonomy entries).
- `total_exercises` is used only to gate warmup. If decay is added, it could also drive the decay schedule (e.g., stronger γ early, relaxed later).

---

## Recommendation priority

In execution order, because each step enables the next:

1. **Pre-seed every arm family at `init_tracking`** across all engines. Removes arm-discovery load from the exploration gate and unifies the cold-start regime. Small, mechanical change.
2. **Add symmetric γ-decay to `thompson.bump`** (γ = 0.98 is a sensible default). Bounded effective sample size; mastery registers. One function edit.
3. **Decide `combined_arms`.** Either wire it into `_thompson_sample` (and apply the same decay) or delete it.
4. **Drop the steady-state uniform-random gate**, keep the `total < threshold` warmup. Only safe after step 1.

Items 5–6 (per-row adaptation, cross-module seeding comments) are cosmetic/refinement.

---

## Open questions

- For step 3, is the preference true joint adaptation or simplification by deletion? Joint sampling over 48 arms is more responsive to real weakness but noisier early; deletion keeps the current marginal model with less code.
- For step 2, is there appetite for per-engine decay tuning (e.g., looser decay for time where exercise pool is smaller), or one shared γ?
- Should there be a manual "I've mastered this, move on" affordance, or is adaptation-via-decay sufficient on its own?
