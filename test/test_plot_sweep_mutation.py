"""Mutation safety tests for plot_sweep() deepcopy optimization.

These tests verify that plot_sweep() does not mutate:
1. The caller's input_vars/result_vars/const_vars when passed explicitly
2. The bench instance's self.input_vars/result_vars/const_vars when used as defaults

All tests should pass BEFORE and AFTER the deepcopy deduplication optimization.
"""

import random
from copy import deepcopy

import pytest

from bencher import Bench, BenchRunCfg
from bencher.example.benchmark_data import ExampleBenchCfg


@pytest.fixture
def bench():
    """Create a fresh Bench instance with ExampleBenchCfg worker."""
    random.seed(42)
    return Bench("test_mutation_safety", ExampleBenchCfg())


@pytest.fixture
def run_cfg():
    """Minimal run config for fast tests."""
    return BenchRunCfg(repeats=1, over_time=False, auto_plot=False)


# --- Tests for self.* attribute mutation safety ---


class TestSelfVarsMutationSafety:
    """Verify that plot_sweep() does not mutate bench.input_vars/result_vars/const_vars."""

    def test_plot_sweep_does_not_mutate_self_input_vars(self, bench, run_cfg):
        bench.input_vars = [ExampleBenchCfg.param.theta]
        snapshot = deepcopy(bench.input_vars)

        bench.plot_sweep(
            title="mutation_test_input",
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=run_cfg,
        )

        assert len(bench.input_vars) == len(snapshot)
        for orig, snap in zip(bench.input_vars, snapshot):
            assert orig.name == snap.name
            assert orig.default == snap.default

    def test_plot_sweep_does_not_mutate_self_result_vars(self, bench, run_cfg):
        bench.result_vars = [ExampleBenchCfg.param.out_sin]
        snapshot = deepcopy(bench.result_vars)

        bench.plot_sweep(
            title="mutation_test_result",
            input_vars=[ExampleBenchCfg.param.theta],
            run_cfg=run_cfg,
        )

        assert len(bench.result_vars) == len(snapshot)
        for orig, snap in zip(bench.result_vars, snapshot):
            assert orig.name == snap.name

    def test_plot_sweep_does_not_mutate_self_const_vars(self, bench, run_cfg):
        bench.const_vars = [(ExampleBenchCfg.param.offset, 0.1)]
        snapshot = deepcopy(bench.const_vars)

        bench.plot_sweep(
            title="mutation_test_const",
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=run_cfg,
        )

        assert len(bench.const_vars) == len(snapshot)
        for orig, snap in zip(bench.const_vars, snapshot):
            assert orig[0].name == snap[0].name
            assert orig[1] == snap[1]


# --- Tests for caller-provided variable mutation safety ---


class TestCallerVarsMutationSafety:
    """Verify that plot_sweep() does not mutate variables passed by the caller."""

    def test_plot_sweep_does_not_mutate_caller_input_vars(self, bench, run_cfg):
        caller_input_vars = [ExampleBenchCfg.param.theta]
        snapshot = deepcopy(caller_input_vars)

        bench.plot_sweep(
            title="caller_mutation_test_input",
            input_vars=caller_input_vars,
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=run_cfg,
        )

        assert len(caller_input_vars) == len(snapshot)
        for orig, snap in zip(caller_input_vars, snapshot):
            assert orig.name == snap.name
            assert orig.default == snap.default

    def test_plot_sweep_does_not_mutate_caller_result_vars(self, bench, run_cfg):
        caller_result_vars = [ExampleBenchCfg.param.out_sin]
        snapshot = deepcopy(caller_result_vars)

        bench.plot_sweep(
            title="caller_mutation_test_result",
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=caller_result_vars,
            run_cfg=run_cfg,
        )

        assert len(caller_result_vars) == len(snapshot)
        for orig, snap in zip(caller_result_vars, snapshot):
            assert orig.name == snap.name

    def test_plot_sweep_does_not_mutate_caller_const_vars(self, bench, run_cfg):
        caller_const_vars = [(ExampleBenchCfg.param.offset, 0.1)]
        snapshot = deepcopy(caller_const_vars)

        bench.plot_sweep(
            title="caller_mutation_test_const",
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            const_vars=caller_const_vars,
            run_cfg=run_cfg,
        )

        assert len(caller_const_vars) == len(snapshot)
        for orig, snap in zip(caller_const_vars, snapshot):
            assert orig[0].name == snap[0].name
            assert orig[1] == snap[1]


# --- Golden output regression test ---


class TestPlotSweepResultConsistency:
    """Verify that plot_sweep() produces consistent results."""

    def test_plot_sweep_results_identical_across_calls(self, bench, run_cfg):
        """Two calls with the same inputs should produce identical datasets."""
        common_kwargs = dict(
            title="consistency_test",
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=run_cfg,
        )

        random.seed(42)
        result1 = bench.plot_sweep(**common_kwargs)
        random.seed(42)
        result2 = bench.plot_sweep(**common_kwargs)

        ds1 = result1.ds
        ds2 = result2.ds

        assert set(ds1.data_vars) == set(ds2.data_vars)
        for var in ds1.data_vars:
            assert ds1[var].equals(ds2[var]), f"Data variable '{var}' differs between runs"

    def test_plot_sweep_with_self_vars_matches_explicit(self, bench, run_cfg):
        """Using self.input_vars should produce the same result as passing them explicitly."""
        input_vars = [ExampleBenchCfg.param.theta]
        result_vars = [ExampleBenchCfg.param.out_sin]

        # Explicit pass
        random.seed(42)
        result_explicit = bench.plot_sweep(
            title="explicit_test",
            input_vars=input_vars,
            result_vars=result_vars,
            run_cfg=run_cfg,
        )

        # Via self.* defaults
        bench2 = Bench("test_mutation_safety_2", ExampleBenchCfg())
        bench2.input_vars = deepcopy(input_vars)
        bench2.result_vars = deepcopy(result_vars)
        random.seed(42)
        result_default = bench2.plot_sweep(
            title="explicit_test",
            run_cfg=run_cfg,
        )

        ds1 = result_explicit.ds
        ds2 = result_default.ds

        assert set(ds1.data_vars) == set(ds2.data_vars)
        for var in ds1.data_vars:
            assert ds1[var].equals(ds2[var]), f"Data variable '{var}' differs"
