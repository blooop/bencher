"""Every pane type gets a correct over_time layout, not just the ones named.

``_to_panes_da`` gives ``ResultRerun`` a grid and ``ResultVideo``/``ResultImage`` a
slider. Before ``_pane_over_time_samples`` became the default, anything else fell
through to the per-sample renderer with the ``over_time`` dimension still on the
dataset, and asking that for one value raised ``ValueError: can only convert an
array of size 1 to a Python scalar``.

The blast radius is what makes it worth a test: ``PaneResult.to_panes`` renders
every pane-typed result var in one loop, and ``BenchResult.to_auto`` catches per
*plugin*, not per variable. So one un-dispatched string deleted the images, videos,
rerun viewers and dataset scatters of the whole report along with itself — and,
before the render-failure surfacing landed, did it with no warning and a zero exit
code.
"""

import warnings
from datetime import datetime, timedelta

import holoviews as hv
import pandas as pd
import panel as pn
import pytest

import bencher as bn
from bencher.results.pane_result import PaneResult
from bencher.results.render_failure import RenderFailedWarning

_RUNS = 2
_BASE_TIME = datetime(2000, 1, 1)


def _frame(run: int) -> pd.DataFrame:
    return pd.DataFrame({"idx": [0, 1], "value": [float(run), float(run) + 1.0]})


def _table_container(df: pd.DataFrame) -> pn.pane.Markdown:
    """Stand-in for a real plot: takes the payload alone, returns something viewable."""
    return pn.pane.Markdown(f"rows={len(df)} sum={df['value'].sum():g}")


class StringAndDataSetSweep(bn.ParametrizedSweep):
    """A string beside a dataset, which is the shape that lost both panes."""

    note = bn.ResultString(doc="text the benchmark produced")
    table = bn.ResultDataSet(container=_table_container, doc="payload")
    score = bn.ResultFloat(units="pt", doc="a plain scalar, which keeps its series")

    run_id = 0

    def benchmark(self):
        self.note = f"run-{self.run_id}"
        self.table = bn.ResultDataSet(_frame(self.run_id))
        self.score = float(self.run_id)


class StringOnlySweep(bn.ParametrizedSweep):
    """A string with no pane-typed sibling, so nothing can mask its own failure."""

    note = bn.ResultString(doc="text the benchmark produced")

    run_id = 0

    def benchmark(self):
        self.note = f"run-{self.run_id}"


class SweptScalarSweep(bn.ParametrizedSweep):
    """The same history with an ordinary swept input, for the numeric half.

    Separate from the sweeps above rather than folded into them, because the two
    shapes exercise different things and swapping one for the other silently costs
    coverage.  With no input vars a pane type at over_time > 1 *raises*, which is
    what the tests above pin.  Add an input var and the very same defect stops
    raising: ``phase`` survives the pane recursion as a scalar coordinate, so
    ``zero_dim_da_to_val`` takes its ``expand_dims`` branch instead of ``.item()``
    and returns the whole two-element array, which renders as one ``Str(ndarray)``
    pane holding both time points and labelled with neither.  Silent-wrong, not
    loud-wrong.  Only the content assertions catch it in that shape.
    """

    phase = bn.IntSweep(default=0, bounds=[0, 1], doc="one ordinary swept input")

    score = bn.ResultFloat(units="pt", doc="a plain scalar, which keeps its series")

    run_id = 0

    def benchmark(self):
        self.score = float(self.run_id + self.phase)


def _run_over_time(worker, result_vars, runs=_RUNS, input_vars=()):
    """Sample *worker* once per run against one history, as a CI report does."""
    run_cfg = bn.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.repeats = 1
    run_cfg.auto_plot = False
    bench = worker.to_bench(run_cfg)
    result = None
    for run in range(runs):
        worker.run_id = run
        run_cfg.clear_cache = True
        run_cfg.clear_history = run == 0
        result = bench.plot_sweep(
            "over_time_panes",
            input_vars=list(input_vars),
            result_vars=result_vars,
            run_cfg=run_cfg,
            time_src=_BASE_TIME + timedelta(seconds=run),
        )
    return result


