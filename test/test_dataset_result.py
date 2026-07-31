"""Tests for DataSetResult (bencher/results/dataset_result.py)."""

import pickle
import unittest
import unittest.mock
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import panel as pn
import xarray as xr

import bencher as bn
from bencher.blob_store import load_blob
from bencher.results.bench_result_base import BenchResultBase
from bencher.results.dataset_result import DataSetResult, render_data_samples
from bencher.variables.results import PANEL_TYPES

SCALES = [1.0, 2.0]


def expected_frame(scale: float) -> pd.DataFrame:
    return pd.DataFrame({"y": [scale * 1.0, scale * 2.0, scale * 3.0]})


def arbitrary_payload(scale: float) -> dict:
    return {"scale": scale, "samples": [scale, scale * 2.0]}


class DataFrameSweep(bn.ParametrizedSweep):
    """1-input sweep whose worker returns a small, scale-dependent DataFrame."""

    scale = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    table = bn.ResultDataSet(doc="small dataframe result")

    def benchmark(self):
        self.table = bn.ResultDataSet(expected_frame(self.scale))


def declared_container(df: pd.DataFrame) -> pn.pane.Markdown:
    """Stand-in for a real plot: takes the frame alone, returns something viewable."""
    return pn.pane.Markdown(f"declared rows={len(df)} sum={df['y'].sum():g}")


def per_sample_container(df: pd.DataFrame) -> pn.pane.Markdown:
    return pn.pane.Markdown(f"per-sample rows={len(df)}")


def explicit_container(df: pd.DataFrame) -> pn.pane.Markdown:
    return pn.pane.Markdown(f"explicit rows={len(df)}")


def payload_container(payload: dict) -> pn.pane.Markdown:
    return pn.pane.Markdown(f"payload scale={payload['scale']:g} samples={len(payload['samples'])}")


class ArbitraryPayloadSweep(bn.ParametrizedSweep):
    """The generic store has no DataFrame/xarray requirement."""

    scale = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    table = bn.ResultDataSet(container=payload_container, doc="structured Python payload")

    def benchmark(self):
        self.table = bn.ResultDataSet(arbitrary_payload(self.scale))


class DeclaredContainerSweep(bn.ParametrizedSweep):
    """Container declared once on the class, applied to every sample."""

    scale = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    table = bn.ResultDataSet(container=declared_container, doc="rendered dataframe result")

    def benchmark(self):
        self.table = bn.ResultDataSet(expected_frame(self.scale))


class PerSampleContainerSweep(DeclaredContainerSweep):
    """Worker overrides the declared container on the sample it stores."""

    def benchmark(self):
        self.table = bn.ResultDataSet(expected_frame(self.scale), container=per_sample_container)


class LegacyPickleSweep(bn.ParametrizedSweep):
    """Owned by the unset-slot test, which mutates its params."""

    scale = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    table = bn.ResultDataSet(doc="frame stored without a container")

    def benchmark(self):
        self.table = bn.ResultDataSet(expected_frame(self.scale))


def tagged_frame(scale: float, run_id: int) -> pd.DataFrame:
    """A frame that says which run produced it, so a render can be traced to its run."""
    return pd.DataFrame({"y": [scale * 1.0, scale * 2.0], "run": [run_id, run_id]})


def run_tagging_container(df: pd.DataFrame) -> pn.pane.Markdown:
    return pn.pane.Markdown(f"declared run={df['run'].iloc[0]} scale={df['y'].iloc[0]:g}")


class OverTimeSweep(bn.ParametrizedSweep):
    """A tabular result and a scalar one, to be run repeatedly against one history."""

    scale = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    table = bn.ResultDataSet(container=run_tagging_container, doc="run-tagged dataframe")
    magnitude = bn.ResultFloat(units="m", doc="scalar result, which does keep history")

    run_id = 0

    def benchmark(self):
        self.table = bn.ResultDataSet(tagged_frame(self.scale, self.run_id))
        self.magnitude = self.scale + self.run_id


class PlainOverTimeSweep(OverTimeSweep):
    """The same shape with no declared container: the defect predates that feature."""

    table = bn.ResultDataSet(doc="run-tagged dataframe, rendered as rows")


OVER_TIME_RUNS = 3


