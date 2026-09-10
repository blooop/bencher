"""Tests for the first-class optimization API (Bench.optimize / to_optimize)."""

from __future__ import annotations

from enum import auto
from typing import ClassVar

import optuna
import pytest

import bencher as bn
from bencher.bencher import WARM_STARTED
from bencher.results.optimize_result import Aggregation
from bencher.utils import AggFn

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


class Sphere(bn.ParametrizedSweep):
    """Simple sphere function: minimum at origin."""

    x = bn.FloatSweep(default=0, bounds=[-5, 5], samples=5)
    y = bn.FloatSweep(default=0, bounds=[-5, 5], samples=5)

    loss = bn.ResultFloat("ul", bn.OptDir.minimize)

    def benchmark(self):
        self.loss = float(self.x**2 + self.y**2)


class MultiObjective(bn.ParametrizedSweep):
    """Two conflicting objectives."""

    x = bn.FloatSweep(default=0, bounds=[0, 5], samples=5)

    obj1 = bn.ResultFloat("ul", bn.OptDir.minimize)
    obj2 = bn.ResultFloat("ul", bn.OptDir.maximize)

    def benchmark(self):
        self.obj1 = float(self.x**2)
        self.obj2 = float(-((self.x - 3) ** 2))


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

    score = bn.ResultFloat("ul", bn.OptDir.minimize)

    def benchmark(self):
        lookup = {Color.red: 1.0, Color.green: 0.5, Color.blue: 2.0}
        self.score = lookup[self.color] + (0.0 if self.flag else 0.3)


class BoolDesign(bn.ParametrizedSweep):
    """Two objectives searched over a float and a boolean."""

    x = bn.FloatSweep(default=0, bounds=[0, 5], samples=5)
    boost = bn.BoolSweep(default=False)

    obj1 = bn.ResultFloat("ul", bn.OptDir.minimize)
    obj2 = bn.ResultFloat("ul", bn.OptDir.maximize)

    def benchmark(self):
        gain = 1.5 if self.boost else 1.0
        self.obj1 = float(self.x**2 * gain)
        self.obj2 = float(-((self.x - 3) ** 2) * gain)


class ArrayLike(bn.ParametrizedSweep):
    """Two objectives plus a result the study cannot rank on."""

    x = bn.FloatSweep(default=0, bounds=[0, 5], samples=5)

    obj1 = bn.ResultFloat("ul", bn.OptDir.minimize)
    obj2 = bn.ResultFloat("ul", bn.OptDir.maximize)
    note = bn.ResultString()

    def benchmark(self):
        self.obj1 = float(self.x**2)
        self.obj2 = float(-((self.x - 3) ** 2))
        self.note = f"x={self.x:.3f}"


class MultiObjectiveWithSeed(bn.ParametrizedSweep):
    """Two conflicting objectives judged across a nuisance dimension."""

    x = bn.FloatSweep(default=0, bounds=[0, 5], samples=5)
    seed = bn.IntSweep(default=0, bounds=[0, 2], samples=3)

    obj1 = bn.ResultFloat("ul", bn.OptDir.minimize)
    obj2 = bn.ResultFloat("ul", bn.OptDir.maximize)

    def benchmark(self):
        self.obj1 = float(self.x**2 + self.seed * 0.1)
        self.obj2 = float(-((self.x - 3) ** 2) - self.seed * 0.1)


class FlakySphere(bn.ParametrizedSweep):
    """Sphere whose worker raises on its first invocation, then succeeds.

    Models a flaky expensive worker (e.g. a simulator cold-start failure).
    Tests must reset ``FlakySphere.calls = 0`` before use.
    """

    calls = 0  # class-level so the counter survives however the worker is invoked

    x = bn.FloatSweep(default=0, bounds=[-5, 5], samples=5)

    loss = bn.ResultFloat("ul", bn.OptDir.minimize)

    def benchmark(self):
        FlakySphere.calls += 1
        if FlakySphere.calls == 1:
            raise RuntimeError("infra flake")
        self.loss = float(self.x**2)


def _run_cfg():
    """Minimal run config (single repeat, default caching off)."""
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


