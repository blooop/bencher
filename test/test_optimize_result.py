"""Tests for bencher/results/optimize_result.py — the OptimizeResult dataclass surface.

Complements test/test_optimize.py (which exercises Bench.optimize end-to-end) by testing
the OptimizeResult accessors directly against deterministic, hand-built optuna studies,
plus minimal sweep-driven structural checks not covered there.
"""

from __future__ import annotations

import math

import optuna
import pytest
from optuna.distributions import FloatDistribution

import bencher as bn
from bencher.results.optimize_result import OptimizeResult

# ---------------------------------------------------------------------------
# Deterministic study builders
# ---------------------------------------------------------------------------


def _make_single_objective_study() -> optuna.Study:
    study = optuna.create_study(direction="minimize", study_name="single_study")
    for x, val in [(1.0, 1.0), (0.5, 0.25), (2.0, 4.0)]:
        study.add_trial(
            optuna.trial.create_trial(
                params={"x": x},
                distributions={"x": FloatDistribution(-5, 5)},
                value=val,
            )
        )
    return study


def _make_multi_objective_study() -> optuna.Study:
    study = optuna.create_study(directions=["minimize", "maximize"], study_name="multi_study")
    # (obj1=minimize, obj2=maximize): (3.0, 0.0) is dominated by (1.0, 1.0);
    # the other three trials form the Pareto front.
    for x, values in [
        (1.0, (1.0, 1.0)),
        (2.0, (2.0, 3.0)),
        (0.5, (0.5, 0.5)),
        (3.0, (3.0, 0.0)),
    ]:
        study.add_trial(
            optuna.trial.create_trial(
                params={"x": x},
                distributions={"x": FloatDistribution(0, 5)},
                values=list(values),
            )
        )
    return study


# ---------------------------------------------------------------------------
# Direct dataclass-surface tests
# ---------------------------------------------------------------------------


class TestSingleObjectiveSurface:
    def test_best_params_and_value(self):
        res = OptimizeResult(study=_make_single_objective_study())
        assert res.best_value == 0.25
        assert res.best_params == {"x": 0.5}

    def test_field_defaults(self):
        res = OptimizeResult(study=_make_single_objective_study())
        assert res.n_warm_start_trials == 0
        assert res.n_new_trials == 0
        assert res.target_names == []
        assert res.bench_cfg is None

    def test_best_trials_returns_single_best(self):
        res = OptimizeResult(study=_make_single_objective_study())
        trials = res.best_trials
        assert len(trials) == 1
        assert trials[0].params == {"x": 0.5}
        assert trials[0].values == [0.25]

    def test_summary_contents(self):
        res = OptimizeResult(
            study=_make_single_objective_study(),
            n_warm_start_trials=2,
            n_new_trials=1,
            target_names=["loss"],
        )
        text = res.summary()
        assert "Study: single_study" in text
        assert "warm-start trials: 2" in text
        assert "new trials:        1" in text
        assert "total trials:      3" in text
        assert "best value:  0.25" in text
        assert "'x': 0.5" in text


class TestMultiObjectiveSurface:
    def test_pareto_front_membership(self):
        res = OptimizeResult(study=_make_multi_objective_study())
        pareto_xs = sorted(t.params["x"] for t in res.best_trials)
        assert pareto_xs == [0.5, 1.0, 2.0]

    def test_single_objective_accessors_raise(self):
        res = OptimizeResult(study=_make_multi_objective_study())
        with pytest.raises(RuntimeError, match="single-objective"):
            _ = res.best_value
        with pytest.raises(RuntimeError, match="single-objective"):
            _ = res.best_params

    def test_summary_reports_pareto_size(self):
        res = OptimizeResult(study=_make_multi_objective_study())
        text = res.summary()
        assert "Pareto-front size: 3" in text
        assert "best params" not in text


# ---------------------------------------------------------------------------
# Sweep-driven structural checks (minimal; behavior of optimize() itself is
# already covered by test_optimize.py)
# ---------------------------------------------------------------------------


class SingleObjectiveSphere(bn.ParametrizedSweep):
    x = bn.FloatSweep(default=0, bounds=[-5, 5], samples=5)
    loss = bn.ResultFloat("ul", bn.OptDir.minimize)

    def benchmark(self):
        self.loss = float(self.x**2)


class TwoObjectives(bn.ParametrizedSweep):
    x = bn.FloatSweep(default=0, bounds=[0, 5], samples=5)
    obj1 = bn.ResultFloat("ul", bn.OptDir.minimize)
    obj2 = bn.ResultFloat("ul", bn.OptDir.maximize)

    def benchmark(self):
        self.obj1 = float(self.x**2)
        self.obj2 = float(-((self.x - 3) ** 2))


class NanSphere(bn.ParametrizedSweep):
    """Sphere whose worker returns NaN for exactly one evaluation."""

    x = bn.FloatSweep(default=0, bounds=[-5, 5], samples=5)
    loss = bn.ResultFloat("ul", bn.OptDir.minimize)
    _counter = [0]

    def benchmark(self):
        i = self._counter[0]
        self._counter[0] += 1
        self.loss = float("nan") if i == 2 else float(self.x**2)


def _run_cfg() -> bn.BenchRunCfg:
    return bn.BenchRunCfg(repeats=1, cache_results=False, cache_samples=False)


class TestSweepStructure:
    def test_single_objective_sweep_structure(self):
        bench = bn.Bench("opt_res_single", SingleObjectiveSphere(), run_cfg=_run_cfg())
        res = bench.optimize(n_trials=5, plot=False)
        assert isinstance(res, OptimizeResult)
        assert isinstance(res.study, optuna.Study)
        assert res.bench_cfg is not None
        assert len(res.study.directions) == 1
        assert len(res.study.trials) == res.n_warm_start_trials + res.n_new_trials
        assert set(res.best_params) == {"x"}

    def test_multi_objective_sweep_structure(self):
        bench = bn.Bench("opt_res_multi", TwoObjectives(), run_cfg=_run_cfg())
        res = bench.optimize(n_trials=5, plot=False)
        assert isinstance(res, OptimizeResult)
        assert res.target_names == ["obj1", "obj2"]
        assert len(res.study.directions) == 2
        assert len(res.best_trials) >= 1
        for trial in res.best_trials:
            assert len(trial.values) == 2
            assert set(trial.params) == {"x"}

    def test_nan_worker_does_not_crash(self):
        """A NaN objective fails that trial but the study and summary still work."""
        NanSphere._counter[0] = 0
        bench = bn.Bench("opt_res_nan", NanSphere(), run_cfg=_run_cfg())
        res = bench.optimize(n_trials=6, plot=False)
        states = [t.state for t in res.study.trials]
        assert optuna.trial.TrialState.FAIL in states
        assert math.isfinite(res.best_value)
        assert "best value" in res.summary()
