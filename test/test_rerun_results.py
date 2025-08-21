#!/usr/bin/env python3
"""Test suite for rerun visualization backends"""

import pytest
import math
import importlib.util
from enum import auto
from strenum import StrEnum
import bencher as bch

# Skip all tests if rerun is not available
pytest_plugins = []

RERUN_AVAILABLE = importlib.util.find_spec("rerun") is not None

pytestmark = pytest.mark.skipif(not RERUN_AVAILABLE, reason="rerun-sdk not available")


class Operation(StrEnum):
    """Test enumeration for categorical data"""

    sin = auto()
    cos = auto()
    tan = auto()


class SimpleFloatBenchmark(bch.ParametrizedSweep):
    """Simple benchmark for testing 1D rerun visualizations"""

    theta = bch.FloatSweep(default=0, bounds=[0, math.pi / 4], samples=3, doc="Input angle")
    result = bch.ResultVar(units="v", doc="Output value")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.result = math.sin(self.theta)
        return super().__call__(**kwargs)


class CategoricalBenchmark(bch.ParametrizedSweep):
    """Benchmark with categorical input for testing categorical handling"""

    operation = bch.EnumSweep(Operation, doc="Mathematical operation")
    theta = bch.FloatSweep(default=0, bounds=[0, math.pi / 4], samples=3, doc="Input angle")
    result = bch.ResultVar(units="v", doc="Output value")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        if self.operation == Operation.sin:
            self.result = math.sin(self.theta)
        elif self.operation == Operation.cos:
            self.result = math.cos(self.theta)
        elif self.operation == Operation.tan:
            self.result = math.tan(self.theta)

        return super().__call__(**kwargs)


class ThreeDimensionalBenchmark(bch.ParametrizedSweep):
    """Benchmark with 3D parameter space for testing tabs visualization"""

    operation = bch.EnumSweep(Operation, doc="Mathematical operation")
    theta = bch.FloatSweep(default=0, bounds=[0, math.pi / 4], samples=2, doc="Input angle")
    amplitude = bch.FloatSweep(default=1, bounds=[0.5, 2], samples=2, doc="Amplitude")
    result = bch.ResultVar(units="v", doc="Output value")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        if self.operation == Operation.sin:
            self.result = self.amplitude * math.sin(self.theta)
        elif self.operation == Operation.cos:
            self.result = self.amplitude * math.cos(self.theta)
        elif self.operation == Operation.tan:
            self.result = self.amplitude * math.tan(self.theta)

        return super().__call__(**kwargs)


class TestRerunLineResult:
    """Test suite for LineRerunResult"""

    def test_line_result_creation(self):
        """Test that line result can be created and matches 1D data"""
        from bencher.results.rerun_results.line_result import LineRerunResult

        # Create 1D benchmark data
        benchmark = SimpleFloatBenchmark().to_bench(bch.BenchRunCfg(level=1))

        # Use run_sweep directly to avoid problematic default plotting
        bench_cfg = bch.BenchCfg(
            title="Test 1D",
            input_vars=[SimpleFloatBenchmark.param.theta],
            result_vars=[SimpleFloatBenchmark.param.result],
        )
        results = benchmark.run_sweep(bench_cfg, bch.BenchRunCfg(level=1))

        # Test that line result matches this dataset
        dataset = results.ds[SimpleFloatBenchmark.param.result.name]
        assert LineRerunResult.matches_dataset(dataset)

        # Create line result instance
        line_result = LineRerunResult(results.bench_cfg)
        line_result.ds = results.ds

        # Test visualization creation
        panel = line_result.to_plot(SimpleFloatBenchmark.param.result)
        assert panel is not None

    def test_line_result_categorical_data(self):
        """Test line result with categorical input data"""
        from bencher.results.rerun_results.line_result import LineRerunResult

        # Create categorical benchmark data (1D categorical)
        benchmark = CategoricalBenchmark().to_bench(bch.BenchRunCfg(level=1))
        results = benchmark.plot_sweep(
            input_vars=[CategoricalBenchmark.param.operation],
            result_vars=[CategoricalBenchmark.param.result],
        )

        # Create line result instance
        line_result = LineRerunResult(results.bench_cfg)
        line_result.ds = results.ds

        # Test visualization creation with categorical data
        panel = line_result.to_plot(CategoricalBenchmark.param.result)
        assert panel is not None

    def test_line_result_no_match_2d(self):
        """Test that line result doesn't match 2D data"""
        from bencher.results.rerun_results.line_result import LineRerunResult

        # Create 2D benchmark data
        benchmark = CategoricalBenchmark().to_bench(bch.BenchRunCfg(level=1))
        results = benchmark.plot_sweep(
            input_vars=[CategoricalBenchmark.param.operation, CategoricalBenchmark.param.theta],
            result_vars=[CategoricalBenchmark.param.result],
        )

        # Test that line result doesn't match 2D dataset
        dataset = results.ds[CategoricalBenchmark.param.result.name]
        assert not LineRerunResult.matches_dataset(dataset)


