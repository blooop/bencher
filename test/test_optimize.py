"""Tests for the first-class optimization API (Bench.optimize / to_optimize)."""

from __future__ import annotations

from enum import auto

import pytest

import bencher as bn


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


class Sphere(bn.ParametrizedSweep):
    """Simple sphere function: minimum at origin."""

    x = bn.FloatSweep(default=0, bounds=[-5, 5], samples=5)
    y = bn.FloatSweep(default=0, bounds=[-5, 5], samples=5)

    loss = bn.ResultVar("ul", bn.OptDir.minimize)

    def __call__(self, **kwargs) -> dict:
        self.update_params_from_kwargs(**kwargs)
        self.loss = float(self.x**2 + self.y**2)
        return super().__call__(**kwargs)


class MultiObjective(bn.ParametrizedSweep):
    """Two conflicting objectives."""

    x = bn.FloatSweep(default=0, bounds=[0, 5], samples=5)

    obj1 = bn.ResultVar("ul", bn.OptDir.minimize)
    obj2 = bn.ResultVar("ul", bn.OptDir.maximize)

    def __call__(self, **kwargs) -> dict:
        self.update_params_from_kwargs(**kwargs)
        self.obj1 = float(self.x**2)
        self.obj2 = float(-((self.x - 3) ** 2))
        return super().__call__(**kwargs)


class Color(bn.ClassEnum):
    red = auto()
    green = auto()
    blue = auto()

    @classmethod
    def to_class(cls, enum_val):
        return enum_val


class CategoricalProblem(bn.ParametrizedSweep):
    """Problem with categorical + boolean inputs."""

    flag = bn.BoolSweep(default=False)
    color = bn.EnumSweep(Color, default=Color.red)

    score = bn.ResultVar("ul", bn.OptDir.minimize)

    def __call__(self, **kwargs) -> dict:
        self.update_params_from_kwargs(**kwargs)
        lookup = {Color.red: 1.0, Color.green: 0.5, Color.blue: 2.0}
        self.score = lookup[self.color] + (0.0 if self.flag else 0.3)
        return super().__call__(**kwargs)


def _run_cfg():
    """Minimal run config with caching enabled."""
    cfg = bn.BenchRunCfg()
    cfg.repeats = 1
    return cfg


def _collect_markdown(panel):
    """Recursively collect all Markdown text from a nested panel layout."""
    import panel as pn

    texts = []
    if isinstance(panel, pn.pane.Markdown):
        texts.append(panel.object)
    elif hasattr(panel, "objects"):
        for obj in panel.objects:
            texts.append(_collect_markdown(obj))
    return " ".join(texts)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSingleObjective:
    def test_basic_optimize(self):
        cfg = Sphere()
        bench = bn.Bench("test_opt_single", cfg, run_cfg=_run_cfg())
        result = bench.optimize(n_trials=20, plot=False)

        assert result.best_params is not None
        assert "x" in result.best_params
        assert "y" in result.best_params
        assert result.best_value >= 0
        assert result.n_new_trials == 20
        assert result.best_value < 10  # should find something reasonable

    def test_summary(self):
        cfg = Sphere()
        bench = bn.Bench("test_opt_summary", cfg, run_cfg=_run_cfg())
        result = bench.optimize(n_trials=10, plot=False)
        text = result.summary()
        assert "best value" in text
        assert "warm-start trials" in text


class TestMultiObjective:
    def test_pareto_front(self):
        cfg = MultiObjective()
        bench = bn.Bench("test_opt_multi", cfg, run_cfg=_run_cfg())
        result = bench.optimize(n_trials=20, plot=False)

        assert len(result.best_trials) > 0
        assert result.n_new_trials == 20
        # Multi-objective: best_value should raise
        with pytest.raises(RuntimeError):
            _ = result.best_value


