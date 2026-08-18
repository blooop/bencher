"""A declared container on a ResultRerun has to survive over_time.

With history off, a rerun result renders through ``ds_to_container`` and a declared
container applies. With history on and more than one time point, rendering is routed
to ``_pane_over_time_grid`` instead — a separate path that used to hardcode the rerun
viewer, so the same benchmark rendered its declared container on the first run and the
rerun viewer on every run after. These tests pin both paths to the same renderer.

The declared container reads the stored path itself, so the sweep can write plain text
files rather than real recordings: what is under test is which renderer is called, not
what the rerun viewer does with an .rrd.
"""

import unittest
from datetime import datetime, timedelta

import panel as pn

import bencher as bn

SIDES = [3, 4]
SNAPSHOTS = 2


def file_contents(path: str) -> pn.pane.Markdown:
    """A declared container that renders the file rather than the rerun viewer."""
    with open(path, encoding="utf-8") as handle:
        return pn.pane.Markdown(f"contents: {handle.read()}")


class RerunSweep(bn.ParametrizedSweep):
    """A ResultRerun declaring how it renders, in place of the rerun viewer."""

    sides = bn.IntSweep(default=3, bounds=[3, 4], samples=2)
    recording = bn.ResultRerun(width=400, height=400, container=file_contents)

    offset = 0

    def benchmark(self):
        filename = bn.gen_path("recording", suffix=".txt")
        with open(filename, "w", encoding="utf-8") as handle:
            handle.write(f"sides {self.sides} run {self.offset}")
        self.recording = filename


def run_over_time(worker: bn.ParametrizedSweep, name: str, snapshots: int):
    """Run the sweep once per time point, so over_time carries real history."""
    run_cfg = bn.BenchRunCfg(
        execution=bn.ExecutionCfg(repeats=1),
        visualization=bn.VisualizationCfg(auto_plot=False),
        time=bn.TimeCfg(over_time=True),
    )
    bench = worker.to_bench(run_cfg)
    base_time = datetime(2000, 1, 1)
    res = None
    for i in range(snapshots):
        worker.offset = i
        run_cfg.cache.clear = True
        run_cfg.time.clear_history = i == 0
        res = bench.plot_sweep(
            name,
            input_vars=["sides"],
            result_vars=["recording"],
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
        )
    return res


def markdown_text(view) -> list[str]:
    return [p.object for p in view.select(pn.pane.Markdown)]


class TestRerunDeclaredContainerOverTime(unittest.TestCase):
    """The grid path must use the declared container, at every time point."""

    def test_declared_container_renders_every_time_point(self):
        res = run_over_time(RerunSweep(), "test_rerun_container_history", SNAPSHOTS)
        view = res.to_auto(plot_list=["panes"])
        rendered = [t for t in markdown_text(view) if t.startswith("contents: ")]

        # One pane per (side, time point): the grid renders the whole history,
        # not just the run being reported.
        self.assertEqual(len(rendered), len(SIDES) * SNAPSHOTS)
        for run in range(SNAPSHOTS):
            self.assertIn(f"contents: sides 3 run {run}", rendered)
            self.assertIn(f"contents: sides 4 run {run}", rendered)

    def test_single_run_and_history_agree(self):
        """The whole point: one time point and several render through one renderer."""
        single = run_over_time(RerunSweep(), "test_rerun_container_single", 1)
        history = run_over_time(RerunSweep(), "test_rerun_container_multi", SNAPSHOTS)

        single_text = list(markdown_text(single.to_auto(plot_list=["panes"])))
        history_text = list(markdown_text(history.to_auto(plot_list=["panes"])))

        self.assertTrue(any(t.startswith("contents: ") for t in single_text))
        self.assertTrue(any(t.startswith("contents: ") for t in history_text))


if __name__ == "__main__":
    unittest.main()
