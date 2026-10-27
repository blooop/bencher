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
``ln(beta/(1-alpha))``. These are Wald's boundaries: they ignore the overshoot past a
boundary, so ``alpha`` and ``beta`` are targets, not hard limits. Wald proves the real
rates stay at or below ``alpha/(1-beta)`` and ``beta/(1-alpha)`` (5.6 % and 10.5 % for
the values below), and their sum stays at or below ``alpha + beta``.

With ``p0=0.1%, p1=1%, alpha=5%, beta=10%`` a test with no failures passes after
249 runs, one failure pushes that out to about 505, and a fresh
test whose first two failures have at most 189 passes between them is rejected.
Passes before the first failure shrink that window: after 100 passes it is 89.

Pick ``p1`` at 5-10x ``p0``: the run count grows roughly as ``1/(p1-p0)**2``. Report
the verdict, not an interval -- the verdict carries the error-rate guarantee, and a
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
import numbers
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

if TYPE_CHECKING:
    from collections.abc import Callable

# Below this |x|, (expm1(x) - x) / x**2 loses digits, so use its Taylor series.
_SERIES_LIMIT = 1e-2


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
        # A float, inf or nan cap would never equal the int run count, so the cap
        # would never stop the test.
        is_int = isinstance(self.max_runs, numbers.Integral) and not isinstance(self.max_runs, bool)
        if not is_int or self.max_runs < 1:
            raise ValueError(f"need an int max_runs >= 1, got {self.max_runs!r}")

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

        ``None`` when no such window exists: either two failures cannot reach FLAKY
        however close they are, or one failure alone reaches FLAKY
        (``fail_step >= flaky_bound``), so there is never a second failure.
        """
        slack = 2 * self.fail_step - self.flaky_bound
        if slack < 0 or self.fail_step >= self.flaky_bound:
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
        h = _oc_exponent(p_fail, f, s)
        if abs(h) * max(a, -b, f, -s) <= 1:
            # Near zero drift Wald's formula is 0/0. Written with _phi and _psi it is a
            # ratio of sums of positive terms, which keeps full precision down to h = 0.
            mass = p_fail * f * f * _psi(h * f) + (1 - p_fail) * s * s * _psi(h * s)
            spread = a * _psi(h * a) - b * _psi(h * b)
            width = a * _phi(h * a) - b * _phi(h * b)
            return -a * b * spread / (width * mass)
        drift = p_fail * f + (1 - p_fail) * s
        # P(PASS) = (exp(h*a) - 1) / (exp(h*a) - exp(h*b)), divided through by the
        # larger exponential so it cannot overflow.
        if h > 0:
            accept = math.expm1(-h * a) / math.expm1(h * (b - a))
        else:
            accept = 1 - math.expm1(-h * b) / math.expm1(h * (a - b))
        return (accept * b + (1 - accept) * a) / drift


def _phi(x: float) -> float:
    """``expm1(x) / x``, which is 1 at 0."""
    return math.expm1(x) / x if x else 1.0


def _psi(x: float) -> float:
    """``(expm1(x) - x) / x**2``, which is 1/2 at 0."""
    if abs(x) < _SERIES_LIMIT:
        return 1 / 2 + x * (1 / 6 + x * (1 / 24 + x * (1 / 120 + x * (1 / 720 + x / 5040))))
    return (math.expm1(x) - x) / (x * x)


def _log_phi(x: float) -> float:
    """``log(expm1(x) / x)`` without overflow."""
    if x > 0:
        return x + math.log(-math.expm1(-x) / x)
    return math.log(_phi(x))


def _oc_exponent(p_fail: float, f: float, s: float) -> float:
    """The ``h`` other than 0 with ``E[exp(h*z)] = 1`` for one run's LLR step ``z``.

    It is 0 when the drift ``E[z]`` is exactly 0, where the two roots meet.
    """
    log_fail = math.log(p_fail) + math.log(f)
    log_pass = math.log1p(-p_fail) + math.log(-s)

    def q(h: float) -> float:
        # (E[exp(h*z)] - 1) / h = p*f*phi(h*f) + (1-p)*s*phi(h*s) is increasing in h
        # and equals the drift at 0. This has its sign, in logs so it cannot overflow.
        return log_fail + _log_phi(h * f) - log_pass - _log_phi(h * s)

    if q(0.0) == 0:
        return 0.0
    # The root lies on the side opposite the drift. Bracket it by doubling, then bisect.
    sign = 1.0 if q(0.0) < 0 else -1.0
    far = 1.0
    while sign * q(sign * far) < 0:
        far *= 2
    near = 0.0
    for _ in range(200):
        mid = (near + far) / 2
        if sign * q(sign * mid) < 0:
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


@dataclass(init=False)
class Sprt:
    """An SPRT fed one run at a time, for callers that own the run loop."""

    _cfg: SprtCfg
    _runs: int
    _llr: float
    _failure_runs: list[int]
    _verdict: SprtVerdict | None

    def __init__(self, cfg: SprtCfg) -> None:
        self._cfg = cfg
        self._runs = 0
        self._llr = 0.0
        self._failure_runs = []
        self._verdict = None

    @property
    def cfg(self) -> SprtCfg:
        return self._cfg

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
            self._llr += self._cfg.pass_step
        else:
            self._llr += self._cfg.fail_step
            self._failure_runs.append(self._runs)
        if self._llr >= self._cfg.flaky_bound:
            self._verdict = SprtVerdict.FLAKY
        elif self._llr <= self._cfg.pass_bound:
            self._verdict = SprtVerdict.PASS
        elif self._runs >= self._cfg.max_runs:
            self._verdict = SprtVerdict.INCONCLUSIVE
        return self._verdict

    def result(self) -> SprtResult:
        if self._verdict is None:
            raise RuntimeError(f"SPRT has no verdict yet after {self._runs} runs")
        return SprtResult(self._verdict, self._runs, tuple(self._failure_runs), self._llr)

    def to_svg(self) -> str:
        """Draw the walk on Wald's chart: cumulative failures against runs.

        Each run is a point: a grey dot for a pass, a red dot for a failure. The two
        boundary lines are the LLR bounds mapped to failure counts, and the walk stops
        at the line it crosses. ``runs`` and ``failure_runs`` fix every point, so the
        chart is exact. Beyond ``_SVG_MAX_PASS_DOTS`` passes it thins the pass dots;
        every failure stays a dot. Only the standard library is used.
        """
        return _render_svg(self.cfg, self._runs, self._failure_runs, self._verdict, self._llr)

    def _repr_svg_(self) -> str:
        return self.to_svg()

    def save_svg(self, path: str | Path) -> Path:
        """Write :meth:`to_svg` to ``path`` and return the path."""
        path = Path(path)
        path.write_text(self.to_svg(), encoding="utf-8")
        return path


# Pass dots beyond this count are thinned to every n-th pass; failures are never thinned.
_SVG_MAX_PASS_DOTS = 1500
_SVG_W, _SVG_H = 760, 460
_SVG_LEFT, _SVG_RIGHT, _SVG_TOP, _SVG_BOTTOM = 64, 24, 72, 84
_VERDICT_COLOUR = {
    SprtVerdict.PASS: "#15803d",
    SprtVerdict.FLAKY: "#b91c1c",
    SprtVerdict.INCONCLUSIVE: "#b45309",
    None: "#374151",
}
_WHY = {
    SprtVerdict.PASS: "the walk fell to the PASS line",
    SprtVerdict.FLAKY: "the walk reached the FLAKY line",
    SprtVerdict.INCONCLUSIVE: "max_runs ran out in the band",
    None: "no verdict yet, still in the band",
}


def _nice_step(span: float, target: int = 6) -> float:
    raw = span / target
    mag = 10 ** math.floor(math.log10(raw))
    for mult in (1, 2, 5):
        if raw <= mult * mag:
            return mult * mag
    return 10 * mag


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _render_svg(
    cfg: SprtCfg,
    runs: int,
    failure_runs: list[int],
    verdict: SprtVerdict | None,
    llr: float,
) -> str:
    failures = len(failure_runs)
    # In (runs n, cumulative failures k) the LLR is k*f + (n-k)*s, so each bound is a line.
    f, s = cfg.fail_step, cfg.pass_step

    def upper(n: float) -> float:
        return (cfg.flaky_bound - n * s) / (f - s)

    def lower(n: float) -> float:
        return (cfg.pass_bound - n * s) / (f - s)

    x_hi = max(runs, cfg.runs_to_pass(0)) * 1.1
    if cfg.max_runs <= x_hi * 1.5:
        x_hi = cfg.max_runs * 1.04
    y_lo = min(0.0, math.floor(lower(0)))
    y_hi = math.ceil(max(failures, upper(min(x_hi, max(runs, 1) * 1.1)))) + 0.5
    pw = _SVG_W - _SVG_LEFT - _SVG_RIGHT
    ph = _SVG_H - _SVG_TOP - _SVG_BOTTOM
    bottom = _SVG_TOP + ph

    def px(n: float) -> float:
        return _SVG_LEFT + n / x_hi * pw

    def py(k: float) -> float:
        return _SVG_TOP + (y_hi - k) / (y_hi - y_lo) * ph

    def pt(n: float, k: float) -> str:
        return f"{px(n):.1f},{py(k):.1f}"

    colour = _VERDICT_COLOUR[verdict]
    why = _WHY[verdict]
    title = f"{verdict or 'SPRT running'}: {_plural(runs, 'run')}, {_plural(failures, 'failure')}"
    params = (
        f"p0={cfg.p0:g}  p1={cfg.p1:g}  alpha={cfg.alpha:g}  beta={cfg.beta:g}  "
        f"max_runs={cfg.max_runs}  LLR={llr:.2f} (FLAKY at {cfg.flaky_bound:.2f}, "
        f"PASS at {cfg.pass_bound:.2f})"
    )

    out = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{_SVG_W}" height="{_SVG_H}" '
            f'viewBox="0 0 {_SVG_W} {_SVG_H}" font-family="sans-serif" font-size="12" '
            'fill="#111827">'
        ),
        f"<title>{escape(title)}; {escape(why)}</title>",
        (
            '<defs><clipPath id="sprt-plot">'
            f'<rect x="{_SVG_LEFT}" y="{_SVG_TOP}" width="{pw}" height="{ph}"/></clipPath></defs>'
        ),
        f'<rect width="{_SVG_W}" height="{_SVG_H}" fill="#ffffff"/>',
        (
            f'<text x="{_SVG_LEFT}" y="26" font-size="17" font-weight="bold" fill="{colour}">'
            f'{escape(title)}<tspan font-weight="normal" fill="#374151">; {escape(why)}'
            "</tspan></text>"
        ),
        f'<text x="{_SVG_LEFT}" y="48" fill="#4b5563">{escape(params)}</text>',
        '<g clip-path="url(#sprt-plot)">',
        # Regions: FLAKY above the upper line, PASS below the lower one.
        f'<rect x="{_SVG_LEFT}" y="{_SVG_TOP}" width="{pw}" height="{ph}" fill="#fee2e2"/>',
        (
            f'<polygon fill="#d1fae5" points="{pt(0, lower(0))} '
            f'{pt(x_hi, lower(x_hi))} {pt(x_hi, y_lo)} {pt(0, y_lo)}"/>'
        ),
        (
            f'<polygon class="continue-band" fill="#ffffff" points="{pt(0, lower(0))} '
            f'{pt(x_hi, lower(x_hi))} {pt(x_hi, upper(x_hi))} {pt(0, upper(0))}"/>'
        ),
        '<g stroke="#d1d5db" stroke-width="1">',
    ]

    labels = []
    x_step = _nice_step(x_hi)
    for i in range(int(x_hi / x_step) + 1):
        x = px(i * x_step)
        out.append(f'<line x1="{x:.1f}" y1="{_SVG_TOP}" x2="{x:.1f}" y2="{bottom}"/>')
        labels.append(
            f'<text x="{x:.1f}" y="{bottom + 16}" text-anchor="middle">{i * x_step:g}</text>'
        )
    y_step = max(1, round(_nice_step(y_hi - y_lo)))
    for k in range(math.ceil(y_lo / y_step) * y_step, math.floor(y_hi) + 1, y_step):
        y = py(k)
        out.append(f'<line x1="{_SVG_LEFT}" y1="{y:.1f}" x2="{_SVG_LEFT + pw}" y2="{y:.1f}"/>')
        labels.append(f'<text x="{_SVG_LEFT - 8}" y="{y + 4:.1f}" text-anchor="end">{k}</text>')
    out.append("</g>")

    out.append(
        f'<line class="boundary-flaky" x1="{px(0):.1f}" y1="{py(upper(0)):.1f}" '
        f'x2="{px(x_hi):.1f}" y2="{py(upper(x_hi)):.1f}" stroke="#b91c1c" stroke-width="2"/>'
    )
    out.append(
        f'<line class="boundary-pass" x1="{px(0):.1f}" y1="{py(lower(0)):.1f}" '
        f'x2="{px(x_hi):.1f}" y2="{py(lower(x_hi)):.1f}" stroke="#15803d" stroke-width="2"/>'
    )

    # The walk is a straight line between failures, so only the failure steps need vertices.
    path = [pt(0, 0)]
    for i, r in enumerate(failure_runs):
        path += [pt(r - 1, i), pt(r, i + 1)]
    path.append(pt(runs, failures))
    out.append(
        f'<polyline fill="none" stroke="#9ca3af" stroke-width="1" points="{" ".join(path)}"/>'
    )

    stride = max(1, math.ceil((runs - failures) / _SVG_MAX_PASS_DOTS))
    fail_set = set(failure_runs)
    out.append('<g fill="#9ca3af">')
    failed = passed = 0
    for r in range(1, runs + 1):
        if r in fail_set:
            failed += 1
            continue
        passed += 1
        if passed % stride == 0 or r == runs:
            out.append(f'<circle class="pass" cx="{px(r):.1f}" cy="{py(failed):.1f}" r="1.6"/>')
    out.append("</g>")
    out.append('<g fill="#dc2626" stroke="#ffffff" stroke-width="1">')
    out += [
        f'<circle class="failure" cx="{px(r):.1f}" cy="{py(i + 1):.1f}" r="4.5"/>'
        for i, r in enumerate(failure_runs)
    ]
    out.append("</g></g>")  # end of the clipped plot

    out.append(
        f'<rect x="{_SVG_LEFT}" y="{_SVG_TOP}" width="{pw}" height="{ph}" fill="none" '
        'stroke="#6b7280"/>'
    )
    if cfg.max_runs <= x_hi:
        cap = px(cfg.max_runs)
        out.append(
            f'<line class="max-runs" x1="{cap:.1f}" y1="{_SVG_TOP}" x2="{cap:.1f}" '
            f'y2="{bottom}" stroke="#b45309" stroke-width="1.5" stroke-dasharray="6 4"/>'
        )
        out.append(
            f'<text x="{cap - 4:.1f}" y="{bottom - 28}" text-anchor="end" '
            f'fill="#b45309">max_runs={cfg.max_runs}</text>'
        )
    else:
        out.append(
            f'<text class="max-runs" x="{_SVG_LEFT + pw - 6}" y="{_SVG_TOP + 30}" '
            f'text-anchor="end" fill="#b45309">max_runs={cfg.max_runs} is off the chart '
            "&#8594;</text>"
        )
    out.append(
        f'<text x="{_SVG_LEFT + 6}" y="{_SVG_TOP + 16}" font-weight="bold" '
        'fill="#b91c1c">FLAKY region</text>'
    )
    out.append(
        f'<text x="{_SVG_LEFT + pw - 6}" y="{bottom - 8}" text-anchor="end" '
        'font-weight="bold" fill="#15803d">PASS region</text>'
    )
    out += labels
    out.append(
        f'<text x="{_SVG_LEFT + pw / 2:.1f}" y="{bottom + 34}" text-anchor="middle">run</text>'
    )
    out.append(
        f'<text transform="translate(20 {_SVG_TOP + ph / 2:.1f}) rotate(-90)" '
        'text-anchor="middle">cumulative failures</text>'
    )

    pass_label = "pass" if stride == 1 else f"pass (1 in {stride} shown)"
    legend = [
        ('<circle cx="0" cy="-4" r="4.5" fill="#dc2626"/>', "failure"),
        ('<circle cx="0" cy="-4" r="2" fill="#9ca3af"/>', pass_label),
        ('<line x1="-8" y1="-4" x2="8" y2="-4" stroke="#b91c1c" stroke-width="2"/>', "FLAKY line"),
        ('<line x1="-8" y1="-4" x2="8" y2="-4" stroke="#15803d" stroke-width="2"/>', "PASS line"),
        (
            '<rect x="-8" y="-10" width="16" height="12" fill="#ffffff" stroke="#6b7280"/>',
            "continue band",
        ),
    ]
    lx = _SVG_LEFT + 8
    for mark, label in legend:
        out.append(
            f'<g transform="translate({lx} {_SVG_H - 16})">{mark}'
            f'<text x="14" y="0">{escape(label)}</text></g>'
        )
        lx += 34 + 7 * len(label)
    out.append("</svg>")
    return "\n".join(out)


def sprt(run_test: Callable[[], bool], cfg: SprtCfg) -> SprtResult:
    """Call ``run_test`` (True on pass) until the SPRT reaches a verdict."""
    test = Sprt(cfg)
    while test.record(run_test()) is None:
        pass
    return test.result()
