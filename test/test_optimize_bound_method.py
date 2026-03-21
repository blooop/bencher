"""Tests that optimize() works when the worker is a bound method of a ParametrizedSweep."""

import unittest

import bencher as bn
from bencher.example.optuna.example_optuna import ToyOptimisationProblem


class TestOptimizeBoundMethod(unittest.TestCase):
    """Regression tests for optimize() after plot_sweep() with a bound-method worker."""

    def test_optimize_after_plot_sweep_with_bound_method(self):
        """optimize() should succeed when the Bench was created with a bound method."""
        explorer = ToyOptimisationProblem()
        run_cfg = bn.BenchRunCfg(level=2)

        bench = bn.Bench("Rastrigin", explorer.rastrigin, run_cfg=run_cfg)
        bench.plot_sweep(
            "Rastrigin",
            input_vars=[explorer.param.input1, explorer.param.input2],
            result_vars=[explorer.param.output],
            run_cfg=run_cfg,
            plot_callbacks=False,
        )

        # This used to raise:
        # ValueError: No result variables with an optimization direction found.
        result = bench.optimize(n_trials=5)
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.study)
        self.assertGreater(len(result.study.trials), 0)

    def test_worker_class_instance_not_set_for_bound_method(self):
        """worker_class_instance stays None for a bound method (no side effects on plot_sweep)."""
        explorer = ToyOptimisationProblem()
        bench = bn.Bench("test", explorer.rastrigin)
        self.assertIsNone(bench.worker_class_instance)

    def test_worker_class_instance_none_for_plain_function(self):
        """worker_class_instance should remain None for a plain function."""

        def plain_fn():
            return {"output": 1.0}

        bench = bn.Bench("test", plain_fn)
        self.assertIsNone(bench.worker_class_instance)

    def test_bn_run_with_optimise(self):
        """bn.run() with optimise parameter should work for bound-method benchmarks."""
        from bencher.example.optuna.example_optuna import optuna_rastrigin

        results = bn.run(optuna_rastrigin, optimise=5, show=False, level=2)
        self.assertIsNotNone(results)


if __name__ == "__main__":
    unittest.main()
