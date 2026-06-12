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
