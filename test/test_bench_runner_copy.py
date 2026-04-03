"""Mutation safety and copy-elimination tests for BenchRunner.run().

These tests verify that:
1. run() does not mutate self.run_cfg or caller-provided run_cfg
2. Each benchmark iteration receives an independent run_cfg object
3. setup_run_cfg() never mutates its input
4. BenchRunCfg has no mutable param fields (guard test)
5. The redundant entry-level deepcopy has been eliminated

All tests except test_deepcopy_count_* should pass BEFORE and AFTER the optimization.
"""

import unittest
from copy import deepcopy
from unittest.mock import patch

import param

import bencher as bn
from bencher.bench_runner import BenchRunner
from bencher.example.benchmark_data import SimpleBenchClassFloat

# These param types hold mutable containers that require deepcopy for isolation
MUTABLE_PARAM_TYPES = (param.List, param.Dict, param.ClassSelector, param.Tuple)


def _simple_benchmark(run_cfg: bn.BenchRunCfg, report: bn.BenchReport) -> bn.BenchCfg:
    bench = bn.Bench("copy_test", SimpleBenchClassFloat(), run_cfg=run_cfg, report=report)
    return bench.plot_sweep("copy_test")


class TestRunCfgMutationSafety(unittest.TestCase):
    """Verify that run() does not mutate self.run_cfg or caller-provided run_cfg."""

    def test_run_does_not_mutate_self_run_cfg(self):
        """run() must never alter the runner's own run_cfg, regardless of arguments."""
        br = bn.BenchRunner("test_no_mutate")
        br.add(_simple_benchmark)

        snapshot = {k: getattr(br.run_cfg, k) for k in br.run_cfg.param if k != "name"}

        br.run(level=3, repeats=1, cache_samples=False, over_time=True)

        for k, v in snapshot.items():
            self.assertEqual(getattr(br.run_cfg, k), v, f"self.run_cfg.{k} was mutated")

    def test_run_does_not_mutate_explicit_run_cfg(self):
        """run(run_cfg=cfg) must not mutate the caller's cfg object."""
        br = bn.BenchRunner("test_explicit")
        br.add(_simple_benchmark)

        explicit_cfg = bn.BenchRunCfg(level=5, repeats=3, run_tag="explicit")
        snapshot = {k: getattr(explicit_cfg, k) for k in explicit_cfg.param if k != "name"}

        br.run(run_cfg=explicit_cfg, level=2, repeats=1)

        for k, v in snapshot.items():
            self.assertEqual(getattr(explicit_cfg, k), v, f"explicit run_cfg.{k} was mutated")


class TestPerIterationIsolation(unittest.TestCase):
    """Verify each benchmark call receives an independent run_cfg."""

    def test_per_iteration_configs_are_independent(self):
        """Each bench function call must get a distinct run_cfg (not aliased)."""
        received_cfgs = []

        def capturing_benchmark(run_cfg, report):
            received_cfgs.append(run_cfg)
            bench = bn.Bench("cap", SimpleBenchClassFloat(), run_cfg=run_cfg, report=report)
            return bench.plot_sweep("cap")

        br = bn.BenchRunner("test_independent")
        br.add(capturing_benchmark)
        br.run(level=2, max_level=3, repeats=1)

        self.assertEqual(len(received_cfgs), 2)
        self.assertIsNot(received_cfgs[0], received_cfgs[1])
        self.assertEqual(received_cfgs[0].level, 2)
        self.assertEqual(received_cfgs[1].level, 3)

    def test_level_repeats_combinations(self):
        """Multi-level, multi-repeat runs must produce the exact (level, repeats) pairs."""
        combos = []

        def tracking_benchmark(run_cfg, report):
            combos.append((run_cfg.level, run_cfg.repeats))
            bench = bn.Bench("track", SimpleBenchClassFloat(), run_cfg=run_cfg, report=report)
            return bench.plot_sweep("track")

        br = bn.BenchRunner("test_combos")
        br.add(tracking_benchmark)
        br.run(level=2, max_level=3, repeats=1, max_repeats=2)

        # repeats is outer loop, level is inner loop
        expected = [(2, 1), (3, 1), (2, 2), (3, 2)]
        self.assertEqual(combos, expected)


class TestSetupRunCfg(unittest.TestCase):
    """Verify setup_run_cfg() isolation guarantees."""

    def test_setup_run_cfg_does_not_mutate_input(self):
        """setup_run_cfg must not mutate the input run_cfg."""
        original = bn.BenchRunCfg(level=5, run_tag="orig")
        snapshot = {k: getattr(original, k) for k in original.param if k != "name"}

        BenchRunner.setup_run_cfg(original, level=2, cache_samples=False)

        for k, v in snapshot.items():
            self.assertEqual(getattr(original, k), v, f"input run_cfg.{k} was mutated")

    def test_setup_run_cfg_returns_new_object(self):
        """setup_run_cfg must always return a new object, never the input."""
        cfg = bn.BenchRunCfg()
        result = BenchRunner.setup_run_cfg(cfg)
        self.assertIsNot(result, cfg)

        result_none = BenchRunner.setup_run_cfg(None)
        self.assertIsInstance(result_none, bn.BenchRunCfg)


class TestCopyStrategyGuards(unittest.TestCase):
    """Guard tests to catch future changes that would break copy assumptions."""

    def test_benchruncfg_has_no_mutable_param_fields(self):
        """Guard: BenchRunCfg must only have primitive/immutable param fields.

        If this test fails, a mutable param field was added to BenchRunCfg.
        The BenchRunner.run() copy strategy assumes all fields are primitive.
        Adding a mutable field (List, Dict, etc.) requires reviewing the copy
        strategy in BenchRunner.run() and setup_run_cfg().
        """
        for name, p in bn.BenchRunCfg.param.objects().items():
            if name == "name":
                continue  # built-in param.Parameterized attribute
            self.assertNotIsInstance(
                p,
                MUTABLE_PARAM_TYPES,
                f"BenchRunCfg.{name} is {type(p).__name__}, a mutable param type. "
                f"Review the copy strategy in BenchRunner.run() before proceeding.",
            )


class TestCopyElimination(unittest.TestCase):
    """Verify the redundant deepcopy has been eliminated."""

    @patch("bencher.bench_runner.deepcopy", wraps=deepcopy)
    def test_deepcopy_count_no_explicit_run_cfg(self, mock_dc):
        """When run_cfg=None, deepcopy should be called once at entry + once in setup_run_cfg + once per iteration."""
        br = bn.BenchRunner("test_count")
        br.add(_simple_benchmark)

        br.run(level=2, repeats=1)  # 1 bench_fn, 1 level, 1 repeat

        # Expected: 1 at entry (copy self.run_cfg) + 1 in setup_run_cfg + 1 per-iteration = 3
        self.assertEqual(mock_dc.call_count, 3)

    @patch("bencher.bench_runner.deepcopy", wraps=deepcopy)
    def test_deepcopy_count_with_explicit_run_cfg(self, mock_dc):
        """When run_cfg is provided, deepcopy should be called once in setup_run_cfg + once per iteration."""
        br = bn.BenchRunner("test_count_explicit")
        br.add(_simple_benchmark)

        br.run(run_cfg=bn.BenchRunCfg(run_tag="test"), level=2, repeats=1)

        # Expected: 1 call in setup_run_cfg + 1 per-iteration = 2 total
        # Before optimization this was also 2 (no redundant copy when run_cfg is provided)
        self.assertEqual(mock_dc.call_count, 2)
