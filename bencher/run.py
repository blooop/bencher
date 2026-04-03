"""Convenience entry point for running benchmarks."""

from __future__ import annotations

import atexit
import signal
import sys
import time
from typing import Callable, TYPE_CHECKING

from bencher.bench_cfg import BenchRunCfg, BenchCfg
from bencher.variables.parametrised_sweep import ParametrizedSweep

if TYPE_CHECKING:
    from bencher.bencher import Bench

# Keep references to BenchRunners with active servers so that __del__ doesn't
# kill the panel servers while the process is still running.
# NOTE: only mutated from the main thread (signal handlers also run there in
# CPython), so no additional synchronisation is needed.
_active_runners: list = []
_sigterm_installed: bool = False


def _shutdown_all_servers() -> None:
    """Stop all active panel servers during interpreter exit."""
    while _active_runners:
        try:
            _active_runners.pop().shutdown()
        except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
            print(
                "bencher: error shutting down panel server, continuing cleanup",
                file=sys.stderr,
            )


atexit.register(_shutdown_all_servers)

_prev_sigterm_handler = None


def _sigterm_handler(signum, frame) -> None:
    """Handle SIGTERM so servers are stopped even when the process is killed."""
    _shutdown_all_servers()
    if _prev_sigterm_handler not in (signal.SIG_DFL, signal.SIG_IGN, None):
        _prev_sigterm_handler(signum, frame)  # type: ignore[misc]
    else:
        sys.exit(128 + signum)


def _install_sigterm_handler() -> None:
    """Install SIGTERM handler lazily, only when servers are actually running."""
    global _sigterm_installed, _prev_sigterm_handler  # noqa: PLW0603  # pylint: disable=global-statement
    if not _sigterm_installed:
        _sigterm_installed = True
        _prev_sigterm_handler = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, _sigterm_handler)


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
    cache_samples: bool | None = None,
    over_time: bool | None = None,
    optimise: int | bool = 0,
    **kwargs,
) -> list[BenchCfg]:
    """Run a benchmark target with sensible defaults.

    Handles three cases:
    1. Callable (e.g. ``bn.run(example_fn)``) — wraps in BenchRunner.
    2. ParametrizedSweep subclass (e.g. ``bn.run(SimpleFloat)``) — instantiates, calls
       ``to_bench()`` + ``plot_sweep()``.
    3. ParametrizedSweep instance (e.g. ``bn.run(SimpleFloat())``) — same as above
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
        cache_samples: Use sample cache for previous results. None (default) auto-enables
            for progressive runs. Pass False to disable even for progressive runs.
        over_time: Enable time-series benchmarking. None preserves run_cfg value.
        optimise: When > 0, appends optuna analysis plots (parameter importance,
            with/without repeats comparison, best parameters) from the sweep results
            to the report. Defaults to 0 (no optimisation analysis).

    Returns:
        list[BenchCfg]: A list of benchmark configuration objects with results.
    """
    from bencher.bench_runner import BenchRunner, _resolve_cache_samples

    cache_samples = _resolve_cache_samples(cache_samples, kwargs, stacklevel=1)

    # Case 2: ParametrizedSweep class (not instance) — instantiate it
    if isinstance(target, type) and issubclass(target, ParametrizedSweep):
        target = target()

    # Case 3: ParametrizedSweep instance — wrap in a bench function
    bench_to_close = None
    if isinstance(target, ParametrizedSweep):
        instance = target
        bench = instance.to_bench()

        def _sweep_fn(run_cfg: BenchRunCfg | None = None) -> "Bench":
            bench.run_cfg = run_cfg
            bench.report.clear()
            bench.plot_sweep()
            return bench

        _sweep_fn.__name__ = f"bench_{instance.name}"
        target = _sweep_fn
        bench_to_close = bench

    # Wrap target to add optimisation analysis from sweep results
    if optimise > 0:
        _original_target = target

        def _with_optimise(run_cfg: BenchRunCfg | None = None) -> "Bench":
            import logging as _log
            import panel as _pn

            bench = _original_target(run_cfg)
            result = bench.optimize(n_trials=optimise, plot=False)
            if result is None:
                bench.report.append(
                    _pn.pane.Markdown(
                        "**Optimisation skipped**: no result variables have an optimization "
                        "direction. Set `direction=OptDir.minimize` or `OptDir.maximize` "
                        "on your `ResultFloat`."
                    )
                )
            elif bench.results:
                for res in bench.results:
                    try:
                        bench.report.append_to_result(res, res.to_optuna_plots())
                    except Exception as e:  # pylint: disable=broad-except
                        _log.exception(e)
                        bench.report.append(
                            _pn.pane.Markdown(f"**Optuna plot generation failed**: {e}")
                        )
            return bench

        _with_optimise.__name__ = getattr(_original_target, "__name__", "optimised")
        target = _with_optimise

    # Case 1: Callable — wrap in BenchRunner
    br = BenchRunner(target)
    try:
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
            cache_samples=cache_samples,
            over_time=over_time,
        )
    finally:
        if bench_to_close is not None:
            bench_to_close.close()
    if show and br.servers:
        # Always register so atexit/SIGTERM can clean up as a safety net.
        _active_runners.append(br)
        _install_sigterm_handler()
        if sys.stdin.isatty():
            # Best-effort delay so Bokeh/Tornado startup logs finish before the
            # prompt is printed (not a guarantee on very slow machines).
            time.sleep(1)
            sys.stdout.flush()
            sys.stderr.flush()
            # Interactive terminal: block until the user is done viewing results.
            try:
                input("Press Enter to stop the server(s) and exit...")
            except (EOFError, KeyboardInterrupt):
                pass
            br.shutdown()
            # Remove so atexit/SIGTERM doesn't double-stop.
            try:
                _active_runners.remove(br)
            except ValueError:
                pass
    return results
