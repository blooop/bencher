from __future__ import annotations

import argparse

import param


class RegressionCfg(param.Parameterized):
    """Configuration for automatic regression detection on over-time benchmarks.

    See ``docs/over_time.md`` for how these parameters interact with the
    time-tracking family (:class:`TimeCfg`).
    """

    enabled: bool = param.Boolean(
        False,
        doc="Enable regression detection when over_time is True. After loading history, "
        "statistically compare the latest run against historical data.",
    )

    method: str = param.Selector(
        default="adaptive",
        objects=["percentage", "adaptive", "delta", "absolute"],
        doc="Detection method. 'percentage': mean comparison vs historical mean. "
        "'adaptive': robust MAD-based step + drift test for noisy metrics. "
        "'delta': absolute-unit change vs historical mean (uses regression.delta). "
        "'absolute': hard directional threshold, no history required (uses "
        "regression.absolute).",
    )

    min_history: int = param.Integer(
        default=1,
        bounds=(1, None),
        doc="Minimum number of historical over_time points a result variable "
        "needs before its regressions can *fail* the run. A variable with a "
        "younger baseline (freshly added, or restarted by a meaning_version "
        "bump) still runs detection and reports regressions, but they are "
        "marked young_baseline and never trigger regression.fail — warn-only "
        "until the baseline matures. The default of 1 preserves the previous "
        "behavior (any history gates). Override per variable with a "
        "'min_history' key in regression.overrides.",
    )

    mad: float = param.Number(
        default=3.5,
        doc="Step-test threshold for the 'adaptive' method, in robust MAD-sigma "
        "units. A current value more than this many MAD-sigma from the historical "
        "median (in the regression direction) is flagged. Higher = less sensitive.",
    )

    percentage: float = param.Number(
        default=10.0,
        doc="Minimum directional percent change required to flag a regression. "
        "For 'percentage' method this is the primary threshold. For 'adaptive' "
        "method it acts as a dual-band AND gate alongside regression.mad: a "
        "regression only fires when BOTH the MAD-based test AND the percent "
        "change exceed their thresholds. Suppresses noise-floor false positives "
        "on low-repeat or integer-valued metrics where the MAD noise floor can "
        "collapse to zero.",
    )

    delta: float = param.Number(
        default=None,
        allow_None=True,
        doc="Threshold for method='delta'. Largest acceptable "
        "absolute-unit delta of the current run's mean from the mean of all "
        "historical per-time means, respecting the result variable's OptDir "
        "(minimize: curr - hist must not exceed; maximize: hist - curr must "
        "not exceed). Ignored when method is not 'delta'.",
    )

    absolute: float = param.Number(
        default=None,
        allow_None=True,
        doc="Threshold for method='absolute'. Hard directional limit "
        "the current run's mean must not violate in the direction of the result "
        "variable's OptDir (minimize: ceiling; maximize: floor). No history "
        "required — fires on the first recording. Ignored when method "
        "is not 'absolute'.",
    )

    overrides: dict = param.Dict(
        default=None,
        allow_None=True,
        doc="Per-variable regression check overrides. Maps result variable name "
        "to either a bare number — shorthand for {'absolute': value}, a hard "
        "directional limit (minimize: ceiling; maximize: floor) — or a dict of "
        "{method: threshold} drawn from 'percentage', 'adaptive', 'delta' and "
        "'absolute'. A listed variable is checked by exactly the methods in "
        "its spec instead of the benchmark-wide method, so a "
        "threshold can be loosened or tightened per variable; multiple "
        "entries run as independent checks (e.g. {'percentage': 15.0, "
        "'absolute': 1.0} tracks the trend and holds a hard floor). An empty "
        "dict opts the variable out of regression detection entirely. "
        "'absolute' checks need no history and fire from the very first "
        "recording; the other methods skip until history exists. An adaptive "
        "override's threshold is its MAD limit; the dual-band percent gate "
        "still comes from regression.percentage, and while history is too "
        "sparse for MAD the check skips rather than falling back to a "
        "percentage check. Malformed entries are dropped with a warning, "
        "never raised; a spec left with no valid checks keeps the "
        "benchmark-wide method. Variables not listed keep the benchmark-wide "
        "method, and override names matching no scalar result variable are "
        "silently skipped, so one override map can be shared across "
        "benchmarks with different result_vars.",
    )

    fail: bool = param.Boolean(
        False,
        doc="If True, raise RegressionError when a regression is detected. "
        "Useful for failing CI pipelines on benchmark regressions.",
    )

    @classmethod
    def add_cli_args(cls, parser: argparse.ArgumentParser) -> None:
        """This group exposes no command-line flags."""

    @classmethod
    def apply_cli_args(cls, namespace: argparse.Namespace) -> RegressionCfg:
        """This group exposes no command-line flags; returns the defaults."""
        return cls()
