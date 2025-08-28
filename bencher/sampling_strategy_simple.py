"""Simplified sampling strategy for unified benchmarking interface.

This module provides a much simpler way to express sampling strategies by focusing
on the core requirement: determining the priority order of (repeat, level, benchmark_function)
permutations.
"""

from typing import List, Optional, Tuple
from enum import Enum
from itertools import product
from bencher.bench_cfg import BenchRunCfg


class SamplingOrder(Enum):
    """Defines the order of priority for sampling dimensions."""

    # Single dimension priorities
    REPEAT_FIRST = "repeat,level,function"  # Increase repeats first, then level, then function
    LEVEL_FIRST = "level,repeat,function"  # Increase level first, then repeats, then function
    FUNCTION_FIRST = "function,repeat,level"  # Change function first, then repeats, then level

    # Alternative orderings
    REPEAT_LEVEL_FUNCTION = "repeat,level,function"  # Same as REPEAT_FIRST
    LEVEL_REPEAT_FUNCTION = "level,repeat,function"  # Same as LEVEL_FIRST
    FUNCTION_REPEAT_LEVEL = "function,repeat,level"  # Same as FUNCTION_FIRST
    FUNCTION_LEVEL_REPEAT = "function,level,repeat"  # Function, then level, then repeat
    REPEAT_FUNCTION_LEVEL = "repeat,function,level"  # Repeat, then function, then level
    LEVEL_FUNCTION_REPEAT = "level,function,repeat"  # Level, then function, then repeat


class SamplingStrategy:
    """Simple, unified sampling strategy.

    Instead of multiple classes, this single class handles all permutation orderings
    through a simple priority specification.
    """

    def __init__(
        self,
        order: SamplingOrder = SamplingOrder.REPEAT_FIRST,
        level_range: Tuple[int, int] = (2, 6),
        repeat_range: Tuple[int, int] = (1, 5),
        functions: Optional[List[str]] = None,
    ):
        """Initialize sampling strategy.

        Args:
            order: The order in which to vary dimensions
            level_range: (min_level, max_level)
            repeat_range: (min_repeats, max_repeats)
            functions: List of function names (if None, assumes single function)
        """
        self.order = order
        self.level_range = level_range
        self.repeat_range = repeat_range
        self.functions = functions or ["default"]

    def generate_configs(self, base_cfg: BenchRunCfg) -> List[BenchRunCfg]:
        """Generate configurations in the specified order."""
        from copy import deepcopy

        # Create all combinations
        levels = list(range(self.level_range[0], self.level_range[1] + 1))
        repeats = list(range(self.repeat_range[0], self.repeat_range[1] + 1))
        functions = self.functions

        # Create all permutations
        all_combinations = list(product(repeats, levels, functions))

        # Sort according to the specified order
        priority_order = self.order.value.split(",")
        sorted_combinations = self._sort_by_priority(all_combinations, priority_order)

        # Generate configs
        configs = []
        for repeat, level, function in sorted_combinations:
            cfg = deepcopy(base_cfg)
            cfg.level = level
            cfg.repeats = repeat
            if len(self.functions) > 1:
                cfg.function_name = function
            configs.append(cfg)

        return configs

    def _sort_by_priority(
        self, combinations: List[Tuple], priority_order: List[str]
    ) -> List[Tuple]:
        """Sort combinations according to priority order.

        Args:
            combinations: List of (repeat, level, function) tuples
            priority_order: List like ['repeat', 'level', 'function']
        """
        # Map dimension names to tuple indices
        dim_map = {"repeat": 0, "level": 1, "function": 2}

        # Create sort key function based on priority order
        def sort_key(combo):
            return tuple(combo[dim_map[dim]] for dim in priority_order)

        return sorted(combinations, key=sort_key)


# Convenience factory functions for common patterns
def single_run(level: int = 2, repeats: int = 1) -> SamplingStrategy:
    """Create a single run strategy."""
    return SamplingStrategy(
        order=SamplingOrder.REPEAT_FIRST,
        level_range=(level, level),
        repeat_range=(repeats, repeats),
    )


def repeats_first(
    level_range: Tuple[int, int] = (2, 6), repeat_range: Tuple[int, int] = (1, 5)
) -> SamplingStrategy:
    """Strategy that varies repeats first, then level."""
    return SamplingStrategy(
        order=SamplingOrder.REPEAT_FIRST, level_range=level_range, repeat_range=repeat_range
    )


def level_first(
    level_range: Tuple[int, int] = (2, 6), repeat_range: Tuple[int, int] = (1, 5)
) -> SamplingStrategy:
    """Strategy that varies level first, then repeats."""
    return SamplingStrategy(
        order=SamplingOrder.LEVEL_FIRST, level_range=level_range, repeat_range=repeat_range
    )


def function_first(
    functions: List[str],
    level_range: Tuple[int, int] = (2, 6),
    repeat_range: Tuple[int, int] = (1, 5),
) -> SamplingStrategy:
    """Strategy that varies function first, then repeats, then level."""
    return SamplingStrategy(
        order=SamplingOrder.FUNCTION_FIRST,
        level_range=level_range,
        repeat_range=repeat_range,
        functions=functions,
    )


def custom_order(
    order_string: str,
    level_range: Tuple[int, int] = (2, 6),
    repeat_range: Tuple[int, int] = (1, 5),
    functions: Optional[List[str]] = None,
) -> SamplingStrategy:
    """Create custom ordering strategy.

    Args:
        order_string: Comma-separated priority order like "level,function,repeat"
        level_range: Range of levels to test
        repeat_range: Range of repeats to test
        functions: List of functions (if testing multiple)

    Example:
        # Level first, then function, then repeat
        strategy = custom_order("level,function,repeat", functions=["algo1", "algo2"])
    """

    # Create a custom enum value
    class CustomOrder(Enum):
        CUSTOM = order_string

    return SamplingStrategy(
        order=CustomOrder.CUSTOM,
        level_range=level_range,
        repeat_range=repeat_range,
        functions=functions,
    )


# Example usage and demonstration
if __name__ == "__main__":
    # Example 1: Simple repeats-first strategy
    strategy1 = repeats_first(level_range=(2, 4), repeat_range=(1, 3))
    print("Repeats first strategy:")
    print(f"Order: {strategy1.order.value}")

    # Example 2: Custom ordering - level first, then function, then repeat
    strategy2 = custom_order(
        "level,function,repeat",
        level_range=(2, 3),
        repeat_range=(1, 2),
        functions=["algo1", "algo2"],
    )
    print(f"\nCustom order strategy: {strategy2.order.value}")

    # Example 3: Single run
    strategy3 = single_run(level=5, repeats=10)
    print(f"\nSingle run strategy: level={strategy3.level_range}, repeats={strategy3.repeat_range}")
