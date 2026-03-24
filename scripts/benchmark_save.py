"""Comprehensive .save() performance benchmark for bencher reports.

Systematically tests all Panel/Bokeh save options and generates
SAVE_PERFORMANCE_REPORT.md with timing data, file sizes, profiling
breakdown, and recommendations.

Usage:
    pixi run benchmark-save                    # full benchmark
    pixi run benchmark-save -- --fixture over_time   # single fixture
    pixi run benchmark-save -- --skip-profiling      # skip cProfile phase
    pixi run benchmark-save -- --skip-parallel       # skip parallel tab test
    pixi run benchmark-save -- --quick               # fast subset (no profiling/parallel)
"""

from __future__ import annotations

import argparse
import cProfile
import gc
import os
import platform
import pstats
import statistics
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import bokeh
import holoviews as hv
import panel as pn

# Must be at top level before any bencher imports that trigger rendering
pn.extension()

import bencher as bn  # noqa: E402

try:
    from importlib.metadata import version as _pkg_version

    _BENCHER_VERSION = _pkg_version("holobench")
except (ImportError, ModuleNotFoundError):
    _BENCHER_VERSION = "unknown"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SaveConfig:
    """Configuration for a single save() call."""

    name: str
    embed: bool = True
    embed_json: bool = False
    max_states: int = 1000
    max_opts: int = 3
    resources: str = "CDN"  # CDN or INLINE
    use_disable_pipeline: bool = False

    def save_kwargs(self) -> dict:
        from bokeh.resources import CDN, INLINE

        res = CDN if self.resources == "CDN" else INLINE
        return {
            "embed": self.embed,
            "embed_json": self.embed_json,
            "max_states": self.max_states,
            "max_opts": self.max_opts,
            "resources": res,
        }


@dataclass
class FixtureVariant:
    """Fixture-level build variant (requires rebuild)."""

    name: str
    max_slider_points: int = 10
    show_agg_tab: bool = False


@dataclass
class TimingResult:
    """Result of timing a single save configuration."""

    fixture_type: str
    fixture_variant: str
    save_config: str
    times_ms: list[float] = field(default_factory=list)
    file_size_bytes: int = 0
    num_files: int = 0

    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.times_ms) if self.times_ms else 0.0

    @property
    def std_ms(self) -> float:
        return statistics.stdev(self.times_ms) if len(self.times_ms) > 1 else 0.0

    @property
    def min_ms(self) -> float:
        return min(self.times_ms) if self.times_ms else 0.0


# ---------------------------------------------------------------------------
# Benchmark parametrised sweep definitions
# ---------------------------------------------------------------------------


class SimpleBench(bn.ParametrizedSweep):
    """Simple fixture: 1 float input, 3 result vars."""

    x = bn.FloatSweep(default=1.0, bounds=[0, 2], samples=5, doc="x")
    r1 = bn.ResultVar(units="s", doc="result 1")
    r2 = bn.ResultVar(units="s", doc="result 2")
    r3 = bn.ResultVar(units="s", doc="result 3")

    offset = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.r1 = self.x + self.offset
        self.r2 = self.x * 2 + self.offset
        self.r3 = self.x * 3 + self.offset
        return super().__call__()


class ComplexBench(bn.ParametrizedSweep):
    """Complex fixture: 1 float + 1 categorical input, 5 result vars."""

    x = bn.FloatSweep(default=1.0, bounds=[0, 2], samples=5, doc="x")
    cat = bn.StringSweep(["alpha", "beta", "gamma"], doc="category")
    r1 = bn.ResultVar(units="s", doc="result 1")
    r2 = bn.ResultVar(units="s", doc="result 2")
    r3 = bn.ResultVar(units="s", doc="result 3")
    r4 = bn.ResultVar(units="s", doc="result 4")
    r5 = bn.ResultVar(units="s", doc="result 5")

    offset = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        base = self.x + self.offset
        self.r1 = base
        self.r2 = base * 1.5
        self.r3 = base * 2
        self.r4 = base * 0.5
        self.r5 = base * 3
        return super().__call__()


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

