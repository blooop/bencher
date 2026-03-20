"""Performance tracking for core bencher features.

Benchmarks parameter sweep execution, caching, and result generation to detect
performance regressions over time. Run locally or via CI to publish to GitHub Pages:

    python bencher/example/example_performance.py
"""

import math
import tempfile
import time
from copy import deepcopy

import bencher as bch


# ── Simple worker for inner benchmarks ──────────────────────────────────────
class _SineWorker(bch.ParametrizedSweep):
    x = bch.FloatSweep(default=0, bounds=[0, math.pi], samples=30)
    y = bch.FloatSweep(default=0, bounds=[0, math.pi], samples=10)
    out = bch.ResultVar(units="v")

    def __call__(self, **kw):
        self.update_params_from_kwargs(**kw)
        self.out = math.sin(self.x) + math.cos(self.y)
        return super().__call__(**kw)


def _fresh_cfg():
    """Create a clean BenchRunCfg for inner benchmarks, avoiding outer runner config."""
    cfg = bch.BenchRunCfg()
    cfg.auto_plot = False
    return cfg


def _perf_run_cfg(run_cfg):
    """Create a run_cfg suitable for performance benchmarks (no caching of outer results)."""
    if run_cfg is not None:
        run_cfg = deepcopy(run_cfg)
    else:
        run_cfg = bch.BenchRunCfg()
    run_cfg.cache_samples = False
    run_cfg.only_hash_tag = False
    return run_cfg


# ── Benchmark: sweep execution time ────────────────────────────────────────
class SweepPerformance(bch.ParametrizedSweep):
    """Measure execution time of 1D and 2D parameter sweeps."""

    sweep_1d_time_ms = bch.ResultVar(
        units="ms", doc="1D sweep execution time", direction=bch.OptDir.minimize
    )
    sweep_2d_time_ms = bch.ResultVar(
        units="ms", doc="2D sweep execution time", direction=bch.OptDir.minimize
    )

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        # 1D sweep
        cfg = _fresh_cfg()
        bench = bch.Bench("_perf_1d", _SineWorker(), run_cfg=cfg)
        t0 = time.perf_counter()
        bench.plot_sweep(input_vars=["x"], result_vars=["out"])
        self.sweep_1d_time_ms = (time.perf_counter() - t0) * 1000

        # 2D sweep
        cfg2 = _fresh_cfg()
        bench2 = bch.Bench("_perf_2d", _SineWorker(), run_cfg=cfg2)
        t0 = time.perf_counter()
        bench2.plot_sweep(input_vars=["x", "y"], result_vars=["out"])
        self.sweep_2d_time_ms = (time.perf_counter() - t0) * 1000

        return super().__call__(**kwargs)


# ── Benchmark: cache performance ───────────────────────────────────────────
class CachePerformance(bch.ParametrizedSweep):
    """Measure cache hit vs miss performance."""

    cold_time_ms = bch.ResultVar(
        units="ms", doc="Time with empty cache", direction=bch.OptDir.minimize
    )
    warm_time_ms = bch.ResultVar(
        units="ms", doc="Time with warm cache", direction=bch.OptDir.minimize
    )
    speedup = bch.ResultVar(units="x", doc="Cache speedup factor", direction=bch.OptDir.maximize)

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        # Cold run
        cfg = _fresh_cfg()
        cfg.clear_sample_cache = True
        cfg.cache_samples = True
        bench = bch.Bench("_cache_perf", _SineWorker(), run_cfg=cfg)
        t0 = time.perf_counter()
        bench.plot_sweep(input_vars=["x"], result_vars=["out"])
        self.cold_time_ms = (time.perf_counter() - t0) * 1000

        # Warm run
        cfg2 = _fresh_cfg()
        cfg2.cache_samples = True
        cfg2.clear_sample_cache = False
        bench2 = bch.Bench("_cache_perf", _SineWorker(), run_cfg=cfg2)
        t0 = time.perf_counter()
        bench2.plot_sweep(input_vars=["x"], result_vars=["out"])
        self.warm_time_ms = (time.perf_counter() - t0) * 1000

        self.speedup = self.cold_time_ms / max(self.warm_time_ms, 0.001)
        return super().__call__(**kwargs)


# ── Benchmark: result generation and save ──────────────────────────────────
class ResultGenerationPerformance(bch.ParametrizedSweep):
    """Measure time to generate plots and save HTML reports."""

    plot_time_ms = bch.ResultVar(
        units="ms", doc="Time to generate plots", direction=bch.OptDir.minimize
    )
    save_time_ms = bch.ResultVar(
        units="ms", doc="Time to save HTML report", direction=bch.OptDir.minimize
    )

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        cfg = _fresh_cfg()
        cfg.auto_plot = True
        bench = bch.Bench("_plot_perf", _SineWorker(), run_cfg=cfg)

        t0 = time.perf_counter()
        bench.plot_sweep(input_vars=["x"], result_vars=["out"])
        self.plot_time_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        with tempfile.TemporaryDirectory() as td:
            bench.report.save(directory=td, in_html_folder=False)
        self.save_time_ms = (time.perf_counter() - t0) * 1000

        return super().__call__(**kwargs)


# ── Example entry points ───────────────────────────────────────────────────
def example_sweep_performance(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Benchmark parameter sweep execution time."""
    bench = SweepPerformance().to_bench(_perf_run_cfg(run_cfg))
    bench.plot_sweep(result_vars=["sweep_1d_time_ms", "sweep_2d_time_ms"])
    return bench


def example_cache_performance(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Benchmark cache hit vs miss performance."""
    bench = CachePerformance().to_bench(_perf_run_cfg(run_cfg))
    bench.plot_sweep(result_vars=["cold_time_ms", "warm_time_ms", "speedup"])
    return bench


def example_result_generation_performance(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Benchmark result visualization and save performance."""
    bench = ResultGenerationPerformance().to_bench(_perf_run_cfg(run_cfg))
    bench.plot_sweep(result_vars=["plot_time_ms", "save_time_ms"])
    return bench


def example_performance(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Run all performance benchmarks and combine into a single report."""
    bench = example_sweep_performance(run_cfg)
    example_cache_performance(run_cfg)
    example_result_generation_performance(run_cfg)
    return bench


if __name__ == "__main__":
    run_cfg = bch.BenchRunCfg()
    run_cfg.cache_samples = False
    run_cfg.only_hash_tag = False
    bench_runner = bch.BenchRunner("performance_benchmarks", run_cfg=run_cfg)
    bench_runner.add(example_sweep_performance)
    bench_runner.add(example_cache_performance)
    bench_runner.add(example_result_generation_performance)
    bench_runner.run(level=2, show=False, save=True, grouped=True)
