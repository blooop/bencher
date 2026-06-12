"""Shared helpers for result-type unit tests.

These small utilities were previously copy-pasted across several
``test_*_result.py`` modules; centralising them keeps the unwrap/inner-element
and run-config logic consistent in one place.
"""

from __future__ import annotations

import bencher as bn


def unwrap_hv(obj):
    """Unwrap a panel Row/HoloViews pane returned by filter() to the hv object inside."""
    while True:
        if hasattr(obj, "object"):
            obj = obj.object
        elif hasattr(obj, "objects"):
            assert len(obj.objects) > 0
            obj = obj.objects[0]
        else:
            return obj


def inner_element(overlay):
    """The plot methods return an hv.Overlay wrapping a single distribution element."""
    items = list(overlay)
    assert len(items) == 1
    return items[0]


def run_cfg_with(repeats: int) -> bn.BenchRunCfg:
    """A BenchRunCfg with caching and auto-plot disabled for the given repeat count."""
    return bn.BenchRunCfg(
        repeats=repeats, cache_results=False, cache_samples=False, auto_plot=False
    )


def run_named_sweep(bench_class, name, input_vars, result_vars, repeats=1):
    """Run a sweep on a freshly named ``Bench`` with caching and plot callbacks disabled.

    Shared by the bar and scatter result tests, which construct the bench by name.
    """
    bench = bn.Bench(name, bench_class(), run_cfg=run_cfg_with(repeats))
    return bench.plot_sweep(
        name, input_vars=input_vars, result_vars=result_vars, plot_callbacks=False
    )


def run_dist_sweep(worker_cls, input_vars, repeats, name_prefix):
    """Run a categorical ``value`` sweep via ``to_bench`` for distribution-style tests.

    Shared by the box-whisker, violin and scatter-jitter result tests, which each
    previously defined an identical ``_run_sweep`` differing only by name prefix.
    """
    run_cfg = run_cfg_with(repeats)
    bench = worker_cls().to_bench(run_cfg)
    return bench.plot_sweep(
        f"{name_prefix}_{worker_cls.__name__}_{repeats}",
        input_vars=input_vars,
        result_vars=["value"],
        run_cfg=run_cfg,
        plot_callbacks=False,
    )