class TestRerunHeatmapResult:
    """Test suite for HeatmapRerunResult"""

    def test_heatmap_result_creation(self):
        """Test that heatmap result can be created and matches 2D data"""
        from bencher.results.rerun_results.heatmap_result import HeatmapRerunResult

        # Create 2D benchmark data
        benchmark = CategoricalBenchmark().to_bench(bch.BenchRunCfg(level=1))
        results = benchmark.plot_sweep(
            input_vars=[CategoricalBenchmark.param.operation, CategoricalBenchmark.param.theta],
            result_vars=[CategoricalBenchmark.param.result],
        )

        # Test that heatmap result matches this dataset
        dataset = results.ds[CategoricalBenchmark.param.result.name]
        assert HeatmapRerunResult.matches_dataset(dataset)

        # Create heatmap result instance
        heatmap_result = HeatmapRerunResult(results.bench_cfg)
        heatmap_result.ds = results.ds

        # Test visualization creation
        panel = heatmap_result.to_plot(CategoricalBenchmark.param.result)
        assert panel is not None

    def test_heatmap_result_mixed_categorical_numeric(self):
        """Test heatmap result with mixed categorical and numeric inputs"""
        from bencher.results.rerun_results.heatmap_result import HeatmapRerunResult

        # Create mixed 2D benchmark data
        benchmark = CategoricalBenchmark().to_bench(bch.BenchRunCfg(level=1))
        results = benchmark.plot_sweep()  # Uses both categorical and numeric inputs

        # Create heatmap result instance
        heatmap_result = HeatmapRerunResult(results.bench_cfg)
        heatmap_result.ds = results.ds

        # Test visualization creation
        panel = heatmap_result.to_plot(CategoricalBenchmark.param.result)
        assert panel is not None

    def test_heatmap_result_no_match_1d(self):
        """Test that heatmap result doesn't match 1D data"""
        from bencher.results.rerun_results.heatmap_result import HeatmapRerunResult

        # Create 1D benchmark data
        benchmark = SimpleFloatBenchmark().to_bench(bch.BenchRunCfg(level=1))
        results = benchmark.plot_sweep()

        # Test that heatmap result doesn't match 1D dataset
        dataset = results.ds[SimpleFloatBenchmark.param.result.name]
        assert not HeatmapRerunResult.matches_dataset(dataset)


