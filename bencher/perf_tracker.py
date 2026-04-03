"""Lightweight performance tracking for benchmark phases."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class PhaseTime:
    """Timing for a single named phase."""

    name: str
    duration_s: float

    @property
    def duration_ms(self) -> float:
        return self.duration_s * 1000


@dataclass
class PerfReport:
    """Collection of phase timings from a benchmark run."""

    phases: list[PhaseTime] = field(default_factory=list)

    @property
    def total_s(self) -> float:
        return sum(p.duration_s for p in self.phases)

    @property
    def total_ms(self) -> float:
        return self.total_s * 1000

    def get_phase(self, name: str) -> PhaseTime | None:
        """Return the first phase matching *name*, or None."""
        for p in self.phases:
            if p.name == name:
                return p
        return None

    def summary(self) -> str:
        """Human-readable summary of all phases."""
        lines = ["Performance report:"]
        for p in self.phases:
            lines.append(f"  {p.name}: {p.duration_ms:.1f} ms")
        lines.append(f"  TOTAL: {self.total_ms:.1f} ms")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Return phases as {name: duration_ms} plus a total."""
        d = {p.name: p.duration_ms for p in self.phases}
        d["total"] = self.total_ms
        return d


class PerfTracker:
    """Context-manager based phase timer.

    Usage::

        tracker = PerfTracker()
        with tracker.phase("setup"):
            do_setup()
        with tracker.phase("compute"):
            do_compute()
        report = tracker.report()
    """

    def __init__(self) -> None:
        self._phases: list[PhaseTime] = []

    @contextmanager
    def phase(self, name: str):
        """Time a block and record it as a named phase."""
        t0 = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - t0
            self._phases.append(PhaseTime(name=name, duration_s=elapsed))

    def report(self) -> PerfReport:
        """Build a PerfReport from all recorded phases."""
        return PerfReport(phases=list(self._phases))

    def log_summary(self) -> None:
        """Log the report summary at INFO level."""
        logging.info(self.report().summary())
