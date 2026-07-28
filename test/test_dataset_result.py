"""Tests for DataSetResult (bencher/results/dataset_result.py)."""

import pickle
import unittest

import numpy as np
import pandas as pd
import panel as pn

import bencher as bn
from bencher.results.dataset_result import DataSetResult

SCALES = [1.0, 2.0]


def expected_frame(scale: float) -> pd.DataFrame:
    return pd.DataFrame({"y": [scale * 1.0, scale * 2.0, scale * 3.0]})


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
        if str(pane.object).startswith(("declared", "per-sample", "explicit"))
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

    def test_dataset_list_round_trips_worker_frames(self):
        """Every worker-produced DataFrame is stored and recoverable unchanged."""
        self.assertEqual(len(self.res.dataset_list), len(SCALES))
        for ref, scale in zip(self.res.dataset_list, SCALES):
            pd.testing.assert_frame_equal(ref.obj, expected_frame(scale))

    def test_ds_indices_map_to_correct_frames(self):
        """The xarray dataset stores indices into dataset_list, keyed by input value."""
        ds = self.res.to_dataset()
        for scale in SCALES:
            idx = int(ds["table"].sel(scale=scale).values)
            frame = self.res.dataset_list[idx].obj
            pd.testing.assert_frame_equal(frame, expected_frame(scale))

    def test_ds_to_container_returns_underlying_frame(self):
        """ds_to_container (used by the viewer) unwraps the stored DataFrame."""
        ds = self.res.to_dataset()
        rv = self.res.bench_cfg.result_vars[0]
        point = ds.sel(scale=SCALES[1])
        frame = self.res.ds_to_container(point, rv, container=None)
        pd.testing.assert_frame_equal(frame, expected_frame(SCALES[1]))
        np.testing.assert_allclose(frame["y"].to_numpy(), [2.0, 4.0, 6.0])


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
        for ref, scale in zip(self.res.dataset_list, SCALES):
            pd.testing.assert_frame_equal(ref.obj, expected_frame(scale))


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
        the dedicated sweep class: the deletions mutate params this test alone owns.
        """
        res = run_sweep(LegacyPickleSweep(), "test_dataset_legacy_pickle")
        rv = res.bench_cfg.result_vars[0]
        del rv.container
        del res.dataset_list[0].container
        frame = res.ds_to_container(res.to_dataset().sel(scale=SCALES[0]), rv, container=None)
        pd.testing.assert_frame_equal(frame, expected_frame(SCALES[0]))


if __name__ == "__main__":
    unittest.main()
