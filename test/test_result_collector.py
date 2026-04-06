"""Tests for ResultCollector extracted from Bench."""

import shutil
import tempfile
import unittest
import uuid
from datetime import datetime
from unittest import mock

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

        bench_res, _, dims_name, total_jobs = self.collector.setup_dataset(
            bench_cfg, datetime(2024, 1, 1)
        )

        self.assertIsNotNone(bench_res)
        self.assertIsNotNone(bench_res.ds)
        self.assertIn("theta", dims_name)
        self.assertIn("repeat", dims_name)
        self.assertGreater(total_jobs, 0)

    def test_setup_dataset_result_vars_scalar(self):
        """Test ResultFloat creates float data_vars."""
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

        bench_res, _, _, _ = self.collector.setup_dataset(bench_cfg, datetime(2024, 1, 1))

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

        bench_res, _, _, _ = self.collector.setup_dataset(bench_cfg, datetime(2024, 1, 1))

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


class TestCacheReuse(unittest.TestCase):
    """Tests for reusing diskcache.Cache instances across calls."""

    def setUp(self):
        self.collector = ResultCollector()

    def tearDown(self):
        self.collector.close_caches()

    def test_benchmark_cache_reused_across_cache_results_calls(self):
        """The same Cache instance should be returned on repeated access."""
        cache1 = self.collector.get_benchmark_cache()
        cache2 = self.collector.get_benchmark_cache()
        self.assertIs(cache1, cache2)

    def test_history_cache_reused_across_calls(self):
        """The same history Cache instance should be returned on repeated access."""
        cache1 = self.collector.get_history_cache()
        cache2 = self.collector.get_history_cache()
        self.assertIs(cache1, cache2)

    def test_benchmark_and_history_caches_are_distinct(self):
        """Benchmark and history caches should be different instances."""
        bc = self.collector.get_benchmark_cache()
        hc = self.collector.get_history_cache()
        self.assertIsNot(bc, hc)

    def test_close_caches_allows_reopen(self):
        """After close_caches(), new instances should be created on next access."""
        cache1 = self.collector.get_benchmark_cache()
        self.collector.close_caches()
        cache2 = self.collector.get_benchmark_cache()
        self.assertIsNot(cache1, cache2)

    def test_close_caches_idempotent(self):
        """Calling close_caches() multiple times should not raise."""
        self.collector.close_caches()
        self.collector.close_caches()

    def test_cache_results_uses_persistent_cache(self):
        """cache_results should use the persistent benchmark cache, not open a new one."""
        instance = ExampleBenchCfg()
        bench_cfg = BenchCfg(
            input_vars=[instance.param.theta],
            result_vars=[instance.param.out_sin],
            const_vars=[],
            bench_name="test_reuse",
            title="test",
            repeats=1,
        )
        bench_res, _, _, _ = self.collector.setup_dataset(bench_cfg, datetime(2024, 1, 1))

        hashes = []
        self.collector.cache_results(bench_res, "hash-a", hashes)
        self.collector.cache_results(bench_res, "hash-b", hashes)

        # Both writes should have gone to the same cache instance
        cache = self.collector.get_benchmark_cache()
        self.assertIn("hash-a", cache)
        self.assertIn("hash-b", cache)

    def test_sequential_plot_sweep_calls_reuse_cache(self):
        """Multiple sequential cache operations should reuse the same Cache instance.

        This is the core regression test: verify identical cache behavior
        across multiple sequential operations (simulating plot_sweep() calls).
        """
        instance = ExampleBenchCfg()
        bench_cfg = BenchCfg(
            input_vars=[instance.param.theta],
            result_vars=[instance.param.out_sin],
            const_vars=[],
            bench_name="test_sequential",
            title="test",
            repeats=1,
        )

        all_hashes = []
        for i in range(3):
            bench_res, _, _, _ = self.collector.setup_dataset(bench_cfg, datetime(2024, 1, 1))
            self.collector.cache_results(bench_res, f"seq-hash-{i}", all_hashes)

        self.assertEqual(all_hashes, ["seq-hash-0", "seq-hash-1", "seq-hash-2"])

        # All results retrievable from the single persistent cache
        cache = self.collector.get_benchmark_cache()
        for i in range(3):
            self.assertIn(f"seq-hash-{i}", cache)


