"""Tests for bencher/optuna_conversions.py"""

import unittest
import warnings
from enum import auto
from unittest.mock import MagicMock

import optuna
import panel as pn
import param
import pytest
from strenum import StrEnum

import bencher as bn
from bencher.optuna_conversions import (
    _append_safe,
    _append_safe_sized,
    optuna_grid_search,
    param_importance,
    summarise_trial,
    sweep_var_to_optuna_dist,
    sweep_var_to_suggest,
)
from bencher.variables.inputs import BoolSweep, EnumSweep, FloatSweep, IntSweep, StringSweep
from bencher.variables.time import TimeSnapshot


class SweepColor(StrEnum):
    red = auto()
    blue = auto()


class SweepCfg(bn.ParametrizedSweep):
    int_var = IntSweep(default=1, bounds=(0, 10))
    float_var = FloatSweep(default=0.5, bounds=(0.0, 1.0))
    enum_var = EnumSweep(SweepColor)
    bool_var = BoolSweep(default=True)
    string_var = StringSweep(["a", "b", "c"])
    result = bn.ResultFloat()

    def benchmark(self):
        self.result = self.float_var * 2


class TestOptimizeFlag(unittest.TestCase):
    """Tests for the optimize flag on sweep variables."""

    def test_default_optimize_true_for_input_types(self):
        assert SweepCfg.param.int_var.optimize
        assert SweepCfg.param.float_var.optimize
        assert SweepCfg.param.enum_var.optimize
        assert SweepCfg.param.bool_var.optimize
        assert SweepCfg.param.string_var.optimize

    def test_default_optimize_false_for_time_types(self):
        from datetime import datetime

        ts = TimeSnapshot(datetime_src=datetime.now())
        assert not ts.optimize

        from bencher.variables.time import TimeEvent

        time_ev = TimeEvent(time_event="ev1")
        assert not time_ev.optimize

    def test_explicit_optimize_false(self):
        f = FloatSweep(default=0.5, bounds=(0.0, 1.0), optimize=False)
        assert not f.optimize
        i = IntSweep(default=1, bounds=(0, 10), optimize=False)
        assert not i.optimize
        s = StringSweep(["a", "b"], optimize=False)
        assert not s.optimize
        e = EnumSweep(SweepColor, optimize=False)
        assert not e.optimize
        b = BoolSweep(optimize=False)
        assert not b.optimize

    def test_deepcopy_preserves_flag(self):
        from copy import deepcopy

        f = FloatSweep(default=0.5, bounds=(0.0, 1.0), optimize=False)
        f_copy = deepcopy(f)
        assert not f_copy.optimize

    def test_with_samples_preserves_flag(self):
        f = FloatSweep(default=0.5, bounds=(0.0, 1.0), optimize=False)
        f2 = f.with_samples(5)
        assert not f2.optimize

    def test_yaml_sweep_optimize_default_and_override(self):
        from pathlib import Path

        from bencher.variables.inputs import YamlSweep

        yaml_path = Path(__file__).resolve().parent.parent / "bencher/example/yaml_sweep_list.yaml"
        default_yaml = YamlSweep(yaml_path)
        assert default_yaml.optimize

        disabled_yaml = YamlSweep(yaml_path, optimize=False)
        assert not disabled_yaml.optimize

    def test_selector_sweep_deepcopy_and_with_samples(self):
        from copy import deepcopy

        s = StringSweep(["a", "b", "c"], optimize=False)
        s_copy = deepcopy(s)
        assert not s_copy.optimize

        s_sampled = s.with_samples(2)
        assert not s_sampled.optimize

        e = EnumSweep(SweepColor, optimize=False)
        e_copy = deepcopy(e)
        assert not e_copy.optimize

        b = BoolSweep(optimize=False)
        b_copy = deepcopy(b)
        assert not b_copy.optimize


