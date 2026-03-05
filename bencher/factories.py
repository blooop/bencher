"""Factory functions for creating Bench and BenchRunner instances.

This module breaks the circular dependency between ParametrizedSweep and
Bench/BenchRunner by providing standalone factory functions that can be
imported without triggering circular imports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bencher.bencher import Bench
    from bencher.bench_runner import BenchRunner
    from bencher.bench_cfg import BenchRunCfg
    from bencher.bench_report import BenchReport
    from bencher.variables.parametrised_sweep import ParametrizedSweep


def create_bench(
    sweep: ParametrizedSweep,
    run_cfg: BenchRunCfg | None = None,
    report: BenchReport | None = None,
    name: str | None = None,
) -> Bench:
    """Create a Bench instance from a ParametrizedSweep.

    Args:
        sweep: The ParametrizedSweep instance to benchmark.
        run_cfg: Optional benchmark run configuration.
        report: Optional existing report to append results to.
        name: Optional name for the benchmark. If None, derived from sweep's class name.

    Returns:
        A configured Bench instance.
    """
    from bencher.bencher import Bench

    if name is None:
        # Use the class name directly instead of trying to strip param's suffix.
        # This handles cases where the param counter exceeds 5 digits.
        name = sweep.__class__.__name__

    return Bench(name, sweep, run_cfg=run_cfg, report=report)


def create_bench_runner(
    sweep: ParametrizedSweep,
    run_cfg: BenchRunCfg | None = None,
    name: str | None = None,
) -> BenchRunner:
    """Create a BenchRunner instance from a ParametrizedSweep.

    Enables fluent chaining like:
        MyConfig().to_bench_runner().add(func).run(level=2, max_level=4)

    Args:
        sweep: The ParametrizedSweep instance to use as the benchmark class.
        run_cfg: Optional benchmark run configuration. Created if not provided.
        name: Optional name for the runner. If None, auto-generated.

    Returns:
        A configured BenchRunner instance.
    """
    from bencher.bench_runner import BenchRunner
    from bencher.bench_cfg import BenchRunCfg

    if run_cfg is None:
        run_cfg = BenchRunCfg()

    return BenchRunner(name=name, bench_class=sweep, run_cfg=run_cfg)
