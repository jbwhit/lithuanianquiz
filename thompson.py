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

    Arms are sampled in sorted key order so results are independent of dict
    insertion order. Ties break by the sampled value itself.
    """
    samples: dict[str, Any] = {}
    for arm in sorted(arms):
        stats = arms[arm]
        alpha = stats["correct"] + 1.0
        beta_val = stats["incorrect"] + 1.0
        samples[arm] = np.random.beta(alpha, beta_val)
    return min(samples, key=lambda k: samples[k])
