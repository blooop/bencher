"""Mutation safety tests for plot_sweep() deepcopy optimization.

These tests verify that plot_sweep() does not mutate:
1. The caller's input_vars/result_vars/const_vars when passed explicitly
2. The bench instance's self.input_vars/result_vars/const_vars when used as defaults

All tests should pass BEFORE and AFTER the deepcopy deduplication optimization.
"""

import random
import unittest
from copy import deepcopy

from bencher import Bench, BenchRunCfg
from bencher.example.benchmark_data import ExampleBenchCfg


class TestSelfVarsMutationSafety(unittest.TestCase):
    """Verify that plot_sweep() does not mutate bench.input_vars/result_vars/const_vars."""

    def setUp(self):
        random.seed(42)
        self.bench = Bench("test_mutation_safety", ExampleBenchCfg())
        self.run_cfg = BenchRunCfg(repeats=1, over_time=False, auto_plot=False)

    def test_plot_sweep_does_not_mutate_self_input_vars(self):
        self.bench.input_vars = [ExampleBenchCfg.param.theta]
        snapshot = deepcopy(self.bench.input_vars)

        self.bench.plot_sweep(
            title="mutation_test_input",
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=self.run_cfg,
        )

        self.assertEqual(len(self.bench.input_vars), len(snapshot))
        for orig, snap in zip(self.bench.input_vars, snapshot):
            self.assertEqual(orig.name, snap.name)
            self.assertEqual(orig.default, snap.default)

    def test_plot_sweep_does_not_mutate_self_result_vars(self):
        self.bench.result_vars = [ExampleBenchCfg.param.out_sin]
        snapshot = deepcopy(self.bench.result_vars)

        self.bench.plot_sweep(
            title="mutation_test_result",
            input_vars=[ExampleBenchCfg.param.theta],
            run_cfg=self.run_cfg,
        )

        self.assertEqual(len(self.bench.result_vars), len(snapshot))
        for orig, snap in zip(self.bench.result_vars, snapshot):
            self.assertEqual(orig.name, snap.name)

    def test_plot_sweep_does_not_mutate_self_const_vars(self):
        self.bench.const_vars = [(ExampleBenchCfg.param.offset, 0.1)]
        snapshot = deepcopy(self.bench.const_vars)

        self.bench.plot_sweep(
            title="mutation_test_const",
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=self.run_cfg,
        )

        self.assertEqual(len(self.bench.const_vars), len(snapshot))
        for orig, snap in zip(self.bench.const_vars, snapshot):
            self.assertEqual(orig[0].name, snap[0].name)
            self.assertEqual(orig[1], snap[1])


class TestCallerVarsMutationSafety(unittest.TestCase):
    """Verify that plot_sweep() does not mutate variables passed by the caller."""

    def setUp(self):
        random.seed(42)
        self.bench = Bench("test_caller_mutation", ExampleBenchCfg())
        self.run_cfg = BenchRunCfg(repeats=1, over_time=False, auto_plot=False)

    def test_plot_sweep_does_not_mutate_caller_input_vars(self):
        caller_input_vars = [ExampleBenchCfg.param.theta]
        snapshot = deepcopy(caller_input_vars)

        self.bench.plot_sweep(
            title="caller_mutation_test_input",
            input_vars=caller_input_vars,
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=self.run_cfg,
        )

        self.assertEqual(len(caller_input_vars), len(snapshot))
        for orig, snap in zip(caller_input_vars, snapshot):
            self.assertEqual(orig.name, snap.name)
            self.assertEqual(orig.default, snap.default)

    def test_plot_sweep_does_not_mutate_caller_result_vars(self):
        caller_result_vars = [ExampleBenchCfg.param.out_sin]
        snapshot = deepcopy(caller_result_vars)

        self.bench.plot_sweep(
            title="caller_mutation_test_result",
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=caller_result_vars,
            run_cfg=self.run_cfg,
        )

        self.assertEqual(len(caller_result_vars), len(snapshot))
        for orig, snap in zip(caller_result_vars, snapshot):
            self.assertEqual(orig.name, snap.name)

    def test_plot_sweep_does_not_mutate_caller_const_vars(self):
        caller_const_vars = [(ExampleBenchCfg.param.offset, 0.1)]
        snapshot = deepcopy(caller_const_vars)

        self.bench.plot_sweep(
            title="caller_mutation_test_const",
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            const_vars=caller_const_vars,
            run_cfg=self.run_cfg,
        )

        self.assertEqual(len(caller_const_vars), len(snapshot))
        for orig, snap in zip(caller_const_vars, snapshot):
            self.assertEqual(orig[0].name, snap[0].name)
            self.assertEqual(orig[1], snap[1])


