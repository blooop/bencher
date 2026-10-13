import unittest

import pytest

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
        assert resolve_aggregate(None, self.vars3) is None

    def test_false_returns_none(self):
        assert resolve_aggregate(False, self.vars3) is None

    # --- True: collapse to 1-D (aggregate all but first) ---

    def test_true_3_keeps_first(self):
        assert resolve_aggregate(True, self.vars3) == ["y", "z"]

    def test_true_2_keeps_first(self):
        assert resolve_aggregate(True, self.vars2) == ["y"]

    def test_true_1_nothing_to_aggregate(self):
        assert resolve_aggregate(True, self.vars1) is None

    def test_true_empty_nothing_to_aggregate(self):
        assert resolve_aggregate(True, self.vars0) is None

    # --- int: last N dims ---

    def test_int_1_of_3(self):
        assert resolve_aggregate(1, self.vars3) == ["z"]

    def test_int_2_of_3(self):
        assert resolve_aggregate(2, self.vars3) == ["y", "z"]

    def test_int_3_of_3(self):
        assert resolve_aggregate(3, self.vars3) == ["x", "y", "z"]

    def test_int_exceeds_length(self):
        with pytest.raises(ValueError, match="aggregate=4 exceeds number of input vars") as cm:
            resolve_aggregate(4, self.vars3)
        assert "aggregate=4 exceeds" in str(cm.value)

    def test_int_zero(self):
        with pytest.raises(ValueError, match="aggregate must be >= 1, got 0") as cm:
            resolve_aggregate(0, self.vars3)
        assert "must be >= 1" in str(cm.value)

    def test_int_negative(self):
        with pytest.raises(ValueError, match="aggregate must be >= 1, got -1") as cm:
            resolve_aggregate(-1, self.vars3)
        assert "must be >= 1" in str(cm.value)

    # --- list[str]: named dims ---

    def test_list_valid_subset(self):
        assert resolve_aggregate(["x", "z"], self.vars3) == ["x", "z"]

    def test_list_all(self):
        assert resolve_aggregate(["x", "y", "z"], self.vars3) == ["x", "y", "z"]

    def test_list_single(self):
        assert resolve_aggregate(["y"], self.vars3) == ["y"]

    def test_list_unknown_name(self):
        with pytest.raises(ValueError, match="aggregate contains unknown input var names") as cm:
            resolve_aggregate(["x", "bogus"], self.vars3)
        assert "unknown input var names" in str(cm.value)

    def test_list_empty(self):
        assert resolve_aggregate([], self.vars3) == []

    def test_list_non_string_elements(self):
        with pytest.raises(TypeError) as cm:
            resolve_aggregate([1, 2], self.vars3)
        assert "aggregate list elements must be str" in str(cm.value)

    def test_list_mixed_elements(self):
        with pytest.raises(TypeError) as cm:
            resolve_aggregate(["x", 42], self.vars3)
        assert "aggregate list elements must be str" in str(cm.value)

    # --- input_var_names=None ---

    def test_true_with_none_input_var_names(self):
        with pytest.raises(ValueError, match="aggregate=True requires input_var_names") as cm:
            resolve_aggregate(True, None)
        assert "requires input_var_names" in str(cm.value)

    def test_int_with_none_input_var_names(self):
        with pytest.raises(ValueError, match="aggregate=<int> requires input_var_names") as cm:
            resolve_aggregate(2, None)
        assert "requires input_var_names" in str(cm.value)

    def test_list_with_none_input_var_names_passes_through(self):
        """When input_var_names is None, list aggregate is returned unvalidated."""
        assert resolve_aggregate(["x", "bogus"], None) == ["x", "bogus"]

    # --- type errors ---

    def test_unsupported_type_string(self):
        with pytest.raises(TypeError):
            resolve_aggregate("x", self.vars3)

    def test_unsupported_type_float(self):
        with pytest.raises(TypeError):
            resolve_aggregate(2.5, self.vars3)


class TestResolveAggregateIntegration(unittest.TestCase):
    """Integration: verify aggregate=True matches explicit dim list via plot_sweep."""

    @classmethod
    def setUpClass(cls):
        import bencher as bn
        from bencher.example.meta.example_meta import BenchableObject

        bench = BenchableObject().to_bench()
        run_cfg = bn.BenchRunCfg(repeats=1, auto_plot=False)

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
        """aggregate=True should resolve to all but the first input dim on BenchCfg."""
        cfg = self.res_agg_true.bench_cfg
        assert cfg.agg_over_dims == ["float2"]

    def test_no_aggregate_has_none(self):
        """Without aggregate, agg_over_dims should be None."""
        cfg = self.res_explicit.bench_cfg
        assert cfg.agg_over_dims is None

    def test_aggregate_int_selects_last_n(self):
        """aggregate=1 should select only the last input dim."""
        import bencher as bn
        from bencher.example.meta.example_meta import BenchableObject

        bench = BenchableObject().to_bench()
        res = bench.plot_sweep(
            "agg_int",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=1, auto_plot=False),
            plot_callbacks=False,
            aggregate=1,
        )
        assert res.bench_cfg.agg_over_dims == ["float2"]

    def test_show_aggregate_plots_false_skips_band_result(self):
        """show_aggregate_plots=False suppresses aggregate section in to_auto_plots."""
        import panel as pn

        import bencher as bn
        from bencher.example.meta.example_meta import BenchableObject

        bench = BenchableObject().to_bench()
        res = bench.plot_sweep(
            "agg_disabled",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=2, auto_plot=False, show_aggregate_plots=False),
            aggregate=True,
        )
        # agg_over_dims is still set on the config
        assert res.bench_cfg.agg_over_dims is not None
        plots = res.to_auto_plots()
        # The "Aggregated View" markdown should not appear
        md_texts = [
            p.object
            for p in plots
            if isinstance(p, pn.pane.Markdown)
            and "Aggregated View" in str(getattr(p, "object", ""))
        ]
        assert len(md_texts) == 0, "Aggregated View section should be suppressed"

    def test_show_aggregate_plots_true_renders_band_result(self):
        """show_aggregate_plots=True (default) renders the aggregate section."""
        import panel as pn

        import bencher as bn
        from bencher.example.meta.example_meta import BenchableObject

        bench = BenchableObject().to_bench()
        res = bench.plot_sweep(
            "agg_enabled",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=2, auto_plot=False),
            aggregate=True,
        )
        plots = res.to_auto_plots()
        md_texts = [
            p.object
            for p in plots
            if isinstance(p, pn.pane.Markdown)
            and "Aggregated View" in str(getattr(p, "object", ""))
        ]
        assert len(md_texts) > 0, "Aggregated View section should be present"
