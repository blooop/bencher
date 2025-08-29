"""Simple sampling strategies that define iteration order for benchmarking.

Uses the 6 basic permutations defined in simple_sampling.py to avoid duplication.
"""

import itertools
from typing import Iterator, List
from copy import deepcopy
from bencher.simple_sampling import SamplingStrategy as SimpleSamplingStrategy


class SamplingOrder:
    """Defines the iteration order for (repeats, levels, benchmarks)."""

    def __init__(self, order: str):
        """Initialize with order string like 'repeats,levels,benchmarks'."""
        self.order = order.split(",")

    def generate_configs(
        self, base_cfg, levels: List[int], repeats: List[int], benchmark_indices: List[int]
    ) -> Iterator:
        """Generate BenchRunCfg instances in the specified order."""
        # Map names to actual values
        values = {"repeats": repeats, "levels": levels, "benchmarks": benchmark_indices}

        # Get ordered iterables
        ordered_values = [values[name] for name in self.order]

        # Generate cartesian product in specified order
        for combo in itertools.product(*ordered_values):
            # Map back to named values
            result = dict(zip(self.order, combo))

            cfg = deepcopy(base_cfg)
            cfg.repeats = result["repeats"]
            cfg.level = result["levels"]
            cfg._benchmark_idx = result["benchmarks"]  # pylint: disable=protected-access
            yield cfg


# Create SamplingOrder instances from the enum values to avoid duplication
REPEATS_LEVELS_BENCHMARKS = SamplingOrder(SimpleSamplingStrategy.REPEATS_LEVELS_BENCHMARKS.value)
REPEATS_BENCHMARKS_LEVELS = SamplingOrder(SimpleSamplingStrategy.REPEATS_BENCHMARKS_LEVELS.value)
LEVELS_REPEATS_BENCHMARKS = SamplingOrder(SimpleSamplingStrategy.LEVELS_REPEATS_BENCHMARKS.value)
LEVELS_BENCHMARKS_REPEATS = SamplingOrder(SimpleSamplingStrategy.LEVELS_BENCHMARKS_REPEATS.value)
BENCHMARKS_REPEATS_LEVELS = SamplingOrder(SimpleSamplingStrategy.BENCHMARKS_REPEATS_LEVELS.value)
BENCHMARKS_LEVELS_REPEATS = SamplingOrder(SimpleSamplingStrategy.BENCHMARKS_LEVELS_REPEATS.value)