class TestRerunTabsResult:
    """Test suite for TabsRerunResult"""

    def test_tabs_result_creation(self):
        """Test that tabs result can be created and matches 3D data"""
        from bencher.results.rerun_results.tabs_result import TabsRerunResult

        # Create 3D benchmark data
        benchmark = ThreeDimensionalBenchmark().to_bench(bch.BenchRunCfg(level=1))
        results = benchmark.plot_sweep()

        # Test that tabs result matches this dataset
        dataset = results.ds[ThreeDimensionalBenchmark.param.result.name]
        assert TabsRerunResult.matches_dataset(dataset)

        # Create tabs result instance
        tabs_result = TabsRerunResult(results.bench_cfg)
        tabs_result.ds = results.ds

        # Test visualization creation
        panel = tabs_result.to_plot(ThreeDimensionalBenchmark.param.result)
        assert panel is not None

    def test_tabs_result_fallback_2d(self):
        """Test tabs result fallback for 2D data"""
        from bencher.results.rerun_results.tabs_result import TabsRerunResult

        # Create 2D benchmark data
        benchmark = CategoricalBenchmark().to_bench(bch.BenchRunCfg(level=1))
        results = benchmark.plot_sweep()

        # Create tabs result instance with override
        tabs_result = TabsRerunResult(results.bench_cfg)
        tabs_result.ds = results.ds

        # Test visualization creation with override (should use fallback)
        panel = tabs_result.to_plot(CategoricalBenchmark.param.result, override=True)
        assert panel is not None

    def test_tabs_result_no_match_1d(self):
        """Test that tabs result doesn't match 1D data"""
        from bencher.results.rerun_results.tabs_result import TabsRerunResult

        # Create 1D benchmark data
        benchmark = SimpleFloatBenchmark().to_bench(bch.BenchRunCfg(level=1))
        results = benchmark.plot_sweep()

        # Test that tabs result doesn't match 1D dataset
        dataset = results.ds[SimpleFloatBenchmark.param.result.name]
        assert not TabsRerunResult.matches_dataset(dataset)


class TestRerunComposableResult:
    """Test suite for RerunComposableResult (main integration)"""

    def test_composable_result_1d_selection(self):
        """Test that composable result selects line plot for 1D data"""
        # Create 1D benchmark data
        benchmark = SimpleFloatBenchmark().to_bench(bch.BenchRunCfg(level=1))
        results = benchmark.plot_sweep()

        # Test to_rerun method
        panel = results.to_rerun()
        assert panel is not None
        assert "Rerun Visualization Created" in panel.object

    def test_composable_result_2d_selection(self):
        """Test that composable result selects heatmap for 2D data"""
        # Create 2D benchmark data
        benchmark = CategoricalBenchmark().to_bench(bch.BenchRunCfg(level=1))
        results = benchmark.plot_sweep()

        # Test to_rerun method
        panel = results.to_rerun()
        assert panel is not None
        assert "Rerun Visualization Created" in panel.object

    def test_composable_result_3d_selection(self):
        """Test that composable result selects tabs for 3D data"""
        # Create 3D benchmark data
        benchmark = ThreeDimensionalBenchmark().to_bench(bch.BenchRunCfg(level=1))
        results = benchmark.plot_sweep()

        # Test to_rerun method
        panel = results.to_rerun()
        assert panel is not None
        assert "Rerun Visualization Created" in panel.object

    def test_composable_result_multiple_result_vars(self):
        """Test composable result with multiple result variables"""

        # Create benchmark with multiple results
        class MultipleBenchmark(bch.ParametrizedSweep):
            theta = bch.FloatSweep(default=0, bounds=[0, math.pi / 4], samples=3)
            result1 = bch.ResultVar(units="v", doc="Sin result")
            result2 = bch.ResultVar(units="v", doc="Cos result")

            def __call__(self, **kwargs):
                self.update_params_from_kwargs(**kwargs)
                self.result1 = math.sin(self.theta)
                self.result2 = math.cos(self.theta)
                return super().__call__(**kwargs)

        benchmark = MultipleBenchmark().to_bench(bch.BenchRunCfg(level=1))
        results = benchmark.plot_sweep()

        # Test to_rerun method with multiple variables
        panel = results.to_rerun()
        assert panel is not None
        assert "Rerun Visualization Created" in panel.object
        assert "result1, result2" in panel.object or "result2, result1" in panel.object

    def test_composable_result_no_rerun_available(self):
        """Test graceful handling when rerun is not available"""
        from bencher.results.rerun_results.rerun_composable_result import RerunComposableResult

        # Temporarily mock rerun as unavailable
        original_available = getattr(RerunComposableResult, "RERUN_AVAILABLE", True)

        try:
            # Create instance with mocked unavailable rerun
            benchmark = SimpleFloatBenchmark().to_bench(bch.BenchRunCfg(level=1))
            results = benchmark.plot_sweep()

            # Temporarily patch RERUN_AVAILABLE
            import bencher.results.rerun_results.rerun_composable_result as rcr_module

            original_flag = getattr(rcr_module, "RERUN_AVAILABLE", True)
            rcr_module.RERUN_AVAILABLE = False

            try:
                panel = results.to_rerun()
                assert panel is not None
                assert "unavailable" in panel.object.lower()
            finally:
                rcr_module.RERUN_AVAILABLE = original_flag

        finally:
            pass  # Restore original state

    def test_composable_result_error_handling(self):
        """Test error handling in rerun visualization creation"""
        # Create valid benchmark data
        benchmark = SimpleFloatBenchmark().to_bench(bch.BenchRunCfg(level=1))
        results = benchmark.plot_sweep()

        # Test with invalid result variable
        panel = results.to_rerun(result_var="nonexistent_var")
        assert panel is not None
        # Should still create visualization or handle gracefully


