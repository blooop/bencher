"""Tests for DataSetResult (bencher/results/dataset_result.py)."""

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


def run_sweep():
    bench = bn.Bench("test_dataset_result", DataFrameSweep())
    return bench.plot_sweep(
        "dataset_sweep",
        input_vars=["scale"],
        result_vars=["table"],
        run_cfg=bn.BenchRunCfg(repeats=1, cache_results=False, cache_samples=False),
        auto_plot=False,
    )


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


if __name__ == "__main__":
    unittest.main()
