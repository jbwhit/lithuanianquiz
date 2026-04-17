# Response to Thompson Sampling review — adaptive question selection

**Author:** Codex, 2026-04-17
**Status:** Response only — no code changes.
**Responds to:** `docs/reviews/2026-04-17-thompson-sampling-review.md`
**Scope:** `thompson.py`, `adaptive.py`, `time_engine.py`, `age_engine.py`, `weather_engine.py`, `number_engine.py`, current tests, and the repo's session-storage constraints.

## TL;DR

The original review is directionally useful, especially in calling out the unused `combined_arms` table and the limits of marginal sampling. But several recommendations overstate or mischaracterize how this codebase actually works:

1. The steady-state `exploration_rate` is not redundant in the current implementation, because several arm spaces are created lazily. Removing random exploration without pre-seeding all candidate arms can strand unseen patterns forever.
2. The proposed exponential-decay update is not sound as written. Decaying only the opposing count does not keep effective sample size bounded under the current `Beta(correct+1, incorrect+1)` parameterization.
3. A posterior like `Beta(101, 101)` does not "effectively stop updating." The real issue is inertia, not impossibility.
4. The code does not implement one global `Beta(1, 2)` cold-start prior. Some arms are pre-seeded that way; others do not exist until first observation.

My read is that the original document should be treated as a design memo, not as a direct implementation plan.

---

## 1. The exploration gate is doing lazy-arm discovery

The strongest disagreement is with the claim that the steady-state 20% random gate is simply redundant on top of Thompson Sampling.

That would be true if every candidate arm already existed in the posterior table. In this codebase, several arm spaces are **not** pre-seeded:

- `adaptive.py` initializes `exercise_types`, but leaves `number_patterns` and `grammatical_cases` empty.
- `number_engine.py` initializes `exercise_types`, but leaves `number_patterns` empty.
- `time_engine.py` initializes `exercise_types`, but leaves `hour_patterns` and `grammatical_cases` empty.

`thompson.sample_weakest()` can only sample from keys that already exist. New keys appear only when `thompson.bump()` sees an observation for that arm and inserts `{"correct": 0, "incorrect": 1}`.

That means the current random exploration branch is doing more than generic exploration:

- it provides warmup before `adaptation_threshold`
- it is also the only generic mechanism that guarantees unseen arms can enter the posterior tables after warmup

If someone removed steady-state random exploration without also pre-seeding all arm spaces, the system could get stuck sampling only the subset of patterns/hours/cases that happened to appear in the first few exercises.

So the right statement is:

- pure TS would be enough **if** all candidate arms were seeded up front
- in the current lazy-arm implementation, the random gate is carrying part of arm discovery

This is especially visible in `time_engine.generate()`, where the extra hour-level randomness is not elegant, but it is also compensating for the fact that `hour_patterns` begins empty.

---

## 2. The forgetting recommendation needs correction

The original review is right that there is currently no forgetting. Counts only increase.

But the specific suggested decay rule:

- "multiply the opposing count by gamma before bumping"

does not actually do what the document claims under the current posterior definition:

- `alpha = correct + 1`
- `beta = incorrect + 1`

If only the opposing count decays, then a long run of correct answers still sends `correct` upward without bound. The posterior still becomes increasingly concentrated; effective sample size does **not** remain bounded in the way the review implies.

If the goal is bounded-memory adaptation, the options are more like:

- decay both counts symmetrically, then apply the new observation
- keep an explicit sliding window and recompute counts from that window

Those are materially different proposals from the one in the current review.

There is also a codebase-specific constraint the original review does not mention: this app uses FastHTML's cookie-backed `SessionMiddleware`, and `HANDOFF.md` explicitly calls out session size as a production risk. A sliding-window design is easy to reason about mathematically, but it is not obviously cheap operationally here if it means storing per-arm outcome buffers across multiple modules inside the session cookie.

So I agree with the diagnosis:

- no forgetting

But not with the writeup's specific implementation guidance as currently phrased.

---

## 3. `Beta(101, 101)` is inertial, not frozen

The review says that once an arm reaches something like `Beta(101, 101)`, Thompson Sampling "effectively can't update it."

That is too strong.

The posterior absolutely still updates on every observation. What changes is:

- variance shrinks
- each new observation moves the posterior mean less
- adaptation to changing skill becomes slower

That is a real problem, but it is a responsiveness problem, not a mathematical inability to update.

I would rewrite that section in terms of:

- slower adaptation
- over-commitment to stale history
- high inertia after lots of early evidence

That preserves the substantive concern without overstating the failure mode.

---

## 4. The cold-start prior is mixed, not global

The review's "Beta(1, 2) seed" section also overgeneralizes the implementation.

Some arm families are explicitly pre-seeded with `{correct: 0, incorrect: 1}`:

- `exercise_types` in all engines
- `pronouns` in `age_engine.py`
- `sign` in `weather_engine.py`

But other arm families begin empty and only receive that same asymmetric seed after their first observed update:

- `number_patterns`
- `hour_patterns`
- `grammatical_cases`
- `combined_arms`

So there is not one uniform prior story here. The code implements a mixed regime:

- pre-seeded families get an immediate cold-start bias toward "weakness"
- lazily created families have no prior at all until they are observed once

That distinction matters because it is exactly why the steady-state exploration gate is still load-bearing.

---

## 5. What still looks fair in the original review

Several parts of the original document still seem useful and worth keeping:

### `combined_arms` really is write-only today

This is not hypothetical. `adaptive.py` populates `combined_arms` during `update()`, but selection never reads it. That deserves an explicit decision:

- either move to true joint-arm selection
- or delete the table and stop pretending joint adaptation is recorded for future use

### Joint weakness is a reasonable design concern

The review is right that marginal weakness and joint weakness are not the same thing. A learner can be weak on a specific combination while looking fine on each marginal dimension independently.

What I would tone down is the framing. The current implementation makes a tradeoff:

- fewer tracked arms
- simpler warmup behavior
- less sparsity

That is not obviously "incorrect," but it is a clear design choice with limits.

### Cross-module seeding caveats are fair

The note about `seed_prefix="n99"` transferring priors into age/weather is a good one. Those priors are informative, but not semantically identical across modules.

That said, the doc should acknowledge the UX reason for it:

- skip relearning obvious number-pattern difficulty from scratch
- trade perfect calibration for a better cold start

---

## 6. Answers to the original "For Codex" questions

### Does `combined_arms` look deliberate or vestigial?

It looks vestigial in the current code, not merely deferred by tests. It is populated and never read. I do not see evidence of a deliberate "record but never sample" design elsewhere in the repo.

### Is the current exploration pattern serving a real purpose?

Yes. Even if it is theoretically redundant relative to fully seeded TS, it is practically doing arm discovery in this implementation because several arm spaces are lazy.

### Sliding window or exponential decay?

Sliding window is easier to reason about statistically. Exponential decay is lighter on state. In this repo, that storage tradeoff matters because session size is already a documented risk, so I would be cautious about any forgetting scheme that stores per-arm event histories in cookie-backed session state.

---

## Recommendation

I would revise the original review before using it as implementation guidance:

1. Reframe the `exploration_rate` critique around **lazy arm creation**.
2. Fix the forgetting section so it recommends either symmetric decay or a real windowed scheme, not "decay only the opposing count."
3. Soften the `Beta(101, 101)` language from "can't update" to "adapts too slowly."
4. Clarify that the cold-start behavior is mixed across arm families, not one universal prior.

After those corrections, the document would be a strong architectural review. In its current form, it identifies real design tensions, but some of the recommended fixes do not yet line up with the actual implementation or operating constraints of this app.