def run_sweep_over_time(
    worker: bn.ParametrizedSweep, name: str, runs: int = OVER_TIME_RUNS
) -> bn.BenchResult:
    """Run one sweep `runs` times against a single history, as a nightly rig does.

    Only the first run clears the history, so from the second run on the rendered
    dataset carries the earlier events on its over_time dimension.
    """
    run_cfg = bn.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.repeats = 1
    run_cfg.auto_plot = False
    bench = bn.Bench(name, worker)
    base_time = datetime(2000, 1, 1)
    res = None
    for i in range(runs):
        worker.run_id = i
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "over_time_dataset_sweep",
            input_vars=["scale"],
            result_vars=["table", "magnitude"],
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
        )
    return res


def run_sweep(worker: bn.ParametrizedSweep | None = None, name: str = "test_dataset_result"):
    worker = DataFrameSweep() if worker is None else worker
    bench = bn.Bench(name, worker)
    return bench.plot_sweep(
        "dataset_sweep",
        input_vars=["scale"],
        result_vars=["table"],
        run_cfg=bn.BenchRunCfg(repeats=1, cache_results=False, cache_samples=False),
        auto_plot=False,
    )


def container_output(viewable: pn.viewable.Viewable) -> list[str]:
    """Container-produced Markdown in a rendered pane tree, in render order.

    Filtered by prefix because the surrounding panes carry their own labels
    (the sample's input values), which is not what these tests are about.
    """
    return [
        pane.object
        for pane in viewable.select(pn.pane.Markdown)
        if str(pane.object).startswith(("declared", "per-sample", "explicit", "payload"))
    ]


class TestDataSetResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep()

    def test_to_plot_returns_viewable(self):
        viewer = self.res.to(DataSetResult)
        self.assertIsNotNone(viewer)
        self.assertIsInstance(viewer, pn.viewable.Viewable)
        self.assertGreater(len(viewer), 0)

    def test_path_cells_round_trip_worker_frames(self):
        """Every worker-produced DataFrame is stored as a blob and recoverable unchanged.

        Since plan 22 the cell stores a path into the blob store rather than an
        index into dataset_list, which stays empty (it is the legacy read path).
        """
        self.assertEqual(len(self.res.dataset_list), 0)
        ds = self.res.to_dataset()
        for scale in SCALES:
            cell = ds["table"].sel(scale=scale).values.item()
            self.assertIsInstance(cell, str)
            pd.testing.assert_frame_equal(load_blob(cell), expected_frame(scale))

    def test_ds_to_container_returns_underlying_frame(self):
        """ds_to_container (used by the viewer) unwraps the stored DataFrame."""
        ds = self.res.to_dataset()
        rv = self.res.bench_cfg.result_vars[0]
        point = ds.sel(scale=SCALES[1])
        frame = self.res.ds_to_container(point, rv, container=None)
        pd.testing.assert_frame_equal(frame, expected_frame(SCALES[1]))
        np.testing.assert_allclose(frame["y"].to_numpy(), [2.0, 4.0, 6.0])


class NonDataSetSweep(bn.ParametrizedSweep):
    """A sweep with a pane-type result that is not a ResultDataSet."""

    scale = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    label = bn.ResultString(doc="a string, not a stored payload")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.label = f"scale={self.scale:g}"
        return self.get_results_values_as_dict()


class TestOnlyDataSetResultsAreClaimed(unittest.TestCase):
    """This view renders stored payloads only, unlike the general ``panes`` view.

    The distinction is the reason the two exist: ``to_panes`` claims every pane-type
    result, so a sweep without a ResultDataSet is its job, not this one's. Returning
    None rather than falling back keeps a ``container=`` written for a stored payload
    from being called with an unrelated result's value.
    """

    @classmethod
    def setUpClass(cls):
        bench = bn.Bench("test_dataset_non_dataset_result", NonDataSetSweep())
        cls.res = bench.plot_sweep(
            "string_sweep",
            input_vars=["scale"],
            result_vars=["label"],
            run_cfg=bn.BenchRunCfg(repeats=1, cache_results=False, cache_samples=False),
            auto_plot=False,
        )

    def test_dataset_view_declines_a_sweep_with_no_stored_payload(self):
        self.assertIsNone(self.res.to(DataSetResult))

    def test_panes_view_still_renders_it(self):
        """Guard on the fixture: the result is renderable, just not by this view."""
        self.assertIsInstance(self.res.to_panes(), pn.viewable.Viewable)


