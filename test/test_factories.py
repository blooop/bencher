"""Tests for the factories module."""

import unittest
from bencher.factories import create_bench, create_bench_runner
from bencher.variables.parametrised_sweep import ParametrizedSweep
from bencher.bench_cfg import BenchRunCfg


class SimpleSweep(ParametrizedSweep):
    """Simple sweep class for testing."""


class TestCreateBench(unittest.TestCase):
    def test_create_bench_default_name(self):
        """Test create_bench derives name from sweep when not provided."""
        sweep = SimpleSweep()
        bench = create_bench(sweep)
        # Name should be sweep.name minus the last 5 chars (param adds digits)
        assert bench.bench_name == sweep.name[:-5]

    def test_create_bench_custom_name(self):
        """Test create_bench uses provided name."""
        sweep = SimpleSweep()
        bench = create_bench(sweep, name="custom_bench")
        assert bench.bench_name == "custom_bench"

    def test_create_bench_with_run_cfg(self):
        """Test create_bench accepts run_cfg."""
        sweep = SimpleSweep()
        run_cfg = BenchRunCfg()
        bench = create_bench(sweep, run_cfg=run_cfg)
        assert bench.run_cfg is run_cfg


class TestCreateBenchRunner(unittest.TestCase):
    def test_create_bench_runner_default_run_cfg(self):
        """Test create_bench_runner creates default run_cfg when not provided."""
        sweep = SimpleSweep()
        runner = create_bench_runner(sweep)
        assert runner.run_cfg is not None

    def test_create_bench_runner_with_run_cfg(self):
        """Test create_bench_runner accepts run_cfg."""
        sweep = SimpleSweep()
        run_cfg = BenchRunCfg()
        runner = create_bench_runner(sweep, run_cfg=run_cfg)
        # BenchRunner.setup_run_cfg creates a copy, so just verify it's set
        assert runner.run_cfg is not None

    def test_create_bench_runner_with_name(self):
        """Test create_bench_runner uses provided name."""
        sweep = SimpleSweep()
        runner = create_bench_runner(sweep, name="custom_runner")
        assert runner.name == "custom_runner"


class TestParametrizedSweepDelegation(unittest.TestCase):
    """Test that ParametrizedSweep methods delegate to factory functions."""

    def test_to_bench_delegation(self):
        """Test to_bench delegates to create_bench."""
        sweep = SimpleSweep()
        bench = sweep.to_bench(name="test_bench")
        assert bench.bench_name == "test_bench"

    def test_to_bench_runner_delegation(self):
        """Test to_bench_runner delegates to create_bench_runner."""
        sweep = SimpleSweep()
        runner = sweep.to_bench_runner(name="test_runner")
        assert runner.name == "test_runner"


if __name__ == "__main__":
    unittest.main()