class TestPlotSweepResultConsistency(unittest.TestCase):
    """Verify that plot_sweep() produces consistent results."""

    def setUp(self):
        random.seed(42)
        self.bench = Bench("test_consistency", ExampleBenchCfg())
        self.run_cfg = BenchRunCfg(repeats=1, over_time=False, auto_plot=False)

    def test_plot_sweep_results_identical_across_calls(self):
        """Two calls with the same inputs should produce identical datasets."""
        common_kwargs = dict(
            title="consistency_test",
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=self.run_cfg,
        )

        random.seed(42)
        result1 = self.bench.plot_sweep(**common_kwargs)
        random.seed(42)
        result2 = self.bench.plot_sweep(**common_kwargs)

        ds1 = result1.ds
        ds2 = result2.ds

        self.assertEqual(set(ds1.data_vars), set(ds2.data_vars))
        for var in ds1.data_vars:
            self.assertTrue(
                ds1[var].equals(ds2[var]), f"Data variable '{var}' differs between runs"
            )

    def test_plot_sweep_with_self_vars_matches_explicit(self):
        """Using self.input_vars should produce the same result as passing them explicitly."""
        input_vars = [ExampleBenchCfg.param.theta]
        result_vars = [ExampleBenchCfg.param.out_sin]

        random.seed(42)
        result_explicit = self.bench.plot_sweep(
            title="explicit_test",
            input_vars=input_vars,
            result_vars=result_vars,
            run_cfg=self.run_cfg,
        )

        bench2 = Bench("test_mutation_safety_2", ExampleBenchCfg())
        bench2.input_vars = deepcopy(input_vars)
        bench2.result_vars = deepcopy(result_vars)
        random.seed(42)
        result_default = bench2.plot_sweep(
            title="explicit_test",
            run_cfg=self.run_cfg,
        )

        ds1 = result_explicit.ds
        ds2 = result_default.ds

        self.assertEqual(set(ds1.data_vars), set(ds2.data_vars))
        for var in ds1.data_vars:
            self.assertTrue(ds1[var].equals(ds2[var]), f"Data variable '{var}' differs")


class TestDictInputVars(unittest.TestCase):
    """Verify that plot_sweep() accepts dict and inline-dict input_vars."""

    def setUp(self):
        random.seed(42)
        self.bench = Bench("test_dict_input", ExampleBenchCfg())
        self.run_cfg = BenchRunCfg(repeats=1, over_time=False, auto_plot=False)

    def test_dict_with_list_values(self):
        res = self.bench.plot_sweep(
            title="dict_list",
            input_vars={"theta": [0.0, 1.0, 2.0]},
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=self.run_cfg,
        )
        self.assertEqual(res.result_samples(), 3)

    def test_dict_with_int_samples(self):
        res = self.bench.plot_sweep(
            title="dict_int",
            input_vars={"theta": 5},
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=self.run_cfg,
        )
        self.assertEqual(res.result_samples(), 5)

    def test_dict_with_none_defaults(self):
        res = self.bench.plot_sweep(
            title="dict_none",
            input_vars={"theta": None},
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=self.run_cfg,
        )
        self.assertEqual(res.result_samples(), 30)  # theta default samples=30

    def test_list_with_inline_dict(self):
        res = self.bench.plot_sweep(
            title="list_inline_dict",
            input_vars=[{"theta": [0.0, 1.0, 2.0]}],
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=self.run_cfg,
        )
        self.assertEqual(res.result_samples(), 3)

    def test_list_mixed_string_and_inline_dict(self):
        res = self.bench.plot_sweep(
            title="list_mixed",
            input_vars=[{"theta": [0.0, 1.0]}, "offset"],
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=self.run_cfg,
        )
        # 2 theta values * 30 offset samples = 60
        self.assertEqual(res.result_samples(), 60)
