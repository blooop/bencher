"""The tests behind the statistical evidence for a change (``docs/statistical_evidence.md`` §4).

Pure functions on numpy arrays that return frozen dataclasses; no xarray and no
plotting, so they run on a light install. Every decision runs at one-sided
α = 0.05, which is the **90 % two-sided CI**; each interval also comes at 95 % for
the report's thin whisker.

* **Continuous** (:func:`continuous_effect`): the effect is the log ratio
  candidate/base for a positive metric (a ratio of geometric means) or the
  difference for a signed one. Unpaired arms, paired arms (per-pair differences)
  and clustered repeats (a cluster bootstrap that resamples shards, not repeats)
  are all handled. The CI is a BCa bootstrap when every arm has at least
  :data:`BCA_MIN_UNITS` units, Welch t otherwise. A Hodges–Lehmann shift with a
  Mann–Whitney (unpaired) or Wilcoxon signed-rank (paired) p-value is the robust
  cross-check.
* **Tails**: :func:`shift_function` (decile differences with bootstrap CIs) and
  :func:`quantile_ci` (a distribution-free order-statistic CI of one quantile).
* **Binary** (:func:`proportion_effect`): Wilson per arm, the Newcombe hybrid score
  CI of the difference, Barnard's exact test (Fisher's on a light install) or
  McNemar's exact test for paired outcomes; :func:`rule_of_three`,
  :func:`zero_event_upper` and :func:`runs_for_flake` for "no failures in n runs".
* **Verdict** (:func:`verdict`): the oriented CI against the margin ±Δ, per the
  §4.3 table, with the non-inferiority flag, the minimum detectable effect and the
  runs needed when the run was too small (§4.5).
* **Many metrics** (:func:`holm`, :func:`benjamini_hochberg`,
  :func:`apply_multiplicity`): Holm over the primary metrics, whose CIs widen to
  the adjusted α, and Benjamini–Hochberg at q = 0.05 over the rest.

scipy is optional. When it is there, Barnard's test and the exact Mann–Whitney and
Wilcoxon p-values come from it; without it the module falls back to Fisher's exact
test and normal approximations, and each result's ``method`` says which it used.
The normal and Student t quantiles are computed here, exactly, so the CIs are the
same either way. Every bootstrap draws from a fixed seed: the same data give the
same numbers every time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import ArrayLike

ALPHA = 0.05
"""One-sided error rate of every decision; the decision CI is the ``1 - 2α`` CI."""
REPORT_LEVEL = 0.95
"""Level of the second, thinner CI the report draws."""
FDR_Q = 0.05
"""Benjamini–Hochberg false discovery rate over secondary metrics and sweep cells."""
POWER = 0.80
"""Power the minimum detectable effect is quoted at."""
RESAMPLES = 10_000
SHIFT_RESAMPLES = 2_000
SEED = 20_261_019
BCA_MIN_UNITS = 10
"""An arm needs this many units (repeats, pairs or clusters) for a BCa CI; below it, Welch t."""
MIN_UNITS = 2
DEFAULT_RELATIVE_MARGIN = 0.05
"""Default margin of a positive metric: ±5 % (TODO: the larger of this and 2× the A/A floor)."""
DEFAULT_ABSOLUTE_MARGIN_PP = 0.05
"""Default margin of a binary or fraction metric: ±5 percentage points."""
DECILES = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)

# Index arrays above this many entries are drawn in chunks, to bound memory.
_CHUNK_ENTRIES = 2_000_000
_CF_TOL = 1e-15  # convergence of the incomplete-beta continued fraction

Scale = Literal["log", "diff"]
MetricKind = Literal["positive", "signed", "fraction", "binary"]
Direction = Literal["minimize", "maximize"]


# --------------------------------------------------------------------------------------
# Distributions, without scipy.


def norm_cdf(x: float) -> float:
    """Standard normal CDF."""
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


# Acklam's rational approximation of the normal quantile; one Halley step on top
# brings it to full double precision.
_A = (-39.69683028665376, 220.9460984245205, -275.9285104469687, 138.357751867269)
_A += (-30.66479806614716, 2.506628277459239)
_B = (-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972)
_B += (-13.28068155288572,)
_C = (-0.007784894002430293, -0.3223964580411365, -2.400758277161838, -2.549732539343734)
_C += (4.374664141464968, 2.938163982698783)
_D = (0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416)
_P_LOW = 0.02425


def norm_ppf(p: float) -> float:
    """Standard normal quantile (inverse CDF)."""
    if not 0.0 < p < 1.0:
        if p == 0.0:
            return -math.inf
        if p == 1.0:
            return math.inf
        raise ValueError(f"norm_ppf: p must lie in [0, 1], got {p}")
    if p < _P_LOW:
        q = math.sqrt(-2.0 * math.log(p))
        x = _poly(_C, q) / (_poly(_D, q) * q + 1.0)
    elif p <= 1.0 - _P_LOW:
        q = p - 0.5
        r = q * q
        x = _poly(_A, r) * q / (_poly(_B, r) * r + 1.0)
    else:
        q = math.sqrt(-2.0 * math.log1p(-p))
        x = -_poly(_C, q) / (_poly(_D, q) * q + 1.0)
    err = norm_cdf(x) - p
    u = err * math.sqrt(2.0 * math.pi) * math.exp(x * x / 2.0)
    return x - u / (1.0 + x * u / 2.0)


def _poly(coefs: tuple[float, ...], x: float) -> float:
    out = 0.0
    for c in coefs:
        out = out * x + c
    return out


def _betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta function I_x(a, b), by Lentz's continued fraction."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    if x > (a + 1.0) / (a + b + 2.0):
        return 1.0 - _betainc(b, a, 1.0 - x)
    log_front = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    log_front += a * math.log(x) + b * math.log1p(-x)
    tiny = 1e-300
    c, d = 1.0, 1.0 - (a + b) * x / (a + 1.0)
    d = 1.0 / (d if abs(d) > tiny else tiny)
    frac = d
    for m in range(1, 500):
        for numerator in (
            m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m)),
            -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1)),
        ):
            d = 1.0 + numerator * d
            d = 1.0 / (d if abs(d) > tiny else tiny)
            c = 1.0 + numerator / c
            c = c if abs(c) > tiny else tiny
            frac *= c * d
        if abs(c * d - 1.0) < _CF_TOL:
            break
    return math.exp(log_front) * frac / a


def t_cdf(t: float, df: float) -> float:
    """Student t CDF with *df* degrees of freedom (any real df > 0)."""
    if math.isinf(df):
        return norm_cdf(t)
    tail = 0.5 * _betainc(df / 2.0, 0.5, df / (df + t * t))
    return tail if t < 0 else 1.0 - tail


def t_ppf(p: float, df: float) -> float:
    """Student t quantile, by bisection on :func:`t_cdf` (exact to ~1e-12)."""
    if math.isinf(df):
        return norm_ppf(p)
    lo, hi = -1.0, 1.0
    while t_cdf(lo, df) > p:
        lo *= 2.0
    while t_cdf(hi, df) < p:
        hi *= 2.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-13 * max(1.0, abs(mid)):
            break
    return (lo + hi) / 2.0


def _log_binom_pmf(k: np.ndarray, n: int, p: float) -> np.ndarray:
    k = np.asarray(k, dtype=float)
    log_choose = np.array(
        [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) for i in k]
    )
    if p <= 0.0:
        return np.where(k == 0, 0.0, -np.inf)
    if p >= 1.0:
        return np.where(k == n, 0.0, -np.inf)
    return log_choose + k * math.log(p) + (n - k) * math.log1p(-p)


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(K ≤ k) for K ~ Binomial(n, p)."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return float(min(1.0, np.exp(_log_binom_pmf(np.arange(k + 1), n, p)).sum()))


# --------------------------------------------------------------------------------------
# Result types.


@dataclass(frozen=True)
class Interval:
    """A two-sided confidence interval ``[low, high]`` at *level*."""

    low: float
    high: float
    level: float

    def contains(self, value: float) -> bool:
        return self.low <= value <= self.high


@dataclass(frozen=True)
class RobustCheck:
    """The rank-based cross-check of a continuous effect.

    *estimate* is the Hodges–Lehmann shift on the effect's scale; *p_value* is the
    two-sided Mann–Whitney (unpaired) or Wilcoxon signed-rank (paired) p-value.
    *agrees* is False when the rank test and the main CI disagree on whether the
    effect differs from 0 (at two-sided 2α), or on its sign.
    """

    method: str
    estimate: float
    p_value: float
    agrees: bool


@dataclass(frozen=True)
class Effect:
    """A continuous effect, candidate against base, on its analysis *scale*.

    On the ``"log"`` scale *estimate* and the CIs are log ratios (``exp`` gives the
    ratio of geometric means); on ``"diff"`` they are differences in the metric's
    units. *ci* is the decision CI (90 % unless widened for Holm), *ci95* the
    report's 95 % CI. *bootstrap* holds the resampled effects when the CI came from
    a bootstrap, for the estimation plot.
    """

    scale: Scale
    estimate: float
    ci: Interval
    ci95: Interval
    p_value: float
    se: float
    method: str
    n_base: int
    n_cand: int
    paired: bool
    n_clusters: int | None = None
    robust: RobustCheck | None = None
    bootstrap: np.ndarray | None = field(default=None, compare=False, repr=False)

    def to_display(self, value: float) -> float:
        """*value* on the scale the report prints: % change for log, units for diff."""
        return 100.0 * math.expm1(value) if self.scale == "log" else value


@dataclass(frozen=True)
class ProportionEffect:
    """A binary effect: the difference of success proportions, candidate − base.

    *wilson_base* / *wilson_cand* are 95 % Wilson intervals of each arm; *ci* (90 %)
    and *ci95* are Newcombe hybrid score intervals of the difference. *bad_upper*
    is the one-sided 95 % upper bound of the candidate's rate of the *bad* outcome
    (failures for a maximised metric, successes for a minimised one): 3/n-ish when
    the candidate saw none of it.
    """

    k_base: int
    n_base: int
    k_cand: int
    n_cand: int
    ci: Interval
    ci95: Interval
    wilson_base: Interval
    wilson_cand: Interval
    p_value: float
    method: str
    paired: bool
    bad_upper: float
    se: float

    @property
    def p_base(self) -> float:
        return self.k_base / self.n_base

    @property
    def p_cand(self) -> float:
        return self.k_cand / self.n_cand

    @property
    def estimate(self) -> float:
        return self.p_cand - self.p_base


class VerdictKind(StrEnum):
    IMPROVED = "improved"
    REGRESSED = "regressed"
    EQUIVALENT = "equivalent"
    INCONCLUSIVE = "inconclusive"


GLYPHS = {
    VerdictKind.IMPROVED: "▲",
    VerdictKind.REGRESSED: "▼",
    VerdictKind.EQUIVALENT: "≈",
    VerdictKind.INCONCLUSIVE: "?",
}


@dataclass(frozen=True)
class Verdict:
    """What a CI means against the margin ±Δ, on the oriented scale (positive = better).

    *low*/*high* are the oriented decision CI and *margin* is Δ on the same scale.
    *detail* splits :attr:`VerdictKind.EQUIVALENT` into ``"no change"`` (the CI
    holds 0), ``"small gain"`` and ``"small loss"``. *mde* is the minimum
    detectable effect at 80 % power; *runs_needed* is the units per arm that would
    bring it down to Δ, set only when the run was *underpowered*.
    """

    kind: VerdictKind
    low: float
    high: float
    margin: float
    detail: str | None = None
    noninferior: bool = False
    mde: float | None = None
    underpowered: bool = False
    runs_needed: int | None = None
    n: int | None = None

    @property
    def glyph(self) -> str:
        return GLYPHS[self.kind]

    @property
    def word(self) -> str:
        """The verdict in words: ``improved``, ``no change``, ``small gain`` ..."""
        return self.detail or str(self.kind)

    @property
    def add_runs(self) -> int | None:
        if self.runs_needed is None or self.n is None:
            return None
        return max(0, self.runs_needed - self.n)


@dataclass(frozen=True)
class ShiftFunction:
    """Decile-by-decile difference candidate − base, each with a bootstrap 95 % CI."""

    probs: tuple[float, ...]
    base: np.ndarray = field(compare=False)
    cand: np.ndarray = field(compare=False)
    diff: np.ndarray = field(compare=False)
    low: np.ndarray = field(compare=False)
    high: np.ndarray = field(compare=False)


@dataclass(frozen=True)
class QuantileCI:
    """A distribution-free CI of the *prob* quantile from the order statistics.

    *low*/*high* are ``None`` when n is too small for the CI to have a finite end.
    *coverage* is the exact binomial coverage of ``[low, high]``.
    """

    prob: float
    estimate: float
    low: float | None
    high: float | None
    level: float
    coverage: float


# --------------------------------------------------------------------------------------
# Helpers.


def _finite(values: ArrayLike) -> np.ndarray:
    arr = np.asarray(values, dtype=float).ravel()
    return arr[np.isfinite(arr)]


def _level_of(alpha: float) -> float:
    return 1.0 - 2.0 * alpha


def _have_scipy() -> bool:
    try:
        import scipy.stats  # noqa: F401
    except ImportError:
        return False
    return True


def rankdata(values: np.ndarray) -> np.ndarray:
    """Ranks 1..n with ties given their average rank."""
    values = np.asarray(values, dtype=float)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values))
    sorted_vals = values[order]
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and sorted_vals[j + 1] == sorted_vals[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def _tie_term(values: np.ndarray) -> float:
    _, counts = np.unique(values, return_counts=True)
    return float(np.sum(counts**3 - counts))


# --------------------------------------------------------------------------------------
# Continuous effects.


@dataclass(frozen=True)
class _Units:
    """One arm as resampling units: the sum and count of the values in each unit."""

    sums: np.ndarray
    counts: np.ndarray

    @property
    def m(self) -> int:
        return len(self.sums)

    @property
    def mean(self) -> float:
        return float(self.sums.sum() / self.counts.sum())

    def unit_means(self) -> np.ndarray:
        return self.sums / self.counts

    def boot_means(self, rng: np.random.Generator) -> np.ndarray:
        out = np.empty(RESAMPLES)
        chunk = max(1, _CHUNK_ENTRIES // self.m)
        for start in range(0, RESAMPLES, chunk):
            stop = min(RESAMPLES, start + chunk)
            idx = rng.integers(0, self.m, size=(stop - start, self.m))
            out[start:stop] = self.sums[idx].sum(axis=1) / self.counts[idx].sum(axis=1)
        return out

    def jackknife_means(self) -> np.ndarray:
        total_s, total_c = self.sums.sum(), self.counts.sum()
        return (total_s - self.sums) / (total_c - self.counts)


def _units(values: np.ndarray, clusters: np.ndarray | None) -> _Units:
    if clusters is None:
        return _Units(values.astype(float), np.ones(len(values)))
    labels, inverse = np.unique(clusters, return_inverse=True)
    sums = np.bincount(inverse, weights=values, minlength=len(labels))
    counts = np.bincount(inverse, minlength=len(labels)).astype(float)
    return _Units(sums, counts)


def _transform(values: np.ndarray, scale: Scale) -> np.ndarray:
    if scale == "log":
        if np.any(values <= 0):
            raise ValueError("a log-scale effect needs every value > 0; use scale='diff'")
        return np.log(values)
    return values


def _bca_interval(
    boot: np.ndarray, theta: float, jackknives: Sequence[np.ndarray], level: float
) -> Interval:
    """BCa interval from bootstrap replicates and one jackknife array per sample.

    Follows Efron & Tibshirani (1993) §14.3 the way ``scipy.stats.bootstrap`` does,
    multi-sample acceleration included, so the two agree on the same replicates.
    """
    if np.ptp(boot) == 0:
        return Interval(theta, theta, level)
    b = len(boot)
    frac = (np.count_nonzero(boot < theta) + np.count_nonzero(boot <= theta)) / (2.0 * b)
    frac = min(max(frac, 0.5 / b), 1.0 - 0.5 / b)
    z0 = norm_ppf(frac)
    num, den = 0.0, 0.0
    for jack in jackknives:
        n = float(len(jack))
        u = (n - 1.0) * (jack.mean() - jack)
        num += float(np.sum(u**3)) / n**3
        den += float(np.sum(u**2)) / n**2
    accel = num / (6.0 * den**1.5) if den > 0 else 0.0
    tail = (1.0 - level) / 2.0
    out = []
    for z in (norm_ppf(tail), norm_ppf(1.0 - tail)):
        adj = z0 + z
        out.append(norm_cdf(z0 + adj / (1.0 - accel * adj)))
    low, high = np.percentile(boot, [100.0 * out[0], 100.0 * out[1]])
    return Interval(float(low), float(high), level)


def _boot_p(boot: np.ndarray) -> float:
    """Two-sided bootstrap p-value of "effect = 0": twice the smaller tail mass at 0."""
    tail = min(np.mean(boot <= 0.0), np.mean(boot >= 0.0))
    return float(min(1.0, max(2.0 * tail, 1.0 / len(boot))))


def _t_effect(diff: float, se: float, df: float, level: float) -> tuple[Interval, Interval, float]:
    if se <= 0:
        p = 1.0 if diff == 0 else 0.0
        return Interval(diff, diff, level), Interval(diff, diff, REPORT_LEVEL), p
    out = []
    for lev in (level, REPORT_LEVEL):
        half = t_ppf(1.0 - (1.0 - lev) / 2.0, df) * se
        out.append(Interval(diff - half, diff + half, lev))
    p = 2.0 * t_cdf(-abs(diff) / se, df)
    return out[0], out[1], p


def _welch(base_u: np.ndarray, cand_u: np.ndarray) -> tuple[float, float, float]:
    nb, nc = len(base_u), len(cand_u)
    vb, vc = base_u.var(ddof=1) / nb, cand_u.var(ddof=1) / nc
    se = math.sqrt(vb + vc)
    denom = vb**2 / (nb - 1) + vc**2 / (nc - 1)
    df = (vb + vc) ** 2 / denom if denom > 0 else float(nb + nc - 2)
    return float(cand_u.mean() - base_u.mean()), se, df


def hodges_lehmann(base: np.ndarray, cand: np.ndarray, *, paired: bool) -> float:
    """Hodges–Lehmann shift: the median of pairwise differences (unpaired) or Walsh averages."""
    if paired:
        d = cand - base
        i, j = np.triu_indices(len(d))
        return float(np.median((d[i] + d[j]) / 2.0))
    return float(np.median(cand[:, None] - base[None, :]))


def mann_whitney_p(base: np.ndarray, cand: np.ndarray) -> tuple[float, str]:
    """Two-sided Mann–Whitney U p-value: scipy's (exact at small n) or the normal approximation."""
    if _have_scipy():
        from scipy.stats import mannwhitneyu

        res = mannwhitneyu(cand, base, alternative="two-sided", method="auto")
        return float(res.pvalue), "Mann–Whitney U"
    nb, nc = len(base), len(cand)
    both = np.concatenate([cand, base])
    ranks = rankdata(both)
    u = ranks[:nc].sum() - nc * (nc + 1) / 2.0
    mu = nb * nc / 2.0
    n = nb + nc
    var = nb * nc / 12.0 * ((n + 1) - _tie_term(both) / (n * (n - 1)))
    if var <= 0:
        return 1.0, "Mann–Whitney U (normal approx.)"
    z = (abs(u - mu) - 0.5) / math.sqrt(var)
    return float(min(1.0, 2.0 * norm_cdf(-max(z, 0.0)))), "Mann–Whitney U (normal approx.)"