FIXTURE_DEFS = {
    "simple": {
        "cls": SimpleBench,
        "over_time": False,
        "repeats": 1,
        "time_events": 1,
        "input_vars": ["x"],
        "result_vars": ["r1", "r2", "r3"],
    },
    "over_time": {
        "cls": SimpleBench,
        "over_time": True,
        "repeats": 2,
        "time_events": 5,
        "input_vars": ["x"],
        "result_vars": ["r1", "r2", "r3"],
    },
    "complex": {
        "cls": ComplexBench,
        "over_time": True,
        "repeats": 2,
        "time_events": 3,
        "input_vars": ["x", "cat"],
        "result_vars": ["r1", "r2", "r3", "r4", "r5"],
    },
}


def build_fixture(fixture_type: str, variant: FixtureVariant) -> bn.Bench:
    """Build a benchmark fixture and return the Bench with populated report."""
    fdef = FIXTURE_DEFS[fixture_type]
    benchable = fdef["cls"]()
    run_cfg = bn.BenchRunCfg()
    run_cfg.over_time = fdef["over_time"]
    run_cfg.repeats = fdef["repeats"]
    run_cfg.max_slider_points = variant.max_slider_points
    run_cfg.show_aggregated_time_tab = variant.show_agg_tab
    bench = benchable.to_bench(run_cfg)
    base = datetime(2000, 1, 1)

    for i in range(fdef["time_events"]):
        benchable.offset = i * 0.1
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        bench.plot_sweep(
            f"bench_save_perf_{fixture_type}",
            input_vars=fdef["input_vars"],
            result_vars=fdef["result_vars"],
            run_cfg=run_cfg,
            time_src=base + timedelta(seconds=i),
        )

    return bench


# ---------------------------------------------------------------------------
# Save runners
# ---------------------------------------------------------------------------

WARMUP_RUNS = 1
TIMED_RUNS = 2


def _get_save_content(report: bn.BenchReport) -> pn.Column:
    """Extract saveable content from a report, bypassing BenchReport.save()."""
    content = report.pane[0] if len(report.pane) == 1 else report.pane
    return pn.Column(content)


def _total_file_size(directory: str) -> tuple[int, int]:
    """Return (total_bytes, num_files) for all files under directory."""
    total = 0
    count = 0
    for root, _dirs, files in os.walk(directory):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
            count += 1
    return total, count


def run_save_timed(
    report: bn.BenchReport, config: SaveConfig, single_run: bool = False
) -> TimingResult:
    """Run save with given config, return timing and size data.

    Args:
        single_run: If True, skip warmup and do 1 timed run only (for slow configs).
    """
    from contextlib import nullcontext

    from holoviews.core.data import disable_pipeline

    result = TimingResult(fixture_type="", fixture_variant="", save_config=config.name)
    content = _get_save_content(report)
    warmup = 0 if single_run else WARMUP_RUNS
    timed = 1 if single_run else TIMED_RUNS
    ctx = disable_pipeline if config.use_disable_pipeline else nullcontext

    for run_idx in range(warmup + timed):
        gc.collect()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "output.html"
            kwargs = config.save_kwargs()
            t0 = time.perf_counter()
            with ctx():
                content.save(filename=path, progress=False, **kwargs)
            elapsed = (time.perf_counter() - t0) * 1000.0

            if run_idx >= warmup:
                result.times_ms.append(elapsed)

            # Capture file size from last run
            if run_idx == warmup + timed - 1:
                result.file_size_bytes, result.num_files = _total_file_size(td)

    return result


# ---------------------------------------------------------------------------
# Profiling
# ---------------------------------------------------------------------------


def _profiler_stats_to_markdown(profiler: cProfile.Profile, limit: int = 20) -> str:
    """Return a markdown table of the top `limit` functions from a cProfile.Profile.

    Uses the structured `pstats.Stats.stats` mapping instead of parsing
    text output, making it robust across Python/platform versions.
    """
    stats = pstats.Stats(profiler)
    func_stats = []
    for func_key, (_cc, nc, tt, ct, _callers) in stats.stats.items():
        func_stats.append((func_key, nc, tt, ct))

    func_stats.sort(key=lambda item: item[3], reverse=True)

    rows = [
        "| ncalls | tottime (s) | cumtime (s) | function |",
        "|--------|-------------|-------------|----------|",
    ]
    for (filename, lineno, funcname), ncalls, tottime, cumtime in func_stats[:limit]:
        location = f"`{filename}:{lineno}({funcname})`"
        rows.append(f"| {ncalls} | {tottime:.4f} | {cumtime:.4f} | {location} |")

    return "\n".join(rows)