class SphereWithSeed(bn.ParametrizedSweep):
    """Sphere with a nuisance dimension to aggregate over."""

    x = bn.FloatSweep(default=0, bounds=[-5, 5], samples=5)
    seed = bn.IntSweep(default=0, bounds=[0, 2], samples=3)

    loss = bn.ResultFloat("ul", bn.OptDir.minimize)

    def benchmark(self):
        self.loss = float(self.x**2 + self.seed * 0.1)


class NoisySphere(bn.ParametrizedSweep):
    """Sphere with stochastic noise — benefits from repeat aggregation."""

    x = bn.FloatSweep(default=0, bounds=[-5, 5], samples=5)

    loss = bn.ResultFloat("ul", bn.OptDir.minimize)

    def benchmark(self):
        import random

        self.loss = float(self.x**2 + random.gauss(0, 0.1))


class TestAggregateOptimize:
    def test_optimize_with_aggregate(self):
        bench = bn.Bench("agg_optim", SphereWithSeed(), run_cfg=_run_cfg())
        result = bench.optimize(
            n_trials=15,
            aggregate=["seed"],
            agg_fn="mean",
            plot=False,
        )
        assert result is not None
        assert result.study.best_value is not None
        assert "seed" not in result.study.best_params
        assert "x" in result.study.best_params

    def test_optimize_with_repeats(self):
        bench = bn.Bench("rep_optim", NoisySphere(), run_cfg=_run_cfg())
        result = bench.optimize(n_trials=15, repeats=3, agg_fn="mean", plot=False)
        assert result is not None
        assert result.study.best_value is not None

    def test_optimize_with_aggregate_and_repeats(self):
        bench = bn.Bench("agg_rep_optim", SphereWithSeed(), run_cfg=_run_cfg())
        result = bench.optimize(
            n_trials=10,
            aggregate=["seed"],
            repeats=2,
            agg_fn="mean",
            plot=False,
        )
        assert result is not None
        assert "seed" not in result.study.best_params

    def test_optimize_no_aggregate_unchanged(self):
        """Default behavior (no aggregate, repeats=1) still works."""
        bench = bn.Bench("no_agg_optim", SphereWithSeed(), run_cfg=_run_cfg())
        result = bench.optimize(n_trials=10, plot=False)
        assert result is not None
        assert "x" in result.study.best_params
        assert "seed" in result.study.best_params
        assert result.aggregation is None
        assert result.searched == ["x", "seed"]

    def test_the_result_records_what_was_aggregated_and_how(self):
        """What a trial's value means -- the mean over which dimensions -- is part of
        the result, so a later reading of the front does not have to guess it."""
        bench = bn.Bench("agg_recorded", SphereWithSeed(), run_cfg=_run_cfg())
        result = bench.optimize(n_trials=4, aggregate=["seed"], agg_fn="max", plot=False)
        assert result.aggregation == Aggregation(fn=AggFn.MAX, dims=("seed",))
        assert result.searched == ["x"]

    @pytest.mark.parametrize("agg_fn", ["mean", "sum", "max", "min", "median"])
    def test_optimize_all_agg_fns(self, agg_fn):
        bench = bn.Bench(f"agg_fn_{agg_fn}", SphereWithSeed(), run_cfg=_run_cfg())
        result = bench.optimize(
            n_trials=10,
            aggregate=["seed"],
            agg_fn=agg_fn,
            plot=False,
        )
        assert result is not None
        assert result.study.best_value is not None

    def test_optimize_invalid_agg_fn(self):
        bench = bn.Bench("bad_agg_fn", SphereWithSeed(), run_cfg=_run_cfg())
        with pytest.raises(ValueError, match="Unknown agg_fn"):
            bench.optimize(n_trials=5, aggregate=["seed"], agg_fn="bogus", plot=False)


class OffsetSphere(bn.ParametrizedSweep):
    """Sphere with a constant offset; records what the worker actually received."""

    x = bn.FloatSweep(default=0, bounds=[-5, 5], samples=5)
    offset = bn.FloatSweep(default=0.0, bounds=[0, 100], samples=3)

    loss = bn.ResultFloat("ul", bn.OptDir.minimize)

    observed_offsets: ClassVar[list[float]] = []
    observed_x: ClassVar[list[float]] = []

    def benchmark(self):
        type(self).observed_offsets.append(float(self.offset))
        type(self).observed_x.append(float(self.x))
        self.loss = float(self.x**2 + self.offset)


