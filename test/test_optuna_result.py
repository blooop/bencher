"""Tests for bencher/results/optuna_result.py"""

import unittest

import numpy as np
import optuna
import panel as pn
import pytest

import bencher as bn
from bencher.example.meta.example_meta import BenchableObject


class TestOptunaResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bench_1 = BenchableObject().to_bench(bn.BenchRunCfg(repeats=1))
        cls.res_1d = bench_1.plot_sweep(
            "test_optuna_1d",
            input_vars=[BenchableObject.param.float1],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        bench_2 = BenchableObject().to_bench(bn.BenchRunCfg(repeats=1))
        cls.res_2d = bench_2.plot_sweep(
            "test_optuna_2d",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        bench_r2 = BenchableObject().to_bench(bn.BenchRunCfg(repeats=2))
        cls.res_2d_r2 = bench_r2.plot_sweep(
            "test_optuna_2d_r2",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=2),
            plot_callbacks=False,
        )

        optuna.logging.set_verbosity(optuna.logging.CRITICAL)

    def test_bench_results_to_optuna_trials_with_meta(self):
        trials = self.res_1d.bench_results_to_optuna_trials(include_meta=True)
        assert isinstance(trials, list)
        assert len(trials) > 0
        assert isinstance(trials[0], optuna.trial.FrozenTrial)
        # include_meta=True should include repeat as a trial parameter
        assert "repeat" in trials[0].params

    def test_bench_results_to_optuna_trials_without_meta(self):
        trials = self.res_1d.bench_results_to_optuna_trials(include_meta=False)
        assert isinstance(trials, list)
        assert len(trials) > 0
        # include_meta=False should NOT include repeat
        assert "repeat" not in trials[0].params

    def test_include_meta_true_no_aggregation(self):
        """include_meta=True should produce one trial per raw data point (no aggregation)."""
        trials_meta = self.res_2d_r2.bench_results_to_optuna_trials(include_meta=True)
        trials_no_meta = self.res_2d_r2.bench_results_to_optuna_trials(include_meta=False)
        # With repeats=2, meta trials should have ~2x as many entries
        assert len(trials_meta) > len(trials_no_meta)
        # All meta trials should have repeat as a parameter
        for t in trials_meta:
            assert "repeat" in t.params

    def test_bench_result_to_study(self):
        study = self.res_1d.bench_result_to_study(include_meta=True)
        assert isinstance(study, optuna.Study)
        assert len(study.trials) > 0

    def test_get_best_trial_params(self):
        params = self.res_1d.get_best_trial_params()
        assert isinstance(params, dict)
        assert "float1" in params

    def test_get_best_trial_params_canonical(self):
        result = self.res_1d.get_best_trial_params(canonical=True)
        assert result is not None

    def test_collect_optuna_plots_single_result(self):
        plots = self.res_2d.collect_optuna_plots()
        assert isinstance(plots, (pn.Row, pn.Column, pn.Tabs))

    def test_to_optuna_plots(self):
        plots = self.res_2d.to_optuna_plots()
        assert isinstance(plots, (pn.Row, pn.Column, pn.Tabs))

    def test_collect_optuna_plots_with_repeats(self):
        plots = self.res_2d_r2.collect_optuna_plots()
        assert isinstance(plots, pn.Tabs)


class _AggCfg(bn.ParametrizedSweep):
    algorithm = bn.StringSweep(["algo_a", "algo_b"], optimize=False)
    param1 = bn.FloatSweep(default=0.5, bounds=(0.0, 1.0))
    score = bn.ResultFloat(units="score", direction=bn.OptDir.minimize)

    def benchmark(self):
        self.score = (self.param1 - 0.3) ** 2


class _MultiAggCfg(bn.ParametrizedSweep):
    """Helper config to exercise multi-output aggregation (two ResultFloats)."""

    algorithm = bn.StringSweep(["algo_a", "algo_b"], optimize=False)
    param1 = bn.FloatSweep(default=0.5, bounds=(0.0, 1.0))
    score = bn.ResultFloat(units="score", direction=bn.OptDir.minimize)
    aux_score = bn.ResultFloat(units="aux", direction=bn.OptDir.minimize)

    def benchmark(self):
        baseline = (self.param1 - 0.3) ** 2
        self.score = baseline
        self.aux_score = baseline + 0.1


class _TrialCfg(bn.ParametrizedSweep):
    category = bn.StringSweep(["cat_a", "cat_b"], optimize=False)
    value = bn.FloatSweep(default=0.5, bounds=(0.0, 1.0), samples=3)
    result = bn.ResultFloat(units="v", direction=bn.OptDir.minimize)

    def benchmark(self):
        self.result = self.value * 2


class _AllFalseCfg(bn.ParametrizedSweep):
    x = bn.FloatSweep(default=0.5, bounds=(0.0, 1.0), optimize=False)
    result = bn.ResultFloat(units="v", direction=bn.OptDir.minimize)

    def benchmark(self):
        self.result = self.x


class TestOptunaOptimizeFlag(unittest.TestCase):
    """Tests for the optimize=False aggregation behavior in Optuna optimization."""

    @classmethod
    def setUpClass(cls):
        optuna.logging.set_verbosity(optuna.logging.CRITICAL)

    def test_optimize_false_aggregation(self):
        """Optuna should only suggest optimized vars and aggregate over non-optimized ones."""
        cfg = _AggCfg()
        bench = cfg.to_bench(bn.BenchRunCfg(repeats=1))
        res = bench.plot_sweep(
            "test_agg",
            input_vars=["algorithm", "param1"],
            result_vars=["score"],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        study = res.to_optuna_from_results(cfg, n_trials=10)
        assert isinstance(study, optuna.Study)
        assert "param1" in study.best_params
        assert "algorithm" not in study.best_params

        # Verify the objective value matches mean aggregation over algorithms
        # _AggCfg.score = (param1 - 0.3)^2, same for both algorithms, so mean == value
        best_p1 = study.best_params["param1"]
        expected = (best_p1 - 0.3) ** 2
        self.assertAlmostEqual(study.best_value, expected, places=5)

    def test_optimize_false_trials_exclude_non_optimized(self):
        """bench_results_to_optuna_trials should only include optimized vars in trial params
        and aggregate results over non-optimized vars."""
        cfg = _TrialCfg()
        bench = cfg.to_bench(bn.BenchRunCfg(repeats=1))
        res = bench.plot_sweep(
            "test_trials",
            input_vars=["category", "value"],
            result_vars=["result"],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        trials = res.bench_results_to_optuna_trials(include_meta=False)
        assert len(trials) > 0
        for trial in trials:
            assert "category" not in trial.params
            assert "value" in trial.params

        # Number of trials should equal unique optimized-param combinations (samples=3)
        unique_values = {t.params["value"] for t in trials}
        assert len(trials) == len(unique_values)

        # Each trial's value should be the mean over categories.
        # _TrialCfg.result = value * 2 (same for both categories), so mean == value * 2
        for trial in trials:
            val = trial.params["value"]
            expected_mean = val * 2
            self.assertAlmostEqual(trial.values[0], expected_mean, places=5)

    def test_multi_output_aggregation(self):
        """Multi-output aggregation should average each result var independently."""
        cfg = _MultiAggCfg()
        bench = cfg.to_bench(bn.BenchRunCfg(repeats=1))
        res = bench.plot_sweep(
            "test_multi_agg",
            input_vars=["algorithm", "param1"],
            result_vars=["score", "aux_score"],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        study = res.to_optuna_from_results(cfg, n_trials=10)
        # Multi-objective study: use best_trials instead of best_params
        assert len(study.best_trials) > 0
        for trial in study.best_trials:
            assert "param1" in trial.params
            assert "algorithm" not in trial.params

        # Verify both objectives are present in trial values
        for trial in study.trials:
            assert len(trial.values) == 2
            # aux_score should be score + 0.1
            np.testing.assert_almost_equal(trial.values[1], trial.values[0] + 0.1, decimal=5)

    def test_multi_output_trials_aggregation(self):
        """bench_results_to_optuna_trials should aggregate both result vars over non-opt vars."""
        cfg = _MultiAggCfg()
        bench = cfg.to_bench(bn.BenchRunCfg(repeats=1))
        res = bench.plot_sweep(
            "test_multi_trials",
            input_vars=["algorithm", "param1"],
            result_vars=["score", "aux_score"],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        trials = res.bench_results_to_optuna_trials(include_meta=False)
        assert len(trials) > 0
        for trial in trials:
            assert "algorithm" not in trial.params
            assert "param1" in trial.params
            assert len(trial.values) == 2
            # aux_score == score + 0.1
            np.testing.assert_almost_equal(trial.values[1], trial.values[0] + 0.1, decimal=5)

    def test_all_optimize_false_raises(self):
        """Should raise ValueError when all input vars have optimize=False."""
        cfg = _AllFalseCfg()
        bench = cfg.to_bench(bn.BenchRunCfg(repeats=1))
        res = bench.plot_sweep(
            "test_all_false",
            input_vars=["x"],
            result_vars=["result"],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        with pytest.raises(ValueError):
            res.to_optuna_from_results(cfg, n_trials=5)

    def test_all_optimize_false_raises_in_trials(self):
        """include_meta=False should raise when all input vars have optimize=False."""
        cfg = _AllFalseCfg()
        bench = cfg.to_bench(bn.BenchRunCfg(repeats=1))
        res = bench.plot_sweep(
            "test_all_false_trials",
            input_vars=["x"],
            result_vars=["result"],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        with pytest.raises(ValueError):
            res.bench_results_to_optuna_trials(include_meta=False)

    def test_all_optimize_false_include_meta_true_succeeds(self):
        """include_meta=True should succeed even when all input vars have optimize=False,
        because importance analysis uses all vars regardless of optimize flag."""
        cfg = _AllFalseCfg()
        bench = cfg.to_bench(bn.BenchRunCfg(repeats=1))
        res = bench.plot_sweep(
            "test_all_false_meta",
            input_vars=["x"],
            result_vars=["result"],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        trials = res.bench_results_to_optuna_trials(include_meta=True)
        assert len(trials) > 0
        # x and repeat should both appear as trial params
        assert "x" in trials[0].params
        assert "repeat" in trials[0].params


class TestOptunaReportRouting(unittest.TestCase):
    """Verify that optuna plots land in the correct report tab for each sweep."""

    @classmethod
    def setUpClass(cls):
        optuna.logging.set_verbosity(optuna.logging.CRITICAL)

    def test_optuna_plots_per_sweep_tab(self):
        """Each sweep's optuna plots must appear in its own tab, not the last tab."""
        cfg = BenchableObject()
        bench = cfg.to_bench(bn.BenchRunCfg(repeats=1))

        bench.plot_sweep(
            "sweep_A",
            input_vars=[BenchableObject.param.float1],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=1),
        )
        bench.plot_sweep(
            "sweep_B",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=1),
        )

        assert len(bench.results) == 2
        assert len(bench.report.pane) == 2

        items_before = [len(bench.report.pane[i].objects) for i in range(2)]

        # Append optuna plots using append_to_result
        for res in bench.results:
            bench.report.append_to_result(res, res.to_optuna_plots())

        # Each tab should have grown by exactly one item
        for i in range(2):
            assert len(bench.report.pane[i].objects) == items_before[i] + 1, (
                f"Tab {i} should have exactly one new optuna pane"
            )

    def test_optimize_routes_plots_to_correct_tabs(self):
        """bench.optimize(plot=True) routes optuna plots to matching sweep tabs."""
        cfg = BenchableObject()
        bench = cfg.to_bench(bn.BenchRunCfg(repeats=1))

        bench.plot_sweep(
            "sweep_A",
            input_vars=[BenchableObject.param.float1],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=1),
        )
        bench.plot_sweep(
            "sweep_B",
            input_vars=[BenchableObject.param.float1],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=1),
        )

        items_before = [len(bench.report.pane[i].objects) for i in range(2)]

        bench.optimize(n_trials=5, plot=True)

        # Both tabs should have gained optuna content
        for i in range(2):
            assert len(bench.report.pane[i].objects) > items_before[i], (
                f"Tab {i} should have optuna content after optimize(plot=True)"
            )