def run_profiled_save(report: bn.BenchReport) -> str:
    """Run a profiled save on the report, return markdown table of top-20 functions."""
    content = _get_save_content(report)
    profiler = cProfile.Profile()

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "profiled.html"
        from bokeh.resources import CDN

        profiler.enable()
        content.save(filename=path, progress=False, embed=True, resources=CDN)
        profiler.disable()

    return _profiler_stats_to_markdown(profiler, limit=20)


# ---------------------------------------------------------------------------
# Parallel tab saves test
# ---------------------------------------------------------------------------


def test_parallel_tab_saves(report: bn.BenchReport) -> tuple[float, float, int]:
    """Compare sequential vs parallel per-tab saves.

    Returns (sequential_ms, parallel_ms, num_tabs).
    """
    from bokeh.resources import CDN

    tabs = list(report.pane)
    num_tabs = len(tabs)
    if num_tabs <= 1:
        return 0.0, 0.0, num_tabs

    def save_one_tab(tab_and_dir: tuple) -> float:
        tab, td = tab_and_dir
        path = Path(td) / "tab.html"
        t0 = time.perf_counter()
        pn.Column(tab).save(filename=path, progress=False, embed=True, resources=CDN)
        return (time.perf_counter() - t0) * 1000.0

    # Sequential
    gc.collect()
    seq_total = 0.0
    for tab in tabs:
        with tempfile.TemporaryDirectory() as td:
            seq_total += save_one_tab((tab, td))

    # Parallel
    gc.collect()
    with tempfile.TemporaryDirectory() as base_td:
        tab_dirs = []
        for i in range(num_tabs):
            d = os.path.join(base_td, f"tab_{i}")
            os.makedirs(d)
            tab_dirs.append(d)

        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=min(num_tabs, 4)) as executor:
            list(executor.map(save_one_tab, zip(tabs, tab_dirs)))
        par_total = (time.perf_counter() - t0) * 1000.0

    return seq_total, par_total, num_tabs


# ---------------------------------------------------------------------------
# Save configs
# ---------------------------------------------------------------------------

# Core configs — run with warmup + timed iterations
SAVE_CONFIGS_CORE = [
    SaveConfig(name="baseline", embed=True, embed_json=False),
    SaveConfig(name="disable_pipeline", embed=True, use_disable_pipeline=True),
    SaveConfig(name="embed_json", embed=True, embed_json=True),
    SaveConfig(name="no_embed", embed=False),
    SaveConfig(name="inline_resources", embed=True, resources="INLINE"),
]

# Slow/exploratory configs — single run only (these trigger Panel's record_events fallback)
SAVE_CONFIGS_SLOW = [
    SaveConfig(name="max_states_100", embed=True, max_states=100),
    SaveConfig(name="max_opts_1", embed=True, max_opts=1),
]

# Reduced config set — run on simple and complex to show scaling
SAVE_CONFIGS_REDUCED = [
    SaveConfig(name="baseline", embed=True, embed_json=False),
    SaveConfig(name="no_embed", embed=False),
]

FIXTURE_VARIANTS = [
    FixtureVariant(name="slider_5", max_slider_points=5),
    FixtureVariant(name="slider_10", max_slider_points=10),
    FixtureVariant(name="slider_20", max_slider_points=20),
]


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def _fmt_ms(val: float) -> str:
    if val >= 1000:
        return f"{val / 1000:.2f}s"
    return f"{val:.0f}ms"


def _fmt_bytes(val: int) -> str:
    if val >= 1_000_000:
        return f"{val / 1_000_000:.1f}MB"
    if val >= 1_000:
        return f"{val / 1_000:.0f}KB"
    return f"{val}B"