class TestCacheOperations(unittest.TestCase):
    """Tests for cache_results and load_history_cache."""

    def setUp(self):
        self.collector = ResultCollector()
        # Use temp directories for cache to avoid polluting real cache
        self.temp_dir = tempfile.mkdtemp()
        self.original_cache_dir = "cachedir/benchmark_inputs"
        self.original_history_dir = "cachedir/history"

    def tearDown(self):
        self.collector.close_caches()
        # Clean up temp directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cache_results_appends_hash_to_list(self):
        """cache_results should append hash to the provided list."""
        instance = ExampleBenchCfg()
        bench_cfg = BenchCfg(
            input_vars=[instance.param.theta],
            result_vars=[instance.param.out_sin],
            const_vars=[],
            bench_name="test_cache_append",
            title="test",
            repeats=1,
        )

        bench_res, _, _, _ = self.collector.setup_dataset(bench_cfg, datetime(2024, 1, 1))

        # Start with empty list
        bench_cfg_hashes = []

        # Cache first result
        self.collector.cache_results(bench_res, "hash-1", bench_cfg_hashes)
        self.assertEqual(bench_cfg_hashes, ["hash-1"])

        # Cache second result - should append, not replace
        self.collector.cache_results(bench_res, "hash-2", bench_cfg_hashes)
        self.assertEqual(bench_cfg_hashes, ["hash-1", "hash-2"])

    def test_cache_results_preserves_object_index_in_memory(self):
        """cache_results should restore object_index after caching."""
        instance = ExampleBenchCfg()
        bench_cfg = BenchCfg(
            input_vars=[instance.param.theta],
            result_vars=[instance.param.out_sin],
            const_vars=[],
            bench_name="test_cache_object_index",
            title="test",
            repeats=1,
        )

        bench_res, _, _, _ = self.collector.setup_dataset(bench_cfg, datetime(2024, 1, 1))

        # Set object_index to something non-empty
        bench_res.object_index = ["obj-1", "obj-2"]

        bench_cfg_hashes = []
        self.collector.cache_results(bench_res, "hash-1", bench_cfg_hashes)

        # object_index should be restored in memory
        self.assertEqual(bench_res.object_index, ["obj-1", "obj-2"])

    def test_load_history_cache_no_existing_history(self):
        """load_history_cache should return dataset unchanged when no history exists."""
        # Create a simple dataset
        dataset = xr.Dataset({"var": (["x"], [1, 2, 3])})

        # Use a truly unique hash that won't exist in any cache
        unique_hash = f"nonexistent-hash-{uuid.uuid4()}"
        result = self.collector.load_history_cache(dataset, unique_hash, False)

        # Should return the same dataset (no concat)
        self.assertTrue(result.equals(dataset))

    def test_load_history_cache_clear_history_flag(self):
        """load_history_cache with clear_history=True should not concat."""
        dataset = xr.Dataset({"var": (["x"], [1, 2, 3])})

        # Even with existing history, clear_history=True should skip concat
        with mock.patch.object(xr, "concat") as mock_concat:
            self.collector.load_history_cache(dataset, "some-hash", clear_history=True)
            mock_concat.assert_not_called()

    def test_add_metadata_to_dataset_scalar_result(self):
        """add_metadata_to_dataset should set attrs for scalar ResultFloat."""
        instance = ExampleBenchCfg()
        bench_cfg = BenchCfg(
            input_vars=[instance.param.theta],
            result_vars=[instance.param.out_sin],
            const_vars=[],
            bench_name="test_metadata",
            title="test",
            repeats=1,
        )

        bench_res, _, _, _ = self.collector.setup_dataset(bench_cfg, datetime(2024, 1, 1))

        # Add metadata for theta input
        self.collector.add_metadata_to_dataset(bench_res, instance.param.theta)

        # Check result var has units and long_name
        self.assertEqual(bench_res.ds["out_sin"].attrs.get("units"), "v")
        self.assertEqual(bench_res.ds["out_sin"].attrs.get("long_name"), "out_sin")

        # Check input var coordinate has metadata
        self.assertEqual(bench_res.ds["theta"].attrs.get("long_name"), "theta")
        self.assertEqual(bench_res.ds["theta"].attrs.get("units"), "rad")


