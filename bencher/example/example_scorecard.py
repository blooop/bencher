"""Example: the benchmark health scorecard across distribution archetypes.

This example is deliberately *generic* — it fabricates benchmark summaries with
hand-shaped over-time distributions rather than running real sweeps, so the
scorecard's rendering (sparklines, verdict colors, ±std bands, category grouping)
and every :class:`~bencher.scorecard.ScorecardConfig` option can be evaluated and
iterated on in isolation, independent of any real benchmark.

Run it directly to write a self-contained ``index.html`` and open it in the
browser (like the other examples pop up a window). To keep the working tree
clean it writes to a temp directory by default; pass a path to write elsewhere::

    python -m bencher.example.example_scorecard            # temp dir, then opens in browser
    python -m bencher.example.example_scorecard /tmp/out    # or a directory you pick

The catalog below is the point of the example: one row per distribution shape, so
stable / noisy / improving / regressing / converging / spiky series sit side by
side in the same column for direct visual comparison.
"""

from __future__ import annotations

import json
import logging
import random
import sys
import tempfile
import webbrowser
from pathlib import Path

from bencher.scorecard import Chrome, ReportLayout, ScorecardConfig, generate_scorecard

logger = logging.getLogger(__name__)

_N_EVENTS = 10
_REPEATS = 8
_SEED = 0


def _labels(n: int) -> list[str]:
    """Deterministic over-time event labels (date + short sha), like git_time_event."""
    return [f"2026-06-{10 + i:02d} {8 + i:02d}:00 {i:07d}" for i in range(n)]


