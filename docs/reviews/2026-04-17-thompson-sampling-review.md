# Thompson Sampling review — adaptive question selection

**Author:** Claude Opus 4.7 (1M context), 2026-04-17
**Status:** Review only — no code changes. Intended to be read alongside Codex's own review.
**Scope:** `thompson.py`, `adaptive.py` (prices), `time_engine.py`, `age_engine.py`, `weather_engine.py`, `number_engine.py`. All use the same shared helpers.

## TL;DR

The TS formulation itself is sound — sampling `Beta(correct+1, incorrect+1)` and taking `argmin` is equivalent to standard TS over the reward "incorrectness" = `1 − p`. The issues are structural, in how the sampler is wrapped and what gets tracked:

1. **Dimensions are sampled independently then stitched** — true joint weakness is invisible, despite a `combined_arms` table already being populated.
2. **No forgetting / no recency weighting** — `α, β` accumulate forever, so mastery can't overwrite early struggle.
3. **`exploration_rate` layered on top of TS is redundant** — pure TS already self-regulates; a 20% uniform gate dilutes the signal.

Details follow.

---

## What the code does

### `thompson.sample_weakest(arms)`

For each arm, draw `θ_i ~ Beta(correct+1, incorrect+1)`, then return `argmin`. This is a legitimate TS over the reward "incorrectness" = `1 − p_i` — equivalent to sampling `Beta(β, α)` and taking `argmax`. ✓

### Per-module wrapping

Every engine (`adaptive.py`, `time_engine.py`, `age_engine.py`, `weather_engine.py`, `number_engine.py`) follows the same shape:

```python
if random.random() < self.exploration_rate or perf["total_exercises"] < self.adaptation_threshold:
    return self._random_exercise(...)
return self._thompson_sample(...)
```

And `_thompson_sample` calls `_sample_weakest` **once per dimension** (exercise type, number pattern, pronoun/hour/sign) and assembles an exercise from the pieces. `_random_exercise` is uniform over all dimensions.

---

## Issues, ordered by student impact

### 1. Independent sampling per dimension — weakness isn't decomposable

In `adaptive._thompson_sample`:
```python
ex_type = _sample_weakest(perf["exercise_types"])
if perf["number_patterns"]:
    np_ = _sample_weakest(perf["number_patterns"])
# then find a row matching np_
```

Same shape in `time_engine` (type × hour), `age_engine` (type × pattern × pronoun), `weather_engine` (type × pattern × sign).

Real weakness is **joint, not marginal**. A student can be fine on `kiek × single_digit` and bad on `kokia × compound`. Independently sampling each dimension and stitching the result frequently picks combinations the student is already fluent on.

**Notable:** there's already a `combined_arms` dict in `adaptive.py` keyed by `f"{ex_type}_{np}_{gc}"`, populated in `update()` — but **nothing ever reads it for selection**. It's either dead code or a half-finished feature. Either wire it into `_thompson_sample` (one TS draw over the joint table, replacing the multi-dimension draws), or delete it.

Selecting from the joint table is slightly more prone to "empty arms" early on — mitigated by the same warmup gate that already exists (`total_exercises < adaptation_threshold`).

### 2. No forgetting — posteriors accumulate forever

`α, β` only ever grow. Consequences:

- A student who struggled with "teens" during their first 50 trials but is now fluent keeps seeing teens because the old `incorrect` count dominates new evidence.
- Once an arm reaches `Beta(101, 101)`, the posterior is razor-sharp at 0.5 and TS effectively can't update it — variance ≈ 1/(4·203) ≈ 0.001.

Two standard remedies; either would help materially:

- **Sliding window**: only keep the last N outcomes per arm (N = 20–50 feels right for practice).
- **Exponential decay**: on each update, multiply the opposing count by γ ≈ 0.98 before bumping. Keeps effective sample size bounded and lets posteriors track current skill.

### 3. `exploration_rate` + TS is redundant

