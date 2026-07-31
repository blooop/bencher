"""Machine-readable export of benchmark results for agents and CI.

Bencher already *computes* per-metric verdicts, optimal values, and regression
deltas during collection — but historically only emitted them as HTML, pickle,
or human-prose markdown. This module turns those already-computed values into a
stable JSON contract so an automated workflow can read ground truth instead of
scraping logs or parsing rendered reports.

Two artifacts:

* :func:`result_to_dict` / :func:`result_to_json` — a single run's metrics +
  regression verdicts + provenance (``result.json``).
* :func:`compare_results` — an A/B diff between two independently-collected
  results (``comparison.json``). It reuses the over-time
  :func:`~bencher.regression.detect_regressions` path verbatim by stacking the
  two results on a synthetic 2-point ``over_time`` axis, so the A/B verdict
  shares identical direction/threshold semantics with the normal pipeline.

The contracts carry ``schema_version`` so downstream consumers can pin to a
shape.
"""

from __future__ import annotations

import json
import warnings
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import xarray as xr

from bencher.regression import (
    _finite_or_none,
    detect_regressions,
)
from bencher.variables.results import SCALAR_RESULT_TYPES, OptDir

if TYPE_CHECKING:
    from bencher.results.bench_result import BenchResult

SCHEMA_VERSION = 1


def _provenance(bench_res: BenchResult) -> dict:
    """Best-effort provenance for a result (time-event label if recorded)."""
    cfg = bench_res.bench_cfg
    prov: dict = {}
    time_event = getattr(cfg, "time_event", None)
    if time_event:
        prov["time_event"] = time_event
    return prov


def _metric_entry(bench_res: BenchResult, rv) -> dict:
    """Per-metric summary: identity + optimal value/inputs when computable."""
    entry: dict = {
        "variable": rv.name,
        "units": getattr(rv, "units", None),
        "direction": rv.direction.value if hasattr(rv, "direction") else OptDir.none.value,
    }
    # Optimal value/inputs can fail for degenerate datasets (empty, all-NaN,
    # ties spanning multiple coords). Treat as best-effort — never fatal.
    try:
        opt_indices = bench_res.get_optimal_value_indices(rv)
        entry["optimal_value"] = _finite_or_none(float(np.asarray(opt_indices.values).ravel()[0]))
        entry["optimal_inputs"] = {
            iv.name: _coord_scalar(opt_indices.coords[iv.name].values)
            for iv in bench_res.bench_cfg.input_vars
            if iv.name in opt_indices.coords
        }
    except (ValueError, IndexError, KeyError, TypeError):
        entry["optimal_value"] = None
        entry["optimal_inputs"] = {}
    return entry


def _coord_scalar(values):
    """Coerce an optimal-input coordinate to a JSON-safe scalar."""
    arr = np.asarray(values).ravel()
    if arr.size == 0:
        return None
    val = arr[0] if arr.size == 1 else arr[-1]
    item = val.item() if hasattr(val, "item") else val
    if isinstance(item, float):
        return _finite_or_none(item)
    return item


def series_for_var(ds: xr.Dataset, var_name: str) -> list[dict]:
    """Per-time-event mean/std/n for a scalar result var across the over_time axis.

    Reduces over every dim except ``over_time`` (the sweep inputs + ``repeat``)
    with NaN-aware reductions, mirroring the history reduction used elsewhere.
    The ``over_time`` coordinate labels can carry embedded newlines (long labels
    are wrapped in place), so strip them back to single-line strings.

    Returns one ``{time_event, mean, std, n}`` record per over-time event, with
    ``mean``/``std`` coerced finite-or-None so the output stays strict-JSON safe.
    """
    da = ds[var_name]
    reduce_dims = [d for d in da.dims if d != "over_time"]
    with warnings.catch_warnings():
        # An all-NaN event (a metric never recorded that run) legitimately
        # reduces to NaN -> None below; numpy's empty-slice warning is noise.
        warnings.simplefilter("ignore", RuntimeWarning)
        mean = da.mean(dim=reduce_dims, skipna=True).values
        std = da.std(dim=reduce_dims, skipna=True).values
    n = da.notnull().sum(dim=reduce_dims).values
    labels = [str(t).replace("\n", " ") for t in ds["over_time"].values]
    return [
        {
            "time_event": labels[i],
            "mean": _finite_or_none(float(mean[i])),
            "std": _finite_or_none(float(std[i])),
            "n": int(n[i]),
        }
        for i in range(len(labels))
    ]


