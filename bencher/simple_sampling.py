"""Ultra-simple sampling strategy with autocomplete-friendly enums."""

from enum import Enum


class SamplingStrategy(Enum):
    """Simple enum for sampling strategies - perfect for autocomplete!

    Each strategy defines the ORDER of iteration through (repeats, levels, benchmarks) combinations.
    The actual values come from the run() method parameters.
    """

    # All possible orderings of (repeats, levels, benchmarks)
    REPEATS_LEVELS_BENCHMARKS = (
        "repeats,levels,benchmarks"  # Vary repeats first, then levels, then benchmarks
    )
    REPEATS_BENCHMARKS_LEVELS = (
        "repeats,benchmarks,levels"  # Vary repeats first, then benchmarks, then levels
    )
    LEVELS_REPEATS_BENCHMARKS = (
        "levels,repeats,benchmarks"  # Vary levels first, then repeats, then benchmarks
    )
    LEVELS_BENCHMARKS_REPEATS = (
        "levels,benchmarks,repeats"  # Vary levels first, then benchmarks, then repeats
    )
    BENCHMARKS_REPEATS_LEVELS = (
        "benchmarks,repeats,levels"  # Vary benchmarks first, then repeats, then levels
    )
    BENCHMARKS_LEVELS_REPEATS = (
        "benchmarks,levels,repeats"  # Vary benchmarks first, then levels, then repeats
    )
