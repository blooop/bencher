#!/usr/bin/env python3
"""Simplified test suite for rerun visualization backends"""

import pytest
import math
import importlib.util
import numpy as np
import bencher as bch

# Skip all tests if rerun is not available
RERUN_AVAILABLE = importlib.util.find_spec("rerun") is not None

pytestmark = pytest.mark.skipif(not RERUN_AVAILABLE, reason="rerun-sdk not available")


def test_rerun_import():
    """Test that rerun modules can be imported"""
    from bencher.results.rerun_results import (
        RerunResultBase,
        LineRerunResult,
        HeatmapRerunResult,
        TabsRerunResult,
        RerunComposableResult,
    )

    assert RerunResultBase is not None
    assert LineRerunResult is not None
    assert HeatmapRerunResult is not None
    assert TabsRerunResult is not None
    assert RerunComposableResult is not None


def test_categorical_conversion():
    """Test categorical to numeric conversion"""
    from bencher.results.rerun_results.rerun_result import RerunResultBase

    # Create a mock benchmark config
    class MockBenchCfg:
        bench_name = "test"

    base_result = RerunResultBase(MockBenchCfg())

    # Test categorical conversion
    categorical_data = np.array(["sin", "cos", "sin", "tan"])
    numeric_data, labels = base_result._convert_coords_to_numeric(categorical_data, None)

    assert labels is not None
    assert len(labels) == 3  # unique values: sin, cos, tan
    assert len(numeric_data) == 4
    assert all(isinstance(x, (int, np.integer)) for x in numeric_data)


def test_numeric_passthrough():
    """Test that numeric data passes through unchanged"""
    from bencher.results.rerun_results.rerun_result import RerunResultBase

    # Create a mock benchmark config
    class MockBenchCfg:
        bench_name = "test"

    base_result = RerunResultBase(MockBenchCfg())

    # Test numeric passthrough
    numeric_data = np.array([1.0, 2.0, 3.0])
    result_data, labels = base_result._convert_coords_to_numeric(numeric_data, None)

    assert labels is None
    assert np.array_equal(result_data, numeric_data)


def test_dataset_matching():
    """Test dataset matching for different plot types"""
    from bencher.results.rerun_results.line_result import LineRerunResult
    from bencher.results.rerun_results.heatmap_result import HeatmapRerunResult
    from bencher.results.rerun_results.tabs_result import TabsRerunResult

    # Mock 1D dataset
    class Mock1DDataset:
        dims = ["theta", "repeat"]
        sizes = {"theta": 5, "repeat": 1}

    # Mock 2D dataset
    class Mock2DDataset:
        dims = ["operation", "theta", "repeat"]
        sizes = {"operation": 3, "theta": 5, "repeat": 1}

    # Mock 3D dataset
    class Mock3DDataset:
        dims = ["operation", "theta", "amplitude", "repeat"]
        sizes = {"operation": 3, "theta": 5, "amplitude": 2, "repeat": 1}

    dataset_1d = Mock1DDataset()
    dataset_2d = Mock2DDataset()
    dataset_3d = Mock3DDataset()

    # Test line result matching
    assert LineRerunResult.matches_dataset(dataset_1d)
    assert not LineRerunResult.matches_dataset(dataset_2d)
    assert not LineRerunResult.matches_dataset(dataset_3d)

    # Test heatmap result matching
    assert not HeatmapRerunResult.matches_dataset(dataset_1d)
    assert HeatmapRerunResult.matches_dataset(dataset_2d)
    assert not HeatmapRerunResult.matches_dataset(dataset_3d)

    # Test tabs result matching
    assert not TabsRerunResult.matches_dataset(dataset_1d)
    assert not TabsRerunResult.matches_dataset(dataset_2d)
    assert TabsRerunResult.matches_dataset(dataset_3d)


def test_rerun_availability_handling():
    """Test graceful handling when rerun is not available"""
    from bencher.results.rerun_results.rerun_result import RerunResultBase

    # Create a mock benchmark config
    class MockBenchCfg:
        bench_name = "test"

    base_result = RerunResultBase(MockBenchCfg())

    # Test that base methods exist
    assert hasattr(base_result, "_ensure_rerun_initialized")
    assert hasattr(base_result, "_convert_coords_to_numeric")
    assert hasattr(base_result, "_create_entity_path")


class SimpleTestBenchmark(bch.ParametrizedSweep):
    """Simple benchmark for integration testing"""

    theta = bch.FloatSweep(default=0, bounds=[0, math.pi / 4], samples=3, doc="Input angle")
    result = bch.ResultVar(units="v", doc="Output value")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.result = math.sin(self.theta)
        return super().__call__(**kwargs)


def test_simple_rerun_integration():
    """Test basic rerun integration without complex plotting"""
    # Create simple benchmark
    benchmark = SimpleTestBenchmark().to_bench(bch.BenchRunCfg(level=1))

    # Run minimal sweep to create data
    bench_cfg = bch.BenchCfg(
        title="Simple Test",
        input_vars=[SimpleTestBenchmark.param.theta],
        result_vars=[SimpleTestBenchmark.param.result],
        plot_callbacks=[],  # Disable default plotting
    )

    results = benchmark.run_sweep(bench_cfg, bch.BenchRunCfg(level=1))

    # Test that result has rerun capability
    assert hasattr(results, "to_rerun")

    # Test rerun method returns something
    panel = results.to_rerun()
    assert panel is not None


def test_bench_result_integration():
    """Test that BenchResult includes rerun functionality"""
    # Test that BenchResult has the rerun composable result
    from bencher.results.bench_result import BenchResult
    from bencher.results.rerun_results import RerunComposableResult

    # Check inheritance
    assert issubclass(BenchResult, RerunComposableResult)

    # Create a minimal benchmark to test integration
    # benchmark = SimpleTestBenchmark()  # Unused but kept for test structure
    bench_cfg = bch.BenchCfg(
        title="Integration Test",
        input_vars=[SimpleTestBenchmark.param.theta],
        result_vars=[SimpleTestBenchmark.param.result],
        plot_callbacks=[],  # Disable default plotting to avoid issues
    )

    # Create BenchResult instance
    result = BenchResult(bench_cfg)

    # Test that it has rerun methods
    assert hasattr(result, "to_rerun")
    assert hasattr(result, "_ensure_rerun_initialized")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
