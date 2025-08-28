"""Ultra-simple sampling strategy with autocomplete-friendly enums."""

from enum import Enum


class SamplingStrategy(Enum):
    """Simple enum for sampling strategies - perfect for autocomplete!

    Each strategy defines the ORDER of iteration through (repeat, level) combinations.
    The actual values come from the run() method parameters.
    """

    # Single run strategies
    SINGLE = "single"  # Just one run with specified level/repeats

    # Progressive strategies (most common)
    REPEATS_FIRST = "repeats_first"  # Exhaust repeats before increasing level
    LEVEL_FIRST = "level_first"  # Exhaust levels before increasing repeats
    ALTERNATING = "alternating"  # Alternate between repeat and level increases

    # Balanced strategy
    BALANCED = "balanced"  # Smart progression balancing time vs accuracy
