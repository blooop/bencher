"""Lightweight timing instrumentation for bencher sweep phases."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass


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
    job_submit_and_execute_ms: float = 0.0
    result_collection_ms: float = 0.0
    history_merge_ms: float = 0.0
    post_setup_ms: float = 0.0
    total_ms: float = 0.0

    def summary(self) -> dict[str, float]:
        """Return all phase timings as a dict."""
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


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


class Stopwatch:
    """Simple stopwatch for measuring total elapsed time across a function.

    Usage::

        sw = Stopwatch()
        ...
        timings.total_ms = sw.elapsed_ms()
    """

    def __init__(self):
        self._t0 = time.perf_counter()

    def elapsed_ms(self) -> float:
        """Return elapsed milliseconds since creation."""
        return (time.perf_counter() - self._t0) * 1000.0
