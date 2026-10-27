"""Decide whether a test is flaky with Wald's sequential probability ratio test.

Running a test a fixed number of times and computing a Clopper-Pearson interval
wastes runs on clear cases. Recomputing that interval after every run and stopping
once it looks good ("optional stopping") is worse: it inflates the false-pass rate
far above the nominal one. The SPRT stops as soon as the evidence allows and still
keeps its error rates.

You state two failure rates and two error tolerances:

- ``p0``: an acceptable failure rate (the test is good)
- ``p1``: an unacceptable failure rate (the test is flaky)
- ``alpha``: the risk of calling a good test flaky
- ``beta``: the risk of passing a flaky test

A running log-likelihood ratio (LLR) moves down a little on each pass and up a lot
on each failure. The test is :attr:`SprtVerdict.FLAKY` once the LLR reaches
``ln((1-beta)/alpha)``, and :attr:`SprtVerdict.PASS` once it falls to
``ln(beta/(1-alpha))``. With ``p0=0.1%, p1=1%, alpha=5%, beta=10%`` a test with no
failures passes after 249 runs, one failure pushes that out to about 505, and a fresh
test whose first two failures have at most 189 passes between them is rejected.
Passes before the first failure shrink that window: after 100 passes it is 89.

Pick ``p1`` at 5-10x ``p0``: the run count grows roughly as ``1/(p1-p0)**2``. Report
the verdict, not an interval -- the verdict carries the alpha/beta guarantee, and a
Clopper-Pearson interval computed after a sequential stop is biased. If you need an
interval that stays valid at any stopping point, use an anytime-valid confidence
sequence instead (e.g. the beta-binomial mixture of Howard et al., 2021).

Example::

    result = bn.sprt(lambda: run_my_test() == 0, bn.SprtCfg(p0=0.001, p1=0.01))
    print(result.verdict, result.runs, result.failure_runs)

This module imports only the standard library, so a caller without bencher's
dependencies can load the file by path.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# Below this |drift| Wald's ASN formula divides by ~0, so use its zero-drift limit.
_ZERO_DRIFT = 1e-12
# Cap on the bracket for the OC exponent; real roots sit well inside it.
_MAX_EXPONENT = 1e3


class SprtVerdict(StrEnum):
    PASS = "PASS"  # noqa: S105 - a verdict, not a password
    """The failure rate is at most ``p0``, with false-pass risk ``beta``."""
    FLAKY = "FLAKY"
    """The failure rate is at least ``p1``, with false-flaky risk ``alpha``."""
    INCONCLUSIVE = "INCONCLUSIVE"
    """``max_runs`` ran out before the evidence crossed either boundary."""


@dataclass(frozen=True)
class SprtCfg:
    """The hypotheses and error tolerances of one SPRT."""

    p0: float
    p1: float
    alpha: float = 0.05
    beta: float = 0.10
    max_runs: int = 10_000

    def __post_init__(self) -> None:
        if not 0.0 < self.p0 < self.p1 < 1.0:
            raise ValueError(f"need 0 < p0 < p1 < 1, got p0={self.p0!r}, p1={self.p1!r}")
        for name, value in (("alpha", self.alpha), ("beta", self.beta)):
            if not 0.0 < value < 1.0:
                raise ValueError(f"need 0 < {name} < 1, got {value!r}")
        if self.alpha + self.beta >= 1.0:
            raise ValueError(f"need alpha + beta < 1, got {self.alpha + self.beta!r}")
        if self.max_runs < 1:
            raise ValueError(f"need max_runs >= 1, got {self.max_runs!r}")

    @property
    def flaky_bound(self) -> float:
        """The LLR at or above which the test is flaky."""
        return math.log((1 - self.beta) / self.alpha)

    @property
    def pass_bound(self) -> float:
        """The LLR at or below which the test passes."""
        return math.log(self.beta / (1 - self.alpha))

    @property
    def fail_step(self) -> float:
        """The LLR increase from one failure (positive)."""
        return math.log(self.p1 / self.p0)

    @property
    def pass_step(self) -> float:
        """The LLR change from one pass (negative)."""
        return math.log((1 - self.p1) / (1 - self.p0))

    def runs_to_pass(self, failures: int = 0) -> int:
        """Fewest total runs that end in PASS when ``failures`` of them failed.

        Assumes the failures are spread out enough not to reach FLAKY first, and
        ignores ``max_runs``.
        """
        if failures < 0:
            raise ValueError(f"need failures >= 0, got {failures!r}")
        start = failures * self.fail_step
        passes = max(0, math.ceil((start - self.pass_bound) / -self.pass_step))
        # Correct the float rounding of ceil so the boundary check matches Sprt.record.
        while passes > 0 and start + (passes - 1) * self.pass_step <= self.pass_bound:
            passes -= 1
        while start + passes * self.pass_step > self.pass_bound:
            passes += 1
        return failures + passes

    def flaky_window(self) -> int | None:
        """Most passes between a fresh test's first two failures that still reach FLAKY.

        ``None`` when two failures cannot reach FLAKY however close they are.
        """
        slack = 2 * self.fail_step - self.flaky_bound
        if slack < 0:
            return None
        return math.floor(slack / -self.pass_step)

    def expected_runs(self, p_fail: float) -> float:
        """Wald's approximation of the mean run count when the true failure rate is ``p_fail``.

        It ignores the overshoot past a boundary and ``max_runs``, so real runs are
        a little longer.
        """
        if not 0.0 <= p_fail <= 1.0:
            raise ValueError(f"need 0 <= p_fail <= 1, got {p_fail!r}")
        a, b = self.flaky_bound, self.pass_bound
        f, s = self.fail_step, self.pass_step
        if p_fail == 0.0:
            return b / s
        if p_fail == 1.0:
            return a / f
        drift = p_fail * f + (1 - p_fail) * s
        if abs(drift) < _ZERO_DRIFT:
            return -a * b / (p_fail * f * f + (1 - p_fail) * s * s)
        h = _oc_exponent(p_fail, f, s, drift)
        accept = (math.exp(h * a) - 1) / (math.exp(h * a) - math.exp(h * b))
        return (accept * b + (1 - accept) * a) / drift


def _oc_exponent(p_fail: float, f: float, s: float, drift: float) -> float:
    """The non-zero ``h`` with ``E[exp(h*z)] = 1`` for one run's LLR step ``z``."""

    def g(h: float) -> float:
        return p_fail * math.exp(h * f) + (1 - p_fail) * math.exp(h * s) - 1

    # g is convex with g(0) = 0 and g'(0) = drift, so the other root lies on the side
    # opposite the drift. Bracket it by doubling, then bisect.
    sign = 1.0 if drift < 0 else -1.0
    far = 1.0
    while g(sign * far) < 0 and far < _MAX_EXPONENT:
        far *= 2
    near = 0.0
    for _ in range(200):
        mid = (near + far) / 2
        if g(sign * mid) < 0:
            near = mid
        else:
            far = mid
    return sign * (near + far) / 2


