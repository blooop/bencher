"""Tests for ResultCollector extracted from Bench."""

import unittest
from datetime import datetime

import numpy as np
import xarray as xr
from hypothesis import given, settings, strategies as st

from bencher.example.benchmark_data import ExampleBenchCfg
from bencher.result_collector import ResultCollector, set_xarray_multidim
from bencher.bench_cfg import BenchCfg


class TestResultCollector(unittest.TestCase):
    """Tests for ResultCollector extracted from Bench."""

    def setUp(self):
        self.collector = ResultCollector()

    def test_init_default_cache_size(self):
        """Test default cache size is set."""
        collector = ResultCollector()
        self.assertEqual(collector.cache_size, int(100e9))

    def test_init_custom_cache_size(self):
        """Test custom cache size is set."""
        collector = ResultCollector(cache_size=int(50e9))
        self.assertEqual(collector.cache_size, int(50e9))

    def test_setup_dataset_creates_bench_result(self):
        """Test xarray dataset has correct structure."""
        instance = ExampleBenchCfg()
        bench_cfg = BenchCfg(
            input_vars=[instance.param.theta],
            result_vars=[instance.param.out_sin],
            const_vars=[],
            bench_name="test",
            title="test",
            repeats=2,
        )

        bench_res, func_inputs, dims_name = self.collector.setup_dataset(
            bench_cfg, datetime(2024, 1, 1)
        )

        self.assertIsNotNone(bench_res)
        self.assertIsNotNone(bench_res.ds)
        self.assertIn("theta", dims_name)
        self.assertIn("repeat", dims_name)

    def test_setup_dataset_result_vars_scalar(self):
        """Test ResultVar creates float data_vars."""
        instance = ExampleBenchCfg()
        instance.param.theta.samples = 3

        bench_cfg = BenchCfg(
            input_vars=[instance.param.theta],
            result_vars=[instance.param.out_sin],
            const_vars=[],
            bench_name="test",
            title="test",
            repeats=1,
        )

        bench_res, _, _ = self.collector.setup_dataset(bench_cfg, datetime(2024, 1, 1))

        self.assertIn("out_sin", bench_res.ds.data_vars)
        self.assertEqual(bench_res.ds["out_sin"].dtype, np.float64)

    def test_define_extra_vars_repeat(self):
        """Test repeat meta variable creation."""
        bench_cfg = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            repeats=5,
            over_time=False,
        )

        extra_vars = self.collector.define_extra_vars(bench_cfg, 5, datetime(2024, 1, 1))

        self.assertEqual(len(extra_vars), 1)
        self.assertEqual(extra_vars[0].name, "repeat")
        self.assertEqual(len(extra_vars[0].values()), 5)

    def test_define_extra_vars_time_snapshot(self):
        """Test TimeSnapshot creation for datetime."""
        bench_cfg = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            repeats=1,
            over_time=True,
        )

        extra_vars = self.collector.define_extra_vars(bench_cfg, 1, datetime(2024, 1, 1))

        self.assertEqual(len(extra_vars), 2)
        self.assertEqual(extra_vars[1].name, "over_time")

    def test_define_extra_vars_time_event(self):
        """Test TimeEvent creation for string."""
        bench_cfg = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            repeats=1,
            over_time=True,
        )

        extra_vars = self.collector.define_extra_vars(bench_cfg, 1, "event_123")

        self.assertEqual(len(extra_vars), 2)
        self.assertEqual(extra_vars[1].name, "over_time")

    def test_report_results_no_print(self):
        """Test report_results with printing disabled."""
        instance = ExampleBenchCfg()
        bench_cfg = BenchCfg(
            input_vars=[instance.param.theta],
            result_vars=[instance.param.out_sin],
            const_vars=[],
            bench_name="test",
            title="test",
            repeats=1,
        )

        bench_res, _, _ = self.collector.setup_dataset(bench_cfg, datetime(2024, 1, 1))

        # Should not raise any errors
        self.collector.report_results(bench_res, print_xarray=False, print_pandas=False)

    # Hypothesis property-based tests
    @settings(deadline=10000)
    @given(
        repeats=st.integers(min_value=1, max_value=5),
        over_time=st.booleans(),
    )
    def test_define_extra_vars_combinations(self, repeats, over_time):
        """Property: extra vars created correctly for all combinations."""
        bench_cfg = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            repeats=repeats,
            over_time=over_time,
        )

        extra_vars = self.collector.define_extra_vars(bench_cfg, repeats, datetime(2024, 1, 1))

        # Always has repeat
        self.assertGreaterEqual(len(extra_vars), 1)
        self.assertEqual(extra_vars[0].name, "repeat")

        # Has time if over_time
        if over_time:
            self.assertEqual(len(extra_vars), 2)
            self.assertEqual(extra_vars[1].name, "over_time")
        else:
            self.assertEqual(len(extra_vars), 1)


class TestSetXarrayMultidim(unittest.TestCase):
    """Tests for set_xarray_multidim utility function."""

    def test_set_value_2d(self):
        """Test setting value in 2D array."""
        data = xr.DataArray(np.zeros((3, 3)), dims=["x", "y"])
        set_xarray_multidim(data, (1, 2), 5.0)
        self.assertEqual(data[1, 2].item(), 5.0)

    def test_set_value_3d(self):
        """Test setting value in 3D array."""
        data = xr.DataArray(np.zeros((2, 2, 2)), dims=["x", "y", "z"])
        set_xarray_multidim(data, (1, 0, 1), 7.5)
        self.assertEqual(data[1, 0, 1].item(), 7.5)

    def test_set_value_preserves_other_values(self):
        """Test setting one value doesn't affect others."""
        data = xr.DataArray(np.ones((3, 3)), dims=["x", "y"])
        set_xarray_multidim(data, (0, 0), 99.0)

        self.assertEqual(data[0, 0].item(), 99.0)
        self.assertEqual(data[1, 1].item(), 1.0)
        self.assertEqual(data[2, 2].item(), 1.0)

    @settings(deadline=10000)
    @given(
        value=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e10, max_value=1e10),
    )
    def test_set_xarray_multidim_values(self, value):
        """Property: set_xarray_multidim works for various values."""
        data = xr.DataArray(np.zeros((3, 3)), dims=["x", "y"])
        set_xarray_multidim(data, (1, 1), value)
        self.assertEqual(data[1, 1].item(), value)


if __name__ == "__main__":
    unittest.main()
