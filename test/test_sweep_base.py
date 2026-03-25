import unittest

from bencher.example.benchmark_data import AllSweepVars, PostprocessFn
import bencher as bn
from hypothesis import given, strategies as st


class TestSweepBase(unittest.TestCase):
    def test_with_samples(self) -> None:
        """Check that using with_samples does not have side effects"""

        sweep_samples_before = AllSweepVars.param.var_float.values()
        custom_samples = AllSweepVars.param.var_float.with_samples(5).values()
        sweep_samples_after = AllSweepVars.param.var_float.values()

        self.assertEqual(str(sweep_samples_before), str(sweep_samples_after))
        self.assertNotEqual(str(sweep_samples_before), str(custom_samples))

    def test_with_const(self) -> None:
        """Check that setting a const returns the right const"""

        res = AllSweepVars.param.var_float.with_const(5)

        self.assertEqual(res[1], 5)

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

        self.assertEqual(consts_len, len(consts))
        self.assertEqual(consts_len - 1, len(consts_after))

        self.assertTrue(AllSweepVars.param.var_float not in consts)
        self.assertTrue(explorer.param.var_float not in consts)

    def test_override_const(self) -> None:
        """Check that setting a const returns the right const"""

        explorer = AllSweepVars()
        bn.Bench("tst_cnst", explorer)

        consts = explorer.get_input_defaults()
        const_override = explorer.get_input_defaults([AllSweepVars.param.var_float.with_const(2)])

        # const_override_class = AllSweepVars.get_input_defaults(
        #     [AllSweepVars.param.var_float.with_const(2)]
        # )

        # const_override_instance = explorer.get_input_defaults(
        #     [explorer.param.var_float.with_const(2)]
        # )

        print(consts)
        print("overridden")
        print(const_override)

        self.assertEqual(consts[0][1], 5)
        self.assertEqual(const_override[0][1], 2)
        # self.assertEqual(const_override_class[0][1], 2)
        # self.assertEqual(const_override_instance[0][1], 2)

        self.assertNotEqual(consts, const_override)
        self.assertEqual(len(consts), len(const_override))

    def test_override_defaults(self):
        exp = AllSweepVars()

        class_defaults = AllSweepVars.get_input_defaults(
            [AllSweepVars.param.var_float.with_const(3)]
        )

        # class_defaults_over = AllSweepVars.get_input_defaults_override(var_float=3)

        # self.assertEqual(class_defaults, class_defaults_over)

        self.assertEqual(class_defaults[0][1], 3)

        # check that the defaults have not been modified
        default_defaults = AllSweepVars.get_input_defaults()
        self.assertEqual(default_defaults[0][1], 5)

        instance_defaults = exp.get_input_defaults([exp.param.var_float.with_const(2)])
        self.assertEqual(instance_defaults[0][1], 2)

    def test_default_values_override(self):
        initial = AllSweepVars.get_input_defaults()

        override_defaults = AllSweepVars.get_input_defaults_override()
        override = AllSweepVars.get_input_defaults_override(var_float=1)
        after = AllSweepVars.get_input_defaults()

        self.assertListEqual(initial, after)
        self.assertNotEqual(override, override_defaults)

    def test_with_sample_values(self):
        vals = AllSweepVars.param.var_float.with_sample_values([0, 1]).values()
        self.assertEqual(vals[0], 0)
        self.assertEqual(vals[1], 1)

        defaults = AllSweepVars.param.var_float.values()
        self.assertEqual(defaults[9], 10)

        vals = AllSweepVars.param.var_enum.with_sample_values([PostprocessFn.negate]).values()
        self.assertEqual(len(vals), 1)
        self.assertEqual(vals[0], PostprocessFn.negate)

    def test_bool_as_dim(self):
        res = AllSweepVars.param.var_bool.as_dim(True)

        self.assertSequenceEqual(res.values, [True, False])

        res = AllSweepVars.param.var_bool.as_dim(False)
        self.assertSequenceEqual(res.values, [True, False])

    def test_float_as_dim(self):
        res = AllSweepVars.param.var_float.as_dim(True)

        self.assertListEqual(res.values, list(AllSweepVars.param.var_float.values()))

        res = AllSweepVars.param.var_float.as_dim(False)
        self.assertSequenceEqual(res.range, (0, 10))

    def test_float_step(self):
        step = 0.0001

        class FloatDim(bn.ParametrizedSweep):
            var_float = bn.FloatSweep(bounds=(0, 0.001), step=step)

        dim = FloatDim.param.var_float.as_dim(False)
        self.assertEqual(dim.step, step)

        vals = FloatDim.param.var_float.as_dim(True)
        self.assertEqual(10, len(vals.values))
        self.assertEqual(dim.step, step)

    def sweep_up_to(self, var, var_type, level=7):
        res_old = var.with_level(1)
        for i in range(2, level):
            res = var.with_level(i)
            new_vals = res.values()
            print(res_old.values(), new_vals)
            for i in res_old.values():
                self.assertTrue(isinstance(i, var_type))
                self.assertTrue(i in new_vals)
                for n in new_vals:
                    print("\t", i == n)
            res_old = res

    @given(st.floats(min_value=0.1, allow_nan=False, allow_infinity=False))
    def test_levels_float(self, upper) -> None:
        var_float = bn.FloatSweep(bounds=(0, upper))
        self.sweep_up_to(var_float, float)

    def test_level_limits(self):
        asv = AllSweepVars()

        bench = bn.Bench("test_level_limits", asv)
        run_cfg = bn.BenchRunCfg()

        run_cfg.level = 4
        res = bench.plot_sweep("asv", input_vars=[AllSweepVars.param.var_float], run_cfg=run_cfg)
        self.assertEqual(res.result_samples(), 5)

        res = bench.plot_sweep("asv", input_vars=[AllSweepVars.param.var_int_big], run_cfg=run_cfg)
        self.assertEqual(res.result_samples(), 5)

        run_cfg.level = 4
        res = bench.plot_sweep(
            "asv",
            input_vars=[AllSweepVars.param.var_float.with_level(level=run_cfg.level, max_level=3)],
            run_cfg=run_cfg,
        )
        self.assertEqual(res.result_samples(), 3, "the number of samples should be limited to 3")

        res = bench.plot_sweep(
            "asv",
            input_vars=[
                AllSweepVars.param.var_int_big.with_level(level=run_cfg.level, max_level=3)
            ],
            run_cfg=run_cfg,
        )
        self.assertEqual(res.result_samples(), 3, "the number of samples should be limited to 3")

    # @given(st.integers(min_value=0), st.integers(min_value=1,max_value=10))
    # def test_levels_int(self, start, var_range):
    #     var_int = bn.IntSweep(default=start, bounds=(start, start + var_range))
    #     self.sweep_up_to(var_int, int, level=5)

    def test_callable_sweep_values(self):
        vals = AllSweepVars.param.var_float([0, 1, 5]).values()
        self.assertEqual(vals, [0, 1, 5])

    def test_callable_sweep_samples(self):
        sampled = AllSweepVars.param.var_float(samples=3).values()
        self.assertEqual(len(sampled), 3)

    def test_callable_sweep_no_args(self):
        original = AllSweepVars.param.var_float.values()
        copy = AllSweepVars.param.var_float().values()
        self.assertEqual(str(original), str(copy))

    def test_p_with_param_object(self):
        result = bn.p(AllSweepVars.param.var_float, [0, 1, 5])
        self.assertIsInstance(result, bn.SweepBase)
        self.assertEqual(result.values(), [0, 1, 5])

    def test_p_with_param_object_samples(self):
        result = bn.p(AllSweepVars.param.var_float, samples=3)
        self.assertIsInstance(result, bn.SweepBase)
        self.assertEqual(len(result.values()), 3)


if __name__ == "__main__":
    # TestSweepBase().test_override_defaults()
    pass

    # TestSweepBase().test_levels_int(0, 10)