class TestSweepVarToOptunaDist(unittest.TestCase):
    def test_int_sweep(self):
        var = SweepCfg.param.int_var
        dist = sweep_var_to_optuna_dist(var)
        assert isinstance(dist, optuna.distributions.IntDistribution)
        assert dist.low == 0
        assert dist.high == 10

    def test_float_sweep(self):
        var = SweepCfg.param.float_var
        dist = sweep_var_to_optuna_dist(var)
        assert isinstance(dist, optuna.distributions.FloatDistribution)
        assert dist.low == pytest.approx(0.0, abs=1e-7)
        assert dist.high == pytest.approx(1.0, abs=1e-7)

    def test_enum_sweep(self):
        var = SweepCfg.param.enum_var
        dist = sweep_var_to_optuna_dist(var)
        assert isinstance(dist, optuna.distributions.CategoricalDistribution)

    def test_bool_sweep(self):
        var = SweepCfg.param.bool_var
        dist = sweep_var_to_optuna_dist(var)
        assert isinstance(dist, optuna.distributions.CategoricalDistribution)
        assert dist.choices == (False, True)

    def test_string_sweep(self):
        var = SweepCfg.param.string_var
        dist = sweep_var_to_optuna_dist(var)
        assert isinstance(dist, optuna.distributions.CategoricalDistribution)

    def test_time_snapshot(self):
        from datetime import datetime

        ts = TimeSnapshot(datetime_src=datetime.now())
        dist = sweep_var_to_optuna_dist(ts)
        assert isinstance(dist, optuna.distributions.FloatDistribution)

    def test_unsupported_type(self):
        # A plain param.Parameter is not supported
        var = param.Parameter()
        with pytest.raises(ValueError, match="is not supported"):
            sweep_var_to_optuna_dist(var)


class TestSweepVarToSuggest(unittest.TestCase):
    def test_int_suggest(self):
        trial = MagicMock()
        trial.suggest_int.return_value = 5
        var = SweepCfg.param.int_var
        result = sweep_var_to_suggest(var, trial)
        assert result == 5
        trial.suggest_int.assert_called_once()

    def test_float_suggest(self):
        trial = MagicMock()
        trial.suggest_float.return_value = 0.5
        var = SweepCfg.param.float_var
        result = sweep_var_to_suggest(var, trial)
        assert result == 0.5

    def test_enum_suggest(self):
        trial = MagicMock()
        trial.suggest_categorical.return_value = SweepColor.red
        var = SweepCfg.param.enum_var
        result = sweep_var_to_suggest(var, trial)
        assert result == SweepColor.red

    def test_bool_suggest(self):
        trial = MagicMock()
        trial.suggest_categorical.return_value = True
        var = SweepCfg.param.bool_var
        result = sweep_var_to_suggest(var, trial)
        assert result

    def test_string_suggest(self):
        trial = MagicMock()
        trial.suggest_categorical.return_value = "a"
        var = SweepCfg.param.string_var
        result = sweep_var_to_suggest(var, trial)
        assert result == "a"

    def test_unsupported_type(self):
        trial = MagicMock()
        var = param.Parameter()
        with pytest.raises(ValueError, match="is not supported"):
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
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )
        # Verify the study can be created from bench results
        study = res.bench_result_to_study(include_meta=True)
        assert isinstance(study, optuna.Study)
        assert len(study.trials) > 0


class TestParamImportance(unittest.TestCase):
    def test_param_importance(self):
        bench = SweepCfg().to_bench()
        res = bench.plot_sweep(
            "test_importance",
            input_vars=["float_var"],
            result_vars=["result"],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )
        study = res.bench_result_to_study(include_meta=True)
        result = param_importance(res.bench_cfg, study)
        assert isinstance(result, pn.Column)
        assert len(result) > 0

    def test_param_importance_with_width(self):
        bench = SweepCfg().to_bench()
        res = bench.plot_sweep(
            "test_importance_w",
            input_vars=["float_var"],
            result_vars=["result"],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )
        study = res.bench_result_to_study(include_meta=True)
        result = param_importance(res.bench_cfg, study, plot_width=500)
        assert isinstance(result, pn.Column)
        assert len(result) > 0


