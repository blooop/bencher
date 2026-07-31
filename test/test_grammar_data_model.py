"""Integration tests for plan 22 (grammar phase 1): path-backed ResultDataSet cells.

Covers items 2-5 and 7 of the plan's test list:

- item 2: a sweep with a ResultDataSet var stores str (blob path) cells, appends
  nothing to dataset_list, and renders through the declared-container chain;
- item 3: collect -> save_result -> load_result -> render succeeds in-process;
- item 4: a hand-built legacy result (int cells + populated dataset_list) still
  renders; the same result without its dataset_list renders a labelled
  placeholder instead of raising;
- item 5: over_time with ResultDataSet across >=2 time points renders ALL points
  (the D4 payoff), including a mixed history of legacy int and path cells;
- item 7: the result_is_missing truth table per relevant type.

Item 1 lives in test/test_blob_store.py, item 6 in test/test_hash_persistent.py,
item 8 in test/test_resulthmap_deprecation.py.
"""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import panel as pn

import bencher as bn
from bencher.blob_store import load_blob
from bencher.results.dataset_result import DataSetResult
from bencher.variables.results import (
    ResultDataSet,
    ResultFloat,
    ResultPath,
    ResultReference,
    result_is_missing,
)

SCALES = [1.0, 2.0]
PLACEHOLDER_MARKER = "predates the path-backed format"


def expected_frame(scale: float) -> pd.DataFrame:
    return pd.DataFrame({"y": [scale, scale * 2.0]})


def tagged_frame(scale: float, run_id: int) -> pd.DataFrame:
    """A frame that says which run produced it, so a render traces to its run."""
    return pd.DataFrame({"y": [scale], "run": [run_id]})


def class_container(df: pd.DataFrame) -> pn.pane.Markdown:
    return pn.pane.Markdown(f"declared sum={df['y'].sum():g}")


def sample_container(df: pd.DataFrame) -> pn.pane.Markdown:
    return pn.pane.Markdown(f"per-sample sum={df['y'].sum():g}")


def renderer_container(df: pd.DataFrame) -> pn.pane.Markdown:
    return pn.pane.Markdown(f"explicit sum={df['y'].sum():g}")


def run_tagging_container(df: pd.DataFrame) -> pn.pane.Markdown:
    return pn.pane.Markdown(f"declared run={df['run'].iloc[0]} scale={df['y'].iloc[0]:g}")


class PathCellSweep(bn.ParametrizedSweep):
    """1-input sweep with a class-declared container on its ResultDataSet."""

    scale = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    table = bn.ResultDataSet(container=class_container, doc="small dataframe result")

    def benchmark(self):
        self.table = bn.ResultDataSet(expected_frame(self.scale))


class PerSampleSweep(PathCellSweep):
    """Worker overrides the declared container on the sample it stores."""

    def benchmark(self):
        self.table = bn.ResultDataSet(expected_frame(self.scale), container=sample_container)


class OverTimeSweep(bn.ParametrizedSweep):
    """A run-tagged tabular result, to be run repeatedly against one history."""

    scale = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    table = bn.ResultDataSet(container=run_tagging_container, doc="run-tagged dataframe")

    run_id = 0

    def benchmark(self):
        self.table = bn.ResultDataSet(tagged_frame(self.scale, self.run_id))


def run_sweep(worker: bn.ParametrizedSweep, name: str) -> bn.BenchResult:
    bench = bn.Bench(name, worker)
    return bench.plot_sweep(
        "grammar_sweep",
        input_vars=["scale"],
        result_vars=["table"],
        run_cfg=bn.BenchRunCfg(repeats=1, cache_results=False, cache_samples=False),
        auto_plot=False,
    )


OVER_TIME_RUNS = 2


def run_sweep_over_time(worker: bn.ParametrizedSweep, name: str) -> bn.BenchResult:
    """Run one sweep repeatedly against a single history, as a nightly rig does."""
    run_cfg = bn.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.repeats = 1
    run_cfg.auto_plot = False
    bench = bn.Bench(name, worker)
    base_time = datetime(2000, 1, 1)
    res = None
    for i in range(OVER_TIME_RUNS):
        worker.run_id = i
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "grammar_over_time_sweep",
            input_vars=["scale"],
            result_vars=["table"],
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
        )
    return res