class TestMaxTimeEvents(unittest.TestCase):
    """Tests for max_time_events trimming in load_history_cache."""

    def setUp(self):
        self.collector = ResultCollector()

    def _make_over_time_dataset(self, n_slices):
        """Create a dataset with n over_time slices."""
        slices = []
        for i in range(n_slices):
            ds = xr.Dataset({"var": (["x", "over_time"], [[float(i)]])})
            slices.append(ds)
        return xr.concat(slices, "over_time")

    def test_max_time_events_trims_oldest(self):
        """max_time_events should keep only the N most recent slices."""
        dataset = self._make_over_time_dataset(5)
        unique_hash = f"trim-test-{uuid.uuid4()}"

        result = self.collector.load_history_cache(
            dataset, unique_hash, clear_history=False, max_time_events=3
        )

        self.assertEqual(result.sizes["over_time"], 3)
        # Should keep the last 3 slices (values 2, 3, 4)
        expected = [2.0, 3.0, 4.0]
        actual = list(result["var"].values[0])
        self.assertEqual(actual, expected)

    def test_max_time_events_none_unlimited(self):
        """max_time_events=None should not trim anything."""
        dataset = self._make_over_time_dataset(5)
        unique_hash = f"unlimited-test-{uuid.uuid4()}"

        result = self.collector.load_history_cache(
            dataset, unique_hash, clear_history=False, max_time_events=None
        )

        self.assertEqual(result.sizes["over_time"], 5)

    def test_max_time_events_exact_count_no_trim(self):
        """When over_time count equals max_time_events, no trimming occurs."""
        dataset = self._make_over_time_dataset(3)
        unique_hash = f"exact-test-{uuid.uuid4()}"

        result = self.collector.load_history_cache(
            dataset, unique_hash, clear_history=False, max_time_events=3
        )

        self.assertEqual(result.sizes["over_time"], 3)
        expected = [0.0, 1.0, 2.0]
        actual = list(result["var"].values[0])
        self.assertEqual(actual, expected)

    def test_max_time_events_with_clear_history(self):
        """clear_history + max_time_events: in practice clear_history yields a single slice,
        but trimming is still correct if the incoming dataset has multiple over_time slices."""
        dataset = self._make_over_time_dataset(5)
        unique_hash = f"clear-trim-test-{uuid.uuid4()}"

        result = self.collector.load_history_cache(
            dataset, unique_hash, clear_history=True, max_time_events=2
        )

        self.assertEqual(result.sizes["over_time"], 2)
        expected = [3.0, 4.0]
        actual = list(result["var"].values[0])
        self.assertEqual(actual, expected)

    def test_max_time_events_incremental_accumulation(self):
        """Simulates repeated plot_sweep() calls: cache should stay bounded."""
        unique_hash = f"incremental-test-{uuid.uuid4()}"

        for i in range(10):
            single_slice = xr.Dataset({"var": (["x", "over_time"], [[float(i)]])})
            result = self.collector.load_history_cache(
                single_slice, unique_hash, clear_history=False, max_time_events=3
            )

        # After 10 incremental calls with max_time_events=3, only the last 3 should remain
        self.assertEqual(result.sizes["over_time"], 3)
        expected = [7.0, 8.0, 9.0]
        actual = list(result["var"].values[0])
        self.assertEqual(actual, expected)

    def test_max_time_events_no_over_time_dim(self):
        """max_time_events should be a no-op when dataset has no over_time dim."""
        dataset = xr.Dataset({"var": (["x"], [1, 2, 3])})
        unique_hash = f"nodim-test-{uuid.uuid4()}"

        result = self.collector.load_history_cache(
            dataset, unique_hash, clear_history=False, max_time_events=2
        )

        self.assertTrue(result.equals(dataset))


