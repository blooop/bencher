"""Contract: over_time is reduced before a per-sample renderer ever sees it.

The defect class this exists to catch, stated once: ``_to_panes_da`` decides what
to do with a result var when the dataset carries more than one ``over_time`` point,
and it decided that by naming types. Naming types means a type nobody named falls
through to ``plot_callback`` with the ``over_time`` dimension still attached — and
``plot_callback`` is a *per-sample* renderer, so it asks a two-element array for one
value and raises ``ValueError: can only convert an array of size 1 to a Python
scalar``. ``ResultString`` fell through that way for as long as the branch existed.

Two properties make it expensive rather than merely wrong, and both argue for a
contract test over one more per-type case:

* ``PaneResult.to_panes`` renders every pane-typed var in a single loop and
  ``BenchResult.to_auto`` catches per *plugin*, so one un-dispatched type deletes
  every image, video, rerun viewer and dataset scatter in the report with it.
* Nothing fails. The report is written, incomplete, and the process exits 0.

So this module asserts the *invariant* over every member of ``PANEL_TYPES``, rather
than testing the types that happen to exist today. A pane type added later is
covered the moment it joins the tuple; if it needs a bespoke layout it must add one,
and if it does not it inherits the per-time-point default. Either way the invariant
below is what says so.

The mirror-image assertion is here too, because it is the mistake this fix nearly
made: numeric callbacks (line, bar, heatmap) *require* the whole dimension, since
they build their own slider via hvplot groupby / ``hv.HoloMap``. Pre-selecting a
time point for them would flatten the series they exist to draw. So the rule is not
"always reduce" — it is "reduce for pane types, never for the rest", and both halves
need pinning or the next fix trades one silent-wrong for the other.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import panel as pn
import pytest
import xarray as xr

from bencher.results.bench_result_base import BenchResultBase
from bencher.variables.results import (
    PANEL_TYPES,
    ResultFloat,
    ResultImage,
    ResultRerun,
    ResultString,
    ResultVideo,
)

_TIME_POINTS = 2

# Types that own an over_time layout of their own and resolve values themselves
# rather than through plot_callback, so a spy sees no calls at all from them. They
# satisfy the invariant trivially; listing them keeps "never called" from reading as
# a test that silently checked nothing.
_SELF_RESOLVING = (ResultRerun, ResultVideo, ResultImage)


class _Spy(BenchResultBase):
    """A result base that records every dataset handed to the per-sample renderer.

    Subclassed rather than mocked so the real ``_to_panes_da`` runs: the dispatch
    under test is exactly the code being bypassed if this were a fake.
    """

    # pylint: disable=super-init-not-called
    def __init__(self, over_time: bool = True) -> None:
        self.bench_cfg = type("_Cfg", (), {"over_time": over_time})()
        self.object_index = []
        self.seen: list[xr.Dataset] = []

    def callback(self, dataset: xr.Dataset, result_var, **_kwargs):
        self.seen.append(dataset)
        return pn.pane.Markdown(f"{result_var.name}")


def _over_time_dataset(var_name: str, values) -> xr.Dataset:
    """A dataset holding *var_name* at ``_TIME_POINTS`` time points and nothing else."""
    times = pd.to_datetime(["2000-01-01T00:00:00", "2000-01-01T00:00:01"])
    return xr.Dataset(
        {var_name: (("over_time",), np.asarray(values, dtype=object))},
        coords={"over_time": times},
    )


def _render(result_var, values) -> tuple[_Spy, object]:
    spy = _Spy()
    dataset = _over_time_dataset(result_var.name, values)
    rendered = spy._to_panes_da(  # pylint: disable=protected-access
        dataset,
        plot_callback=spy.callback,
        target_dimension=0,
        result_var=result_var,
    )
    return spy, rendered


@pytest.mark.parametrize("result_type", PANEL_TYPES, ids=lambda t: t.__name__)
def test_pane_types_never_see_an_unreduced_over_time(result_type):
    """No pane type may reach the per-sample renderer with over_time unreduced."""
    result_var = result_type()
    result_var.name = "v"
    # Strings for every type: the spy replaces the renderer that would interpret
    # them, so what matters is the dataset's shape, not what the cells mean.
    spy, rendered = _render(result_var, ["a", "b"])

    if issubclass(result_type, _SELF_RESOLVING):
        assert not spy.seen, (
            f"{result_type.__name__} resolves its own values, so plot_callback "
            "should not be called; it now is, and this test no longer checks it"
        )
        # "never called the spy" is also true of a branch that returned nothing,
        # so pin that these types reached a layout rather than falling off the
        # dispatch — otherwise this parametrisation checks nothing at all.
        assert rendered is not None, (
            f"{result_type.__name__} took no over_time layout: it neither called "
            "the per-sample renderer nor produced a viewable of its own"
        )
        return

    assert spy.seen, (
        f"{result_type.__name__} rendered nothing at all — it neither reduced "
        "over_time nor delegated to a layout of its own"
    )
    unreduced = [ds.sizes.get("over_time") for ds in spy.seen if ds.sizes.get("over_time", 1) > 1]
    assert not unreduced, (
        f"{result_type.__name__} reached the per-sample renderer with over_time "
        f"still at {unreduced} — that call raises 'can only convert an array of "
        "size 1 to a Python scalar', and the failure takes every other pane in the "
        "report with it"
    )


@pytest.mark.parametrize("result_type", PANEL_TYPES, ids=lambda t: t.__name__)
def test_pane_types_render_every_time_point(result_type):
    """Each retained event gets its own pane, so history is not silently dropped."""
    if issubclass(result_type, _SELF_RESOLVING):
        pytest.skip(f"{result_type.__name__} has a layout of its own with its own test")
    result_var = result_type()
    result_var.name = "v"
    spy, _ = _render(result_var, ["a", "b"])
    assert len(spy.seen) == _TIME_POINTS, (
        f"{result_type.__name__} rendered {len(spy.seen)} of {_TIME_POINTS} time "
        "points; a report that drops history silently is the failure mode the "
        "per-event layout replaced"
    )


def test_numeric_types_keep_the_whole_over_time_dimension():
    """The other half of the rule: numeric callbacks build their own slider.

    A fix that reduced over_time for everything would pass every assertion above
    and quietly flatten every line and bar plot in every over_time report.
    """
    result_var = ResultFloat()
    result_var.name = "v"
    spy = _Spy()
    dataset = xr.Dataset(
        {"v": (("over_time",), np.asarray([1.0, 2.0]))},
        coords={"over_time": pd.to_datetime(["2000-01-01", "2000-01-02"])},
    )
    spy._to_panes_da(  # pylint: disable=protected-access
        dataset,
        plot_callback=spy.callback,
        target_dimension=0,
        result_var=result_var,
    )
    assert [ds.sizes.get("over_time") for ds in spy.seen] == [_TIME_POINTS], (
        "a numeric result var must be handed the whole over_time dimension; "
        "hvplot groupby / hv.HoloMap is what turns it into a slider"
    )


def test_single_time_point_is_unchanged_for_pane_types():
    """One event is not history, so it takes the plain single-sample path.

    Pins the boundary the dispatch keys on. Without this, a change that treated
    ``over_time`` as present whenever the coordinate exists would wrap every
    ordinary one-run report in a one-cell per-event grid and no other test here
    would notice.
    """
    result_var = ResultString()
    result_var.name = "v"
    spy = _Spy()
    dataset = xr.Dataset(
        {"v": (("over_time",), np.asarray(["a"], dtype=object))},
        coords={"over_time": pd.to_datetime(["2000-01-01"])},
    )
    spy._to_panes_da(  # pylint: disable=protected-access
        dataset,
        plot_callback=spy.callback,
        target_dimension=0,
        result_var=result_var,
    )
    # One call, and over_time is gone as a *dimension* — the pane recursion sliced
    # it away, which is what leaves a single value for the renderer. It survives as
    # a scalar coordinate, so assert on dims rather than on the coord's presence.
    assert len(spy.seen) == 1
    assert "over_time" not in spy.seen[0].sizes
