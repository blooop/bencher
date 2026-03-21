"""Tests for bencher/results/optuna_result.py"""

import unittest
import numpy as np
import panel as pn
import optuna

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


class TestOptunaResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bench_1 = BenchableObject().to_bench(bch.BenchRunCfg(repeats=1))
        cls.res_1d = bench_1.plot_sweep(
            "test_optuna_1d",
            input_vars=[BenchableObject.param.float1],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bch.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        bench_2 = BenchableObject().to_bench(bch.BenchRunCfg(repeats=1))
        cls.res_2d = bench_2.plot_sweep(
            "test_optuna_2d",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bch.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        bench_r2 = BenchableObject().to_bench(bch.BenchRunCfg(repeats=2))
        cls.res_2d_r2 = bench_r2.plot_sweep(
            "test_optuna_2d_r2",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bch.BenchRunCfg(repeats=2),
            plot_callbacks=False,
        )

        optuna.logging.set_verbosity(optuna.logging.CRITICAL)

    def test_bench_results_to_optuna_trials_with_meta(self):
        trials = self.res_1d.bench_results_to_optuna_trials(include_meta=True)
        self.assertIsInstance(trials, list)
        self.assertGreater(len(trials), 0)
        self.assertIsInstance(trials[0], optuna.trial.FrozenTrial)
        # include_meta=True should include repeat as a trial parameter
        self.assertIn("repeat", trials[0].params)

    def test_bench_results_to_optuna_trials_without_meta(self):
        trials = self.res_1d.bench_results_to_optuna_trials(include_meta=False)
        self.assertIsInstance(trials, list)
        self.assertGreater(len(trials), 0)
        # include_meta=False should NOT include repeat
        self.assertNotIn("repeat", trials[0].params)

    def test_include_meta_true_no_aggregation(self):
        """include_meta=True should produce one trial per raw data point (no aggregation)."""
        trials_meta = self.res_2d_r2.bench_results_to_optuna_trials(include_meta=True)
        trials_no_meta = self.res_2d_r2.bench_results_to_optuna_trials(include_meta=False)
        # With repeats=2, meta trials should have ~2x as many entries
        self.assertGreater(len(trials_meta), len(trials_no_meta))
        # All meta trials should have repeat as a parameter
        for t in trials_meta:
            self.assertIn("repeat", t.params)

    def test_bench_result_to_study(self):
        study = self.res_1d.bench_result_to_study(include_meta=True)
        self.assertIsInstance(study, optuna.Study)
        self.assertGreater(len(study.trials), 0)

    def test_get_best_trial_params(self):
        params = self.res_1d.get_best_trial_params()
        self.assertIsInstance(params, dict)
        self.assertIn("float1", params)

    def test_get_best_trial_params_canonical(self):
        result = self.res_1d.get_best_trial_params(canonical=True)
        self.assertIsNotNone(result)

    def test_collect_optuna_plots_single_result(self):
        plots = self.res_2d.collect_optuna_plots()
        self.assertIsInstance(plots, pn.Row)

    def test_to_optuna_plots(self):
        plots = self.res_2d.to_optuna_plots()
        self.assertIsInstance(plots, pn.Row)

    def test_collect_optuna_plots_with_repeats(self):
        plots = self.res_2d_r2.collect_optuna_plots()
        self.assertIsInstance(plots, pn.Row)


class _AggCfg(bch.ParametrizedSweep):
    algorithm = bch.StringSweep(["algo_a", "algo_b"], optimize=False)
    param1 = bch.FloatSweep(default=0.5, bounds=(0.0, 1.0))
    score = bch.ResultVar(units="score", direction=bch.OptDir.minimize)

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.score = (self.param1 - 0.3) ** 2
        return super().__call__()


class _MultiAggCfg(bch.ParametrizedSweep):
    """Helper config to exercise multi-output aggregation (two ResultVars)."""

    algorithm = bch.StringSweep(["algo_a", "algo_b"], optimize=False)
    param1 = bch.FloatSweep(default=0.5, bounds=(0.0, 1.0))
    score = bch.ResultVar(units="score", direction=bch.OptDir.minimize)
    aux_score = bch.ResultVar(units="aux", direction=bch.OptDir.minimize)

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        baseline = (self.param1 - 0.3) ** 2
        self.score = baseline
        self.aux_score = baseline + 0.1
        return super().__call__()


class _TrialCfg(bch.ParametrizedSweep):
    category = bch.StringSweep(["cat_a", "cat_b"], optimize=False)
    value = bch.FloatSweep(default=0.5, bounds=(0.0, 1.0), samples=3)
    result = bch.ResultVar(units="v", direction=bch.OptDir.minimize)

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.result = self.value * 2
        return super().__call__()


class _AllFalseCfg(bch.ParametrizedSweep):
    x = bch.FloatSweep(default=0.5, bounds=(0.0, 1.0), optimize=False)
    result = bch.ResultVar(units="v", direction=bch.OptDir.minimize)

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.result = self.x
        return super().__call__()


class TestOptunaOptimizeFlag(unittest.TestCase):
    """Tests for the optimize=False aggregation behavior in Optuna optimization."""

    @classmethod
    def setUpClass(cls):
        optuna.logging.set_verbosity(optuna.logging.CRITICAL)

    def test_optimize_false_aggregation(self):
        """Optuna should only suggest optimized vars and aggregate over non-optimized ones."""
        cfg = _AggCfg()
        bench = cfg.to_bench(bch.BenchRunCfg(repeats=1))
        res = bench.plot_sweep(
            "test_agg",
            input_vars=["algorithm", "param1"],
            result_vars=["score"],
            run_cfg=bch.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        study = res.to_optuna_from_results(cfg, n_trials=10)
        self.assertIsInstance(study, optuna.Study)
        self.assertIn("param1", study.best_params)
        self.assertNotIn("algorithm", study.best_params)

        # Verify the objective value matches mean aggregation over algorithms
        # _AggCfg.score = (param1 - 0.3)^2, same for both algorithms, so mean == value
        best_p1 = study.best_params["param1"]
        expected = (best_p1 - 0.3) ** 2
        self.assertAlmostEqual(study.best_value, expected, places=5)

    def test_optimize_false_trials_exclude_non_optimized(self):
        """bench_results_to_optuna_trials should only include optimized vars in trial params
        and aggregate results over non-optimized vars."""
        cfg = _TrialCfg()
        bench = cfg.to_bench(bch.BenchRunCfg(repeats=1))
        res = bench.plot_sweep(
            "test_trials",
            input_vars=["category", "value"],
            result_vars=["result"],
            run_cfg=bch.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        trials = res.bench_results_to_optuna_trials(include_meta=False)
        self.assertGreater(len(trials), 0)
        for trial in trials:
            self.assertNotIn("category", trial.params)
            self.assertIn("value", trial.params)

        # Number of trials should equal unique optimized-param combinations (samples=3)
        unique_values = {t.params["value"] for t in trials}
        self.assertEqual(len(trials), len(unique_values))

        # Each trial's value should be the mean over categories.
        # _TrialCfg.result = value * 2 (same for both categories), so mean == value * 2
        for trial in trials:
            val = trial.params["value"]
            expected_mean = val * 2
            self.assertAlmostEqual(trial.values[0], expected_mean, places=5)

    def test_multi_output_aggregation(self):
        """Multi-output aggregation should average each result var independently."""
        cfg = _MultiAggCfg()
        bench = cfg.to_bench(bch.BenchRunCfg(repeats=1))
        res = bench.plot_sweep(
            "test_multi_agg",
            input_vars=["algorithm", "param1"],
            result_vars=["score", "aux_score"],
            run_cfg=bch.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        study = res.to_optuna_from_results(cfg, n_trials=10)
        # Multi-objective study: use best_trials instead of best_params
        self.assertGreater(len(study.best_trials), 0)
        for trial in study.best_trials:
            self.assertIn("param1", trial.params)
            self.assertNotIn("algorithm", trial.params)

        # Verify both objectives are present in trial values
        for trial in study.trials:
            self.assertEqual(len(trial.values), 2)
            # aux_score should be score + 0.1
            np.testing.assert_almost_equal(trial.values[1], trial.values[0] + 0.1, decimal=5)

    def test_multi_output_trials_aggregation(self):
        """bench_results_to_optuna_trials should aggregate both result vars over non-opt vars."""
        cfg = _MultiAggCfg()
        bench = cfg.to_bench(bch.BenchRunCfg(repeats=1))
        res = bench.plot_sweep(
            "test_multi_trials",
            input_vars=["algorithm", "param1"],
            result_vars=["score", "aux_score"],
            run_cfg=bch.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        trials = res.bench_results_to_optuna_trials(include_meta=False)
        self.assertGreater(len(trials), 0)
        for trial in trials:
            self.assertNotIn("algorithm", trial.params)
            self.assertIn("param1", trial.params)
            self.assertEqual(len(trial.values), 2)
            # aux_score == score + 0.1
            np.testing.assert_almost_equal(trial.values[1], trial.values[0] + 0.1, decimal=5)

    def test_all_optimize_false_raises(self):
        """Should raise ValueError when all input vars have optimize=False."""
        cfg = _AllFalseCfg()
        bench = cfg.to_bench(bch.BenchRunCfg(repeats=1))
        res = bench.plot_sweep(
            "test_all_false",
            input_vars=["x"],
            result_vars=["result"],
            run_cfg=bch.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        with self.assertRaises(ValueError):
            res.to_optuna_from_results(cfg, n_trials=5)

    def test_all_optimize_false_raises_in_trials(self):
        """include_meta=False should raise when all input vars have optimize=False."""
        cfg = _AllFalseCfg()
        bench = cfg.to_bench(bch.BenchRunCfg(repeats=1))
        res = bench.plot_sweep(
            "test_all_false_trials",
            input_vars=["x"],
            result_vars=["result"],
            run_cfg=bch.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        with self.assertRaises(ValueError):
            res.bench_results_to_optuna_trials(include_meta=False)

    def test_all_optimize_false_include_meta_true_succeeds(self):
        """include_meta=True should succeed even when all input vars have optimize=False,
        because importance analysis uses all vars regardless of optimize flag."""
        cfg = _AllFalseCfg()
        bench = cfg.to_bench(bch.BenchRunCfg(repeats=1))
        res = bench.plot_sweep(
            "test_all_false_meta",
            input_vars=["x"],
            result_vars=["result"],
            run_cfg=bch.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        trials = res.bench_results_to_optuna_trials(include_meta=True)
        self.assertGreater(len(trials), 0)
        # x and repeat should both appear as trial params
        self.assertIn("x", trials[0].params)
        self.assertIn("repeat", trials[0].params)
