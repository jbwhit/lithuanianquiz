"""Shared Thompson Sampling utilities for adaptive learning."""

from typing import Any

import numpy as np


def bump(
    category: dict[str, dict[str, int]],
    key: str,
    is_correct: bool,
) -> None:
    """Create arm if missing, then increment correct/incorrect."""
    if key not in category:
        category[key] = {"correct": 0, "incorrect": 1}
    side = "correct" if is_correct else "incorrect"
    category[key][side] += 1


def sample_weakest(arms: dict[str, dict[str, int]]) -> str:
    """Thompson-sample and return the arm with the *lowest* draw."""
    samples: dict[str, Any] = {}
    for arm, stats in arms.items():
        alpha = stats["correct"] + 1
        beta_val = stats["incorrect"] + 1
        samples[arm] = np.random.beta(alpha, beta_val)
    return min(samples, key=samples.get)
