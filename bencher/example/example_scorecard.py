"""Example: the benchmark health scorecard across distribution archetypes.

This example is deliberately *generic* — it fabricates benchmark summaries with
hand-shaped over-time distributions rather than running real sweeps, so the
scorecard's rendering (sparklines, verdict colors, ±std bands, category grouping)
and every :class:`~bencher.scorecard.ScorecardConfig` option can be evaluated and
iterated on in isolation, independent of any real benchmark.

Run it directly to write a self-contained ``index.html`` you can open and refine
the design against::

    python -m bencher.example.example_scorecard            # writes to ./scorecard_example/
    python -m bencher.example.example_scorecard /tmp/out    # or a directory you pick

The catalog below is the point of the example: one row per distribution shape, so
stable / noisy / improving / regressing / converging / spiky series sit side by
side in the same column for direct visual comparison.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from bencher.scorecard import Chrome, ReportLayout, ScorecardConfig, generate_scorecard

_N_EVENTS = 10
_REPEATS = 8
_SEED = 0


def _labels(n: int) -> list[str]:
    """Deterministic over-time event labels (date + short sha), like git_time_event."""
    return [f"2026-06-{10 + i:02d} {8 + i:02d}:00 {i:07d}" for i in range(n)]


def _series(means: list[float], stds: list[float]) -> list[dict]:
    labels = _labels(len(means))
    return [
        {
            "time_event": labels[i],
            "mean": round(means[i], 4),
            "std": round(abs(stds[i]), 4),
            "n": _REPEATS,
        }
        for i in range(len(means))
    ]


def _traj(
    rng: random.Random,
    start: float,
    end: float,
    noise: float,
    *,
    n: int = _N_EVENTS,
    noise_end: float | None = None,
) -> tuple[list[float], list[float]]:
    """A mean trajectory from *start* to *end* with per-event wobble and a ±std band.

    ``noise`` is the band half-width; set ``noise_end`` to ramp it (converging or
    expanding noise). The mean gets a small deterministic wobble so the line reads
    as real run-to-run data rather than a clean ramp.
    """
    means, stds = [], []
    for i in range(n):
        f = i / (n - 1) if n > 1 else 1.0
        base = start + (end - start) * f
        band = noise if noise_end is None else noise + (noise_end - noise) * f
        means.append(base + rng.uniform(-1.0, 1.0) * max(band, 1e-6) * 0.35)
        stds.append(band)
    return means, stds


def _metric(variable, direction, units, means, stds, optimal=None) -> dict:
    return {
        "variable": variable,
        "units": units,
        "direction": direction,
        "optimal_value": optimal,
        "optimal_inputs": {},
        "series": _series(means, stds),
    }


def _reg(variable, direction, regressed, means, threshold=15.0) -> dict:
    """A percentage regression verdict computed from the last two events of *means*."""
    baseline, current = means[-2], means[-1]
    change = (current - baseline) / abs(baseline) * 100.0 if baseline else 0.0
    return {
        "variable": variable,
        "method": "percentage",
        "regressed": regressed,
        "current_value": round(current, 4),
        "baseline_value": round(baseline, 4),
        "change_percent": round(change, 2),
        "threshold": threshold,
        "direction": direction,
    }


def _distribution_benches(rng: random.Random) -> list[dict]:
    """One bench per distribution archetype, all sharing a single ``value`` column.

    Sharing the column lines the sparklines up so the shapes compare directly; the
    per-bench regression entry drives the verdict color (or its absence -> trend).
    """
    benches: list[dict] = []

    def add(tag, name, direction, means, stds, *, regressed=None, threshold=15.0):
        metric = _metric("value", direction, "", means, stds)
        regs = []
        if regressed is not None:
            regs = [_reg("value", direction, regressed, means, threshold)]
        benches.append(
            {
                "tag": tag,
                "category": "Distribution Showcase",
                "name": name,
                "metrics": [metric],
                "regressions": regs,
            }
        )

    m, s = _traj(rng, 1.0, 1.0, 0.0)
    add("bench_stable", "Rock Solid", "maximize", m, s, regressed=False)

    m, s = _traj(rng, 0.95, 0.95, 0.02)
    add("bench_low_noise", "Low Noise", "maximize", m, s, regressed=False)

    m, s = _traj(rng, 0.9, 0.9, 0.18)
    add("bench_high_noise", "High Noise", "maximize", m, s, regressed=False)

    m, s = _traj(rng, 5.0, 3.0, 0.15)
    add("bench_improving", "Improving", "minimize", m, s, regressed=False)

    m, s = _traj(rng, 1.0, 0.6, 0.05)
    add("bench_regressing", "Regressing", "maximize", m, s, regressed=True)

    m, s = _traj(rng, 2.0, 2.55, 0.1)
    add("bench_trend", "Ungated Trend", "maximize", m, s)  # no reg entry -> trend

    m, s = _traj(rng, 10.0, 10.0, 0.4)
    for i in range(5, _N_EVENTS):
        m[i] += 6.0  # sudden step up (worse for a minimize metric)
    add("bench_step", "Step Change", "minimize", m, s, regressed=True)

    m, s = _traj(rng, 3.0, 3.0, 0.5, noise_end=0.05)
    add("bench_converging", "Converging Noise", "maximize", m, s, regressed=False)

    m, s = _traj(rng, 3.0, 3.0, 0.05, noise_end=0.5)
    add("bench_expanding", "Expanding Noise", "maximize", m, s, regressed=False)

    m, s = _traj(rng, 1.0, 1.0, 0.03)
    m[7] += 0.5
    s[7] = 0.6  # single spiky event
    add("bench_spike", "Outlier Spike", "maximize", m, s, regressed=False)

    m, s = _traj(rng, 0.8, 0.8, 0.0, n=1)
    add("bench_first_run", "First Run", "maximize", m, s)  # single event -> trend, no delta

    return benches


def _config_option_benches(rng: random.Random) -> list[dict]:
    """A second category exercising aliases, percent metrics, and shared columns."""
    succ_m, succ_s = _traj(rng, 1.0, 1.0, 0.0)
    wall_m, wall_s = _traj(rng, 0.9, 0.8, 0.04)
    comp_m, comp_s = _traj(rng, 0.7, 0.95, 0.03)
    dur_m, dur_s = _traj(rng, 4.0, 4.1, 0.2)

    pipeline = {
        "tag": "bench_pipeline",
        "category": "Config Options",
        "name": "Pipeline",
        "metrics": [
            _metric("success", "maximize", "ratio", succ_m, succ_s),
            # wall_time is aliased to the shared "duration" column; the cell tooltip
            # surfaces the raw source variable.
            _metric("wall_time", "minimize", "s", wall_m, wall_s),
            # completion is a 0..1 fraction rendered as a percentage.
            _metric("completion", "maximize", "ratio", comp_m, comp_s),
        ],
        "regressions": [
            _reg("success", "maximize", False, succ_m),
            _reg("wall_time", "minimize", False, wall_m),
        ],
    }
    latency = {
        "tag": "bench_service",
        "category": "Config Options",
        "name": "Service",
        "metrics": [
            _metric("success", "maximize", "ratio", succ_m, succ_s),
            _metric("duration", "minimize", "s", dur_m, dur_s),
        ],
        "regressions": [_reg("duration", "minimize", False, dur_m)],
    }
    return [pipeline, latency]


def _write_summaries(reports_dir: Path, benches: list[dict]) -> None:
    root = reports_dir / "benchmarks"
    for b in benches:
        tag_dir = root / b["tag"]
        tag_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "schema_version": 1,
            "bench_name": b["name"].replace(" ", ""),
            "provenance": {"time_event": _labels(_N_EVENTS)[-1]},
            "input_vars": [],
            "over_time": True,
            "metrics": b["metrics"],
            "regressions": {
                "has_regressions": any(r["regressed"] for r in b["regressions"]),
                "results": b["regressions"],
            },
        }
        (tag_dir / f"{data['bench_name']}.summary.json").write_text(json.dumps(data, indent=2))

    # An image-only benchmark: no scalar metrics, but an HTML report — it lands in
    # the "Reports without metrics" link section so it stays reachable.
    gallery = root / "bench_gallery"
    gallery.mkdir(parents=True, exist_ok=True)
    (gallery / "Gallery.html").write_text("<html><body>image sweep</body></html>")


def _config(benches: list[dict]) -> ScorecardConfig:
    registry = {b["tag"]: (b["category"], b["name"], "") for b in benches}
    registry["bench_gallery"] = (
        "Rendering",
        "Render Gallery",
        "Image-only visual regression sweep.",
    )
    return ScorecardConfig(
        registry=registry,
        aliases={"wall_time": "duration"},
        percent_metrics=frozenset({"completion"}),
        layout=ReportLayout(root="benchmarks"),
    )


def example_scorecard(output_dir: str | Path | None = None) -> Path:
    """Fabricate a diverse set of benchmark summaries and render the scorecard.

    Args:
        output_dir: where to write the summaries and the ``index.html`` page.
            Defaults to ``./scorecard_example``.

    Returns:
        Path to the rendered scorecard HTML.
    """
    reports_dir = Path(output_dir) if output_dir is not None else Path("scorecard_example")
    reports_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(_SEED)
    benches = _distribution_benches(rng) + _config_option_benches(rng)
    _write_summaries(reports_dir, benches)

    chrome = Chrome(
        title="Benchmark Health Scorecard — Example",
        commit_sha="abc1234def567",
        branch="main",
        pr_number="123",
        repo_url="https://github.com/blooop/bencher",
    )
    return generate_scorecard(
        reports_dir, _config(benches), chrome=chrome, output_name="index.html"
    )


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else None
    path = example_scorecard(out)
    print(f"Wrote scorecard example to {path}")
