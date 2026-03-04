"""Convenience entry point for running benchmarks."""

from __future__ import annotations

from typing import Callable, List, TYPE_CHECKING

from bencher.bench_cfg import BenchRunCfg, BenchCfg
from bencher.variables.parametrised_sweep import ParametrizedSweep

if TYPE_CHECKING:
    from bencher.bencher import Bench

# Keep references to BenchRunners with active servers so that __del__ doesn't
# kill the panel servers while the process is still running.
_active_runners: list = []


def run(
    target: Callable | type | ParametrizedSweep,
    *,
    level: int = 2,
    repeats: int = 1,
    max_level: int | None = None,
    max_repeats: int | None = None,
    run_cfg: BenchRunCfg | None = None,
    show: bool = True,
    save: bool = False,
    publish: bool = False,
    grouped: bool = False,
    cache_results: bool = True,
) -> List[BenchCfg]:
    """Run a benchmark target with sensible defaults.

    Handles three cases:
    1. Callable (e.g. ``bch.run(example_fn)``) — wraps in BenchRunner.
    2. ParametrizedSweep subclass (e.g. ``bch.run(SimpleFloat)``) — instantiates, calls
       ``to_bench()`` + ``plot_sweep()``.
    3. ParametrizedSweep instance (e.g. ``bch.run(SimpleFloat())``) — same as above
       without instantiation.

    Args:
        target: A benchmark function, ParametrizedSweep class, or ParametrizedSweep instance.
        level: Benchmark sampling resolution level. Defaults to 2.
        repeats: Number of repeats. Defaults to 1.
        max_level: Maximum level for progressive runs. Defaults to None (single level).
        max_repeats: Maximum repeats for progressive runs. Defaults to None (single repeat count).
        run_cfg: Optional explicit BenchRunCfg. Defaults to None.
        show: Show results in browser. Defaults to True.
        save: Save results to disk. Defaults to False.
        publish: Publish results. Defaults to False.
        grouped: Produce a single HTML page with all benchmarks. Defaults to False.
        cache_results: Use sample cache for previous results. Defaults to True.

    Returns:
        List[BenchCfg]: A list of benchmark configuration objects with results.
    """
    from bencher.bench_runner import BenchRunner

    # Case 2: ParametrizedSweep class (not instance) — instantiate it
    if isinstance(target, type) and issubclass(target, ParametrizedSweep):
        target = target()

    # Case 3: ParametrizedSweep instance — wrap in a bench function
    if isinstance(target, ParametrizedSweep):
        instance = target

        def _sweep_fn(run_cfg: BenchRunCfg | None = None) -> Bench:
            bench = instance.to_bench(run_cfg)
            bench.plot_sweep()
            return bench

        _sweep_fn.__name__ = f"bench_{instance.name}"
        target = _sweep_fn

    # Case 1: Callable — wrap in BenchRunner
    br = BenchRunner(target)
    results = br.run(
        level=level,
        repeats=repeats,
        max_level=max_level,
        max_repeats=max_repeats,
        run_cfg=run_cfg,
        show=show,
        save=save,
        publish=publish,
        grouped=grouped,
        cache_results=cache_results,
    )
    # Prevent garbage collection from killing the panel servers
    if show and br.servers:
        _active_runners.append(br)
    return results