def wilcoxon_p(diffs: np.ndarray) -> tuple[float, str]:
    """Two-sided Wilcoxon signed-rank p-value: scipy's or the normal approximation."""
    d = diffs[diffs != 0]
    if len(d) == 0:
        return 1.0, "Wilcoxon signed-rank"
    if _have_scipy():
        from scipy.stats import wilcoxon

        return float(wilcoxon(d).pvalue), "Wilcoxon signed-rank"
    n = len(d)
    ranks = rankdata(np.abs(d))
    w = ranks[d > 0].sum()
    mu = n * (n + 1) / 4.0
    var = n * (n + 1) * (2 * n + 1) / 24.0 - _tie_term(np.abs(d)) / 48.0
    z = (abs(w - mu) - 0.5) / math.sqrt(var)
    return float(min(1.0, 2.0 * norm_cdf(-max(z, 0.0)))), "Wilcoxon signed-rank (normal approx.)"


def continuous_effect(
    base: ArrayLike,
    cand: ArrayLike,
    *,
    scale: Scale = "log",
    paired: bool = False,
    clusters: ArrayLike | tuple[ArrayLike, ArrayLike] | None = None,
    alpha: float = ALPHA,
) -> Effect:
    """The effect of the candidate on a continuous metric, with its CIs (spec §4.1).

    Args:
        base: the samples of the base arm.
        cand: the samples of the candidate arm. Paired arms must be the same length
            and in pair order; NaNs drop pairwise.
        scale: ``"log"`` for a positive metric (log ratio), ``"diff"`` for a signed one.
        paired: analyse the per-pair differences.
        clusters: the shard (or VM) of each sample; the bootstrap then resamples
            clusters, not samples. One array for paired arms, ``(base, cand)``
            arrays for unpaired ones.
        alpha: one-sided error rate; the decision CI is the ``1 - 2α`` CI.

    Raises:
        ValueError: on fewer than :data:`MIN_UNITS` units in an arm, unequal paired
            arms, or a non-positive value on the log scale.
    """
    base_arr = np.asarray(base, dtype=float).ravel()
    cand_arr = np.asarray(cand, dtype=float).ravel()
    level = _level_of(alpha)
    rng = np.random.default_rng(SEED)
    what = "log" if scale == "log" else ""
    if paired:
        if len(base_arr) != len(cand_arr):
            raise ValueError("paired arms must have the same length")
        keep = np.isfinite(base_arr) & np.isfinite(cand_arr)
        cl = None if clusters is None else np.asarray(clusters).ravel()[keep]
        b, c = _transform(base_arr[keep], scale), _transform(cand_arr[keep], scale)
        d = c - b
        units = _units(d, cl)
        if units.m < MIN_UNITS:
            raise ValueError(f"too few pairs ({units.m}) for a CI")
        theta = units.mean
        kind = "clusters of paired" if cl is not None else "paired"
        if units.m >= BCA_MIN_UNITS:
            boot = units.boot_means(rng)
            ci = _bca_interval(boot, theta, [units.jackknife_means()], level)
            ci95 = _bca_interval(boot, theta, [units.jackknife_means()], REPORT_LEVEL)
            p, se = _boot_p(boot), float(boot.std(ddof=1))
            method = f"BCa bootstrap of {kind} {what} differences".replace("  ", " ")
        else:
            boot = None
            um = units.unit_means()
            se = float(um.std(ddof=1) / math.sqrt(units.m))
            ci, ci95, p = _t_effect(theta, se, units.m - 1, level)
            method = f"paired t on {what} differences".replace("  ", " ")
        p_rank, rank_method = wilcoxon_p(d)
        hl = hodges_lehmann(b, c, paired=True)
        n_b = n_c = len(d)
    else:
        if isinstance(clusters, tuple):
            cl_b, cl_c = (np.asarray(x).ravel() for x in clusters)
        elif clusters is None:
            cl_b = cl_c = None
        else:
            raise ValueError("unpaired clusters must be a (base, cand) tuple of arrays")
        keep_b, keep_c = np.isfinite(base_arr), np.isfinite(cand_arr)
        b, c = _transform(base_arr[keep_b], scale), _transform(cand_arr[keep_c], scale)
        ub = _units(b, None if cl_b is None else cl_b[keep_b])
        uc = _units(c, None if cl_c is None else cl_c[keep_c])
        if min(ub.m, uc.m) < MIN_UNITS:
            raise ValueError(f"too few units for a CI (base {ub.m}, candidate {uc.m})")
        theta = uc.mean - ub.mean
        kind = "clusters" if cl_b is not None else "samples"
        if min(ub.m, uc.m) >= BCA_MIN_UNITS:
            boot = uc.boot_means(rng) - ub.boot_means(rng)
            jacks = [uc.mean - ub.jackknife_means(), uc.jackknife_means() - ub.mean]
            ci = _bca_interval(boot, theta, jacks, level)
            ci95 = _bca_interval(boot, theta, jacks, REPORT_LEVEL)
            p, se = _boot_p(boot), float(boot.std(ddof=1))
            noun = "log ratio" if scale == "log" else "difference"
            method = f"BCa bootstrap of the {noun}, resampling {kind}"
        else:
            boot = None
            theta, se, df = _welch(ub.unit_means(), uc.unit_means())
            ci, ci95, p = _t_effect(theta, se, df, level)
            method = f"Welch t on {what} values".replace("  ", " ")
            if cl_b is not None:
                method = f"Welch t on cluster means of {what} values".replace("  ", " ")
        p_rank, rank_method = mann_whitney_p(b, c)
        hl = hodges_lehmann(b, c, paired=False)
        n_b, n_c = len(b), len(c)
        units = ub if ub.m <= uc.m else uc
    main_sig = not ci.contains(0.0)
    rank_sig = p_rank < 2.0 * alpha
    agrees = main_sig == rank_sig and (not main_sig or np.sign(hl) == np.sign(theta))
    n_clusters = None
    if clusters is not None:
        n_clusters = units.m
    return Effect(
        scale=scale,
        estimate=float(theta),
        ci=ci,
        ci95=ci95,
        p_value=float(p),
        se=se,
        method=method,
        n_base=n_b,
        n_cand=n_c,
        paired=paired,
        n_clusters=n_clusters,
        robust=RobustCheck(f"Hodges–Lehmann + {rank_method}", hl, p_rank, bool(agrees)),
        bootstrap=boot,
    )


