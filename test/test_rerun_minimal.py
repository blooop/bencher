#!/usr/bin/env python3
"""Minimal test suite for rerun visualization backends"""

import pytest
import numpy as np

# Skip all tests if rerun is not available
try:
    import rerun as rr  # noqa: F401

    RERUN_AVAILABLE = True
except ImportError:
    RERUN_AVAILABLE = False

pytestmark = pytest.mark.skipif(not RERUN_AVAILABLE, reason="rerun-sdk not available")


def test_rerun_imports():
    """Test that all rerun modules can be imported"""
    from bencher.results.rerun_results import (
        RerunResultBase,
        LineRerunResult,
        HeatmapRerunResult,
        TabsRerunResult,
        RerunComposableResult,
    )

    # Test that classes exist
    assert RerunResultBase is not None
    assert LineRerunResult is not None
    assert HeatmapRerunResult is not None
    assert TabsRerunResult is not None
    assert RerunComposableResult is not None


def test_categorical_conversion_standalone():
    """Test categorical conversion function independently"""

    # Test just the static method without creating instance
    categorical_data = np.array(["sin", "cos", "sin", "tan"])

    # Create minimal mock for the method
    class MockVar:
        name = "test"

    # Test the conversion logic directly
    if hasattr(categorical_data, "dtype") and categorical_data.dtype.kind in ["U", "S", "O"]:
        # This is the core logic from _convert_coords_to_numeric
        unique_values = list(set(categorical_data))
        value_to_index = {val: i for i, val in enumerate(unique_values)}
        numeric_coords = np.array([value_to_index[val] for val in categorical_data])

        assert len(unique_values) == 3  # sin, cos, tan
        assert len(numeric_coords) == 4
        assert all(isinstance(x, (int, np.integer)) for x in numeric_coords)


def test_dataset_matching_logic():
    """Test the dataset matching logic for different plot types"""
    from bencher.results.rerun_results.line_result import LineRerunResult
    from bencher.results.rerun_results.heatmap_result import HeatmapRerunResult
    from bencher.results.rerun_results.tabs_result import TabsRerunResult

    # Test the matching logic directly

    # Mock 1D dataset (should match line)
    class Mock1DDataset:
        dims = ["theta", "repeat"]
        sizes = {"theta": 5, "repeat": 1}

    # Mock 2D dataset (should match heatmap)
    class Mock2DDataset:
        dims = ["operation", "theta", "repeat"]
        sizes = {"operation": 3, "theta": 5, "repeat": 1}

    # Mock 3D dataset (should match tabs)
    class Mock3DDataset:
        dims = ["operation", "theta", "amplitude", "repeat"]
        sizes = {"operation": 3, "theta": 5, "amplitude": 2, "repeat": 1}

    # Test line result matching (1D non-repeat dimensions)
    def test_line_matches(dataset):
        if hasattr(dataset, "dims"):
            significant_dims = [
                dim for dim in dataset.dims if dim != "repeat" and dataset.sizes[dim] > 1
            ]
            return len(significant_dims) == 1
        return False

    # Test heatmap matching (2D non-repeat dimensions)
    def test_heatmap_matches(dataset):
        if hasattr(dataset, "dims"):
            significant_dims = [
                dim for dim in dataset.dims if dim != "repeat" and dataset.sizes[dim] > 1
            ]
            return len(significant_dims) == 2
        return False

    # Test tabs matching (3+ non-repeat dimensions)
    def test_tabs_matches(dataset):
        if hasattr(dataset, "dims"):
            significant_dims = [
                dim for dim in dataset.dims if dim != "repeat" and dataset.sizes[dim] > 1
            ]
            return len(significant_dims) >= 3
        return False

    dataset_1d = Mock1DDataset()
    dataset_2d = Mock2DDataset()
    dataset_3d = Mock3DDataset()

    # Test matching logic
    assert test_line_matches(dataset_1d)
    assert not test_line_matches(dataset_2d)
    assert not test_line_matches(dataset_3d)

    assert not test_heatmap_matches(dataset_1d)
    assert test_heatmap_matches(dataset_2d)
    assert not test_heatmap_matches(dataset_3d)

    assert not test_tabs_matches(dataset_1d)
    assert not test_tabs_matches(dataset_2d)
    assert test_tabs_matches(dataset_3d)

    # Test actual class methods
    assert LineRerunResult.matches_dataset(dataset_1d)
    assert HeatmapRerunResult.matches_dataset(dataset_2d)
    assert TabsRerunResult.matches_dataset(dataset_3d)


def test_bench_result_includes_rerun():
    """Test that BenchResult includes rerun functionality"""
    from bencher.results.bench_result import BenchResult
    from bencher.results.rerun_results import RerunComposableResult

    # Test inheritance
    assert issubclass(BenchResult, RerunComposableResult)

    # Test method availability (without creating instance)
    assert hasattr(BenchResult, "to_rerun")


def test_rerun_panel_creation():
    """Test that rerun methods return proper panel types"""
    from bencher.results.rerun_results.rerun_result import RerunResultBase
    import panel as pn

    # Test that unavailable rerun is handled gracefully
    # Temporarily disable rerun for testing
    import bencher.results.rerun_results.rerun_result as rr_module

    original_available = getattr(rr_module, "RERUN_AVAILABLE", True)

    try:
        # Test with rerun disabled
        rr_module.RERUN_AVAILABLE = False

        # Mock minimal bench_cfg
        class MinimalBenchCfg:
            bench_name = "test"
            result_hmaps = {}
            input_vars = []
            result_vars = []

        base_result = RerunResultBase(MinimalBenchCfg())
        panel = base_result.to_plot()

        assert isinstance(panel, pn.pane.Markdown)
        assert "unavailable" in panel.object.lower()

    finally:
        # Restore original state
        rr_module.RERUN_AVAILABLE = original_available


def test_entity_path_creation():
    """Test entity path creation"""
    from bencher.results.rerun_results.rerun_result import RerunResultBase

    # Mock minimal bench_cfg
    class MinimalBenchCfg:
        bench_name = "test"
        result_hmaps = {}

    # Mock result var
    class MockResultVar:
        name = "test_result"

    base_result = RerunResultBase(MinimalBenchCfg())

    # Test entity path creation
    path = base_result._create_entity_path(MockResultVar(), "line")
    assert path == "bencher/line/test_result"

    # Test without result var
    path = base_result._create_entity_path(None, "heatmap")
    assert path == "bencher/heatmap"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