class TestSharedRenderPath(unittest.TestCase):
    """Both per-sample views go through one render path, differing only in claim.

    The default report renders a declared ``container=`` through ``to_panes``, not
    through this view, so if the two paths were separate copies a fix to one would
    silently not reach the report.
    """

    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep()

    def _claimed_types(self, render) -> tuple:
        with unittest.mock.patch.object(BenchResultBase, "map_sample_panes", autospec=True) as spy:
            render()
        self.assertEqual(spy.call_count, 1, "the view must delegate, not reimplement")
        return spy.call_args.args[1]

    def test_dataset_view_claims_only_stored_payloads(self):
        self.assertEqual(
            self._claimed_types(lambda: self.res.to(DataSetResult)), (bn.ResultDataSet,)
        )

    def test_panes_view_claims_every_pane_type(self):
        self.assertEqual(self._claimed_types(self.res.to_panes), PANEL_TYPES)

    def test_chart_types_reuse_the_same_path(self):
        """A chart type composes the shared path rather than adding a parallel one."""
        self.assertEqual(
            self._claimed_types(lambda: render_data_samples(self.res)), (bn.ResultDataSet,)
        )


class TestArbitraryPayload(unittest.TestCase):
    """ResultDataSet stores data; only its renderer interprets the payload."""

    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep(ArbitraryPayloadSweep(), "test_dataset_arbitrary_payload")

    def test_payload_round_trips_without_tabular_coercion(self):
        ds = self.res.to_dataset()
        self.assertEqual(
            [load_blob(ds["table"].sel(scale=scale).values.item()) for scale in SCALES],
            [arbitrary_payload(scale) for scale in SCALES],
        )

    def test_declared_renderer_receives_the_original_payload(self):
        self.assertEqual(
            container_output(self.res.to(DataSetResult)),
            ["payload scale=1 samples=2", "payload scale=2 samples=2"],
        )


class TestDeclaredContainer(unittest.TestCase):
    """A container declared on the ResultDataSet renders every sample through it."""

    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep(DeclaredContainerSweep(), "test_dataset_declared_container")

    def _point(self, scale: float):
        return self.res.to_dataset().sel(scale=scale)

    def test_declared_container_replaces_raw_frame(self):
        rv = self.res.bench_cfg.result_vars[0]
        pane = self.res.ds_to_container(self._point(SCALES[1]), rv, container=None)
        self.assertIsInstance(pane, pn.pane.Markdown)
        self.assertEqual(pane.object, "declared rows=3 sum=12")

    def test_explicit_container_beats_declared(self):
        """A renderer that is given a container keeps using it."""
        rv = self.res.bench_cfg.result_vars[0]
        pane = self.res.ds_to_container(self._point(SCALES[0]), rv, container=explicit_container)
        self.assertEqual(pane.object, "explicit rows=3")

    def test_dataset_view_renders_through_container(self):
        """The dataset viewer shows the container output, not the raw table."""
        rendered = container_output(self.res.to(DataSetResult))
        self.assertEqual(rendered, ["declared rows=3 sum=6", "declared rows=3 sum=12"])

    def test_panes_view_renders_through_container(self):
        """ResultDataSet is a panel type, so the auto panes pass picks it up too."""
        rendered = container_output(self.res.to_auto(plot_list=["panes"]))
        self.assertEqual(rendered, ["declared rows=3 sum=6", "declared rows=3 sum=12"])

    def test_stored_frame_is_untouched(self):
        """Rendering is a view: the container never rewrites what was measured."""
        ds = self.res.to_dataset()
        for scale in SCALES:
            frame = load_blob(ds["table"].sel(scale=scale).values.item())
            pd.testing.assert_frame_equal(frame, expected_frame(scale))


class TestPerSampleContainer(unittest.TestCase):
    def test_sample_container_beats_declared(self):
        res = run_sweep(PerSampleContainerSweep(), "test_dataset_per_sample_container")
        rv = res.bench_cfg.result_vars[0]
        pane = res.ds_to_container(res.to_dataset().sel(scale=SCALES[0]), rv, container=None)
        self.assertEqual(pane.object, "per-sample rows=3")


class TestContainerIsNotData(unittest.TestCase):
    """The container is a renderer, so it must not participate in cache identity."""

    def test_container_excluded_from_hash(self):
        plain = bn.ResultDataSet(doc="d")
        with_container = bn.ResultDataSet(container=declared_container, doc="d")
        other_container = bn.ResultDataSet(container=explicit_container, doc="d")
        self.assertEqual(plain.hash_persistent(), with_container.hash_persistent())
        self.assertEqual(with_container.hash_persistent(), other_container.hash_persistent())

    def test_declared_container_survives_pickling(self):
        """It rides in BenchCfg, which the result cache and split render both pickle."""
        rv = pickle.loads(pickle.dumps(DeclaredContainerSweep.param.table))
        self.assertIs(rv.container, declared_container)

    def test_unset_slot_falls_back_to_raw_frame(self):
        """A result pickled before the slot existed unpickles with it unset, and still renders.

        Unsetting the slot is the only way to reproduce that state in-process, hence
        the dedicated sweep class: the deletion mutates a param this test alone owns.
        """
        res = run_sweep(LegacyPickleSweep(), "test_dataset_legacy_pickle")
        rv = res.bench_cfg.result_vars[0]
        del rv.container
        frame = res.ds_to_container(res.to_dataset().sel(scale=SCALES[0]), rv, container=None)
        pd.testing.assert_frame_equal(frame, expected_frame(SCALES[0]))