def shift_function(
    base: ArrayLike,
    cand: ArrayLike,
    *,
    scale: Scale = "diff",
    paired: bool = False,
    probs: Sequence[float] = DECILES,
) -> ShiftFunction:
    """Rousselet–Wilcox shift function: cand − base at each decile, with a 95 % bootstrap CI.

    Paired arms resample pairs together. The quantiles are on *scale* (``"log"``
    gives log ratios per decile).
    """
    b = _transform(_finite(base), scale)
    c = _transform(_finite(cand), scale)
    if paired and len(b) != len(c):
        raise ValueError("paired arms must have the same length")
    q = np.asarray(probs, dtype=float)
    qb, qc = np.quantile(b, q), np.quantile(c, q)
    rng = np.random.default_rng(SEED)
    diffs = np.empty((SHIFT_RESAMPLES, len(q)))
    for i in range(SHIFT_RESAMPLES):
        ib = rng.integers(0, len(b), len(b))
        ic = ib if paired else rng.integers(0, len(c), len(c))
        diffs[i] = np.quantile(c[ic], q) - np.quantile(b[ib], q)
    low, high = np.percentile(diffs, [2.5, 97.5], axis=0)
    return ShiftFunction(tuple(float(x) for x in q), qb, qc, qc - qb, low, high)