class TestConstVars:
    def setup_method(self):
        OffsetSphere.observed_offsets.clear()
        OffsetSphere.observed_x.clear()

    def test_const_vars_reach_worker(self):
        """const_vars must be passed to the worker, not just hashed into the cache key."""
        cfg = OffsetSphere()
        bench = bn.Bench("test_opt_const_vars", cfg, run_cfg=_run_cfg())
        result = bench.optimize(
            input_vars=["x"],
            const_vars={"offset": 50.0},
            n_trials=5,
            warm_start=False,
            plot=False,
        )

        # Every trial must see the non-default constant, not the class default of 0.0.
        assert OffsetSphere.observed_offsets == [50.0] * 5
        # loss = x**2 + offset, so with offset delivered the best value is >= 50.
        assert result.best_value >= 50.0
        # Constants must not override the trial-suggested values for optimized vars.
        suggested_x = [t.params["x"] for t in result.study.trials]
        assert sorted(OffsetSphere.observed_x) == sorted(suggested_x)

    def test_const_vars_reach_worker_with_repeats(self):
        """The aggregate/repeats branch must also deliver const_vars to the worker."""
        cfg = OffsetSphere()
        bench = bn.Bench("test_opt_const_vars_rep", cfg, run_cfg=_run_cfg())
        result = bench.optimize(
            input_vars=["x"],
            const_vars={"offset": 50.0},
            n_trials=3,
            repeats=2,
            agg_fn="mean",
            warm_start=False,
            plot=False,
        )

        assert OffsetSphere.observed_offsets == [50.0] * 6
        assert result.best_value >= 50.0


class TestConvenience:
    def test_to_optimize(self):
        result = Sphere().to_optimize(n_trials=15, plot=False)
        assert result.best_params is not None
        assert result.best_value >= 0
        assert result.n_new_trials == 15


class TestCatch:
    def test_optimize_without_catch_aborts_study(self):
        FlakySphere.calls = 0
        bench = bn.Bench("test_opt_no_catch", FlakySphere(), run_cfg=_run_cfg())
        with pytest.raises(RuntimeError, match="infra flake"):
            bench.optimize(n_trials=5, plot=False, warm_start=False)

    def test_optimize_with_catch_continues_after_failed_trial(self):
        from optuna.trial import TrialState

        FlakySphere.calls = 0
        bench = bn.Bench("test_opt_catch", FlakySphere(), run_cfg=_run_cfg())
        result = bench.optimize(n_trials=5, plot=False, warm_start=False, catch=(RuntimeError,))

        assert result is not None
        states = [t.state for t in result.study.trials]
        assert len(states) == 5
        assert states.count(TrialState.FAIL) == 1
        assert states.count(TrialState.COMPLETE) == 4
        assert result.best_value >= 0  # surviving trials still produce a best value

    def test_to_optimize_forwards_catch(self):
        FlakySphere.calls = 0
        result = FlakySphere().to_optimize(
            n_trials=3, plot=False, warm_start=False, catch=(RuntimeError,)
        )
        assert result is not None
        assert len(result.study.trials) == 3


class TestCategoricalInputs:
    def test_enum_and_bool(self):
        cfg = CategoricalProblem()
        bench = bn.Bench("test_opt_cat", cfg, run_cfg=_run_cfg())
        result = bench.optimize(n_trials=15, plot=False)
        assert "flag" in result.best_params
        assert "color" in result.best_params
        assert result.best_value <= 1.0  # best is green + flag=True → 0.5


class TestOptimizeResult:
    def test_target_names(self):
        cfg = Sphere()
        bench = bn.Bench("test_opt_targets", cfg, run_cfg=_run_cfg())
        result = bench.optimize(n_trials=5, plot=False)
        assert result.target_names == ["loss"]

    def test_summary_text(self):
        cfg = Sphere()
        bench = bn.Bench("test_opt_summary_text", cfg, run_cfg=_run_cfg())
        result = bench.optimize(n_trials=5, plot=False)
        text = result.summary()
        assert "best value" in text
        assert "new trials" in text


# ---------------------------------------------------------------------------
# Sweeping along the Pareto front
# ---------------------------------------------------------------------------