class TestDTypeIncompatibleHistory(unittest.TestCase):
    """Test that load_history_cache handles dtype changes in over_time coords."""

    def setUp(self):
        self.collector = ResultCollector()

    def test_datetime_then_string_over_time_no_crash(self):
        """Switching from datetime to string over_time coords should not crash."""
        unique_hash = f"dtype-compat-{uuid.uuid4()}"

        # First run: datetime over_time coord (TimeSnapshot style)
        ds_datetime = xr.Dataset(
            {"var": (["x", "over_time"], [[1.0]])},
            coords={"over_time": [np.datetime64("2024-01-01")]},
        )
        self.collector.load_history_cache(ds_datetime, unique_hash, clear_history=False)

        # Second run: string over_time coord (TimeEvent style)
        ds_string = xr.Dataset(
            {"var": (["x", "over_time"], [[2.0]])},
            coords={"over_time": ["v1.0"]},
        )
        with self.assertLogs(level="WARNING") as captured_logs:
            result = self.collector.load_history_cache(ds_string, unique_hash, clear_history=False)

        # Should warn about discarded history
        self.assertTrue(
            any("Discarding incompatible historical data" in msg for msg in captured_logs.output)
        )
        # Old data discarded, result matches the new dataset exactly
        self.assertTrue(result.equals(ds_string))

    def test_string_then_datetime_over_time_no_crash(self):
        """Switching from string to datetime over_time coords should not crash."""
        unique_hash = f"dtype-compat-reverse-{uuid.uuid4()}"

        # First run: string over_time coord (TimeEvent style)
        ds_string = xr.Dataset(
            {"var": (["x", "over_time"], [[1.0]])},
            coords={"over_time": ["v1.0"]},
        )
        self.collector.load_history_cache(ds_string, unique_hash, clear_history=False)

        # Second run: datetime over_time coord (TimeSnapshot style)
        ds_datetime = xr.Dataset(
            {"var": (["x", "over_time"], [[2.0]])},
            coords={"over_time": [np.datetime64("2024-06-15")]},
        )
        with self.assertLogs(level="WARNING") as captured_logs:
            result = self.collector.load_history_cache(
                ds_datetime, unique_hash, clear_history=False
            )

        self.assertTrue(
            any("Discarding incompatible historical data" in msg for msg in captured_logs.output)
        )
        self.assertTrue(result.equals(ds_datetime))


class TestStaleCacheRecovery(unittest.TestCase):
    """Test that load_history_cache recovers from stale/corrupt cache entries."""

    def setUp(self):
        self.collector = ResultCollector()

    def test_attribute_error_on_deserialize_discards_entry(self):
        """A stale cache entry that raises AttributeError should be discarded gracefully."""
        unique_hash = f"stale-cache-{uuid.uuid4()}"
        dataset = xr.Dataset(
            {"var": (["x", "over_time"], [[1.0]])},
            coords={"over_time": ["v1"]},
        )

        # Seed the cache with a value, then make __getitem__ raise AttributeError
        # to simulate a pickle deserialization failure from an upgraded dependency.
        c = self.collector.get_history_cache()
        c[unique_hash] = dataset

        with mock.patch.object(
            type(c),
            "__getitem__",
            side_effect=AttributeError("'List' object has no attribute 'class_'"),
        ):
            with self.assertLogs("bencher.result_collector", level="WARNING") as captured_logs:
                result = self.collector.load_history_cache(
                    dataset, unique_hash, clear_history=False
                )

        self.assertTrue(
            any("Failed to deserialize cached history" in msg for msg in captured_logs.output)
        )
        # Should return the fresh dataset without crashing
        self.assertTrue(result.equals(dataset))

    def test_module_not_found_error_on_deserialize_discards_entry(self):
        """A cache entry referencing a removed module should be discarded gracefully."""
        unique_hash = f"stale-module-{uuid.uuid4()}"
        dataset = xr.Dataset({"var": (["x"], [1, 2, 3])})

        c = self.collector.get_history_cache()
        c[unique_hash] = dataset

        with mock.patch.object(
            type(c),
            "__getitem__",
            side_effect=ModuleNotFoundError("No module named 'old_dep'"),
        ):
            with self.assertLogs("bencher.result_collector", level="WARNING") as captured_logs:
                result = self.collector.load_history_cache(
                    dataset, unique_hash, clear_history=False
                )

        self.assertTrue(
            any("Failed to deserialize cached history" in msg for msg in captured_logs.output)
        )
        self.assertTrue(result.equals(dataset))