def _series(means: list[float], stds: list[float], *, n: int = _REPEATS) -> list[dict]:
    labels = _labels(len(means))
    return [
        {
            "time_event": labels[i],
            "mean": round(means[i], 4),
            "std": round(abs(stds[i]), 4),
            "n": n,
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
    wobble: float = 0.35,
) -> tuple[list[float], list[float]]:
    """A mean trajectory from *start* to *end* with per-event wobble and a ±std band.

    ``noise`` is the band half-width; set ``noise_end`` to ramp it (converging or
    expanding noise). The mean gets per-event wobble so the line reads as real
    run-to-run data rather than a clean ramp; ``wobble`` scales that jitter as a
    fraction of the band (raise it for a genuinely chaotic, high-noise line).
    """
    means, stds = [], []
    for i in range(n):
        f = i / (n - 1) if n > 1 else 1.0
        base = start + (end - start) * f
        band = noise if noise_end is None else noise + (noise_end - noise) * f
        means.append(base + rng.uniform(-1.0, 1.0) * max(band, 1e-6) * wobble)
        stds.append(band)
    return means, stds


def _noisy(
    rng: random.Random, base: float, jitter: float, *, trend: float = 0.0
) -> tuple[list[float], list[float]]:
    """A single-repeat series: one measurement per event, so there is *no* ±std
    band — the value itself jumps around run-to-run (optionally drifting by
    *trend* from first to last event). This is what a real single-repeat
    benchmark looks like: a bare, jittery line rather than a mean±band ribbon.
    """
    means, stds = [], []
    for i in range(_N_EVENTS):
        f = i / (_N_EVENTS - 1)
        means.append(base + trend * f + rng.uniform(-1.0, 1.0) * jitter)
        stds.append(0.0)  # single repeat -> no std to draw
    return means, stds


def _flip(low: float, high: float) -> tuple[list[float], list[float]]:
    """A single-repeat sawtooth: the value flips between *low* and *high* every
    event. One run per event means no ±std band — just the bare zig-zag line.
    """
    means = [high if i % 2 == 0 else low for i in range(_N_EVENTS)]
    stds = [0.0] * _N_EVENTS
    return means, stds


def _metric(variable, direction, units, means, stds, optimal=None, *, repeats=_REPEATS) -> dict:
    return {
        "variable": variable,
        "units": units,
        "direction": direction,
        "optimal_value": optimal,
        "optimal_inputs": {},
        "series": _series(means, stds, n=repeats),
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

    def add(tag, name, direction, means, stds, *, regressed=None, threshold=15.0, repeats=_REPEATS):
        metric = _metric("value", direction, "", means, stds, repeats=repeats)
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

    m, s = _traj(rng, 0.9, 0.9, 0.18, wobble=0.7)
    add("bench_high_noise", "High Noise", "maximize", m, s, regressed=False)

    # Single repeat, so no band — just a bare line whose value jumps around a lot
    # from event to event (a genuinely noisy metric measured once per run).
    m, s = _noisy(rng, 0.9, 0.22)
    add("bench_very_noisy", "Very Noisy", "maximize", m, s, regressed=False, repeats=1)

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

    # Sawtooth: single repeat flipping between two levels every event (no band).
    m, s = _flip(0.5, 1.0)
    add("bench_sawtooth", "Sawtooth Flip", "maximize", m, s, regressed=False, repeats=1)

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


# A deliberately wide metric set (10 columns) so the scorecard renders a
# many-column table. (variable, direction, units, start, end, noise).
_FLEET_METRICS = [
    ("cpu", "minimize", "%", 55.0, 52.0, 2.0),
    ("memory", "minimize", "MB", 480.0, 505.0, 8.0),
    ("latency_p50", "minimize", "ms", 12.0, 11.4, 0.4),
    ("latency_p99", "minimize", "ms", 48.0, 52.0, 3.0),
    ("throughput", "maximize", "rps", 8200.0, 8600.0, 120.0),
    ("error_rate", "minimize", "ratio", 0.012, 0.009, 0.002),
    ("cache_hit", "maximize", "ratio", 0.86, 0.9, 0.01),
    ("disk_read", "minimize", "MB", 32.0, 30.0, 1.5),
    ("startup", "minimize", "ms", 640.0, 610.0, 20.0),
    ("success_rate", "maximize", "ratio", 0.995, 0.998, 0.001),
]


def _fleet_benches(rng: random.Random) -> list[dict]:
    """A wide category: several services each reporting the same ~10 metrics, so
    the scorecard renders a many-column table (and exercises horizontal scroll).
    """
    benches: list[dict] = []
    for tag, name in (
        ("bench_api", "API"),
        ("bench_worker", "Worker"),
        ("bench_gateway", "Gateway"),
    ):
        metrics, regs = [], []
        for var, direction, units, start, end, noise in _FLEET_METRICS:
            scale = 1.0 + rng.uniform(-0.06, 0.06)  # per-service variation
            m, s = _traj(rng, start * scale, end * scale, noise)
            metrics.append(_metric(var, direction, units, m, s))
            regs.append(_reg(var, direction, False, m))
        benches.append(
            {
                "tag": tag,
                "category": "Service Fleet",
                "name": name,
                "metrics": metrics,
                "regressions": regs,
            }
        )
    return benches


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
        percent_metrics=frozenset({"completion", "error_rate", "cache_hit", "success_rate"}),
        layout=ReportLayout(root="benchmarks"),
    )


def example_scorecard(output_dir: str | Path | None = None) -> Path:
    """Fabricate a diverse set of benchmark summaries and render the scorecard.

    Args:
        output_dir: where to write the summaries and the ``index.html`` page.
            Defaults to a fresh temp directory so running the example never
            pollutes the working tree.

    Returns:
        Path to the rendered scorecard HTML.
    """
    if output_dir is not None:
        reports_dir = Path(output_dir)
        reports_dir.mkdir(parents=True, exist_ok=True)
    else:
        # A *fresh* directory per run: reusing a fixed path makes the auto-opened
        # browser re-focus the already-open tab without reloading, so edits to
        # the example would silently show the previous render.
        reports_dir = Path(tempfile.mkdtemp(prefix="bencher_scorecard_"))

    rng = random.Random(_SEED)
    benches = _distribution_benches(rng) + _fleet_benches(rng) + _config_option_benches(rng)
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
    # Open the rendered page in the browser, like the other examples pop up a
    # window. The scorecard is a self-contained HTML file, so the file:// URI
    # opens directly with no server needed (mirrors bencher's ShowMode.HTML path).
    try:
        webbrowser.open(path.resolve().as_uri())
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Failed to open browser for %s", path)
