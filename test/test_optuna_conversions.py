"""Tests for bencher/optuna_conversions.py"""

import unittest
from unittest.mock import MagicMock
from enum import auto
from strenum import StrEnum

import optuna
import panel as pn
import param

import bencher as bch
from bencher.optuna_conversions import (
    sweep_var_to_optuna_dist,
    sweep_var_to_suggest,
    summarise_optuna_study,
    summarise_trial,
    optuna_grid_search,
)
from bencher.variables.inputs import IntSweep, FloatSweep, StringSweep, EnumSweep, BoolSweep
from bencher.variables.time import TimeSnapshot


class SweepColor(StrEnum):
    red = auto()
    blue = auto()


class SweepCfg(bch.ParametrizedSweep):
    int_var = IntSweep(default=1, bounds=(0, 10))
    float_var = FloatSweep(default=0.5, bounds=(0.0, 1.0))
    enum_var = EnumSweep(SweepColor)
    bool_var = BoolSweep(default=True)
    string_var = StringSweep(["a", "b", "c"])
    result = bch.ResultVar()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.result = self.float_var * 2
        return super().__call__()


class TestOptimizeFlag(unittest.TestCase):
    """Tests for the optimize flag on sweep variables."""

    def test_default_optimize_true_for_input_types(self):
        self.assertTrue(SweepCfg.param.int_var.optimize)
        self.assertTrue(SweepCfg.param.float_var.optimize)
        self.assertTrue(SweepCfg.param.enum_var.optimize)
        self.assertTrue(SweepCfg.param.bool_var.optimize)
        self.assertTrue(SweepCfg.param.string_var.optimize)

    def test_default_optimize_false_for_time_types(self):
        from datetime import datetime

        ts = TimeSnapshot(datetime_src=datetime.now())
        self.assertFalse(ts.optimize)

        from bencher.variables.time import TimeEvent

        te = TimeEvent(time_event="ev1")
        self.assertFalse(te.optimize)

    def test_explicit_optimize_false(self):
        f = FloatSweep(default=0.5, bounds=(0.0, 1.0), optimize=False)
        self.assertFalse(f.optimize)
        i = IntSweep(default=1, bounds=(0, 10), optimize=False)
        self.assertFalse(i.optimize)
        s = StringSweep(["a", "b"], optimize=False)
        self.assertFalse(s.optimize)
        e = EnumSweep(SweepColor, optimize=False)
        self.assertFalse(e.optimize)
        b = BoolSweep(optimize=False)
        self.assertFalse(b.optimize)

    def test_deepcopy_preserves_flag(self):
        from copy import deepcopy

        f = FloatSweep(default=0.5, bounds=(0.0, 1.0), optimize=False)
        f_copy = deepcopy(f)
        self.assertFalse(f_copy.optimize)

    def test_with_samples_preserves_flag(self):
        f = FloatSweep(default=0.5, bounds=(0.0, 1.0), optimize=False)
        f2 = f.with_samples(5)
        self.assertFalse(f2.optimize)

    def test_yaml_sweep_optimize_default_and_override(self):
        from pathlib import Path
        from bencher.variables.inputs import YamlSweep

        yaml_path = (
            Path(__file__).resolve().parent.parent / "bencher/example/example_yaml_sweep_list.yaml"
        )
        default_yaml = YamlSweep(yaml_path)
        self.assertTrue(default_yaml.optimize)

        disabled_yaml = YamlSweep(yaml_path, optimize=False)
        self.assertFalse(disabled_yaml.optimize)

    def test_selector_sweep_deepcopy_and_with_samples(self):
        from copy import deepcopy

        s = StringSweep(["a", "b", "c"], optimize=False)
        s_copy = deepcopy(s)
        self.assertFalse(s_copy.optimize)

        s_sampled = s.with_samples(2)
        self.assertFalse(s_sampled.optimize)

        e = EnumSweep(SweepColor, optimize=False)
        e_copy = deepcopy(e)
        self.assertFalse(e_copy.optimize)

        b = BoolSweep(optimize=False)
        b_copy = deepcopy(b)
        self.assertFalse(b_copy.optimize)


class TestSweepVarToOptunaDist(unittest.TestCase):
    def test_int_sweep(self):
        var = SweepCfg.param.int_var
        dist = sweep_var_to_optuna_dist(var)
        self.assertIsInstance(dist, optuna.distributions.IntDistribution)
        self.assertEqual(dist.low, 0)
        self.assertEqual(dist.high, 10)

    def test_float_sweep(self):
        var = SweepCfg.param.float_var
        dist = sweep_var_to_optuna_dist(var)
        self.assertIsInstance(dist, optuna.distributions.FloatDistribution)
        self.assertAlmostEqual(dist.low, 0.0)
        self.assertAlmostEqual(dist.high, 1.0)

    def test_enum_sweep(self):
        var = SweepCfg.param.enum_var
        dist = sweep_var_to_optuna_dist(var)
        self.assertIsInstance(dist, optuna.distributions.CategoricalDistribution)

    def test_bool_sweep(self):
        var = SweepCfg.param.bool_var
        dist = sweep_var_to_optuna_dist(var)
        self.assertIsInstance(dist, optuna.distributions.CategoricalDistribution)
        self.assertEqual(dist.choices, (False, True))

    def test_string_sweep(self):
        var = SweepCfg.param.string_var
        dist = sweep_var_to_optuna_dist(var)
        self.assertIsInstance(dist, optuna.distributions.CategoricalDistribution)

    def test_time_snapshot(self):
        from datetime import datetime

        ts = TimeSnapshot(datetime_src=datetime.now())
        dist = sweep_var_to_optuna_dist(ts)
        self.assertIsInstance(dist, optuna.distributions.FloatDistribution)

    def test_unsupported_type(self):
        # A plain param.Parameter is not supported
        var = param.Parameter()
        with self.assertRaises(ValueError):
            sweep_var_to_optuna_dist(var)