def container_output(viewable: pn.viewable.Viewable) -> list[str]:
    """Container-produced Markdown in a rendered pane tree, in render order."""
    return [
        pane.object
        for pane in viewable.select(pn.pane.Markdown)
        if str(pane.object).startswith(("declared", "per-sample", "explicit"))
    ]


def placeholder_output(viewable: pn.viewable.Viewable) -> list[str]:
    return [
        pane.object
        for pane in viewable.select(pn.pane.Markdown)
        if PLACEHOLDER_MARKER in str(pane.object)
    ]


def make_legacy(res: bn.BenchResult, payloads: list[bn.ResultDataSet]) -> bn.BenchResult:
    """Rewrite a fresh result into the pre-plan-22 representation: int cells
    indexing a populated dataset_list."""
    res.dataset_list = payloads
    da = res.ds["table"]
    for i, scale in enumerate(SCALES):
        da.loc[{"scale": scale}] = i
    res._to_dataset_cache.clear()  # pylint: disable=protected-access
    return res


class TestPathBackedCells(unittest.TestCase):
    """Item 2: str cells, empty dataset_list, unchanged container chain."""

    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep(PathCellSweep(), "test_grammar_path_cells")

    def test_cells_are_blob_paths_that_round_trip(self):
        ds = self.res.to_dataset()
        for scale in SCALES:
            cell = ds["table"].sel(scale=scale).values.item()
            with self.subTest(scale=scale):
                self.assertIsInstance(cell, str)
                self.assertTrue(Path(cell).is_file())
                pd.testing.assert_frame_equal(load_blob(cell), expected_frame(scale))

    def test_nothing_appended_to_dataset_list(self):
        self.assertEqual(self.res.dataset_list, [])

    def test_class_declared_container_renders(self):
        rv = self.res.bench_cfg.result_vars[0]
        point = self.res.to_dataset().sel(scale=SCALES[0])
        pane = self.res.ds_to_container(point, rv, container=None)
        self.assertEqual(pane.object, "declared sum=3")

    def test_renderer_supplied_container_beats_declared(self):
        rv = self.res.bench_cfg.result_vars[0]
        point = self.res.to_dataset().sel(scale=SCALES[0])
        pane = self.res.ds_to_container(point, rv, container=renderer_container)
        self.assertEqual(pane.object, "explicit sum=3")

    def test_per_sample_container_beats_declared(self):
        res = run_sweep(PerSampleSweep(), "test_grammar_per_sample_container")
        self.assertEqual(res.dataset_list, [])
        rv = res.bench_cfg.result_vars[0]
        pane = res.ds_to_container(res.to_dataset().sel(scale=SCALES[0]), rv, container=None)
        self.assertEqual(pane.object, "per-sample sum=3")

    def test_dataset_view_renders_every_sample_through_the_chain(self):
        self.assertEqual(
            container_output(self.res.to(DataSetResult)),
            ["declared sum=3", "declared sum=6"],
        )


class TestSplitRenderRoundTrip(unittest.TestCase):
    """Item 3: collect -> save_result -> load_result -> render, in-process."""

    def test_save_load_render(self):
        res = run_sweep(PathCellSweep(), "test_grammar_split_render")
        with tempfile.TemporaryDirectory() as tmp:
            pkl = Path(tmp) / "result.pkl"
            bn.save_result(res, pkl)
            loaded = bn.load_result(pkl)

            # The loaded result renders from its path cells alone.
            self.assertEqual(loaded.dataset_list, [])
            self.assertEqual(
                container_output(loaded.to(DataSetResult)),
                ["declared sum=3", "declared sum=6"],
            )

            out = bn.render_report(loaded, Path(tmp) / "report")
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 0)


