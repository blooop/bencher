import unittest

from bencher.utils import resolve_aggregate


class TestResolveAggregate(unittest.TestCase):
    """Unit tests for the resolve_aggregate helper."""

    def setUp(self):
        self.vars3 = ["x", "y", "z"]
        self.vars2 = ["x", "y"]
        self.vars1 = ["x"]
        self.vars0 = []

    # --- None / False: no aggregation ---

    def test_none_returns_none(self):
        self.assertIsNone(resolve_aggregate(None, self.vars3))

    def test_false_returns_none(self):
        self.assertIsNone(resolve_aggregate(False, self.vars3))

    # --- True: aggregate all ---

    def test_true_all_3(self):
        self.assertEqual(resolve_aggregate(True, self.vars3), ["x", "y", "z"])

    def test_true_all_2(self):
        self.assertEqual(resolve_aggregate(True, self.vars2), ["x", "y"])

    def test_true_all_1(self):
        self.assertEqual(resolve_aggregate(True, self.vars1), ["x"])

    def test_true_empty(self):
        self.assertEqual(resolve_aggregate(True, self.vars0), [])

    # --- int: last N dims ---

    def test_int_1_of_3(self):
        self.assertEqual(resolve_aggregate(1, self.vars3), ["z"])

    def test_int_2_of_3(self):
        self.assertEqual(resolve_aggregate(2, self.vars3), ["y", "z"])

    def test_int_3_of_3(self):
        self.assertEqual(resolve_aggregate(3, self.vars3), ["x", "y", "z"])

    def test_int_exceeds_length(self):
        with self.assertRaises(ValueError, msg="aggregate=4 exceeds"):
            resolve_aggregate(4, self.vars3)

    def test_int_zero(self):
        with self.assertRaises(ValueError, msg="must be >= 1"):
            resolve_aggregate(0, self.vars3)

    def test_int_negative(self):
        with self.assertRaises(ValueError, msg="must be >= 1"):
            resolve_aggregate(-1, self.vars3)

    # --- list[str]: named dims ---

    def test_list_valid_subset(self):
        self.assertEqual(resolve_aggregate(["x", "z"], self.vars3), ["x", "z"])

    def test_list_all(self):
        self.assertEqual(resolve_aggregate(["x", "y", "z"], self.vars3), ["x", "y", "z"])

    def test_list_single(self):
        self.assertEqual(resolve_aggregate(["y"], self.vars3), ["y"])

    def test_list_unknown_name(self):
        with self.assertRaises(ValueError, msg="unknown input var names"):
            resolve_aggregate(["x", "bogus"], self.vars3)

    def test_list_empty(self):
        self.assertEqual(resolve_aggregate([], self.vars3), [])

    # --- type errors ---

    def test_unsupported_type_string(self):
        with self.assertRaises(TypeError):
            resolve_aggregate("x", self.vars3)

    def test_unsupported_type_float(self):
        with self.assertRaises(TypeError):
            resolve_aggregate(2.5, self.vars3)


class TestResolveAggregateIntegration(unittest.TestCase):
    """Integration: verify aggregate=True matches explicit dim list via plot_sweep."""

    @classmethod
    def setUpClass(cls):
        import bencher as bch
        from bencher.example.meta.example_meta import BenchableObject

        bench = BenchableObject().to_bench()
        run_cfg = bch.BenchRunCfg(repeats=1, auto_plot=False)

        cls.res_explicit = bench.plot_sweep(
            "agg_explicit",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=run_cfg,
            plot_callbacks=False,
        )
        cls.res_agg_true = bench.plot_sweep(
            "agg_true",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=run_cfg,
            plot_callbacks=False,
            aggregate=True,
        )

    def test_aggregate_true_sets_agg_over_dims(self):
        """aggregate=True should resolve to all input dim names on BenchCfg."""
        cfg = self.res_agg_true.bench_cfg
        self.assertEqual(cfg.agg_over_dims, ["float1", "float2"])

    def test_no_aggregate_has_none(self):
        """Without aggregate, agg_over_dims should be None."""
        cfg = self.res_explicit.bench_cfg
        self.assertIsNone(cfg.agg_over_dims)

    def test_aggregate_int_selects_last_n(self):
        """aggregate=1 should select only the last input dim."""
        import bencher as bch
        from bencher.example.meta.example_meta import BenchableObject

        bench = BenchableObject().to_bench()
        res = bench.plot_sweep(
            "agg_int",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bch.BenchRunCfg(repeats=1, auto_plot=False),
            plot_callbacks=False,
            aggregate=1,
        )
        self.assertEqual(res.bench_cfg.agg_over_dims, ["float2"])