def result_to_dict(bench_res: BenchResult, *, include_series: bool = False) -> dict:
    """Build the stable, JSON-serializable contract for a single result.

    Args:
        bench_res: A collected :class:`BenchResult` (e.g. from
            ``plot_sweep(auto_plot=False)`` / :meth:`Bench.collect`).
        include_series: When True and the result carries an ``over_time`` axis,
            attach a per-time-event ``series`` (:func:`series_for_var`) to each
            scalar metric — the trend behind the regression verdict, for callers
            that render sparklines. Off by default so the base contract stays
            byte-stable.

    Returns:
        A dict with ``schema_version``, ``bench_name``, ``provenance``,
        ``input_vars``, ``over_time``, ``metrics``, and ``regressions``.
    """
    cfg = bench_res.bench_cfg
    scalar_vars = [rv for rv in cfg.result_vars if isinstance(rv, SCALAR_RESULT_TYPES)]

    regressions = (
        bench_res.regression_report.to_dict()
        if getattr(bench_res, "regression_report", None) is not None
        else {"has_regressions": False, "has_blocking_regressions": False, "results": []}
    )

    metrics = [_metric_entry(bench_res, rv) for rv in scalar_vars]
    if include_series:
        ds = getattr(bench_res, "ds", None)
        if ds is not None and "over_time" in getattr(ds, "dims", ()):
            for metric in metrics:
                if metric["variable"] in ds:
                    metric["series"] = series_for_var(ds, metric["variable"])

    return {
        "schema_version": SCHEMA_VERSION,
        "bench_name": cfg.bench_name,
        "provenance": _provenance(bench_res),
        "input_vars": [
            {"name": iv.name, "units": getattr(iv, "units", None)} for iv in cfg.input_vars
        ],
        "over_time": bool(getattr(cfg, "over_time", False)),
        "metrics": metrics,
        "regressions": regressions,
    }


def result_to_json(
    bench_res: BenchResult, path: str | Path, *, indent: int = 2, include_series: bool = False
) -> Path:
    """Write :func:`result_to_dict` for *bench_res* to *path* as JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result_to_dict(bench_res, include_series=include_series), indent=indent),
        encoding="utf-8",
    )
    return path


def _snapshot_ds(bench_res: BenchResult) -> xr.Dataset:
    """Return a single-snapshot dataset (collapse a pre-existing over_time axis)."""
    ds = bench_res.ds
    if "over_time" in ds.dims:
        ds = ds.isel(over_time=-1, drop=True)
    return ds


def _finite_value(value: object) -> float | None:
    """Coerce *value* to a finite float, or None for anything that isn't one.

    The tolerant *reader* counterpart to
    :func:`~bencher.regression._finite_or_none` (the strict *writer* used by
    ``to_dict``): this one is fed records parsed from ``*.summary.json`` files
    that bencher may not have written, so every non-numeric, non-finite, or
    unrepresentable input degrades to ``None`` (which the verdict branches treat
    as "abstain") rather than aborting a scorecard build. ``OverflowError``
    matters in particular because JSON integers are arbitrary-precision, so a
    hand-edited or foreign summary can carry an int too large for a float.
    """
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None
    return number if np.isfinite(number) else None


def _verdict(reg: Mapping[str, object]) -> str:
    """Classify a metric movement as improved / regressed / unchanged.

    *reg* follows the :meth:`~bencher.regression.RegressionResult.to_dict`
    contract. ``regressed`` comes straight from the detector (direction- and
    threshold-aware). An improvement is the mirror image — a beneficial-direction
    move that clears the detector's gate — measured in each method's own units,
    because ``threshold`` means percent, absolute delta, MAD-sigma, or an
    absolute limit depending on ``method``:

    * ``percentage`` (and unknown methods, mirroring the fallback in
      :func:`~bencher.regression.method_cells`): ``|change_percent|`` clears
      ``threshold`` (a percent).
    * ``delta``: ``|current_value - baseline_value|`` clears ``threshold``
      (absolute units).
    * ``adaptive``: ``current_value`` lies outside the MAD acceptance band
      (``band_lower``/``band_upper``) and, when the dual-band percent gate is
      present, outside ``percent_band_lower``/``percent_band_upper`` too —
      mirroring :func:`~bencher.regression.detect_adaptive`'s AND gate.
      Abstains to "unchanged" when the bands are absent from the record.
    * ``absolute``: a fixed limit with no baseline to improve against
      (``change_percent`` is always NaN/None), so a non-regressed check is
      explicitly "unchanged".
    """
    if reg.get("regressed"):
        return "regressed"
    method = reg.get("method")
    if method == "absolute":
        improved = False
    elif method == "delta":
        improved = _delta_improved(reg)
    elif method == "adaptive":
        improved = _adaptive_improved(reg)
    else:
        improved = _percent_improved(reg)
    return "improved" if improved else "unchanged"


def _beneficial(delta: float, direction: object) -> bool:
    """True when a signed movement is in the variable's beneficial direction."""
    return (direction == OptDir.minimize.value and delta < 0) or (
        direction == OptDir.maximize.value and delta > 0
    )


def _delta_improved(reg: Mapping[str, object]) -> bool:
    """delta method: gate the improvement on |current - baseline| in absolute units.

    Strict ``>`` to mirror :func:`~bencher.regression.detect_delta`'s
    ``delta > max_delta`` exactly (contrast :func:`_percent_improved`, which keeps
    the pre-existing inclusive convention).
    """
    current = _finite_value(reg.get("current_value"))
    baseline = _finite_value(reg.get("baseline_value"))
    threshold = _finite_value(reg.get("threshold"))
    if current is None or baseline is None or threshold is None:
        return False
    delta = current - baseline
    return _beneficial(delta, reg.get("direction")) and abs(delta) > threshold