class TestWarmStart:
    def test_warm_start_from_sweep(self):
        cfg = Sphere()
        run_cfg = _run_cfg()
        bench = bn.Bench("test_opt_warm", cfg, run_cfg=run_cfg)

        # Run a grid sweep first to populate cache
        bench.plot_sweep(
            input_vars=[cfg.param.x, cfg.param.y],
            result_vars=[cfg.param.loss],
            run_cfg=run_cfg,
        )

        result = bench.optimize(n_trials=10, warm_start=True, plot=False)
        assert result.n_warm_start_trials > 0

    def test_no_warm_start(self):
        cfg = Sphere()
        bench = bn.Bench("test_opt_no_warm", cfg, run_cfg=_run_cfg())
        result = bench.optimize(n_trials=10, warm_start=False, plot=False)
        assert result.n_warm_start_trials == 0


class TestAutoDetection:
    def test_auto_detect_vars(self):
        """optimize() should auto-detect input/result vars from the worker class."""
        cfg = Sphere()
        bench = bn.Bench("test_opt_auto", cfg, run_cfg=_run_cfg())
        result = bench.optimize(n_trials=10, plot=False)
        assert "x" in result.best_params
        assert "y" in result.best_params


class TestConvenience:
    def test_to_optimize(self):
        result = Sphere().to_optimize(n_trials=15, plot=False)
        assert result.best_params is not None
        assert result.best_value >= 0
        assert result.n_new_trials == 15


class TestCategoricalInputs:
    def test_enum_and_bool(self):
        cfg = CategoricalProblem()
        bench = bn.Bench("test_opt_cat", cfg, run_cfg=_run_cfg())
        result = bench.optimize(n_trials=15, plot=False)
        assert "flag" in result.best_params
        assert "color" in result.best_params
        assert result.best_value <= 1.0  # best is green + flag=True → 0.5


class TestOptimizeResult:
    def test_to_panel(self):
        cfg = Sphere()
        bench = bn.Bench("test_opt_panel", cfg, run_cfg=_run_cfg())
        result = bench.optimize(n_trials=10, plot=False)
        panel = result.to_panel()
        assert panel is not None

    def test_target_names(self):
        cfg = Sphere()
        bench = bn.Bench("test_opt_targets", cfg, run_cfg=_run_cfg())
        result = bench.optimize(n_trials=5, plot=False)
        assert result.target_names == ["loss"]


class TestSummariseOptunaStudy:
    """Tests for summarise_optuna_study handling single vs multi-objective correctly."""

    def test_single_objective_no_pareto_error(self, caplog):
        """Single-objective study should not attempt plot_pareto_front."""
        cfg = Sphere()
        bench = bn.Bench("test_summary_single", cfg, run_cfg=_run_cfg())
        result = bench.optimize(n_trials=5, plot=False)
        panel = result.to_panel()
        assert panel is not None
        # Should not log any plot_pareto_front error
        assert "plot_pareto_front" not in caplog.text

    def test_single_objective_panel_shows_best_params(self):
        """Single-objective panel should contain best parameters text."""
        cfg = Sphere()
        bench = bn.Bench("test_summary_best", cfg, run_cfg=_run_cfg())
        result = bench.optimize(n_trials=5, plot=False)
        panel = result.to_panel()
        md_text = _collect_markdown(panel)
        assert "Best Parameters" in md_text

    def test_multi_objective_panel_no_best_value_error(self):
        """Multi-objective panel should not call study.best_value (which raises)."""
        cfg = MultiObjective()
        bench = bn.Bench("test_summary_multi", cfg, run_cfg=_run_cfg())
        result = bench.optimize(n_trials=10, plot=False)
        # Should not raise — previously would crash on study.best_value
        panel = result.to_panel()
        assert panel is not None

    def test_multi_objective_panel_shows_pareto_size(self):
        """Multi-objective panel should show Pareto-front size."""
        cfg = MultiObjective()
        bench = bn.Bench("test_summary_pareto_size", cfg, run_cfg=_run_cfg())
        result = bench.optimize(n_trials=10, plot=False)
        panel = result.to_panel()
        md_text = _collect_markdown(panel)
        assert "Pareto front" in md_text.lower() or "Number of trials" in md_text
