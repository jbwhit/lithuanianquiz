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


_COLD_START: dict[str, float] = {
    "correct": _SEED_CORRECT,
    "incorrect": _SEED_INCORRECT,
}


def sample_weakest(
    tracked: dict[str, dict[str, float]],
    full_keys: list[str] | None = None,
) -> str:
    """Thompson-sample and return the arm with the lowest posterior draw.

    If `full_keys` is provided, sample over that full taxonomy and treat
    missing keys as being at the cold-start seed. This lets the caller keep
    only observed arms in persisted state (small session cookies) while
    still considering the complete arm space at selection time.

    If `full_keys` is None, sample only over existing keys in `tracked`.

    Arms are sampled in sorted key order so results are independent of dict
    insertion order. Ties break by the sampled value itself.
    """
    keys = sorted(full_keys) if full_keys is not None else sorted(tracked)
    samples: dict[str, Any] = {}
    for key in keys:
        stats = tracked.get(key, _COLD_START)
        alpha = stats["correct"] + 1.0
        beta_val = stats["incorrect"] + 1.0
        samples[key] = np.random.beta(alpha, beta_val)
    return min(samples, key=lambda k: samples[k])


def strip_cold_start(arms: dict[str, dict[str, float]]) -> None:
    """Remove arms still at the exact cold-start seed.

    Untouched arms carry no information beyond the sampler's built-in
    cold-start prior (see sample_weakest). Stripping them keeps persisted
    session state compact — important for cookie-backed sessions.

    Safe: any arm that has been through `bump` is no longer at cold-start
    (γ-decay multiplied by γ<1 and then +1 to at least one side leaves
    both counts ≠ _SEED_*), so no information is lost by this strip.
    """
    for key in list(arms.keys()):
        arm = arms[key]
        if (
            arm.get("correct") == _SEED_CORRECT
            and arm.get("incorrect") == _SEED_INCORRECT
        ):
            del arms[key]
