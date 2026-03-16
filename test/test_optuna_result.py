"""Tests for bencher/results/optuna_result.py"""

import unittest
import optuna

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def _run_sweep(repeats=1, num_inputs=1):
    bench = BenchableObject().to_bench(bch.BenchRunCfg(repeats=repeats))
    input_vars = [BenchableObject.param.float1]
    if num_inputs >= 2:
        input_vars.append(BenchableObject.param.float2)
    return bench.plot_sweep(
        "test_optuna_res",
        input_vars=input_vars,
        result_vars=[BenchableObject.param.distance],
        run_cfg=bch.BenchRunCfg(repeats=repeats),
        plot_callbacks=False,
    )


class TestBenchResultsToOptunaTrials(unittest.TestCase):
    def test_bench_results_to_optuna_trials_with_meta(self):
        res = _run_sweep()
        trials = res.bench_results_to_optuna_trials(include_meta=True)
        self.assertIsInstance(trials, list)
        self.assertTrue(len(trials) > 0)
        self.assertIsInstance(trials[0], optuna.trial.FrozenTrial)

    def test_bench_results_to_optuna_trials_without_meta(self):
        res = _run_sweep()
        trials = res.bench_results_to_optuna_trials(include_meta=False)
        self.assertIsInstance(trials, list)
        self.assertTrue(len(trials) > 0)


class TestBenchResultToStudy(unittest.TestCase):
    def test_bench_result_to_study(self):
        res = _run_sweep()
        study = res.bench_result_to_study(include_meta=True)
        self.assertIsInstance(study, optuna.Study)
        self.assertTrue(len(study.trials) > 0)


class TestGetBestTrialParams(unittest.TestCase):
    def test_get_best_trial_params(self):
        res = _run_sweep()
        params = res.get_best_trial_params()
        self.assertIsInstance(params, dict)
        self.assertIn("float1", params)

    def test_get_best_trial_params_canonical(self):
        res = _run_sweep()
        result = res.get_best_trial_params(canonical=True)
        self.assertIsNotNone(result)


class TestCollectOptunaPlots(unittest.TestCase):
    def test_collect_optuna_plots_single_result(self):
        res = _run_sweep(num_inputs=2)
        optuna.logging.set_verbosity(optuna.logging.CRITICAL)
        plots = res.collect_optuna_plots()
        self.assertIsNotNone(plots)

    def test_to_optuna_plots(self):
        res = _run_sweep(num_inputs=2)
        optuna.logging.set_verbosity(optuna.logging.CRITICAL)
        plots = res.to_optuna_plots()
        self.assertIsNotNone(plots)

    def test_collect_optuna_plots_with_repeats(self):
        res = _run_sweep(repeats=2, num_inputs=2)
        optuna.logging.set_verbosity(optuna.logging.CRITICAL)
        plots = res.collect_optuna_plots()
        self.assertIsNotNone(plots)
