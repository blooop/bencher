"""Lightweight timing instrumentation for bencher sweep phases."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, fields


@dataclass
class SweepTimings:
    """Timing data for a single run_sweep() call.

    Each field records the wall-clock duration in milliseconds of a
    major phase inside ``Bench.run_sweep()`` or
    ``Bench.calculate_benchmark_results()``.
    """

    cache_check_ms: float = 0.0
    sample_cache_init_ms: float = 0.0
    dataset_setup_ms: float = 0.0
    job_submission_ms: float = 0.0  #: Job object creation (consistent across executors)
    job_execution_ms: float = 0.0  #: Job submission, execution, and result storage
    history_merge_ms: float = 0.0
    post_setup_ms: float = 0.0
    total_ms: float = 0.0  #: Sum of all phase timings above

    def compute_total(self) -> float:
        """Compute total_ms as the sum of all phase timing fields."""
        return sum(
            getattr(self, f.name)
            for f in fields(self)
            if f.name != "total_ms" and f.name.endswith("_ms")
        )

    def summary(self) -> dict[str, float]:
        """Return all phase timings as a dict."""
        return {f.name: getattr(self, f.name) for f in fields(self)}


@contextmanager
def phase_timer():
    """Context manager that yields a callable returning elapsed milliseconds.

    Usage::

        with phase_timer() as elapsed:
            do_work()
        timings.some_phase_ms = elapsed()
    """
    t0 = time.perf_counter()
    result = [0.0]

    def _elapsed():
        return result[0]

    yield _elapsed
    result[0] = (time.perf_counter() - t0) * 1000.0