def quantile_ci(values: ArrayLike, prob: float, *, level: float = REPORT_LEVEL) -> QuantileCI:
    """Distribution-free CI of the *prob* quantile from order statistics.

    The CI is ``[x_(l), x_(u)]`` (1-based order statistics) with the binomial
    coverage ``P(l ≤ K < u) ≥ level``, K ~ Binomial(n, prob), split evenly between
    the tails. An end is ``None`` when n is too small for it.
    """
    x = np.sort(_finite(values))
    n = len(x)
    if n == 0:
        raise ValueError("quantile_ci needs at least one finite value")
    tail = (1.0 - level) / 2.0
    cdf = np.array([binom_cdf(k, n, prob) for k in range(n + 1)])
    # l: largest rank with P(K <= l-1) <= tail; u: smallest with P(K <= u-1) >= 1-tail.
    lows = [r for r in range(1, n + 1) if cdf[r - 1] <= tail]
    highs = [r for r in range(1, n + 1) if cdf[r - 1] >= 1.0 - tail]
    l_rank = lows[-1] if lows else None
    u_rank = highs[0] if highs else None
    f_low = cdf[l_rank - 1] if l_rank else 0.0
    f_high = cdf[u_rank - 1] if u_rank else 1.0
    return QuantileCI(
        prob=prob,
        estimate=float(np.quantile(x, prob)),
        low=None if l_rank is None else float(x[l_rank - 1]),
        high=None if u_rank is None else float(x[u_rank - 1]),
        level=level,
        coverage=float(f_high - f_low),
    )


