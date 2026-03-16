"""Tests for bencher/results/optuna_result.py"""

import unittest
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

    def test_bench_results_to_optuna_trials_without_meta(self):
        trials = self.res_1d.bench_results_to_optuna_trials(include_meta=False)
        self.assertIsInstance(trials, list)
        self.assertGreater(len(trials), 0)

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
