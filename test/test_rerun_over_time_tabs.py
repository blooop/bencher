"""A ResultRerun's over_time history follows ``pane_layout``.

Under ``grid`` the history is a row of labelled viewers. That reads for two runs and
not for ten: every viewer is live at once, so the page grows sideways with each run.
Under ``tabs`` each run is a tab named by its time label, and the latest run is the
one on show.

The declared container reads the stored path itself, so the sweep writes plain text
files rather than real recordings: what is under test is the layout around each run,
not what the rerun viewer does with an .rrd.
"""

import unittest
from datetime import datetime, timedelta

import panel as pn

import bencher as bn

SNAPSHOTS = 3


def file_contents(path: str) -> pn.pane.Markdown:
    """A declared container that renders the file rather than the rerun viewer."""
    with open(path, encoding="utf-8") as handle:
        return pn.pane.Markdown(f"contents: {handle.read()}")


class RerunSweep(bn.ParametrizedSweep):
    """A ResultRerun that renders its stored file, swept over one input."""

    sides = bn.IntSweep(default=3, bounds=[3, 4], samples=2)
    recording = bn.ResultRerun(width=400, height=400, container=file_contents)

    offset = 0

    def benchmark(self):
        filename = bn.gen_path("recording", suffix=".txt")
        with open(filename, "w", encoding="utf-8") as handle:
            handle.write(f"sides {self.sides} run {self.offset}")
        self.recording = filename


def run_over_time(name: str, pane_layout: bn.PaneLayout, input_vars: list[str]):
    """Run the sweep once per time point, so over_time carries real history."""
    worker = RerunSweep()
    run_cfg = bn.BenchRunCfg(over_time=True, repeats=1, auto_plot=False, pane_layout=pane_layout)
    bench = worker.to_bench(run_cfg)
    base_time = datetime(2000, 1, 1)
    res = None
    for i in range(SNAPSHOTS):
        worker.offset = i
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            name,
            input_vars=input_vars,
            result_vars=["recording"],
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
        )
    return res


def report_view(res) -> pn.Column:
    """The report as published: ``to_auto_plots`` is what applies ``pane_layout``."""
    return pn.Column(*res.to_auto_plots())


def history_tabs(view) -> list[pn.Tabs]:
    """Every Tabs whose tabs each hold exactly one run's rendered recording.

    Exactly one, so the outer tab per swept value — which holds a whole history —
    is not mistaken for a history itself.
    """
    return [
        tabs
        for tabs in view.select(pn.Tabs)
        if len(tabs) and all(len(recordings(tab)) == 1 for tab in tabs)
    ]


def recordings(view) -> list[str]:
    return [
        p.object for p in view.select(pn.pane.Markdown) if str(p.object).startswith("contents: ")
    ]


def tab_contents(tabs: pn.Tabs) -> list[str]:
    return [recordings(tab)[0] for tab in tabs]


class TestRerunOverTimeTabs(unittest.TestCase):
    """Rerun history renders as tabs under a tabs layout, and as a row otherwise."""

    def test_tabs_layout_puts_each_run_in_its_own_tab(self):
        res = run_over_time("test_rerun_tabs_no_inputs", bn.PaneLayout.tabs, [])
        tabs = history_tabs(report_view(res))

        self.assertEqual(len(tabs), 1)
        self.assertEqual(
            tab_contents(tabs[0]), [f"contents: sides 3 run {i}" for i in range(SNAPSHOTS)]
        )

    def test_tabs_are_named_by_time_label_and_open_on_the_latest_run(self):
        res = run_over_time("test_rerun_tabs_labels", bn.PaneLayout.tabs, [])
        tabs = history_tabs(report_view(res))[0]

        self.assertEqual(len(set(tabs._names)), SNAPSHOTS)  # pylint: disable=protected-access
        self.assertTrue(all("2000-01-01" in name for name in tabs._names))  # pylint: disable=protected-access
        self.assertEqual(tabs.active, SNAPSHOTS - 1)

    def test_tabs_layout_gives_every_swept_value_its_own_history(self):
        res = run_over_time("test_rerun_tabs_one_input", bn.PaneLayout.tabs, ["sides"])
        tabs = history_tabs(report_view(res))

        contents = sorted(tab_contents(t)[0] for t in tabs)
        self.assertEqual(contents, ["contents: sides 3 run 0", "contents: sides 4 run 0"])
        self.assertTrue(all(len(t) == SNAPSHOTS for t in tabs))

    def test_grid_layout_keeps_the_row(self):
        res = run_over_time("test_rerun_tabs_grid", bn.PaneLayout.grid, [])
        view = report_view(res)

        self.assertEqual(history_tabs(view), [])
        self.assertEqual(len(recordings(view)), SNAPSHOTS)


if __name__ == "__main__":
    unittest.main()
