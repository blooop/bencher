"""Tests for bencher/results/explorer_result.py"""

import unittest

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject
from bencher.results.explorer_result import ExplorerResult


class TestExplorerResult(unittest.TestCase):
    def test_to_plot_with_inputs(self):
        bench = BenchableObject().to_bench()
        res = bench.plot_sweep(
            "explorer_test",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bch.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )
        # Call ExplorerResult.to_plot via the result object (it inherits from ExplorerResult)
        result = ExplorerResult.to_plot(res)
        self.assertIsNotNone(result)

    def test_to_plot_without_inputs(self):
        bench = BenchableObject().to_bench()
        res = bench.plot_sweep(
            "explorer_no_inputs",
            input_vars=[],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bch.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )
        # Falls back to pandas hvplot explorer for 0D
        result = ExplorerResult.to_plot(res)
        self.assertIsNotNone(result)