class TestSummariseTrial(unittest.TestCase):
    def test_summarise_trial(self):
        bench = SweepCfg().to_bench()
        res = bench.plot_sweep(
            "test",
            input_vars=["float_var"],
            result_vars=["result"],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        study = optuna.create_study(direction="minimize")
        study.optimize(lambda trial: trial.suggest_float("float_var", 0, 1), n_trials=3)
        trial = study.best_trial
        output = summarise_trial(trial, res.bench_cfg)
        assert isinstance(output, list)
        assert len(output) > 0
        assert "Trial id:" in output[0]


class TestOptunaGridSearch(unittest.TestCase):
    def test_default_excludes_optimize_false(self):
        bench = SweepCfg().to_bench()
        res = bench.plot_sweep(
            "test_grid",
            input_vars=["float_var"],
            result_vars=["result"],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )
        study = optuna_grid_search(res.bench_cfg)
        # repeat has optimize=False, should not be in search space
        search_space = study.sampler._search_space
        assert "repeat" not in search_space

    def test_trial_vars_includes_all(self):
        bench = SweepCfg().to_bench()
        res = bench.plot_sweep(
            "test_grid_vars",
            input_vars=["float_var"],
            result_vars=["result"],
            run_cfg=bn.BenchRunCfg(repeats=2),
            plot_callbacks=False,
        )
        trial_vars = list(res.bench_cfg.all_vars)
        study = optuna_grid_search(res.bench_cfg, trial_vars=trial_vars)
        # When trial_vars provided, all vars should be in search space
        search_space = study.sampler._search_space
        assert "repeat" in search_space
        assert "float_var" in search_space


class _UnexpectedPlotError(Exception):
    """An exception type outside _EXPECTED_PLOT_FAILURES."""


def _boom_expected():
    raise ValueError("expected boom")


def _boom_unexpected():
    raise _UnexpectedPlotError("unexpected boom")


class TestAppendSafe(unittest.TestCase):
    """A failed optuna plot must never abort report building.

    By the time these run the sweep has already paid for every sample, so a
    propagating exception would discard the whole run to report one missing
    plot. Both handlers append a visible pane instead.
    """

    def _panes(self, append_fn, plot_fn):
        row = pn.Row()
        with (
            self.assertLogs(level="ERROR") as captured,
            warnings.catch_warnings(record=True),
        ):
            warnings.simplefilter("always")
            append_fn(row, plot_fn)
        return row, "\n".join(captured.output)

    def test_expected_failure_appends_pane(self):
        row, logs = self._panes(_append_safe, _boom_expected)
        assert len(row) == 1
        assert "_boom_expected" in row[0].object
        assert "expected boom" in logs
        # The expected path adds no "Unexpected" log of its own.
        assert "Unexpected" not in logs

    def test_unexpected_failure_also_appends_pane_and_logs(self):
        row, logs = self._panes(_append_safe, _boom_unexpected)
        assert len(row) == 1
        assert "_boom_unexpected" in row[0].object
        assert "Unexpected _UnexpectedPlotError" in logs

    def test_sized_variant_handles_both_paths(self):
        for plot_fn in (_boom_expected, _boom_unexpected):
            with self.subTest(plot_fn=plot_fn.__name__):
                row = pn.Row()
                with (
                    self.assertLogs(level="ERROR"),
                    warnings.catch_warnings(record=True),
                ):
                    warnings.simplefilter("always")
                    _append_safe_sized(row, plot_fn, 400)
                assert len(row) == 1
                assert plot_fn.__name__ in row[0].object

    def test_successful_plot_is_appended_unchanged(self):
        row = pn.Row()
        marker = pn.pane.Markdown("ok")
        _append_safe(row, lambda: marker)
        assert marker is row[0]