class TestRerunCategoricalHandling:
    """Test suite for categorical data handling across all rerun results"""

    def test_categorical_conversion(self):
        """Test categorical to numeric conversion"""
        from bencher.results.rerun_results.rerun_result import RerunResultBase
        import numpy as np

        # Create base result instance
        benchmark = CategoricalBenchmark().to_bench(bch.BenchRunCfg(level=1))
        base_result = RerunResultBase(benchmark.bench_cfg)

        # Test categorical conversion
        categorical_data = np.array(["sin", "cos", "sin", "tan"])
        numeric_data, labels = base_result._convert_coords_to_numeric(categorical_data, None)

        assert labels is not None
        assert len(labels) == 3  # unique values: sin, cos, tan
        assert len(numeric_data) == 4
        assert all(isinstance(x, (int, np.integer)) for x in numeric_data)

    def test_numeric_passthrough(self):
        """Test that numeric data passes through unchanged"""
        from bencher.results.rerun_results.rerun_result import RerunResultBase
        import numpy as np

        # Create base result instance
        benchmark = SimpleFloatBenchmark().to_bench(bch.BenchRunCfg(level=1))
        base_result = RerunResultBase(benchmark.bench_cfg)

        # Test numeric passthrough
        numeric_data = np.array([1.0, 2.0, 3.0])
        result_data, labels = base_result._convert_coords_to_numeric(numeric_data, None)

        assert labels is None
        assert np.array_equal(result_data, numeric_data)


class TestRerunIntegration:
    """Integration tests for rerun with existing bencher examples"""

    def test_simple_float_example_integration(self):
        """Test that simple float example works with rerun"""
        # Test the actual simple float example
        benchmark = SimpleFloatBenchmark().to_bench(bch.BenchRunCfg(level=1))
        results = benchmark.plot_sweep()

        # Verify it has rerun capability
        assert hasattr(results, "to_rerun")

        # Test rerun visualization
        panel = results.to_rerun()
        assert panel is not None

    def test_backwards_compatibility(self):
        """Test that existing code still works with rerun integration"""
        # Create benchmark the old way
        benchmark = SimpleFloatBenchmark().to_bench(bch.BenchRunCfg(level=1))
        results = benchmark.plot_sweep()

        # Verify other visualization methods still work
        assert hasattr(results, "to_curve")
        assert hasattr(results, "to_line")
        assert hasattr(results, "to_heatmap")

        # Verify rerun is additional, not replacement
        curve_panel = results.to_curve()
        rerun_panel = results.to_rerun()

        assert curve_panel is not None
        assert rerun_panel is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