@dataclass(frozen=True)
class SprtResult:
    """The verdict of a finished SPRT and the runs that led to it."""

    verdict: SprtVerdict
    runs: int
    failure_runs: tuple[int, ...]
    """The 1-based run index of each failure, to check for clustering (state leakage)."""
    llr: float

    @property
    def failures(self) -> int:
        return len(self.failure_runs)


@dataclass
class Sprt:
    """An SPRT fed one run at a time, for callers that own the run loop."""

    cfg: SprtCfg
    _runs: int = field(default=0, init=False)
    _llr: float = field(default=0.0, init=False)
    _failure_runs: list[int] = field(default_factory=list, init=False)
    _verdict: SprtVerdict | None = field(default=None, init=False)

    @property
    def runs(self) -> int:
        return self._runs

    @property
    def llr(self) -> float:
        return self._llr

    @property
    def failure_runs(self) -> tuple[int, ...]:
        return tuple(self._failure_runs)

    @property
    def verdict(self) -> SprtVerdict | None:
        return self._verdict

    def record(self, passed: bool) -> SprtVerdict | None:
        """Add one run. Return the verdict once there is one, else ``None``."""
        if self._verdict is not None:
            raise RuntimeError(f"SPRT already decided {self._verdict} after {self._runs} runs")
        self._runs += 1
        if passed:
            self._llr += self.cfg.pass_step
        else:
            self._llr += self.cfg.fail_step
            self._failure_runs.append(self._runs)
        if self._llr >= self.cfg.flaky_bound:
            self._verdict = SprtVerdict.FLAKY
        elif self._llr <= self.cfg.pass_bound:
            self._verdict = SprtVerdict.PASS
        elif self._runs >= self.cfg.max_runs:
            self._verdict = SprtVerdict.INCONCLUSIVE
        return self._verdict

    def result(self) -> SprtResult:
        if self._verdict is None:
            raise RuntimeError(f"SPRT has no verdict yet after {self._runs} runs")
        return SprtResult(self._verdict, self._runs, tuple(self._failure_runs), self._llr)


def sprt(run_test: Callable[[], bool], cfg: SprtCfg) -> SprtResult:
    """Call ``run_test`` (True on pass) until the SPRT reaches a verdict."""
    test = Sprt(cfg)
    while test.record(run_test()) is None:
        pass
    return test.result()