Pure Thompson Sampling is self-regulating: the variance of `Beta(α, β)` is exactly the exploration mechanism. As evidence accumulates, the posterior tightens and "greedy" behavior emerges automatically.

Adding an explicit 20% uniform-random gate on top (as the prices, age, weather, number, and time engines all do) means every fifth question is chosen as if we'd learned nothing. It dilutes the TS signal without a clear purpose.

The warmup branch (`total < adaptation_threshold`) is defensible — 10 pulls is thin. The steady-state 20% random is the part I'd drop.

`time_engine.generate` compounds this: a separate `random() > exploration_rate` gate on the *hour* dimension, layered on top of TS on hour. Three chances to bypass adaptation per question.

### 4. `Beta(1, 2)` seed is a deliberate bias worth naming

Fresh arms initialize to `{correct: 0, incorrect: 1}` → posterior mean 1/3, not 1/2. This nudges selection toward untouched arms, which is reasonable cold-start behavior.

But it's not a neutral prior. Either:
- keep it and add a comment explaining the cold-start nudge, or
- switch to `{0, 0}` → `Beta(1, 1)` = uniform for cleanliness (`_sample_weakest` would then lean on variance alone to explore new arms).

### 5. Cross-module prior seeding is clever but not strictly calibrated

`age_engine.init_tracking(seed_prefix="n99")` deep-copies `exercise_types`, `number_patterns`, and `total_exercises` from the numbers module. Good UX for warm-start.

Two wrinkles worth flagging:

- The semantics of "produce" differ across modules. In numbers it's "say the number word"; in age it's "dative pronoun + number + metai/metų agreement." The prior is **informative but not equivalent**.
- Copying `total_exercises` means a student who did 20 number questions skips age's own warmup and enters TS mode immediately with borrowed priors. Probably fine; worth being explicit about.

### 6. Within a sampled `number_pattern`, row is uniform

After TS picks `np_` = "teens", `_thompson_sample` does `random.choice(matching)`. No per-row adaptation, so if 13 and 14 are genuinely harder than 10 inside "teens," the system can't find that.

For small, stable categories this is fine. If finer targeting is desired later, per-row tracking (or a nested TS on rows within pattern) is the natural next step.

---

## Smaller observations

- `_sample_weakest` uses `min(samples, key=samples.get)`. Correct, but ties break by `dict` insertion order (CPython-defined, not algorithmically specified). Use `key=lambda k: samples[k]` for explicitness, or randomize ties.
- `get_weak_areas` requires `total > 1` before reporting a rate — so an arm with only the `{0, 1}` seed is skipped. Good: avoids reporting pure prior noise as "weakness."
- `bump()` creates missing arms with `{correct: 0, incorrect: 1}`. Consistent with init but asymmetric — be aware this biases newly-observed-but-unseeded arms toward being picked.
- `total_exercises` is incremented on every `update()` but only used to gate the warmup. It could also drive decay schedules if forgetting were added.

---

## Recommendation priority

If you wanted to tighten this, in bang-for-buck order:

1. **Decide the fate of `combined_arms`.** Either wire it into selection (true joint adaptation) or delete it. Leaving it half-built is the single most load-bearing correctness issue.
2. **Add decay** (γ ≈ 0.98 on the opposing count each update). Lets mastery register and bounds effective sample size. Small change, large student-facing effect.
3. **Drop the steady-state 20% uniform-random gate.** Keep the `total < threshold` warmup. Reduces noise, trusts TS to do its job.

Items 4–6 above are refinements worth doing once the big three are settled.

---

## For Codex

Questions I'd particularly value your take on:

- Does `combined_arms` reflect a deliberate design choice to *not* use joint sampling (e.g., data-sparsity concerns on 4 × 4 × 3 = 48 arms with only a few hundred pulls)? Or is it vestigial?
- Is there an existing preference in this codebase for the current "exploration rate on top of TS" pattern that I'm missing? I only see it as redundant.
- For decay/forgetting: would a sliding window be easier to reason about here than exponential decay, given the small per-session counts?
