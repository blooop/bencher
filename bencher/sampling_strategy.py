"""DEPRECATED: Complex sampling strategy definitions.

This module is deprecated. Use the simple enum-based approach instead:

from bencher.simple_sampling import SamplingStrategy

# Old way (deprecated):
from bencher.sampling_strategy import repeats_first, level_first
runner.run(sampling_strategy=repeats_first(...))

# New way (recommended):
runner.run(level=2, max_level=6, repeats=1, max_repeats=5,
           simple_sampling=SamplingStrategy.REPEATS_FIRST)
"""

import warnings

warnings.warn(
    "bencher.sampling_strategy is deprecated. Use bencher.simple_sampling instead.",
    DeprecationWarning,
    stacklevel=2,
)