class TestLazyCartesianProduct(unittest.TestCase):
    """Tests for lazy Cartesian product in setup_dataset (plan item 1.3)."""

    def setUp(self):
        self.collector = ResultCollector()

    def _make_bench_cfg(self, n_theta_samples=3, repeats=2):
        instance = ExampleBenchCfg()
        instance.param.theta.samples = n_theta_samples
        return BenchCfg(
            input_vars=[instance.param.theta],
            result_vars=[instance.param.out_sin],
            const_vars=[],
            bench_name="test_lazy",
            title="test_lazy",
            repeats=repeats,
        )

    def test_setup_dataset_returns_lazy_iterator(self):
        """function_inputs should be a lazy zip, not a list."""
        bench_cfg = self._make_bench_cfg()
        _, func_inputs, _, total_jobs = self.collector.setup_dataset(
            bench_cfg, datetime(2024, 1, 1)
        )
        self.assertNotIsInstance(func_inputs, list)
        self.assertIsInstance(func_inputs, zip)
        self.assertEqual(total_jobs, 3 * 2)  # theta_samples * repeats

    def test_total_jobs_matches_iterator_length(self):
        """total_jobs count must match the number of items yielded by the iterator."""
        bench_cfg = self._make_bench_cfg(n_theta_samples=5, repeats=3)
        _, func_inputs, _, total_jobs = self.collector.setup_dataset(
            bench_cfg, datetime(2024, 1, 1)
        )
        items = list(func_inputs)
        self.assertEqual(len(items), total_jobs)

    def test_iterator_yields_correct_values(self):
        """Materialized iterator should match the expected Cartesian product."""
        bench_cfg = self._make_bench_cfg(n_theta_samples=3, repeats=2)
        _, func_inputs, _, _ = self.collector.setup_dataset(bench_cfg, datetime(2024, 1, 1))
        items = list(func_inputs)
        # Each item is (index_tuple, value_tuple)
        # With 3 theta samples and 2 repeats, expect 6 items
        self.assertEqual(len(items), 6)
        # First element should be indices, second should be values
        for idx_tuple, val_tuple in items:
            self.assertIsInstance(idx_tuple, tuple)
            self.assertIsInstance(val_tuple, tuple)
            self.assertEqual(len(idx_tuple), 2)  # theta dim + repeat dim
            self.assertEqual(len(val_tuple), 2)

    def test_iteration_does_not_mutate_bench_cfg(self):
        """Consuming the iterator must not change bench_cfg."""
        bench_cfg = self._make_bench_cfg()
        input_vars_before = list(bench_cfg.input_vars)
        all_vars_before = list(bench_cfg.all_vars) if bench_cfg.all_vars else None

        _, func_inputs, _, _ = self.collector.setup_dataset(bench_cfg, datetime(2024, 1, 1))
        # Consume the iterator fully
        _ = list(func_inputs)

        self.assertEqual(bench_cfg.input_vars, input_vars_before)
        if all_vars_before is not None:
            self.assertEqual(list(bench_cfg.all_vars), all_vars_before)


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
