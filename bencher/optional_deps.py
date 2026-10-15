"""The heavy packages bencher plots, serves and optimises with, and what to do without them.

``pip install holobench`` installs everything. A light install
(``pip install --no-deps holobench`` plus the light dependencies by hand) has only what
a sweep, its claims, ``bencher compare`` and ``bencher ab`` need, and leaves out the
plotting stack (HoloViews, Panel, Bokeh, hvplot, plotly), Optuna, moviepy and
scikit-learn.

So the modules that use one of those import it from here, not directly::

    from bencher.optional_deps import hv, pn

On a full install each name *is* the real module, imported here at the point
``import bencher`` always imported it -- nothing changes. On a light install it is a
stand-in, and the first use of it raises :class:`FullInstallRequiredError`, which
says to ``pip install holobench``, instead of failing ``import bencher`` with a
``ModuleNotFoundError`` from deep inside a plotting module.

A heavy import inside a function (moviepy, hvplot, ``optuna.visualization``,
``bokeh.models``) keeps its ordinary, typed ``import`` statement and goes under
:func:`full_install_required`, which rewrites the same failure the same way.
"""

from __future__ import annotations

import importlib
from contextlib import contextmanager
from types import ModuleType
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from collections.abc import Iterator

# Top-level names of every package a full install has and a light install does not.
# scipy and tornado are not declared by holobench, but come with what it declares
# (scikit-learn, panel), and bencher uses them only on paths that need the full install.
HEAVY_PACKAGES = frozenset(
    {
        "bokeh",
        "holoviews",
        "hvplot",
        "moviepy",
        "optuna",
        "panel",
        "plotly",
        "scipy",
        "sklearn",
        "tornado",
    }
)


class FullInstallRequiredError(ModuleNotFoundError):
    """A feature needs a package that only the full ``holobench`` install has.

    A ``ModuleNotFoundError`` (so an ``ImportError``), so code that already guards an
    optional feature with ``except ImportError`` keeps working on a light install.
    """


def _message(package: str) -> str:
    return (
        f"this bencher feature needs '{package}', which is not installed. "
        "A light install leaves out the plotting, report-server, optimisation and video "
        "packages; install the full package with `pip install holobench`."
    )


def _is_heavy(exc: ModuleNotFoundError) -> bool:
    return (exc.name or "").partition(".")[0] in HEAVY_PACKAGES


@contextmanager
def full_install_required() -> Iterator[None]:
    """Turn a missing heavy package, imported in the block, into a message that says how to get it."""
    try:
        yield
    except FullInstallRequiredError:
        raise
    except ModuleNotFoundError as exc:
        if not _is_heavy(exc):
            raise
        raise FullInstallRequiredError(_message(exc.name or ""), name=exc.name) from exc


class _MissingModule(ModuleType):
    """Stands in for a heavy package a light install does not have.

    Any public attribute read raises, because reading one (``hv.Curve``,
    ``pn.Column``) is how a module uses the package. Dunder reads raise
    ``AttributeError`` as usual, so ``hasattr``, ``getattr(x, n, default)``, pickle and
    introspection still probe the stand-in safely.
    """

    def __init__(self, name: str, cause: ModuleNotFoundError) -> None:
        super().__init__(name)
        self._cause = cause

    def __getattr__(self, name: str) -> NoReturn:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        raise FullInstallRequiredError(_message(self.__name__), name=self.__name__) from (
            self._cause
        )


def _import_or_stand_in(name: str) -> ModuleType:
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        # Only the package itself being absent is a light install; an installed package
        # missing one of its own dependencies is a broken install, and says which one.
        if exc.name != name.partition(".")[0]:
            raise
        return _MissingModule(name, exc)


if TYPE_CHECKING:
    import holoviews as hv
    import optuna
    import panel as pn
    import plotly.graph_objs as go
else:
    hv = _import_or_stand_in("holoviews")
    pn = _import_or_stand_in("panel")
    go = _import_or_stand_in("plotly.graph_objs")
    optuna = _import_or_stand_in("optuna")

#: True when HoloViews and Panel are installed, so bencher can build and show reports.
PLOTTING_INSTALLED = not isinstance(hv, _MissingModule) and not isinstance(pn, _MissingModule)