def _adaptive_improved(reg: Mapping[str, object]) -> bool:
    """adaptive method: improved iff outside the MAD band (and any percent band)."""
    current = _finite_value(reg.get("current_value"))
    baseline = _finite_value(reg.get("baseline_value"))
    band_lower = _finite_value(reg.get("band_lower"))
    band_upper = _finite_value(reg.get("band_upper"))
    if current is None or baseline is None or band_lower is None or band_upper is None:
        return False  # bands absent from the record: abstain.
    if not _beneficial(current - baseline, reg.get("direction")):
        return False
    if band_lower <= current <= band_upper:
        return False
    # Dual-band AND gate: when the percent band is present, being inside it suppresses.
    pct_lower = _finite_value(reg.get("percent_band_lower"))
    pct_upper = _finite_value(reg.get("percent_band_upper"))
    if pct_lower is None or pct_upper is None:
        return True
    # detect_adaptive derives the band as baseline*(1 ± pct/100), which INVERTS the
    # endpoints for a negative baseline (baseline=-100, pct=5 -> (-95, -105)); sort so
    # the membership test still holds there. The detector itself is unaffected because
    # it gates on _safe_change_percent, which divides by abs(baseline).
    pct_lower, pct_upper = sorted((pct_lower, pct_upper))
    return not pct_lower <= current <= pct_upper


def _percent_improved(reg: Mapping[str, object]) -> bool:
    """percentage method (and unknown-method fallback, mirroring method_cells)."""
    change_percent = _finite_value(reg.get("change_percent"))
    threshold = _finite_value(reg.get("threshold"))
    if change_percent is None or threshold is None:
        return False
    return _beneficial(change_percent, reg.get("direction")) and abs(change_percent) >= threshold


def compare_results(baseline: BenchResult, candidate: BenchResult, *, run_cfg=None) -> dict:
    """Diff two independently-collected results into an A/B comparison contract.

    Stacks *baseline* and *candidate* on a synthetic 2-point ``over_time`` axis
    (baseline first, candidate last) and runs the regular
    :func:`~bencher.regression.detect_regressions` over it, so the A/B verdict
    uses identical direction/threshold logic to the over-time path.

    Args:
        baseline: The reference result.
        candidate: The result being compared against the baseline.
        run_cfg: Optional :class:`BenchRunCfg` controlling the detector. When
            omitted, a percentage comparison (``regression_method='percentage'``)
            is used — the natural choice for a two-point A/B.

    Returns:
        A dict with ``schema_version``, ``baseline``/``candidate`` provenance,
        per-metric ``metrics`` (with a ``verdict``), and a ``summary`` count.

    Raises:
        ValueError: when the two results share no comparable scalar metric.
    """
    base_vars = {
        rv.name for rv in baseline.bench_cfg.result_vars if isinstance(rv, SCALAR_RESULT_TYPES)
    }
    cand_scalar = [
        rv for rv in candidate.bench_cfg.result_vars if isinstance(rv, SCALAR_RESULT_TYPES)
    ]
    shared = [rv for rv in cand_scalar if rv.name in base_vars]
    if not shared:
        raise ValueError(
            "compare_results: baseline and candidate share no comparable scalar result variables"
        )

    if run_cfg is None:
        from bencher.bench_cfg import BenchRunCfg

        run_cfg = BenchRunCfg(regression_method="percentage")

    base_ds = _snapshot_ds(baseline)
    cand_ds = _snapshot_ds(candidate)
    combined = xr.concat([base_ds, cand_ds], dim="over_time", join="outer")
    combined = combined.assign_coords(over_time=["baseline", "candidate"])

    # detect_regressions only inspects bench_cfg.result_vars; reuse candidate's.
    report = detect_regressions(combined, candidate.bench_cfg, run_cfg)

    metrics = []
    counts = {"improved": 0, "regressed": 0, "unchanged": 0}
    for r in report.results:
        verdict = _verdict(r.to_dict())
        counts[verdict] += 1
        metrics.append(
            {
                "variable": r.variable,
                "baseline_value": _finite_or_none(r.baseline_value),
                "current_value": _finite_or_none(r.current_value),
                "change_percent": _finite_or_none(r.change_percent),
                "direction": r.direction,
                "method": r.method,
                "regressed": bool(r.regressed),
                "verdict": verdict,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "baseline": {
            "bench_name": baseline.bench_cfg.bench_name,
            "provenance": _provenance(baseline),
        },
        "candidate": {
            "bench_name": candidate.bench_cfg.bench_name,
            "provenance": _provenance(candidate),
        },
        "metrics": metrics,
        "summary": counts,
    }


def comparison_to_json(
    baseline: BenchResult,
    candidate: BenchResult,
    path: str | Path,
    *,
    run_cfg=None,
    indent: int = 2,
) -> Path:
    """Write :func:`compare_results` for the two results to *path* as JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = compare_results(baseline, candidate, run_cfg=run_cfg)
    path.write_text(json.dumps(data, indent=indent), encoding="utf-8")
    return path
