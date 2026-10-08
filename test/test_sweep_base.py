import unittest

import pytest
from hypothesis import given, strategies as st

import bencher as bn
from bencher.example.benchmark_data import AllSweepVars, PostprocessFn


class TestSweepBase(unittest.TestCase):
    def test_with_samples(self) -> None:
        """Check that using with_samples does not have side effects"""

        sweep_samples_before = AllSweepVars.param.var_float.values()
        custom_samples = AllSweepVars.param.var_float.with_samples(5).values()
        sweep_samples_after = AllSweepVars.param.var_float.values()

        assert str(sweep_samples_before) == str(sweep_samples_after)
        assert str(sweep_samples_before) != str(custom_samples)

    def test_with_const(self) -> None:
        """Check that setting a const returns the right const"""

        res = AllSweepVars.param.var_float.with_const(5)

        assert res[1] == 5

    def test_setting_const(self) -> None:
        """Check that setting a const returns the right const"""

        explorer = AllSweepVars()
        bench = bn.Bench("tst_cnst", explorer.__call__)

        consts = explorer.get_input_defaults()
        consts_len = len(consts)

        res = bench.plot_sweep(
            "tst",
            input_vars=[AllSweepVars.param.var_float.with_samples(3)],
            const_vars=consts,
            plot_callbacks=False,
        )

        consts_after = [i[0] for i in res.bench_cfg.const_vars]

        assert consts_len == len(consts)
        assert consts_len - 1 == len(consts_after)

        assert AllSweepVars.param.var_float not in consts
        assert explorer.param.var_float not in consts

    def test_override_const(self) -> None:
        """Check that setting a const returns the right const"""

        explorer = AllSweepVars()
        bn.Bench("tst_cnst", explorer)

        consts = explorer.get_input_defaults()
        const_override = explorer.get_input_defaults([AllSweepVars.param.var_float.with_const(2)])

        assert consts[0][1] == 5
        assert const_override[0][1] == 2

        assert consts != const_override
        assert len(consts) == len(const_override)

    def test_override_defaults(self):
        exp = AllSweepVars()

        class_defaults = AllSweepVars.get_input_defaults(
            [AllSweepVars.param.var_float.with_const(3)]
        )

        assert class_defaults[0][1] == 3

        # check that the defaults have not been modified
        default_defaults = AllSweepVars.get_input_defaults()
        assert default_defaults[0][1] == 5

        instance_defaults = exp.get_input_defaults([exp.param.var_float.with_const(2)])
        assert instance_defaults[0][1] == 2

    def test_default_values_override(self):
        initial = AllSweepVars.get_input_defaults()

        override_defaults = AllSweepVars.get_input_defaults_override()
        override = AllSweepVars.get_input_defaults_override(var_float=1)
        after = AllSweepVars.get_input_defaults()

        assert initial == after
        assert override != override_defaults

    def test_with_sample_values(self):
        vals = AllSweepVars.param.var_float.with_sample_values([0, 1]).values()
        assert vals[0] == 0
        assert vals[1] == 1

        defaults = AllSweepVars.param.var_float.values()
        assert defaults[9] == 10

        vals = AllSweepVars.param.var_enum.with_sample_values([PostprocessFn.negate]).values()
        assert len(vals) == 1
        assert vals[0] == PostprocessFn.negate

    def test_bool_as_dim(self):
        res = AllSweepVars.param.var_bool.as_dim(True)

        assert list(res.values) == [True, False]

        res = AllSweepVars.param.var_bool.as_dim(False)
        assert list(res.values) == [True, False]

    def test_float_as_dim(self):
        res = AllSweepVars.param.var_float.as_dim(True)

        assert res.values == list(AllSweepVars.param.var_float.values())

        res = AllSweepVars.param.var_float.as_dim(False)
        assert tuple(res.range) == (0, 10)

    def test_float_step(self):
        step = 0.0001

        class FloatDim(bn.ParametrizedSweep):
            var_float = bn.FloatSweep(bounds=(0, 0.001), step=step)

        dim = FloatDim.param.var_float.as_dim(False)
        assert dim.step == step

        vals = FloatDim.param.var_float.as_dim(True)
        assert len(vals.values) == 10
        assert dim.step == step

    def test_with_subsampling_divisions_invalid_raises(self):
        sw = bn.FloatSweep(bounds=[0, 1])
        with pytest.raises(ValueError, match="subsampling_divisions must be >= 1"):
            sw.with_subsampling_divisions(0)
        with pytest.raises(ValueError, match="subsampling_divisions must be >= 1"):
            sw.with_subsampling_divisions(-1)

    def sweep_up_to(self, var, var_type, subsampling_divisions=7):
        res_old = var.with_subsampling_divisions(1)
        for i in range(2, subsampling_divisions):
            res = var.with_subsampling_divisions(i)
            new_vals = res.values()
            for val in res_old.values():
                assert isinstance(val, var_type)
                assert val in new_vals
            res_old = res

    @given(st.floats(min_value=0.1, allow_nan=False, allow_infinity=False))
    def test_levels_float(self, upper) -> None:
        var_float = bn.FloatSweep(bounds=(0, upper))
        self.sweep_up_to(var_float, float)

    def test_level_limits(self):
        asv = AllSweepVars()

        bench = bn.Bench("test_level_limits", asv)
        run_cfg = bn.BenchRunCfg()

        run_cfg.subsampling_divisions = 4
        res = bench.plot_sweep("asv", input_vars=[AllSweepVars.param.var_float], run_cfg=run_cfg)
        assert res.result_samples() == 5

        res = bench.plot_sweep("asv", input_vars=[AllSweepVars.param.var_int_big], run_cfg=run_cfg)
        assert res.result_samples() == 5

        run_cfg.subsampling_divisions = 4
        res = bench.plot_sweep(
            "asv",
            input_vars=[
                AllSweepVars.param.var_float.with_subsampling_divisions(
                    subsampling_divisions=run_cfg.subsampling_divisions, max_subsampling_divisions=3
                )
            ],
            run_cfg=run_cfg,
        )
        assert res.result_samples() == 3, "the number of samples should be limited to 3"

        res = bench.plot_sweep(
            "asv",
            input_vars=[
                AllSweepVars.param.var_int_big.with_subsampling_divisions(
                    subsampling_divisions=run_cfg.subsampling_divisions, max_subsampling_divisions=3
                )
            ],
            run_cfg=run_cfg,
        )
        assert res.result_samples() == 3, "the number of samples should be limited to 3"

    def test_callable_sweep_values(self):
        vals = AllSweepVars.param.var_float([0, 1, 5]).values()
        assert vals == [0, 1, 5]

    def test_callable_sweep_samples(self):
        sampled = AllSweepVars.param.var_float(samples=3).values()
        assert len(sampled) == 3

    def test_callable_sweep_no_args(self):
        original = AllSweepVars.param.var_float.values()
        copy = AllSweepVars.param.var_float().values()
        assert str(original) == str(copy)

    def test_sweep_with_param_object(self):
        result = bn.sweep(AllSweepVars.param.var_float, [0, 1, 5])
        assert isinstance(result, bn.SweepBase)
        assert result.values() == [0, 1, 5]

    def test_sweep_with_param_object_samples(self):
        result = bn.sweep(AllSweepVars.param.var_float, samples=3)
        assert isinstance(result, bn.SweepBase)
        assert len(result.values()) == 3

    def test_sweep_with_param_object_bounds(self):
        result = bn.sweep(AllSweepVars.param.var_float, bounds=(0, 5), samples=3)
        assert isinstance(result, bn.SweepBase)
        assert len(result.values()) == 3
        assert result.values()[0] == pytest.approx(0.0, abs=1e-7)
        assert result.values()[-1] == pytest.approx(5.0, abs=1e-7)

    def test_sweep_with_string_bounds(self):
        result = bn.sweep("var_float", bounds=(0, 5), samples=3)
        assert isinstance(result, dict)
        assert result["bounds"] == (0, 5)
        assert result["samples"] == 3

    def test_callable_sweep_bounds(self):
        result = AllSweepVars.param.var_float(bounds=(0, 5), samples=3)
        assert isinstance(result, bn.SweepBase)
        assert len(result.values()) == 3
        assert result.values()[0] == pytest.approx(0.0, abs=1e-7)
        assert result.values()[-1] == pytest.approx(5.0, abs=1e-7)

    def test_with_bounds_direct(self):
        """Directly test SweepBase.with_bounds() for immutability, bounds, samples, and step."""
        original = AllSweepVars.param.var_float
        original_bounds = getattr(original, "softbounds", getattr(original, "bounds", None))
        original_samples = original.samples

        # Manually set step so we can verify with_bounds resets it
        original.step = 0.5

        # with_bounds without samples: bounds updated, samples preserved, step reset
        updated = original.with_bounds(2.0, 8.0)
        assert original is not updated
        # original unchanged
        assert getattr(original, "softbounds", getattr(original, "bounds", None)) == original_bounds
        assert original.step == 0.5
        # updated has new bounds
        updated_bounds = getattr(updated, "softbounds", getattr(updated, "bounds", None))
        assert updated_bounds == (2.0, 8.0)
        assert updated.samples == original_samples
        assert updated.step is None

        # with_bounds with samples: both bounds and samples updated, step reset
        updated2 = original.with_bounds(1.0, 9.0, samples=10)
        assert original is not updated2
        updated2_bounds = getattr(updated2, "softbounds", getattr(updated2, "bounds", None))
        assert updated2_bounds == (1.0, 9.0)
        assert updated2.samples == 10
        assert updated2.step is None

        # Clean up
        original.step = None

    def test_with_bounds_invalid_range(self):
        """with_bounds(low > high) raises ValueError."""
        with pytest.raises(ValueError, match="low must not exceed high"):
            AllSweepVars.param.var_float.with_bounds(10.0, 2.0)

    def test_with_bounds_zero_width_is_one_sample(self):
        """A zero-width range is legal and yields a single sample.

        Previously rejected alongside an inverted range. Expressing a collapsed
        range as ``sample_values`` instead changes the sweep's identity, so a
        caller with a computed range had no way to stay in one series.
        """
        collapsed = AllSweepVars.param.var_float.with_bounds(5.0, 5.0)
        assert list(collapsed.values()) == [5.0]

    def test_with_bounds_zero_width_rejects_multiple_samples(self):
        """samples > 1 over a zero-width range is a contradiction."""
        with pytest.raises(ValueError, match="zero-width"):
            AllSweepVars.param.var_float.with_bounds(5.0, 5.0, samples=5)

    def test_callable_conflicts_raise(self):
        """Passing values together with bounds or samples raises ValueError."""
        with pytest.raises(ValueError, match="Cannot combine 'values' with 'bounds' or 'samples'"):
            AllSweepVars.param.var_float([1, 2], bounds=(0, 5))
        with pytest.raises(ValueError, match="Cannot combine 'values' with 'bounds' or 'samples'"):
            AllSweepVars.param.var_float([1, 2], samples=3)
