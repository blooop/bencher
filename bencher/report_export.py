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
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import xarray as xr

from bencher.regression import (
    _finite_or_none,
    detect_regressions,
)
from bencher.variables.results import OptDir, SCALAR_RESULT_TYPES

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


def result_to_dict(bench_res: BenchResult) -> dict:
    """Build the stable, JSON-serializable contract for a single result.

    Args:
        bench_res: A collected :class:`BenchResult` (e.g. from
            ``plot_sweep(auto_plot=False)`` / :meth:`Bench.collect`).

    Returns:
        A dict with ``schema_version``, ``bench_name``, ``provenance``,
        ``input_vars``, ``over_time``, ``metrics``, and ``regressions``.
    """
    cfg = bench_res.bench_cfg
    scalar_vars = [rv for rv in cfg.result_vars if isinstance(rv, SCALAR_RESULT_TYPES)]

    regressions = (
        bench_res.regression_report.to_dict()
        if getattr(bench_res, "regression_report", None) is not None
        else {"has_regressions": False, "results": []}
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "bench_name": cfg.bench_name,
        "provenance": _provenance(bench_res),
        "input_vars": [
            {"name": iv.name, "units": getattr(iv, "units", None)} for iv in cfg.input_vars
        ],
        "over_time": bool(getattr(cfg, "over_time", False)),
        "metrics": [_metric_entry(bench_res, rv) for rv in scalar_vars],
        "regressions": regressions,
    }


def result_to_json(bench_res: BenchResult, path: str | Path, *, indent: int = 2) -> Path:
    """Write :func:`result_to_dict` for *bench_res* to *path* as JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result_to_dict(bench_res), indent=indent), encoding="utf-8")
    return path


def _snapshot_ds(bench_res: BenchResult) -> xr.Dataset:
    """Return a single-snapshot dataset (collapse a pre-existing over_time axis)."""
    ds = bench_res.ds
    if "over_time" in ds.dims:
        ds = ds.isel(over_time=-1, drop=True)
    return ds


def _verdict(
    change_percent: float | None, direction: str, regressed: bool, threshold: float
) -> str:
    """Classify a metric movement as improved / regressed / unchanged.

    ``regressed`` comes straight from the detector (direction- and
    threshold-aware). An improvement is the mirror image: a beneficial-direction
    move whose magnitude clears the same threshold.
    """
    if regressed:
        return "regressed"
    if change_percent is None or not np.isfinite(change_percent):
        return "unchanged"
    beneficial = (direction == OptDir.minimize.value and change_percent < 0) or (
        direction == OptDir.maximize.value and change_percent > 0
    )
    if beneficial and abs(change_percent) >= threshold:
        return "improved"
    return "unchanged"


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
        verdict = _verdict(r.change_percent, r.direction, r.regressed, r.threshold)
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
