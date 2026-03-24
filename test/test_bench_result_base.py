import unittest
import bencher as bn
import numpy as np
import panel as pn

from bencher.example.meta.example_meta import BenchableObject
from bencher.results.bench_result_base import ReduceType


class TstBench(bn.ParametrizedSweep):
    float_var = bn.FloatSweep(default=0, bounds=[0, 4])
    cat_var = bn.StringSweep(["a", "b", "c", "d", "e"])
    result = bn.ResultVar()

    def __call__(self, **kwargs):
        self.result = 1
        return super().__call__()


class TestAggOverDimsStd(unittest.TestCase):
    """Comprehensive tests for _std computation when aggregating over dims."""

    @classmethod
    def setUpClass(cls):
        """Create reusable sweep results to avoid repeated setup cost."""
        cls.bench = BenchableObject().to_bench()

        # Single-dim sweep, 1 repeat, 1 result var
        cls.res_1d_1rep = cls.bench.plot_sweep(
            "agg_1d_1rep",
            input_vars=[BenchableObject.param.float1],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        # Single-dim sweep, 2 repeats, 1 result var (has repeat-based _std)
        cls.res_1d_2rep = cls.bench.plot_sweep(
            "agg_1d_2rep",
            input_vars=[BenchableObject.param.float1],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=2),
            plot_callbacks=False,
        )

        # Single-dim sweep, 1 repeat, 2 result vars
        cls.res_1d_multi = cls.bench.plot_sweep(
            "agg_1d_multi",
            input_vars=[BenchableObject.param.float1],
            result_vars=[BenchableObject.param.distance, BenchableObject.param.sample_noise],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        # 2D sweep (float1 x float2), 1 repeat
        cls.res_2d = cls.bench.plot_sweep(
            "agg_2d",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        # 2D sweep, 2 repeats
        cls.res_2d_2rep = cls.bench.plot_sweep(
            "agg_2d_2rep",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=2),
            plot_callbacks=False,
        )

    # --- mean agg produces _std ---

    def test_mean_agg_produces_std(self):
        ds = self.res_1d_1rep.to_dataset(agg_over_dims=["float1"], agg_fn="mean")
        self.assertIn("distance", ds.data_vars)
        self.assertIn("distance_std", ds.data_vars)

    def test_mean_std_is_non_negative(self):
        ds = self.res_1d_1rep.to_dataset(agg_over_dims=["float1"], agg_fn="mean")
        self.assertTrue((ds["distance_std"].values >= 0).all())

    def test_mean_agg_removes_aggregated_dim(self):
        """The aggregated dimension should no longer appear as a coordinate."""
        ds = self.res_1d_1rep.to_dataset(agg_over_dims=["float1"], agg_fn="mean")
        self.assertNotIn("float1", ds.dims)

    def test_mean_agg_default_fn(self):
        """agg_fn=None should default to mean and produce _std."""
        ds = self.res_1d_1rep.to_dataset(agg_over_dims=["float1"], agg_fn=None)
        self.assertIn("distance_std", ds.data_vars)

    # --- multiple result vars ---

    def test_mean_agg_multiple_result_vars(self):
        """Each result var should get its own _std."""
        ds = self.res_1d_multi.to_dataset(agg_over_dims=["float1"], agg_fn="mean")
        self.assertIn("distance", ds.data_vars)
        self.assertIn("distance_std", ds.data_vars)
        self.assertIn("sample_noise", ds.data_vars)
        self.assertIn("sample_noise_std", ds.data_vars)

    # --- repeat-based _std replacement ---

    def test_mean_agg_replaces_repeat_std(self):
        """Agg std should replace repeat-based std without merge conflict."""
        ds = self.res_1d_2rep.to_dataset(agg_over_dims=["float1"], agg_fn="mean")
        self.assertIn("distance_std", ds.data_vars)
        std_vars = [v for v in ds.data_vars if v.endswith("_std")]
        self.assertEqual(std_vars, ["distance_std"])

    def test_agg_std_differs_from_repeat_std(self):
        """Agg std (across float1 values) should differ from repeat std."""
        ds_repeat_only = self.res_1d_2rep.to_dataset()
        ds_agg = self.res_1d_2rep.to_dataset(agg_over_dims=["float1"], agg_fn="mean")
        # Repeat std is per-float1-point; agg std is across float1 values.
        # They measure different things, so the agg result should be a scalar
        # while repeat result still has the float1 dim.
        self.assertIn("float1", ds_repeat_only.dims)
        self.assertNotIn("float1", ds_agg.dims)

    # --- 2D sweep: partial and full aggregation ---

    def test_2d_agg_one_dim(self):
        """Aggregating one of two dims should keep the other."""
        ds = self.res_2d.to_dataset(agg_over_dims=["float1"], agg_fn="mean")
        self.assertNotIn("float1", ds.dims)
        self.assertIn("float2", ds.dims)
        self.assertIn("distance_std", ds.data_vars)

    def test_2d_agg_both_dims(self):
        """Aggregating both dims should produce a scalar dataset."""
        ds = self.res_2d.to_dataset(agg_over_dims=["float1", "float2"], agg_fn="mean")
        self.assertNotIn("float1", ds.dims)
        self.assertNotIn("float2", ds.dims)
        self.assertIn("distance_std", ds.data_vars)

    def test_2d_agg_with_repeats(self):
        """2D sweep + repeats: agg should replace repeat std cleanly."""
        ds = self.res_2d_2rep.to_dataset(agg_over_dims=["float1", "float2"], agg_fn="mean")
        self.assertIn("distance_std", ds.data_vars)
        std_vars = [v for v in ds.data_vars if v.endswith("_std")]
        self.assertEqual(std_vars, ["distance_std"])

    # --- std correctness: known values ---

    def test_std_value_correctness(self):
        """Verify std is computed from the spread of values, not zero."""
        ds_raw = self.res_1d_1rep.to_dataset()
        ds_agg = self.res_1d_1rep.to_dataset(agg_over_dims=["float1"], agg_fn="mean")
        # Raw dataset has varying distance values across float1
        raw_vals = ds_raw["distance"].values
        if raw_vals.size > 1 and not np.all(raw_vals == raw_vals.flat[0]):
            # If there is any variation, std should be > 0
            self.assertGreater(float(ds_agg["distance_std"].values), 0.0)

    def test_mean_value_correctness(self):
        """Mean in the aggregated dataset should match manual computation."""
        ds_raw = self.res_1d_1rep.to_dataset()
        ds_agg = self.res_1d_1rep.to_dataset(agg_over_dims=["float1"], agg_fn="mean")
        expected_mean = float(ds_raw["distance"].mean(skipna=True).values)
        actual_mean = float(ds_agg["distance"].values)
        np.testing.assert_allclose(actual_mean, expected_mean, rtol=1e-10)

    # --- non-mean aggregations should NOT produce _std ---

    def test_sum_agg_no_std(self):
        ds = self.res_1d_1rep.to_dataset(agg_over_dims=["float1"], agg_fn="sum")
        self.assertNotIn("distance_std", ds.data_vars)

    def test_max_agg_no_std(self):
        ds = self.res_1d_1rep.to_dataset(agg_over_dims=["float1"], agg_fn="max")
        self.assertNotIn("distance_std", ds.data_vars)

    def test_min_agg_no_std(self):
        ds = self.res_1d_1rep.to_dataset(agg_over_dims=["float1"], agg_fn="min")
        self.assertNotIn("distance_std", ds.data_vars)

    def test_median_agg_no_std(self):
        ds = self.res_1d_1rep.to_dataset(agg_over_dims=["float1"], agg_fn="median")
        self.assertNotIn("distance_std", ds.data_vars)

    # --- edge cases ---

    def test_missing_dim_ignored(self):
        """Requesting aggregation over a nonexistent dim should not error."""
        ds = self.res_1d_1rep.to_dataset(agg_over_dims=["nonexistent"], agg_fn="mean")
        # Should return unaggregated dataset (with float1 still present)
        self.assertIn("float1", ds.dims)

    def test_partial_missing_dims(self):
        """Only present dims should be aggregated; missing ones are ignored."""
        ds = self.res_1d_1rep.to_dataset(agg_over_dims=["float1", "nonexistent"], agg_fn="mean")
        self.assertNotIn("float1", ds.dims)
        self.assertIn("distance_std", ds.data_vars)

    def test_no_agg_over_dims_no_std(self):
        """Without agg_over_dims, no extra _std should appear (repeats=1)."""
        ds = self.res_1d_1rep.to_dataset()
        self.assertNotIn("distance_std", ds.data_vars)

    def test_case_insensitive_agg_fn(self):
        """agg_fn should be case-insensitive."""
        ds = self.res_1d_1rep.to_dataset(agg_over_dims=["float1"], agg_fn="MEAN")
        self.assertIn("distance_std", ds.data_vars)


class TestBenchResultBase(unittest.TestCase):
    def test_to_dataset(self):
        bench = BenchableObject().to_bench()

        res_repeat1 = bench.plot_sweep(
            "sweep1repeat",
            input_vars=[BenchableObject.param.float1],
            result_vars=[BenchableObject.param.distance, BenchableObject.param.sample_noise],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        res_repeat2 = bench.plot_sweep(
            "sweep2repeat",
            input_vars=[BenchableObject.param.float1],
            result_vars=[BenchableObject.param.distance, BenchableObject.param.sample_noise],
            run_cfg=bn.BenchRunCfg(repeats=2),
            plot_callbacks=False,
        )

        # print(res_repeat1.to_dataset())
        # print(res_repeat1.to_hv_dataset().data)
        # print(res_repeat1.to_hv_dataset_old().data)

        # print(res_repeat1.to_dataset()["distance"].attrs)

        # print(res_repeat2.to_dataset())
        # print(res_repeat2.to_hv_dataset())
        # print(res_repeat2.to_dataset()["distance"].attrs)

        self.assertEqual(
            res_repeat1.to_dataset()["distance"].attrs, res_repeat2.to_dataset()["distance"].attrs
        )

        # bm.__call__(float_vars=1, sample_with_repeats=1)

    def test_select_level(self):
        bench = TstBench().to_bench()

        res = bench.plot_sweep(
            input_vars=["float_var", "cat_var"],
            run_cfg=bn.BenchRunCfg(level=4),
            plot_callbacks=False,
        )

        def asserts(ds, expected_float, expected_cat):
            np.testing.assert_array_equal(
                ds.coords["float_var"].to_numpy(), np.array(expected_float, dtype=float)
            )
            np.testing.assert_array_equal(ds.coords["cat_var"].to_numpy(), np.array(expected_cat))

        ds_raw = res.to_dataset()
        asserts(ds_raw, [0, 1, 2, 3, 4], ["a", "b", "c", "d", "e"])

        ds_filtered_all = res.select_level(ds_raw, 2)
        asserts(ds_filtered_all, [0, 4], ["a", "e"])

        ds_filtered_types = res.select_level(ds_raw, 2, float)
        asserts(ds_filtered_types, [0, 4], ["a", "b", "c", "d", "e"])

        ds_filtered_names = res.select_level(ds_raw, 2, exclude_names="cat_var")
        asserts(ds_filtered_names, [0, 4], ["a", "b", "c", "d", "e"])

    def _make_1d_result(self, repeats=1):
        bench = BenchableObject().to_bench(bn.BenchRunCfg(repeats=repeats))
        return bench.plot_sweep(
            "test_base",
            input_vars=[BenchableObject.param.float1],
            result_vars=[BenchableObject.param.distance, BenchableObject.param.sample_noise],
            run_cfg=bn.BenchRunCfg(repeats=repeats),
            plot_callbacks=False,
        )

    def test_get_optimal_value_indices(self):
        res = self._make_1d_result()
        rv = res.bench_cfg.result_vars[0]
        da = res.get_optimal_value_indices(rv)
        self.assertIsNotNone(da)
        import xarray as xr

        self.assertIsInstance(da, xr.DataArray)

    def test_get_optimal_vec(self):
        res = self._make_1d_result()
        rv = res.bench_cfg.result_vars[0]
        ivs = res.bench_cfg.input_vars
        vec = res.get_optimal_vec(rv, ivs)
        self.assertIsInstance(vec, list)
        self.assertEqual(len(vec), len(ivs))

    def test_get_optimal_inputs_tuple(self):
        res = self._make_1d_result()
        rv = res.bench_cfg.result_vars[0]
        output = res.get_optimal_inputs(rv)
        self.assertIsInstance(output, list)
        self.assertTrue(len(output) > 0)

    def test_get_optimal_inputs_dict(self):
        res = self._make_1d_result()
        rv = res.bench_cfg.result_vars[0]
        output = res.get_optimal_inputs(rv, as_dict=True)
        self.assertIsInstance(output, dict)

    def test_get_optimal_inputs_no_consts(self):
        res = self._make_1d_result()
        rv = res.bench_cfg.result_vars[0]
        output = res.get_optimal_inputs(rv, keep_existing_consts=False)
        self.assertIsInstance(output, list)

    def test_get_hmap_none(self):
        res = self._make_1d_result()
        # No hmaps stored, should return None
        result = res.get_hmap("nonexistent")
        self.assertIsNone(result)

    def test_to_plot_title(self):
        res = self._make_1d_result()
        title = res.to_plot_title()
        self.assertIsInstance(title, str)
        self.assertIn("distance", title)
        self.assertIn("float1", title)

    def test_to_plot_title_empty(self):
        # Test with no input vars
        bench = BenchableObject().to_bench()
        res = bench.plot_sweep(
            "test_base_empty",
            input_vars=[],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )
        title = res.to_plot_title()
        self.assertEqual(title, "")

    def test_to_dataset_with_result_var_str(self):
        res = self._make_1d_result()
        ds = res.to_dataset(result_var="distance")
        self.assertIn("distance", ds.data_vars)

    def test_to_dataset_with_result_var_param(self):
        res = self._make_1d_result()
        rv = res.bench_cfg.result_vars[0]
        ds = res.to_dataset(result_var=rv)
        self.assertIn("distance", ds.data_vars)

    def test_to_dataset_reduce_none(self):
        res = self._make_1d_result(repeats=2)
        ds = res.to_dataset(reduce=ReduceType.NONE)
        self.assertIn("repeat", ds.dims)

    def test_to_dataset_reduce_minmax(self):
        res = self._make_1d_result(repeats=2)
        ds = res.to_dataset(reduce=ReduceType.MINMAX)
        # Should have mean and range vars
        self.assertIn("distance", ds.data_vars)
        self.assertIn("distance_range", ds.data_vars)

    def test_to_dataset_agg_mean(self):
        res = self._make_1d_result()
        ds = res.to_dataset(agg_over_dims=["float1"], agg_fn="mean")
        self.assertNotIn("float1", ds.dims)

    def test_to_dataset_agg_sum(self):
        res = self._make_1d_result()
        ds = res.to_dataset(agg_over_dims=["float1"], agg_fn="sum")
        self.assertNotIn("float1", ds.dims)

    def test_to_dataset_agg_max(self):
        res = self._make_1d_result()
        ds = res.to_dataset(agg_over_dims=["float1"], agg_fn="max")
        self.assertNotIn("float1", ds.dims)

    def test_to_dataset_agg_min(self):
        res = self._make_1d_result()
        ds = res.to_dataset(agg_over_dims=["float1"], agg_fn="min")
        self.assertNotIn("float1", ds.dims)

    def test_to_dataset_agg_median(self):
        res = self._make_1d_result()
        ds = res.to_dataset(agg_over_dims=["float1"], agg_fn="median")
        self.assertNotIn("float1", ds.dims)

    def test_to_dataset_agg_missing_dim(self):
        res = self._make_1d_result()
        # Aggregate over non-existent dim - should warn and return unaggregated
        ds = res.to_dataset(agg_over_dims=["nonexistent_dim"], agg_fn="mean")
        self.assertIn("float1", ds.dims)

    def test_describe_sweep(self):
        res = self._make_1d_result()
        desc = res.describe_sweep()
        self.assertIsNotNone(desc)

    def test_map_plot_panes(self):
        res = self._make_1d_result()

        def plot_cb(dataset, result_var, **kwargs):
            return pn.pane.Markdown(f"# {result_var.name}")

        result = res.map_plot_panes(plot_cb)
        self.assertIsNotNone(result)

    def test_to_hv_dataset_none_reduce(self):
        from bencher.results.bench_result_base import DatasetWrapper

        res = self._make_1d_result(repeats=2)
        hv_ds = res.to_hv_dataset(ReduceType.NONE)
        self.assertIsInstance(hv_ds, DatasetWrapper)

    def test_to_pandas(self):
        res = self._make_1d_result()
        df = res.to_pandas()
        self.assertIn("distance", df.columns)
        self.assertIn("float1", df.columns)

    def test_to_pandas_no_reset(self):
        res = self._make_1d_result()
        df = res.to_pandas(reset_index=False)
        self.assertIn("distance", df.columns)

    def test_to_xarray(self):
        res = self._make_1d_result()
        ds = res.to_xarray()
        self.assertIn("distance", ds.data_vars)

    def test_set_plot_size(self):
        res = self._make_1d_result()
        res.bench_cfg.plot_size = 500
        kwargs = res.set_plot_size()
        self.assertEqual(kwargs["width"], 500)
        self.assertEqual(kwargs["height"], 500)

    def test_set_plot_size_with_overrides(self):
        res = self._make_1d_result()
        res.bench_cfg.plot_size = 500
        res.bench_cfg.plot_width = 700
        res.bench_cfg.plot_height = 300
        kwargs = res.set_plot_size()
        self.assertEqual(kwargs["width"], 700)
        self.assertEqual(kwargs["height"], 300)

    def test_title_from_ds(self):
        res = self._make_1d_result()
        ds = res.to_dataset()
        rv = res.bench_cfg.result_vars[0]
        title = res.title_from_ds(ds, rv)
        self.assertIsInstance(title, str)

    def test_title_from_ds_override(self):
        res = self._make_1d_result()
        ds = res.to_dataset()
        rv = res.bench_cfg.result_vars[0]
        title = res.title_from_ds(ds, rv, title="Custom Title")
        self.assertEqual(title, "Custom Title")

    def test_title_from_ds_dataarray(self):
        res = self._make_1d_result()
        ds = res.to_dataset()
        da = ds["distance"]
        rv = res.bench_cfg.result_vars[0]
        title = res.title_from_ds(da, rv)
        self.assertIsInstance(title, str)

    def test_to_dataset_mutation_safety(self):
        """Mutating the returned dataset must not affect the source self.ds."""
        res = self._make_1d_result(repeats=2)
        original_values = res.ds["distance"].values.copy()

        for reduce in (ReduceType.REDUCE, ReduceType.MINMAX, ReduceType.SQUEEZE, ReduceType.NONE):
            ds = res.to_dataset(reduce=reduce)
            # Mutate the returned dataset in-place
            for var in ds.data_vars:
                ds[var].values[:] = -999.0
            # Verify source is unaffected
            np.testing.assert_array_equal(
                res.ds["distance"].values,
                original_values,
                err_msg=f"self.ds mutated after to_dataset(reduce={reduce.name})",
            )

    def test_result_samples(self):
        res = self._make_1d_result()
        samples = res.result_samples()
        self.assertIsNotNone(samples)
