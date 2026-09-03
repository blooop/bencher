"""Deferred registration of hvplot's ``.hvplot`` accessor.

``hvplot.pandas`` and ``hvplot.xarray`` do nothing but attach the ``.hvplot``
accessor to pandas/xarray objects, yet importing either costs ~2s -- nearly all
of it inside ``colorcet``, which builds ~200 matplotlib colormaps in its module
body. Nothing needs the accessor until a plot is actually built, so the plotting
methods that use it call ``ensure_hvplot()`` first instead of the package
importing hvplot up front. That keeps ~2s off ``import bencher``.

Both hvplot patch functions guard against re-patching, so repeat calls are just
a ``sys.modules`` hit.
"""

from __future__ import annotations


def ensure_hvplot() -> None:
    """Register the ``.hvplot`` accessor on pandas and xarray objects."""
    # pylint: disable=import-outside-toplevel,unused-import
    import hvplot.pandas
    import hvplot.xarray  # noqa: F401
