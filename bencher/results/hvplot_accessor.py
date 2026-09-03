"""Deferred access to hvplot's ``.hvplot`` accessor.

``hvplot.pandas`` and ``hvplot.xarray`` do nothing but attach the ``.hvplot``
accessor to pandas/xarray objects, yet importing either costs ~2s -- nearly all of
it inside ``colorcet``, which builds ~200 matplotlib colormaps in its module body.
Nothing needs the accessor until a plot is actually drawn, so bencher reaches it
through ``hvplot_of()`` instead of importing hvplot up front. That keeps ~2s off
``import bencher``.

Returning the accessor, rather than offering a separate "register it first" call,
is what ties the import to the expression that needs it. A plotting method cannot
reach the accessor without triggering the import, so no new plot type can forget
it -- and a method that returns before it plots, or that builds its plot with
``hv.`` instead, never pays for it. An entry-point guard got both of those wrong.

Both hvplot patch functions guard against re-patching, so repeat calls are just a
``sys.modules`` hit.
"""

from __future__ import annotations

from typing import Any


def hvplot_of(obj: Any) -> Any:
    """Return *obj*'s ``.hvplot`` accessor, importing hvplot on first use.

    Typed loosely because the accessor differs by argument: pandas objects get
    ``hvPlotTabular``, xarray objects ``hvPlot``, and neither is re-exported.
    """
    # pylint: disable=import-outside-toplevel,unused-import
    import hvplot.pandas
    import hvplot.xarray  # noqa: F401

    return obj.hvplot