class TestSweepVarToSuggest(unittest.TestCase):
    def test_int_suggest(self):
        trial = MagicMock()
        trial.suggest_int.return_value = 5
        var = SweepCfg.param.int_var
        result = sweep_var_to_suggest(var, trial)
        self.assertEqual(result, 5)
        trial.suggest_int.assert_called_once()

    def test_float_suggest(self):
        trial = MagicMock()
        trial.suggest_float.return_value = 0.5
        var = SweepCfg.param.float_var
        result = sweep_var_to_suggest(var, trial)
        self.assertEqual(result, 0.5)

    def test_enum_suggest(self):
        trial = MagicMock()
        trial.suggest_categorical.return_value = SweepColor.red
        var = SweepCfg.param.enum_var
        result = sweep_var_to_suggest(var, trial)
        self.assertEqual(result, SweepColor.red)

    def test_bool_suggest(self):
        trial = MagicMock()
        trial.suggest_categorical.return_value = True
        var = SweepCfg.param.bool_var
        result = sweep_var_to_suggest(var, trial)
        self.assertTrue(result)

    def test_string_suggest(self):
        trial = MagicMock()
        trial.suggest_categorical.return_value = "a"
        var = SweepCfg.param.string_var
        result = sweep_var_to_suggest(var, trial)
        self.assertEqual(result, "a")

    def test_unsupported_type(self):
        trial = MagicMock()
        var = param.Parameter()
        with self.assertRaises(ValueError):
            sweep_var_to_suggest(var, trial)


class TestCfgFromOptunaTrial(unittest.TestCase):
    def test_creates_config(self):
        # cfg_from_optuna_trial uses param.set_param which may not exist
        # in newer param versions, so we test via the full optuna pipeline
        # (bench_result_to_study) rather than calling it directly.
        bench = SweepCfg().to_bench()
        res = bench.plot_sweep(
            "test_optuna",
            input_vars=["float_var"],
            result_vars=["result"],
            run_cfg=bch.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )
        # Verify the study can be created from bench results
        study = res.bench_result_to_study(include_meta=True)
        self.assertIsInstance(study, optuna.Study)
        self.assertTrue(len(study.trials) > 0)


class TestSummariseOptunaStudy(unittest.TestCase):
    def test_summarise_study(self):
        study = optuna.create_study(direction="minimize")
        study.optimize(lambda trial: trial.suggest_float("x", 0, 1) ** 2, n_trials=5)
        result = summarise_optuna_study(study)
        self.assertIsInstance(result, pn.Column)
        self.assertTrue(len(result) > 0)


class TestSummariseTrial(unittest.TestCase):
    def test_summarise_trial(self):
        bench = SweepCfg().to_bench()
        res = bench.plot_sweep(
            "test",
            input_vars=["float_var"],
            result_vars=["result"],
            run_cfg=bch.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        study = optuna.create_study(direction="minimize")
        study.optimize(lambda trial: trial.suggest_float("float_var", 0, 1), n_trials=3)
        trial = study.best_trial
        output = summarise_trial(trial, res.bench_cfg)
        self.assertIsInstance(output, list)
        self.assertTrue(len(output) > 0)
        self.assertIn("Trial id:", output[0])


class TestOptunaGridSearch(unittest.TestCase):
    def test_default_excludes_optimize_false(self):
        bench = SweepCfg().to_bench()
        res = bench.plot_sweep(
            "test_grid",
            input_vars=["float_var"],
            result_vars=["result"],
            run_cfg=bch.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )
        study = optuna_grid_search(res.bench_cfg)
        # repeat has optimize=False, should not be in search space
        search_space = study.sampler._search_space  # pylint: disable=protected-access
        self.assertNotIn("repeat", search_space)

    def test_trial_vars_includes_all(self):
        bench = SweepCfg().to_bench()
        res = bench.plot_sweep(
            "test_grid_vars",
            input_vars=["float_var"],
            result_vars=["result"],
            run_cfg=bch.BenchRunCfg(repeats=2),
            plot_callbacks=False,
        )
        trial_vars = list(res.bench_cfg.all_vars)
        study = optuna_grid_search(res.bench_cfg, trial_vars=trial_vars)
        # When trial_vars provided, all vars should be in search space
        search_space = study.sampler._search_space  # pylint: disable=protected-access
        self.assertIn("repeat", search_space)
        self.assertIn("float_var", search_space)
