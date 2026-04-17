"""Unit tests for the shared Thompson-sampling helpers."""

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
        """ESS converges to 1/(1-γ) under any fixed correct/incorrect mix.

        Each bump adds exactly 1.0 to the total and both sides decay at γ,
        so the steady-state bound is independent of the outcome distribution.
        The all-correct streak here is just one convenient way to exercise it.
        """
        arms: dict[str, dict[str, float]] = {}
        for _ in range(1000):
            bump(arms, "a", is_correct=True)
        ess = arms["a"]["correct"] + arms["a"]["incorrect"]
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
        ab = sample_weakest(
            {
                "a": {"correct": 1.0, "incorrect": 1.0},
                "b": {"correct": 1.0, "incorrect": 1.0},
            }
        )
        np.random.seed(42)
        ba = sample_weakest(
            {
                "b": {"correct": 1.0, "incorrect": 1.0},
                "a": {"correct": 1.0, "incorrect": 1.0},
            }
        )
        # With the same RNG seed and equal posteriors, the chosen arm should
        # be determined by sample values, not by which key is listed first.
        assert ab == ba


class TestSampleWeakestVirtual:
    def test_full_keys_covers_unseen_arms_without_mutating_tracked(self) -> None:
        """Passing `full_keys` must let the sampler consider arms that
        aren't in `tracked` (using the cold-start seed), while leaving
        `tracked` untouched."""
        np.random.seed(0)
        tracked: dict[str, dict[str, float]] = {}
        # Any single call must return a key from full_keys even though
        # tracked is empty — the sampler treats missing keys as cold-start.
        result = sample_weakest(tracked, ["a", "b", "c"])
        assert result in {"a", "b", "c"}
        assert tracked == {}  # unchanged

    def test_full_keys_heavily_favors_observed_weakness(self) -> None:
        """A strongly-observed arm should still be overridden by an
        unseen (cold-start) arm, because cold-start posterior mean 1/3
        is weaker than an arm with many correct observations."""
        np.random.seed(0)
        tracked = {"strong": {"correct": 20.0, "incorrect": 0.5}}
        full_keys = ["strong", "fresh"]
        picks = [sample_weakest(tracked, full_keys) for _ in range(200)]
        # "fresh" (cold-start, mean 1/3) should dominate "strong" (mean ~0.97).
        assert picks.count("fresh") > picks.count("strong") * 5

    def test_missing_full_keys_falls_back_to_tracked(self) -> None:
        tracked = {"only": {"correct": 1.0, "incorrect": 1.0}}
        result = sample_weakest(tracked)
        assert result == "only"


class TestStripColdStart:
    def test_removes_only_exact_cold_start_arms(self) -> None:
        from thompson import strip_cold_start

        arms = {
            "untouched": {"correct": 0.0, "incorrect": 1.0},
            "touched": {"correct": 1.0, "incorrect": 0.98},
            "also_untouched": {"correct": 0.0, "incorrect": 1.0},
        }
        strip_cold_start(arms)
        assert set(arms.keys()) == {"touched"}

    def test_never_strips_a_bumped_arm(self) -> None:
        """Post-γ-decay bump, no arm can land exactly at (0.0, 1.0)."""
        from thompson import strip_cold_start

        arms: dict[str, dict[str, float]] = {}
        for is_correct in (True, False):
            key = "c" if is_correct else "i"
            bump(arms, key, is_correct)
        strip_cold_start(arms)
        assert set(arms.keys()) == {"c", "i"}  # both survive