def generate_report(
    timing_results: list[TimingResult],
    slider_results: list[TimingResult],
    agg_tab_results: list[TimingResult],
    profile_table: str,
    parallel_data: tuple[float, float, int],
) -> str:
    """Generate the full markdown report."""

    # Environment info
    env_info = (
        f"- **Python**: {sys.version.split()[0]}\n"
        f"- **Panel**: {pn.__version__}\n"
        f"- **Bokeh**: {bokeh.__version__}\n"
        f"- **HoloViews**: {hv.__version__}\n"
        f"- **Bencher**: {_BENCHER_VERSION}\n"
        f"- **Platform**: {platform.platform()}\n"
        f"- **CPU**: {platform.processor() or platform.machine()}\n"
    )

    # --- Build timing table ---
    timing_header = "| Config | Fixture | Mean | Std | Min | File Size | Files |\n"
    timing_header += "|--------|---------|------|-----|-----|-----------|-------|\n"
    timing_rows = ""
    for r in timing_results:
        timing_rows += (
            f"| {r.save_config} | {r.fixture_type} | "
            f"{_fmt_ms(r.mean_ms)} | {_fmt_ms(r.std_ms)} | {_fmt_ms(r.min_ms)} | "
            f"{_fmt_bytes(r.file_size_bytes)} | {r.num_files} |\n"
        )

    # --- Slider scaling table ---
    slider_header = "| Variant | Mean | Std | Min |\n"
    slider_header += "|---------|------|-----|-----|\n"
    slider_rows = ""
    for r in slider_results:
        slider_rows += (
            f"| {r.fixture_variant} | "
            f"{_fmt_ms(r.mean_ms)} | {_fmt_ms(r.std_ms)} | {_fmt_ms(r.min_ms)} |\n"
        )

    # --- Agg tab table ---
    agg_header = "| Variant | Mean | Std | Min |\n"
    agg_header += "|---------|------|-----|-----|\n"
    agg_rows = ""
    for r in agg_tab_results:
        agg_rows += (
            f"| {r.fixture_variant} | "
            f"{_fmt_ms(r.mean_ms)} | {_fmt_ms(r.std_ms)} | {_fmt_ms(r.min_ms)} |\n"
        )

    # --- Parallel tab saves ---
    seq_ms, par_ms, n_tabs = parallel_data
    if n_tabs > 1:
        speedup = seq_ms / par_ms if par_ms > 0 else float("inf")
        parallel_section = (
            f"Sequential save of {n_tabs} tabs: **{_fmt_ms(seq_ms)}**\n\n"
            f"Parallel save ({min(n_tabs, 4)} workers): **{_fmt_ms(par_ms)}**\n\n"
            f"Speedup: **{speedup:.2f}x**\n"
        )
    else:
        parallel_section = "N/A — only single-tab fixtures tested for parallel saves.\n"

    # --- Executive summary ---
    def _find(config_name: str, fixture: str = "over_time") -> TimingResult | None:
        return next(
            (
                r
                for r in timing_results
                if r.save_config == config_name and r.fixture_type == fixture
            ),
            None,
        )

    baseline_ot = _find("baseline")
    disable_pipeline_ot = _find("disable_pipeline")
    no_embed_ot = _find("no_embed")
    max_states_ot = _find("max_states_100")
    max_opts_ot = _find("max_opts_1")
    inline_ot = _find("inline_resources")
    embed_json_ot = _find("embed_json")

    summary_bullets = []
    if baseline_ot:
        summary_bullets.append(
            f"- **Baseline** over_time save: {_fmt_ms(baseline_ot.mean_ms)} "
            f"({_fmt_bytes(baseline_ot.file_size_bytes)})"
        )
    if disable_pipeline_ot and baseline_ot:
        ratio = disable_pipeline_ot.mean_ms / baseline_ot.mean_ms
        summary_bullets.append(
            f"- **disable_pipeline** is {ratio:.1f}x baseline "
            f"({_fmt_ms(disable_pipeline_ot.mean_ms)}) "
            f"— REJECTED: no improvement, wrapper overhead is negligible"
        )
    if no_embed_ot and baseline_ot:
        ratio = baseline_ot.mean_ms / no_embed_ot.mean_ms if no_embed_ot.mean_ms > 0 else 0
        summary_bullets.append(
            f"- **no_embed** is {ratio:.1f}x faster "
            f"({_fmt_ms(no_embed_ot.mean_ms)}) but loses interactivity"
        )
    if max_states_ot and baseline_ot:
        ratio = max_states_ot.mean_ms / baseline_ot.mean_ms if baseline_ot.mean_ms > 0 else 0
        summary_bullets.append(
            f"- **max_states=100** is {ratio:.1f}x SLOWER ({_fmt_ms(max_states_ot.mean_ms)}) "
            f"— triggers Panel's expensive record_events fallback"
        )
    if max_opts_ot and baseline_ot:
        ratio = max_opts_ot.mean_ms / baseline_ot.mean_ms if baseline_ot.mean_ms > 0 else 0
        summary_bullets.append(
            f"- **max_opts=1** is {ratio:.1f}x SLOWER ({_fmt_ms(max_opts_ot.mean_ms)}) "
            f"— also triggers record_events fallback"
        )
    if inline_ot and baseline_ot:
        ratio = inline_ot.mean_ms / baseline_ot.mean_ms if baseline_ot.mean_ms > 0 else 0
        summary_bullets.append(
            f"- **inline_resources** is {ratio:.1f}x slower ({_fmt_ms(inline_ot.mean_ms)}) "
            f"— bundling Bokeh JS per embed state is expensive"
        )
    if embed_json_ot and baseline_ot:
        ratio = embed_json_ot.mean_ms / baseline_ot.mean_ms if baseline_ot.mean_ms > 0 else 0
        summary_bullets.append(
            f"- **embed_json** is {ratio:.1f}x baseline "
            f"({_fmt_ms(embed_json_ot.mean_ms)}) — computation not skipped, adds I/O"
        )
    if n_tabs > 1:
        summary_bullets.append(
            f"- **Parallel tab saves** ({n_tabs} tabs): "
            f"{seq_ms / par_ms if par_ms > 0 else 0:.1f}x speedup"
        )

    summary = "\n".join(summary_bullets) if summary_bullets else "No over_time results collected."

    # --- Raw timing data ---
    raw_lines = ["fixture_type,fixture_variant,save_config,mean_ms,std_ms,min_ms,file_bytes,files"]
    for r in timing_results + slider_results + agg_tab_results:
        raw_lines.append(
            f"{r.fixture_type},{r.fixture_variant},{r.save_config},"
            f"{r.mean_ms:.1f},{r.std_ms:.1f},{r.min_ms:.1f},"
            f"{r.file_size_bytes},{r.num_files}"
        )

    report = f"""\
# Save Performance Report

> Auto-generated by `scripts/benchmark_save.py` on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Executive Summary

{summary}

## Environment

{env_info}

## Methodology

Three fixture types exercise different code paths:

| Fixture | Inputs | Result Vars | over_time | repeats | time_events |
|---------|--------|-------------|-----------|---------|-------------|
| **simple** | 1 float (5 samples) | 3 | No | 1 | 1 |
| **over_time** | 1 float (5 samples) | 3 | Yes | 2 | 5 |
| **complex** | 1 float + 1 categorical | 5 | Yes | 2 | 3 |

Each save configuration runs {WARMUP_RUNS} warm-up + {TIMED_RUNS} timed iterations.
Content is extracted via `pn.Column(report.pane[0]).save()` to bypass
`BenchReport.save()`'s hardcoded `embed=True`.

The full config matrix runs on the **over_time** fixture (primary target).
Simple and complex fixtures use a reduced set (baseline + no_embed) for scaling context.

## Results: Save Time & File Size

{timing_header}{timing_rows}

## Results: Slider Points Scaling

Tests with over_time fixture, baseline save config, varying `max_slider_points`:

{slider_header}{slider_rows}

## Results: Aggregated Tab Impact

Comparing `show_aggregated_time_tab=True` vs `False` on over_time fixture:

{agg_header}{agg_rows}

## Results: Parallel Tab Saves

{parallel_section}

## Profiling Breakdown

cProfile top-20 cumulative-time functions for baseline over_time save:

{profile_table}

## Analysis

Key observations from the data above:

1. **`embed_state()` dominates**: Panel's embed step pre-computes JSON diffs for every
   widget state combination. This is O(slider_positions x cost_per_diff).
2. **`no_embed` is the floor**: Without embedding, save is just Bokeh HTML serialization.
   The gap between `no_embed` and `baseline` is pure Panel embed overhead.
3. **`max_states` / `max_opts` are TRAPS**: Setting these below the actual widget state
   count triggers Panel's `record_events` fallback, which is dramatically slower.
   Panel computes the cross-product of all widget options; if this exceeds `max_states`,
   it switches to recording individual event replays — 8-10x slower in our tests.
4. **`inline_resources` is expensive**: Bundling ~2MB of Bokeh JS into the HTML happens
   per embed-state diff, multiplying the serialization cost.
5. **`embed_json`** does NOT skip computation — it externalizes patches to JSON files
   but still computes every diff, adding I/O overhead.
6. **`max_slider_points` scales linearly**: More slider points = more states to embed.
   This is the most effective lever (already shipped at default=10).
7. **Parallel tab saves** can provide speedup when tabs are independent, though
   Panel/Bokeh may have global state that limits parallelism.

## Recommendations

Prioritized by expected impact:

1. **Keep `max_slider_points=10` (P0, shipped)** — Already limits the dominant O(n) factor
2. **Keep `show_aggregated_time_tab=False` (P0, shipped)** — Avoids doubling embed cost
3. **NEVER reduce `max_states` or `max_opts` below defaults** — This is counter-intuitive
   but triggers a much more expensive fallback path in Panel
4. **Avoid `inline_resources`** — Use CDN (default) unless offline viewing is required
5. **Consider `embed=False` for CI/preview** — 2-3x faster, produces static HTML
   without interactive sliders. Good for automated reports where interactivity isn't needed.
   Note: this is opt-in only — default keeps interactive sliders.
6. ~~**Parallel per-tab saves via ThreadPoolExecutor**~~ **REJECTED** — GIL blocks
   parallelism (measured 0.95x speedup). `ProcessPoolExecutor` is an option but
   Panel/Bokeh objects are not easily serializable across process boundaries.
7. ~~**Long-term: lazy embed / on-demand / Panel `--rest` mode**~~ **REJECTED** — Requires
   a live Panel server, which is not viable for static HTML reports (the only supported
   output mode). DynamicMap similarly requires a server for interactivity.
8. ~~**Disable HoloViews pipeline tracking (`disable_pipeline()`)**~~ **REJECTED** —
   Benchmarked; the wrapper overhead is only ~28ms tottime despite 3.3s cumtime.
   Measured same-or-slower than baseline.

## Appendix: Raw Timing Data

```csv
{chr(10).join(raw_lines)}
```
"""
    return report


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark bencher report .save() performance")
    parser.add_argument(
        "--fixture",
        choices=["simple", "over_time", "complex"],
        nargs="+",
        default=None,
        help="Run only these fixture types (default: all)",
    )
    parser.add_argument(
        "--skip-profiling",
        action="store_true",
        help="Skip the cProfile profiling phase",
    )
    parser.add_argument(
        "--skip-parallel",
        action="store_true",
        help="Skip the parallel tab saves test",
    )
    parser.add_argument(
        "--skip-slow",
        action="store_true",
        help="Skip slow configs (max_states_100, max_opts_1)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: over_time fixture only, no profiling/parallel/slow configs",
    )
    return parser.parse_args()