class TestPlotParetoFront:
    def test_every_result_var_the_worker_declares_is_evaluated_on_the_front(self):
        """The objectives are what a study can rank; what makes a front worth walking
        is usually what it cannot. Defaulting to the objectives left that out."""
        bench = bn.Bench("pareto_rv_default", ArrayLike(), run_cfg=_run_cfg())
        result = bench.optimize(
            result_vars=["obj1", "obj2"], n_trials=6, warm_start=False, plot=False
        )
        assert result.target_names == ["obj1", "obj2"]
        res = bench.plot_pareto_front(result, auto_plot=False)
        assert set(res.ds.data_vars) >= {"obj1", "obj2", "note"}

    def test_the_front_becomes_a_sweep_over_its_rank(self):
        """Each rank re-evaluates one trial's own design, in the order the walk takes."""
        bench = bn.Bench("pareto_sweep", MultiObjective(), run_cfg=_run_cfg())
        result = bench.optimize(n_trials=12, warm_start=False, plot=False)
        front = result.pareto_trials()
        res = bench.plot_pareto_front(result)
        ds = res.to_dataset(bn.ReduceType.SQUEEZE)
        assert list(ds.sizes) == ["pareto_rank"]
        assert list(ds.coords["pareto_rank"].values) == list(range(len(front)))
        assert list(ds.coords["x"].values) == pytest.approx([t.params["x"] for t in front])
        assert list(ds["obj1"].values) == pytest.approx([t.values[0] for t in front])
        assert list(ds["obj2"].values) == pytest.approx([t.values[1] for t in front])
        # obj1 is minimised, so the walk starts where it is smallest.
        assert list(ds["obj1"].values) == sorted(ds["obj1"].values)
        # Nothing was aggregated, so the trial's values are the samples themselves
        # and there is no separate aggregated reading to carry.
        assert not [name for name in ds.coords if name.startswith("obj")]
        assert "Pareto front of obj1 vs obj2" in [pane.name for pane in bench.report.pane]
        # A later optimize() takes its defaults from bench.results, and the rank
        # is not an input the worker accepts.
        assert res not in bench.results

    def test_two_objectives_put_optunas_pareto_plot_in_the_front_tab(self):
        """The walk along the front and optuna's picture of it belong together: the
        scatter says where each rank sits among every trial, dominated ones included."""
        import panel as pn

        bench = bn.Bench("pareto_plotly", MultiObjective(), run_cfg=_run_cfg())
        result = bench.optimize(n_trials=6, warm_start=False, plot=False)
        bench.plot_pareto_front(result)
        tab = bench.report.pane[-1]
        assert tab.name == "Pareto front of obj1 vs obj2"
        plots = [pane for pane in tab.objects if isinstance(pane, pn.pane.Plotly)]
        assert len(plots) == 1
        assert "Pareto" in plots[0].object.layout.title.text
        assert plots[0].object.layout.xaxis.title.text == "obj1"
        assert plots[0].object.layout.yaxis.title.text == "obj2"

    def test_a_single_objective_front_has_no_pareto_plot_to_add(self):
        import panel as pn

        bench = bn.Bench("pareto_plotly_one", SphereWithSeed(), run_cfg=_run_cfg())
        result = bench.optimize(n_trials=4, aggregate=["seed"], agg_fn="mean", plot=False)
        bench.plot_pareto_front(result)
        tab = bench.report.pane[-1]
        assert not [pane for pane in tab.objects if isinstance(pane, pn.pane.Plotly)]

    def test_aggregated_dimensions_are_swept_beside_the_rank(self):
        """A design is shown under every condition it was judged across, and the
        study's own reading of it -- the aggregate -- rides on the rank."""
        bench = bn.Bench("pareto_agg", MultiObjectiveWithSeed(), run_cfg=_run_cfg())
        result = bench.optimize(
            n_trials=8, aggregate=["seed"], agg_fn="mean", warm_start=False, plot=False
        )
        front = result.pareto_trials()
        res = bench.plot_pareto_front(result, auto_plot=False)
        ds = res.to_dataset(bn.ReduceType.SQUEEZE)
        assert dict(ds.sizes) == {"pareto_rank": len(front), "seed": 3}
        assert list(ds.coords["seed"].values) == [0, 1, 2]
        assert list(ds.coords["x"].values) == pytest.approx([t.params["x"] for t in front])
        for index, target in enumerate(("obj1", "obj2")):
            aggregated = ds.coords[f"{target}_mean"]
            assert list(aggregated.values) == pytest.approx([t.values[index] for t in front])
            # The study's number really is the mean of the samples now beside it.
            assert list(ds[target].mean("seed").values) == pytest.approx(list(aggregated.values))
        assert ds.coords["obj1_mean"].attrs["units"] == "ul"

    def test_a_single_objective_front_is_the_winner_as_one_rank(self):
        bench = bn.Bench("pareto_one", SphereWithSeed(), run_cfg=_run_cfg())
        result = bench.optimize(n_trials=6, aggregate=["seed"], agg_fn="mean", plot=False)
        (best,) = result.pareto_trials()
        res = bench.plot_pareto_front(result, auto_plot=False)
        assert res.ds.sizes["pareto_rank"] == 1
        assert res.ds.coords["x"].item() == pytest.approx(best.params["x"])
        assert res.ds.coords["loss_mean"].item() == pytest.approx(best.values[0])
        assert res.ds["loss"].mean().item() == pytest.approx(best.values[0])

    def test_the_front_is_never_thinned(self):
        """A rank is a design; subsampling would silently drop designs off the front."""
        run_cfg = _run_cfg()
        run_cfg.subsampling_divisions = 1
        bench = bn.Bench("pareto_thin", MultiObjective(), run_cfg=run_cfg)
        result = bench.optimize(n_trials=20, warm_start=False, plot=False)
        assert len(result.pareto_trials()) > 2, "the front is too short for thinning to bite"
        res = bench.plot_pareto_front(result, auto_plot=False)
        assert res.ds.sizes["pareto_rank"] == len(result.pareto_trials())

    def test_result_vars_are_named_against_the_worker(self):
        bench = bn.Bench("pareto_rv", MultiObjective(), run_cfg=_run_cfg())
        result = bench.optimize(n_trials=4, warm_start=False, plot=False)
        res = bench.plot_pareto_front(result, result_vars=["obj2"], auto_plot=False)
        assert list(res.ds.data_vars) == ["obj2"]

    def test_the_walk_can_follow_the_other_objective(self):
        bench = bn.Bench("pareto_along", MultiObjective(), run_cfg=_run_cfg())
        result = bench.optimize(n_trials=12, warm_start=False, plot=False)
        res = bench.plot_pareto_front(result, objective="obj2", auto_plot=False)
        obj2 = list(res.to_dataset(bn.ReduceType.SQUEEZE)["obj2"].values)
        # obj2 is maximised, so its walk starts where it is largest.
        assert obj2 == sorted(obj2, reverse=True)
        with pytest.raises(ValueError, match="not an objective"):
            bench.plot_pareto_front(result, objective="loss")

    def test_a_study_that_finished_no_trial_has_no_front(self):
        bench = bn.Bench("pareto_empty", MultiObjective(), run_cfg=_run_cfg())
        result = bench.optimize(n_trials=1, warm_start=False, plot=False)
        result.study = optuna.create_study(directions=["minimize", "maximize"])
        with pytest.raises(ValueError, match="no front"):
            bench.plot_pareto_front(result)

    def test_a_front_runs_on_a_bench_configured_for_multiprocessing(self):
        """The front's worker was a closure over the designs, which a process pool
        cannot look up: `AttributeError: Can't get local object
        'Bench.plot_pareto_front.<locals>.pareto_front_worker'` took down every front
        on a bench whose run_cfg asked for parallel samples."""
        cfg = bn.BenchRunCfg()
        cfg.repeats = 1
        cfg.executor = bn.Executors.MULTIPROCESSING
        bench = bn.Bench("pareto_multiprocessing", MultiObjective(), run_cfg=cfg)
        result = bench.optimize(n_trials=8, warm_start=False, plot=False)
        res = bench.plot_pareto_front(result, auto_plot=False)
        ds = res.to_dataset(bn.ReduceType.SQUEEZE)
        front = result.pareto_trials()
        assert ds.sizes["pareto_rank"] == len(front)
        assert [float(v) for v in ds["obj1"].values] == pytest.approx(
            [trial.params["x"] ** 2 for trial in front]
        )

    def test_a_second_front_is_not_served_the_first_ones_data(self):
        """``pareto_rank`` is a position, not an identity: nothing in either cache key
        -- ``hash_persistent`` or ``hash_sha1(sorted(job_args))`` -- can see which
        designs the ranks stand for. With caching on, a second front over the same
        bench replayed the first front's samples under the second's coordinates, so
        every value and every picture belonged to a different design than the
        read-out named."""
        cfg = bn.BenchRunCfg()
        cfg.repeats = 1
        cfg.cache_results = True
        cfg.cache_samples = True
        cfg.clear_cache = True
        cfg.clear_sample_cache = True

        def walk(sampler_seed: int):
            bench = bn.Bench("pareto_cache_blind", MultiObjective(), run_cfg=cfg)
            result = bench.optimize(
                n_trials=12,
                warm_start=False,
                plot=False,
                sampler=optuna.samplers.TPESampler(seed=sampler_seed),
            )
            res = bench.plot_pareto_front(result, auto_plot=False)
            ds = res.to_dataset(bn.ReduceType.SQUEEZE)
            return [float(v) for v in ds.coords["x"].values], [float(v) for v in ds["obj1"].values]

        first_x, _ = walk(3)
        cfg.clear_cache = False
        cfg.clear_sample_cache = False
        second_x, second_obj1 = walk(5)

        # Two different fronts, or the replay would be indistinguishable from a hit.
        assert first_x != second_x
        # MultiObjective scores obj1 = x**2, so every rank's value is checkable
        # against the design the coordinate says is there.
        assert second_obj1 == pytest.approx([x**2 for x in second_x])

    def test_a_boolean_design_input_still_rides_on_the_rank(self):
        """``convert_dataset_bool_dims_to_str`` rebuilt every bool coordinate from a
        bare list, which xarray reads as a new dimension of that name. That is right
        for a bool that *is* a dimension and wrong for one riding on another, which
        is the only shape a searched input takes here: ``boost`` became an axis of
        its own, as wide as the front and every label the same, so it no longer
        travelled with the rank and the read-out could not name it."""
        bench = bn.Bench("pareto_bool_rank", BoolDesign(), run_cfg=_run_cfg())
        result = bench.optimize(n_trials=12, warm_start=False, plot=False)
        res = bench.plot_pareto_front(result, auto_plot=False)
        ds = res.to_dataset(bn.ReduceType.SQUEEZE)
        assert "boost" not in ds.sizes
        assert ds.coords["boost"].dims == ("pareto_rank",)
        assert list(ds.coords["boost"].values) == [
            str(trial.params["boost"]) for trial in result.pareto_trials()
        ]