class TestOverTimeHistory(unittest.TestCase):
    """A ResultDataSet history has to render every event, not only the latest one.

    Cells are blob paths since plan 22, meaningful in any run, so the events merged
    in from history render alongside the current one (D4).  Before that, cells were
    indices into dataset_list — rebuilt from whichever run was rendering — so the
    render was forcibly restricted to ``isel(over_time=-1)`` and history existed in
    the data but could not be shown.
    """

    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep_over_time(OverTimeSweep(), "test_dataset_over_time")

    def expected_panes(self) -> list[str]:
        """One pane per (sample, event): samples are peeled outermost, time innermost."""
        return [
            f"declared run={run} scale={scale:g}"
            for scale in SCALES
            for run in range(OVER_TIME_RUNS)
        ]

    def test_history_accumulated(self):
        """Guard on the fixture: with a single event there is no regression to catch."""
        self.assertEqual(self.res.to_dataset().sizes["over_time"], OVER_TIME_RUNS)

    def test_panes_pass_renders_every_run(self):
        self.assertEqual(
            container_output(self.res.to_auto(plot_list=["panes"])), self.expected_panes()
        )

    def test_dataset_view_renders_every_run(self):
        self.assertEqual(container_output(self.res.to(DataSetResult)), self.expected_panes())

    def test_one_pane_per_sample_per_event(self):
        """The D4 payoff: history multiplies the panes, one per stored payload."""
        self.assertEqual(
            len(container_output(self.res.to(DataSetResult))), len(SCALES) * OVER_TIME_RUNS
        )

    def test_scalar_results_keep_their_history(self):
        """Slicing the tables must not cost the metrics their over_time series."""
        magnitude = self.res.to_dataset()["magnitude"]
        self.assertEqual(magnitude.sizes["over_time"], OVER_TIME_RUNS)
        for run in range(OVER_TIME_RUNS):
            observed = magnitude.isel(over_time=run).sel(scale=SCALES[0]).values.squeeze()
            self.assertAlmostEqual(float(observed), SCALES[0] + run)


class TestOverTimeWithoutContainer(unittest.TestCase):
    def test_raw_frame_renders_after_the_first_run(self):
        res = run_sweep_over_time(PlainOverTimeSweep(), "test_dataset_over_time_plain", runs=2)
        rv = res.bench_cfg.result_vars[0]
        point = res.to_dataset().isel(over_time=-1).sel(scale=SCALES[0])
        frame = res.ds_to_container(point, rv, container=None)
        self.assertEqual(frame["run"].tolist(), [1, 1])
        self.assertIsInstance(res.to(DataSetResult), pn.viewable.Viewable)


class TestSinglePointGuard(unittest.TestCase):
    """ds_to_container renders one sample, and names the dimension when it cannot."""

    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep(DeclaredContainerSweep(), "test_dataset_single_point_guard")

    def test_unreduced_dimension_is_named(self):
        """A whole dataset is not a point: the error says what was not reduced.

        Indexing dataset_list with an array otherwise fails several frames away,
        naming neither the result variable nor the dimension.
        """
        rv = self.res.bench_cfg.result_vars[0]
        with self.assertRaises(ValueError) as raised:
            self.res.ds_to_container(self.res.to_dataset(), rv, container=None)
        self.assertIn("scale", str(raised.exception))
        self.assertIn("table", str(raised.exception))

    def test_length_one_dimensions_collapse_to_a_value(self):
        """A point that kept its length-1 dimensions is one value, not an array."""
        da = xr.DataArray(
            [[4.0]],
            dims=["over_time", "repeat"],
            coords={"over_time": [0], "repeat": [0]},
        )
        value = self.res.zero_dim_da_to_val(da)
        self.assertNotIsInstance(value, np.ndarray)
        self.assertEqual(float(value), 4.0)


if __name__ == "__main__":
    unittest.main()
