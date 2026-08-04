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


def _run_over_time(worker, result_vars, runs=_RUNS):
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
            input_vars=[],
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
    # wrong reason.
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


def test_scalar_keeps_its_over_time_series(mixed):
    # Rendering panes per event must not cost the scalars their series — that
    # series is what regression detection reads.
    assert mixed.to_dataset()["score"].sizes["over_time"] == _RUNS