class TestParetoScrubExample:
    def test_the_example_walks_a_real_front(self, monkeypatch):
        """The gallery example is the documented shape of this feature, so it has to
        actually produce a front with something on it to scrub."""
        from bencher.example.optuna.example_optimize_pareto_scrub import (
            example_optimize_pareto_scrub,
        )

        fronts = []
        original = bn.Bench.plot_pareto_front

        def spy(self, result, *args, **kwargs):
            res = original(self, result, *args, **kwargs)
            fronts.append((result, res))
            return res

        monkeypatch.setattr(bn.Bench, "plot_pareto_front", spy)
        bench = example_optimize_pareto_scrub(_run_cfg())
        assert len(fronts) == 1
        result, res = fronts[0]
        # A front of one would make the slider pointless, which is what the example
        # exists to show -- the two objectives really do have to conflict.
        assert res.ds.sizes["pareto_rank"] > 1
        assert res.ds.sizes["steer"] == 2
        assert {"spacing", "taper", "beam_width_max", "side_lobe_max"} <= set(res.ds.coords)
        assert result.searched == ["spacing", "taper"]
        # The point of the whole thing: one rerun viewer scrubbed by the rank.
        assert res.to_rerun_timeline() is not None
        titles = [pane.name for pane in bench.report.pane]
        assert any(title.startswith("Pareto front of") for title in titles), titles