class TestLegacyIntCells(unittest.TestCase):
    """Item 4: pre-plan-22 results (int cells + dataset_list) keep rendering."""

    def test_legacy_result_renders_from_dataset_list(self):
        res = make_legacy(
            run_sweep(PathCellSweep(), "test_grammar_legacy_render"),
            [bn.ResultDataSet(expected_frame(scale)) for scale in SCALES],
        )
        rv = res.bench_cfg.result_vars[0]
        pane = res.ds_to_container(res.to_dataset().sel(scale=SCALES[1]), rv, container=None)
        self.assertEqual(pane.object, "declared sum=6")
        self.assertEqual(
            container_output(res.to(DataSetResult)), ["declared sum=3", "declared sum=6"]
        )

    def test_missing_dataset_list_renders_placeholder_not_raise(self):
        res = make_legacy(run_sweep(PathCellSweep(), "test_grammar_legacy_no_list"), [])
        rv = res.bench_cfg.result_vars[0]

        # Attribute deleted entirely (a result pickled without it).
        del res.dataset_list
        pane = res.ds_to_container(res.to_dataset().sel(scale=SCALES[0]), rv, container=None)
        self.assertIsInstance(pane, pn.pane.Markdown)
        self.assertIn(PLACEHOLDER_MARKER, pane.object)
        self.assertIn("table", pane.object)

        # List present but too short (another run's list): same placeholder.
        res.dataset_list = []
        view = res.to(DataSetResult)
        self.assertIsInstance(view, pn.viewable.Viewable)
        self.assertEqual(container_output(view), [])
        self.assertEqual(len(placeholder_output(view)), len(SCALES))


class TestOverTimeRendersAllPoints(unittest.TestCase):
    """Item 5: the D4 payoff — every time point renders, mixed histories included."""

    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep_over_time(OverTimeSweep(), "test_grammar_over_time")

    def test_history_accumulated(self):
        """Guard on the fixture: with a single event there is no payoff to check."""
        self.assertEqual(self.res.to_dataset().sizes["over_time"], OVER_TIME_RUNS)

    def test_all_time_points_render(self):
        self.assertEqual(
            container_output(self.res.to(DataSetResult)),
            [
                f"declared run={run} scale={scale:g}"
                for scale in SCALES
                for run in range(OVER_TIME_RUNS)
            ],
        )

    def _make_mixed(self, payloads: list[bn.ResultDataSet]) -> bn.BenchResult:
        """Rewrite the oldest cell of the first sample into a legacy int index."""
        res = run_sweep_over_time(OverTimeSweep(), "test_grammar_over_time_mixed")
        da = res.ds["table"]
        first_cell = {dim: 0 for dim in da.dims}
        da.values[tuple(first_cell[dim] for dim in da.dims)] = 0
        res.dataset_list = payloads
        res._to_dataset_cache.clear()  # pylint: disable=protected-access
        return res

    def test_mixed_history_renders_legacy_cell_from_dataset_list(self):
        res = self._make_mixed([bn.ResultDataSet(tagged_frame(SCALES[0], 99))])
        rendered = container_output(res.to(DataSetResult))
        self.assertEqual(len(rendered), len(SCALES) * OVER_TIME_RUNS)
        self.assertIn("declared run=99 scale=1", rendered)

    def test_mixed_history_without_dataset_list_degrades_to_placeholder(self):
        res = self._make_mixed([])
        view = res.to(DataSetResult)
        rendered = container_output(view)
        # The three path cells still render; the orphaned legacy cell degrades.
        self.assertEqual(len(rendered), len(SCALES) * OVER_TIME_RUNS - 1)
        self.assertEqual(len(placeholder_output(view)), 1)


class TestResultIsMissingTruthTable(unittest.TestCase):
    """Item 7: the single missing-value oracle, per relevant type."""

    def test_truth_table(self):
        nan = float("nan")
        cases = [
            (ResultFloat(), [(nan, True), (None, True), (1.5, False), ("NAN", False)]),
            (
                ResultReference(),
                [(-1, True), (np.int64(-1), True), (0, False), (7, False), (None, False)],
            ),
            (
                ResultPath(),
                [("NAN", True), ("img/frame_001.png", False), ("", False), (None, False)],
            ),
            (
                ResultDataSet(),
                [
                    # New generation: the blob-family sentinel.
                    ("NAN", True),
                    # Legacy generation: -1 index, including numpy and the float
                    # promotion an over_time concat applies to int columns.
                    (-1, True),
                    (np.int64(-1), True),
                    (np.float64(-1.0), True),
                    # Defensive: an unrepaired concat fill is missing, not data.
                    (nan, True),
                    (None, True),
                    # Valid cells of both generations.
                    ("cachedir/blobs/0123abcd.parquet", False),
                    (0, False),
                    (7, False),
                ],
            ),
        ]
        for rv, pairs in cases:
            for value, expected in pairs:
                with self.subTest(rv=type(rv).__name__, value=value):
                    self.assertEqual(result_is_missing(rv, value), expected)


if __name__ == "__main__":
    unittest.main()