# --------------------------------------------------------------------------------------
# Binary effects.


def wilson(k: int, n: int, *, level: float = REPORT_LEVEL) -> Interval:
    """Wilson score interval of the proportion k/n."""
    if n <= 0:
        raise ValueError("wilson needs n > 0")
    z = norm_ppf(1.0 - (1.0 - level) / 2.0)
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    low = 0.0 if k == 0 else max(0.0, centre - half)
    high = 1.0 if k == n else min(1.0, centre + half)
    return Interval(low, high, level)


def newcombe(k1: int, n1: int, k2: int, n2: int, *, level: float = REPORT_LEVEL) -> Interval:
    """Newcombe's hybrid score interval (his method 10) of p1 − p2."""
    p1, p2 = k1 / n1, k2 / n2
    w1, w2 = wilson(k1, n1, level=level), wilson(k2, n2, level=level)
    d = p1 - p2
    low = d - math.sqrt((p1 - w1.low) ** 2 + (w2.high - p2) ** 2)
    high = d + math.sqrt((w1.high - p1) ** 2 + (p2 - w2.low) ** 2)
    return Interval(low, high, level)


def fisher_exact_p(k1: int, n1: int, k2: int, n2: int) -> float:
    """Two-sided Fisher exact p-value of a 2×2 table (sum of tables no more likely)."""
    total_k, n = k1 + k2, n1 + n2

    def log_pmf(a: int) -> float:
        return _lchoose(n1, a) + _lchoose(n2, total_k - a) - _lchoose(n, total_k)

    lo, hi = max(0, total_k - n2), min(total_k, n1)
    probs = np.exp([log_pmf(a) for a in range(lo, hi + 1)])
    observed = math.exp(log_pmf(k1))
    return float(min(1.0, probs[probs <= observed * (1.0 + 1e-7)].sum()))