class TestParetoFrontAggregation:
    def test_a_study_that_reduced_only_its_repeats_still_carries_its_score(self):
        """``repeats > 1`` aggregates as surely as ``aggregate=`` does: the trial's
        value is a mean over the repeats and is a different number from any one
        sample. Reading "did it aggregate" off the aggregated *dimensions* answered
        no, so the front carried no reading of its own and the scatter was stamped
        with the sweep's fresh re-evaluation in place of what the study ranked on."""
        bench = bn.Bench("pareto_repeats", MultiObjective(), run_cfg=_run_cfg())
        result = bench.optimize(n_trials=6, repeats=3, warm_start=False, plot=False)
        assert result.aggregation is not None
        assert result.aggregation.dims == ()
        assert result.aggregation.fn is AggFn.MEAN
        assert result.searched == ["x"]
        front = result.pareto_trials()
        res = bench.plot_pareto_front(result, auto_plot=False)
        assert list(res.ds.coords["obj1_mean"].values) == pytest.approx(
            [t.values[0] for t in front]
        )
        assert list(res.ds.coords["obj2_mean"].values) == pytest.approx(
            [t.values[1] for t in front]
        )
        assert res.ds.attrs["bencher_readout_scatter"] == ["obj1_mean", "obj2_mean"]

    def test_a_study_that_reduced_nothing_has_no_aggregation(self):
        """One repeat and nothing looped: a trial's value *is* the sample, so there
        is no separate reading for the front to carry."""
        bench = bn.Bench("pareto_plain", MultiObjective(), run_cfg=_run_cfg())
        result = bench.optimize(n_trials=6, warm_start=False, plot=False)
        assert result.aggregation is None
        res = bench.plot_pareto_front(result, auto_plot=False)
        assert res.ds.attrs["bencher_readout_scatter"] == ["obj1", "obj2"]