@pytest.fixture(name="mixed")
def _mixed(tmp_path, monkeypatch):
    """A two-run history of a string beside a dataset, from a scratch cache dir."""
    monkeypatch.chdir(tmp_path)
    return _run_over_time(StringAndDataSetSweep(), ["note", "table", "score"])


@pytest.fixture(name="swept")
def _swept(tmp_path, monkeypatch):
    """A two-run history of a scalar over a swept input — see ``SweptScalarSweep``."""
    monkeypatch.chdir(tmp_path)
    return _run_over_time(SweptScalarSweep(), ["score"], input_vars=["phase"])


def _markdown_text(viewable) -> list[str]:
    return [str(pane.object) for pane in viewable.select(pn.pane.Markdown)]


def test_string_over_time_renders_instead_of_raising(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = _run_over_time(StringOnlySweep(), ["note"])
    assert result.to_dataset().sizes["over_time"] == _RUNS
    # The regression: this call raised, so there is no weaker assertion to make.
    panes = PaneResult.to_panes(result)
    assert panes is not None


def test_one_pane_per_time_point_labelled_with_its_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = _run_over_time(StringOnlySweep(), ["note"])
    text = _markdown_text(PaneResult.to_panes(result))
    # Each event contributes its own value, so a stale or repeated pane shows up
    # here rather than as a plausible-looking report.
    for run in range(_RUNS):
        assert any(f"run-{run}" in line for line in text), text


def test_string_does_not_delete_its_sibling_panes(mixed):
    # The actual damage: one raising var dropped every other pane-typed var with
    # it, because to_auto catches per plugin rather than per variable.
    text = _markdown_text(PaneResult.to_panes(mixed))
    assert any("rows=2" in line for line in text), text
    for run in range(_RUNS):
        assert any(f"run-{run}" in line for line in text), text


def test_auto_report_reports_no_pane_render_failure(mixed):
    # to_auto turns a plugin exception into a visible pane and a warning rather
    # than a failure, so a report can be incomplete while the job stays green.
    # Assert neither mark, since neither would fail this test on its own.
    #
    # Scoped to the panes plugin rather than to any failure: a sweep with no input
    # vars also trips hvplot's numeric path ("no valid index for a 0-dimensional
    # object"), which is a separate defect and would make this test fail for the
    # wrong reason.  Widening the scope by giving the fixture an input var is not
    # the trade it looks like — see ``SweptScalarSweep``: with an input var the
    # pane defect stops raising at all, so this assertion would gain a plugin and
    # lose its subject.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        auto = mixed.to_auto()
    failures = [
        str(w.message)
        for w in caught
        if issubclass(w.category, RenderFailedWarning) and "panes" in str(w.message)
    ]
    assert not failures, failures
    assert not [t for t in _markdown_text(auto) if "panes" in t and "failed to render" in t]


def _holomaps(viewable) -> list:
    """Every HoloMap in a rendered panel object."""
    return [
        pane.object
        for pane in viewable.select(pn.pane.HoloViews)
        if isinstance(pane.object, hv.HoloMap)
    ]


def test_scalar_keeps_its_over_time_series(swept):
    # Rendering panes per event must not cost the scalars their series — that
    # series is what regression detection reads.
    #
    # Asserted on the *rendered* curve, not on to_dataset(): the dataset is built
    # before any dispatch decision, so a version of this that read to_dataset()
    # alone would pass no matter what _to_panes_da did with the dimension, and so
    # could not guard the half of the rule it names.
    score = next(rv for rv in swept.get_results_var_list() if rv.name == "score")
    curve = swept.to_curve(result_var=score)
    assert curve is not None

    hmaps = _holomaps(curve)
    assert hmaps, f"a numeric var over_time must render an hv.HoloMap: {curve!r}"
    # over_time reaches the plot as a HoloMap *key dimension* with one key per
    # run: that is the slider hvplot builds from the whole dimension, and it is
    # exactly what pre-selecting a time point in _to_panes_da would flatten away.
    hmap = hmaps[0]
    assert "over_time" in [d.name for d in hmap.kdims], hmap.kdims
    assert len(hmap.keys()) == _RUNS, hmap.keys()