def _lchoose(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def mcnemar_exact_p(b: int, c: int) -> float:
    """McNemar's exact p-value from the discordant pair counts *b* and *c*."""
    if b + c == 0:
        return 1.0
    return float(min(1.0, 2.0 * binom_cdf(min(b, c), b + c, 0.5)))


def two_proportion_p(k1: int, n1: int, k2: int, n2: int) -> tuple[float, str]:
    """Barnard's exact test (scipy), else Fisher's exact test; returns ``(p, method)``."""
    if _have_scipy():
        from scipy.stats import barnard_exact

        table = [[k1, k2], [n1 - k1, n2 - k2]]
        return float(barnard_exact(table).pvalue), "Barnard exact"
    return fisher_exact_p(k1, n1, k2, n2), "Fisher exact (Barnard needs scipy)"


def rule_of_three(n: int) -> float:
    """Approximate 95 % upper bound on a rate after 0 events in *n* trials: 3/n."""
    return 3.0 / n


def zero_event_upper(n: int, alpha: float = ALPHA) -> float:
    """Exact one-sided ``1 - alpha`` upper bound after 0 events in *n* trials."""
    return 1.0 - alpha ** (1.0 / n)


def clopper_pearson_upper(k: int, n: int, alpha: float = ALPHA) -> float:
    """Exact one-sided ``1 - alpha`` upper bound of a rate after *k* events in *n*."""
    if k >= n:
        return 1.0
    if k == 0:
        return zero_event_upper(n, alpha)
    lo, hi = k / n, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if binom_cdf(k, n, mid) > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def runs_for_flake(p0: float, alpha: float = ALPHA) -> int:
    """Clean runs needed to claim a flake rate of *p0* is gone: ⌈ln α / ln(1 − p0)⌉."""
    if not 0.0 < p0 < 1.0:
        raise ValueError("runs_for_flake needs 0 < p0 < 1")
    return math.ceil(math.log(alpha) / math.log1p(-p0) - 1e-9)


def proportion_effect(
    base: ArrayLike,
    cand: ArrayLike,
    *,
    paired: bool = False,
    direction: Direction = "maximize",
    alpha: float = ALPHA,
) -> ProportionEffect:
    """The effect of the candidate on a binary metric (spec §4.2).

    *base* / *cand* hold 0/1 outcomes (NaNs drop). Paired outcomes (same seeds) use
    McNemar's exact test on the discordant pairs; the CI stays Newcombe's.
    *direction* names which outcome is good, for the *bad_upper* bound.
    """
    b_arr = np.asarray(base, dtype=float).ravel()
    c_arr = np.asarray(cand, dtype=float).ravel()
    if paired:
        if len(b_arr) != len(c_arr):
            raise ValueError("paired arms must have the same length")
        keep = np.isfinite(b_arr) & np.isfinite(c_arr)
        b_arr, c_arr = b_arr[keep], c_arr[keep]
    else:
        b_arr, c_arr = _finite(b_arr), _finite(c_arr)
    if len(b_arr) == 0 or len(c_arr) == 0:
        raise ValueError("a binary effect needs at least one outcome per arm")
    if not (np.isin(b_arr, (0.0, 1.0)).all() and np.isin(c_arr, (0.0, 1.0)).all()):
        raise ValueError("binary outcomes must be 0 or 1")
    kb, nb = int(b_arr.sum()), len(b_arr)
    kc, nc = int(c_arr.sum()), len(c_arr)
    level = _level_of(alpha)
    if paired:
        disc_b = int(np.sum((b_arr == 1) & (c_arr == 0)))
        disc_c = int(np.sum((b_arr == 0) & (c_arr == 1)))
        p, method = mcnemar_exact_p(disc_b, disc_c), "McNemar exact"
    else:
        p, method = two_proportion_p(kc, nc, kb, nb)
    ci = newcombe(kc, nc, kb, nb, level=level)
    bad = nc - kc if direction == "maximize" else kc
    return ProportionEffect(
        k_base=kb,
        n_base=nb,
        k_cand=kc,
        n_cand=nc,
        ci=ci,
        ci95=newcombe(kc, nc, kb, nb, level=REPORT_LEVEL),
        wilson_base=wilson(kb, nb),
        wilson_cand=wilson(kc, nc),
        p_value=p,
        method=f"Newcombe hybrid score CI · {method}",
        paired=paired,
        bad_upper=clopper_pearson_upper(bad, nc),
        se=(ci.high - ci.low) / (2.0 * norm_ppf(1.0 - alpha)),
    )


# --------------------------------------------------------------------------------------
# Verdict, power, multiplicity.


def mde(se: float, alpha: float = ALPHA, power: float = POWER) -> float:
    """Minimum detectable effect at *power*: (z_{1-α} + z_{power}) · SE."""
    return (norm_ppf(1.0 - alpha) + norm_ppf(power)) * se


def runs_needed(n: int, mde_value: float, margin: float) -> int:
    """Units per arm that bring the MDE down to *margin*: ⌈n · (MDE / Δ)²⌉."""
    return math.ceil(n * (mde_value / margin) ** 2)


def verdict(
    low: float,
    high: float,
    margin: float,
    *,
    se: float | None = None,
    n: int | None = None,
    alpha: float = ALPHA,
) -> Verdict:
    """Read an oriented CI ``[low, high]`` (positive = better) against ±*margin* (§4.3).

    ========== ================================ ==========================
    Verdict    Rule                             Detail
    ========== ================================ ==========================
    improved   L > 0 and U ≥ Δ
    regressed  U < 0 and L ≤ −Δ
    equivalent −Δ < L and U < Δ                 no change / small gain / small loss
    inconclusive L ≤ 0 ≤ U and the CI crosses a margin
    ========== ================================ ==========================

    The spec's table writes U > Δ and L < −Δ; a CI that clears 0 and touches the
    margin exactly is called improved (regressed) here, so the table is total.
    Non-inferiority passes when L > −Δ. With *se* and *n* it also gives the MDE
    and, when MDE > Δ, the units per arm that would reach Δ.
    """
    if margin <= 0:
        raise ValueError("verdict needs a margin > 0")
    if low > high:
        low, high = high, low
    detail = None
    if low > 0 and high >= margin:
        kind = VerdictKind.IMPROVED
    elif high < 0 and low <= -margin:
        kind = VerdictKind.REGRESSED
    elif -margin < low and high < margin:
        kind = VerdictKind.EQUIVALENT
        detail = "no change" if low <= 0 <= high else ("small gain" if low > 0 else "small loss")
    else:
        kind = VerdictKind.INCONCLUSIVE
    mde_value = None if se is None else mde(se, alpha)
    underpowered = mde_value is not None and mde_value > margin
    needed = None
    if underpowered and n is not None and mde_value is not None:
        needed = runs_needed(n, mde_value, margin)
    return Verdict(
        kind=kind,
        low=low,
        high=high,
        margin=margin,
        detail=detail,
        noninferior=low > -margin,
        mde=mde_value,
        underpowered=underpowered,
        runs_needed=needed,
        n=n,
    )


def holm(p_values: Sequence[float]) -> np.ndarray:
    """Holm step-down adjusted p-values (family-wise error)."""
    p = np.asarray(p_values, dtype=float)
    m = len(p)
    order = np.argsort(p, kind="mergesort")
    adj = np.minimum(1.0, (m - np.arange(m)) * p[order])
    adj = np.maximum.accumulate(adj)
    out = np.empty(m)
    out[order] = adj
    return out


def benjamini_hochberg(p_values: Sequence[float]) -> np.ndarray:
    """Benjamini–Hochberg adjusted p-values (false discovery rate)."""
    p = np.asarray(p_values, dtype=float)
    m = len(p)
    if m == 0:
        return p
    order = np.argsort(p, kind="mergesort")
    adj = p[order] * m / np.arange(1, m + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(1.0, adj)
    return out


# --------------------------------------------------------------------------------------
# One metric, end to end.


@dataclass(frozen=True)
class MetricEvidence:
    """Everything the report says about one metric (or one sweep cell of it).

    *effect* is an :class:`Effect` or a :class:`ProportionEffect`; *verdict* reads
    it oriented so that positive is better. *margin* is Δ as the user gives it
    (relative for a positive metric, absolute otherwise). *adjusted_p* and
    *fdr_pass* are set by :func:`apply_multiplicity`. *order* is each sample's run
    order (an index or a timestamp; ``None`` when not recorded), in the same order
    as *base* / *cand*, and *seed_policy* says how the runs were seeded, when known.
    """

    name: str
    units: str
    direction: Direction
    kind: MetricKind
    effect: Effect | ProportionEffect
    verdict: Verdict
    margin: float
    base: np.ndarray = field(compare=False, repr=False)
    cand: np.ndarray = field(compare=False, repr=False)
    paired: bool = False
    clusters: tuple[np.ndarray | None, np.ndarray | None] = field(
        default=(None, None), compare=False, repr=False
    )
    primary: bool = False
    adjusted_p: float | None = None
    fdr_pass: bool = True
    alpha: float = ALPHA
    point: dict = field(default_factory=dict)
    order: tuple[np.ndarray | None, np.ndarray | None] = field(
        default=(None, None), compare=False, repr=False
    )
    seed_policy: str | None = None

    @property
    def holm_m(self) -> int:
        """How many primary metrics Holm ran over (1 when not primary or alone)."""
        return max(1, round(ALPHA / self.alpha)) if self.primary else 1

    @property
    def sign(self) -> float:
        """+1 when a higher value is better, −1 when lower is better."""
        return 1.0 if self.direction == "maximize" else -1.0


def infer_kind(base: np.ndarray, cand: np.ndarray) -> MetricKind:
    """Binary when every value is 0/1, positive when every value is > 0, else signed."""
    both = np.concatenate([_finite(base), _finite(cand)])
    if both.size and np.isin(both, (0.0, 1.0)).all():
        return "binary"
    if both.size and np.all(both > 0):
        return "positive"
    return "signed"


def default_margin(kind: MetricKind, base: np.ndarray) -> float:
    """Spec §4.3 default Δ: 5 % relative, 5 pp for binary/fraction, 5 % of |mean| when signed.

    TODO: take the larger of this and twice the A/A noise floor of the metric.
    """
    if kind == "positive":
        return DEFAULT_RELATIVE_MARGIN
    if kind in ("binary", "fraction"):
        return DEFAULT_ABSOLUTE_MARGIN_PP
    scale = float(np.nanmean(np.abs(base))) if np.isfinite(base).any() else 0.0
    return DEFAULT_RELATIVE_MARGIN * scale if scale > 0 else DEFAULT_RELATIVE_MARGIN


def oriented_margin(kind: MetricKind, margin: float) -> float:
    """Δ on the effect's analysis scale: ``log(1 + Δ)`` for a positive metric."""
    return math.log1p(margin) if kind == "positive" else margin


def analyse(
    name: str,
    base: ArrayLike,
    cand: ArrayLike,
    *,
    direction: Direction = "minimize",
    units: str = "",
    kind: MetricKind | None = None,
    margin: float | None = None,
    paired: bool = False,
    clusters: tuple[ArrayLike | None, ArrayLike | None] = (None, None),
    alpha: float = ALPHA,
    primary: bool = False,
    point: dict | None = None,
    order: tuple[ArrayLike | None, ArrayLike | None] = (None, None),
    seed_policy: str | None = None,
) -> MetricEvidence:
    """Effect + verdict for one metric; *kind* and *margin* default per spec §2 / §4.3.

    *clusters* is ``(base_clusters, cand_clusters)``; for paired arms only the
    first is used (pairs share a shard). *order* is ``(base_order, cand_order)``,
    the run order of each sample, carried for the design strip of the graphics.
    """
    b = np.asarray(base, dtype=float).ravel()
    c = np.asarray(cand, dtype=float).ravel()
    kind = kind or infer_kind(b, c)
    margin = default_margin(kind, b) if margin is None else margin
    sign = 1.0 if direction == "maximize" else -1.0
    cl_b = None if clusters[0] is None else np.asarray(clusters[0]).ravel()
    cl_c = None if clusters[1] is None else np.asarray(clusters[1]).ravel()
    effect: Effect | ProportionEffect
    if kind == "binary":
        effect = proportion_effect(b, c, paired=paired, direction=direction, alpha=alpha)
        n = min(effect.n_base, effect.n_cand)
    else:
        scale: Scale = "log" if kind == "positive" else "diff"
        cl: ArrayLike | tuple[ArrayLike, ArrayLike] | None = cl_b
        if not paired:
            cl = None if cl_b is None or cl_c is None else (cl_b, cl_c)
        effect = continuous_effect(b, c, scale=scale, paired=paired, clusters=cl, alpha=alpha)
        n = effect.n_clusters or min(effect.n_base, effect.n_cand)
    low, high = sorted((sign * effect.ci.low, sign * effect.ci.high))
    v = verdict(low, high, oriented_margin(kind, margin), se=effect.se, n=n, alpha=alpha)
    return MetricEvidence(
        name=name,
        units=units,
        direction=direction,
        kind=kind,
        effect=effect,
        verdict=v,
        margin=margin,
        base=b,
        cand=c,
        paired=paired,
        clusters=(cl_b, cl_c),
        primary=primary,
        alpha=alpha,
        point=point or {},
        order=tuple(None if o is None else np.asarray(o, dtype=float).ravel() for o in order),
        seed_policy=seed_policy,
    )


def apply_multiplicity(metrics: Sequence[MetricEvidence]) -> list[MetricEvidence]:
    """Holm over the primary metrics, Benjamini–Hochberg over the rest (spec §4.4).

    Each primary metric is re-analysed at α / m (m primary metrics), so its CI
    widens to the adjusted level (the Bonferroni level, the conservative CI that
    goes with Holm's test) and its verdict is read from that CI. A secondary
    metric whose BH-adjusted p is above :data:`FDR_Q` gets ``fdr_pass = False``;
    it flags, it does not gate.
    """
    primary = [i for i, m in enumerate(metrics) if m.primary]
    secondary = [i for i, m in enumerate(metrics) if not m.primary]
    out = list(metrics)
    if primary:
        adj = holm([metrics[i].effect.p_value for i in primary])
        alpha = ALPHA / len(primary)
        for i, p in zip(primary, adj, strict=True):
            m = metrics[i]
            if len(primary) > 1:
                m = analyse(
                    m.name,
                    m.base,
                    m.cand,
                    direction=m.direction,
                    units=m.units,
                    kind=m.kind,
                    margin=m.margin,
                    paired=m.paired,
                    clusters=m.clusters,
                    alpha=alpha,
                    primary=True,
                    point=m.point,
                    order=m.order,
                    seed_policy=m.seed_policy,
                )
            out[i] = replace(m, adjusted_p=float(p), fdr_pass=bool(p <= 2 * ALPHA))
    if secondary:
        adj = benjamini_hochberg([metrics[i].effect.p_value for i in secondary])
        for i, p in zip(secondary, adj, strict=True):
            out[i] = replace(metrics[i], adjusted_p=float(p), fdr_pass=bool(p <= FDR_Q))
    return out