class TestParetoFrontWarmStartedTrials:
    """A warm-started trial's params are the seeding sweep's vars, not a design."""

    def test_the_aggregated_dimension_is_swept_and_not_also_passed(self):
        """Warm start builds a trial from every var the seeding sweep recorded, the
        aggregated dims and ``repeat`` among them. Handing those to the worker whole
        collided with the dims the front sweeps beside the rank."""
        bench = bn.Bench("pareto_warm_agg", MultiObjectiveWithSeed(), run_cfg=_run_cfg())
        bench.plot_sweep(input_vars=["x", "seed"], auto_plot=False)
        result = bench.optimize(n_trials=4, aggregate=["seed"], agg_fn="mean", plot=False)
        assert result.n_warm_start_trials > 0
        front = result.pareto_trials()
        # x=0, seed=0 scores obj1=0, which no aggregated trial can match, so a
        # warm-started trial is on the front whatever optuna suggested.
        assert any("seed" in trial.params for trial in front)
        res = bench.plot_pareto_front(result, auto_plot=False)
        ds = res.to_dataset(bn.ReduceType.SQUEEZE)
        assert set(ds.sizes) == {"pareto_rank", "seed"}
        assert list(ds.coords["x"].values) == pytest.approx([t.params["x"] for t in front])

    def test_a_warm_seeded_score_is_not_the_aggregate_it_is_stamped_as(self, caplog):
        """Warm start seeds one trial per raw sample, so a warm trial's value is one
        evaluation and not the reduction over the looped dims. It competes on the
        front against aggregated trials anyway, and the front then stamps every value
        `{target}_{agg_fn}` -- a name the warm ones do not answer to. Reproduced:
        obj1_mean read 0.0 at a rank whose mean over `seed` is 0.1."""
        bench = bn.Bench("pareto_warm_score", MultiObjectiveWithSeed(), run_cfg=_run_cfg())
        bench.plot_sweep(input_vars=["x", "seed"], auto_plot=False)
        result = bench.optimize(n_trials=4, aggregate=["seed"], agg_fn="mean", plot=False)
        front = result.pareto_trials()
        assert any(trial.user_attrs.get(WARM_STARTED) for trial in front)
        with caplog.at_level("WARNING", logger="bencher.bencher"):
            res = bench.plot_pareto_front(result, auto_plot=False)
        assert "obj1_mean" in caplog.text
        assert "seeded from cache" in caplog.text
        # The stamped score really is the un-aggregated one, which is what the
        # warning is about.
        ds = res.to_dataset(bn.ReduceType.SQUEEZE)
        stamped = [float(v) for v in ds.coords["obj1_mean"].values]
        actual = [float(v) for v in ds["obj1"].mean(dim="seed").values]
        assert stamped != pytest.approx(actual)

    def test_a_front_with_no_warm_trial_on_it_is_stamped_without_complaint(self, caplog):
        """The warning is about provenance, not about aggregating: a study that
        aggregated and searched every trial itself stamps a score that is the
        aggregate, and says nothing."""
        bench = bn.Bench("pareto_warm_clean", MultiObjectiveWithSeed(), run_cfg=_run_cfg())
        result = bench.optimize(
            n_trials=4, aggregate=["seed"], agg_fn="mean", warm_start=False, plot=False
        )
        front = result.pareto_trials()
        assert not any(trial.user_attrs.get(WARM_STARTED) for trial in front)
        with caplog.at_level("WARNING", logger="bencher.bencher"):
            res = bench.plot_pareto_front(result, auto_plot=False)
        assert "seeded from cache" not in caplog.text
        ds = res.to_dataset(bn.ReduceType.SQUEEZE)
        stamped = [float(v) for v in ds.coords["obj1_mean"].values]
        actual = [float(v) for v in ds["obj1"].mean(dim="seed").values]
        assert stamped == pytest.approx(actual)

    def test_a_trial_missing_an_input_the_study_searched_is_named(self):
        """A trial seeded by a narrower sweep carries no value for an input the study
        searched, so it is not a design this bench can re-evaluate. Reading it as one
        reached the coordinate build as a bare KeyError."""
        bench = bn.Bench("pareto_warm_narrow", MultiObjectiveWithSeed(), run_cfg=_run_cfg())
        bench.plot_sweep(input_vars=["x"], auto_plot=False)
        result = bench.optimize(input_vars=["x", "seed"], n_trials=4, plot=False)
        assert result.n_warm_start_trials > 0
        assert any("seed" not in trial.params for trial in result.pareto_trials())
        with pytest.raises(ValueError, match="seed"):
            bench.plot_pareto_front(result, auto_plot=False)