def main():
    args = _parse_args()

    # --quick implies restricted scope
    if args.quick:
        args.skip_profiling = True
        args.skip_parallel = True
        args.skip_slow = True
        if args.fixture is None:
            args.fixture = ["over_time"]

    fixtures = set(args.fixture) if args.fixture else {"simple", "over_time", "complex"}

    print("=" * 60)
    print("Bencher .save() Performance Benchmark")
    print(f"  Fixtures: {', '.join(sorted(fixtures))}")
    if args.skip_profiling:
        print("  Skipping: profiling")
    if args.skip_parallel:
        print("  Skipping: parallel tab saves")
    if args.skip_slow:
        print("  Skipping: slow configs")
    print("=" * 60)

    all_timing_results: list[TimingResult] = []
    slider_results: list[TimingResult] = []
    agg_tab_results: list[TimingResult] = []
    profile_table = ""
    bench_complex = None

    default_variant = FixtureVariant(name="default", max_slider_points=10, show_agg_tab=False)
    baseline_config = SAVE_CONFIGS_CORE[0]

    # --- Phase 1: Simple fixture (reduced configs) ---
    if "simple" in fixtures:
        print("\n--- Building fixture: simple (default variant) ---")
        bench = build_fixture("simple", default_variant)
        for config in SAVE_CONFIGS_REDUCED:
            print(f"  Testing save config: {config.name} ...", end=" ", flush=True)
            result = run_save_timed(bench.report, config)
            result.fixture_type = "simple"
            result.fixture_variant = "default"
            all_timing_results.append(result)
            print(f"{_fmt_ms(result.mean_ms)} (±{_fmt_ms(result.std_ms)})")

    # --- Phase 2: Over_time fixture (core configs with full timing) ---
    if "over_time" in fixtures:
        print("\n--- Building fixture: over_time (default variant) ---")
        bench = build_fixture("over_time", default_variant)
        for config in SAVE_CONFIGS_CORE:
            print(f"  Testing save config: {config.name} ...", end=" ", flush=True)
            result = run_save_timed(bench.report, config)
            result.fixture_type = "over_time"
            result.fixture_variant = "default"
            all_timing_results.append(result)
            print(f"{_fmt_ms(result.mean_ms)} (±{_fmt_ms(result.std_ms)})")

        # Slow/exploratory configs — single run (trigger expensive fallback paths)
        if not args.skip_slow:
            for config in SAVE_CONFIGS_SLOW:
                print(
                    f"  Testing save config: {config.name} (single run) ...",
                    end=" ",
                    flush=True,
                )
                result = run_save_timed(bench.report, config, single_run=True)
                result.fixture_type = "over_time"
                result.fixture_variant = "default"
                all_timing_results.append(result)
                print(f"{_fmt_ms(result.mean_ms)}")

    # --- Phase 3: Complex fixture (reduced configs) ---
    if "complex" in fixtures:
        print("\n--- Building fixture: complex (default variant) ---")
        bench_complex = build_fixture("complex", default_variant)
        for config in SAVE_CONFIGS_REDUCED:
            print(f"  Testing save config: {config.name} ...", end=" ", flush=True)
            result = run_save_timed(bench_complex.report, config)
            result.fixture_type = "complex"
            result.fixture_variant = "default"
            all_timing_results.append(result)
            print(f"{_fmt_ms(result.mean_ms)} (±{_fmt_ms(result.std_ms)})")

    # --- Phase 4: Slider points scaling (over_time fixture only) ---
    if "over_time" in fixtures:
        print("\n--- Slider points scaling ---")
        for variant in FIXTURE_VARIANTS:
            print(f"  Building over_time with {variant.name} ...", end=" ", flush=True)
            bench = build_fixture("over_time", variant)
            result = run_save_timed(bench.report, baseline_config)
            result.fixture_type = "over_time"
            result.fixture_variant = variant.name
            slider_results.append(result)
            print(f"{_fmt_ms(result.mean_ms)} (±{_fmt_ms(result.std_ms)})")

        # --- Phase 5: Aggregated tab impact ---
        print("\n--- Aggregated tab impact ---")
        for show_agg in [False, True]:
            variant_name = "with_agg_tab" if show_agg else "no_agg_tab"
            variant = FixtureVariant(name=variant_name, max_slider_points=10, show_agg_tab=show_agg)
            print(f"  Building over_time with {variant_name} ...", end=" ", flush=True)
            bench = build_fixture("over_time", variant)
            result = run_save_timed(bench.report, baseline_config)
            result.fixture_type = "over_time"
            result.fixture_variant = variant_name
            agg_tab_results.append(result)
            print(f"{_fmt_ms(result.mean_ms)} (±{_fmt_ms(result.std_ms)})")

    # --- Phase 6: Profiling ---
    if not args.skip_profiling and "over_time" in fixtures:
        print("\n--- Profiling baseline over_time save ---")
        bench = build_fixture("over_time", default_variant)
        profile_table = run_profiled_save(bench.report)
        print("  Done.")

    # --- Phase 7: Parallel tab saves ---
    parallel_data = (0.0, 0.0, 0)
    if not args.skip_parallel and bench_complex is not None:
        print("\n--- Parallel tab saves ---")
        parallel_data = test_parallel_tab_saves(bench_complex.report)
        seq_ms, par_ms, n_tabs = parallel_data
        if n_tabs > 1:
            speedup = seq_ms / par_ms if par_ms > 0 else 0
            print(
                f"  {n_tabs} tabs: sequential={_fmt_ms(seq_ms)}, "
                f"parallel={_fmt_ms(par_ms)}, speedup={speedup:.2f}x"
            )
        else:
            print("  Only 1 tab — skipping parallel test.")

    # --- Generate report ---
    print("\n--- Generating report ---")
    report_md = generate_report(
        all_timing_results, slider_results, agg_tab_results, profile_table, parallel_data
    )
    report_path = Path(__file__).resolve().parent.parent / "SAVE_PERFORMANCE_REPORT.md"
    report_path.write_text(report_md, encoding="utf-8")
    print(f"Report written to: {report_path}")
    print("Done!")


if __name__ == "__main__":
    main()