class TestWarmStartTargets:
    """A sweep's objectives need not be the study's."""

    def test_a_narrower_study_still_takes_the_sweeps_seeds(self):
        """`optimize(result_vars=[one])` on a worker declaring two directional
        results used to warm-start from nothing: the trials were built with both
        values, the study had one direction, and the rejection was swallowed."""
        cfg = MultiObjective()
        run_cfg = _run_cfg()
        bench = bn.Bench("warm_narrow", cfg, run_cfg=run_cfg)
        bench.plot_sweep(
            input_vars=[cfg.param.x],
            result_vars=[cfg.param.obj1, cfg.param.obj2],
            run_cfg=run_cfg,
        )
        result = bench.optimize(
            result_vars=[cfg.param.obj1], n_trials=3, warm_start=True, plot=False
        )
        assert len(result.study.directions) == 1
        assert result.n_warm_start_trials > 0
        for trial in result.study.trials:
            assert len(trial.values) == 1

    def test_the_values_land_in_the_studys_own_order(self):
        """Trial values are positional against the study's directions, so seeding
        a reordered study must reorder the values and not just their count."""
        cfg = MultiObjective()
        run_cfg = _run_cfg()
        bench = bn.Bench("warm_order", cfg, run_cfg=run_cfg)
        sweep = bench.plot_sweep(
            input_vars=[cfg.param.x],
            result_vars=[cfg.param.obj1, cfg.param.obj2],
            run_cfg=run_cfg,
        )
        trials = sweep.bench_results_to_optuna_trials(True, ["obj2", "obj1"])
        forward = sweep.bench_results_to_optuna_trials(True, ["obj1", "obj2"])
        assert [t.values for t in trials] == [list(reversed(v.values)) for v in forward]

    def test_an_objective_the_sweep_never_recorded_is_refused(self):
        cfg = MultiObjective()
        run_cfg = _run_cfg()
        bench = bn.Bench("warm_missing", cfg, run_cfg=run_cfg)
        sweep = bench.plot_sweep(
            input_vars=[cfg.param.x], result_vars=[cfg.param.obj1], run_cfg=run_cfg
        )
        with pytest.raises(ValueError, match="cannot build trials"):
            sweep.bench_results_to_optuna_trials(True, ["obj1", "obj2"])
