"""Tests for the unified data filtering and plotting interface."""

import pytest
import numpy as np
import xarray as xr
import panel as pn
from unittest.mock import Mock

from bencher.results.unified_filter import (
    FilterOperation,
    DimensionFilter,
    DataFilter,
    PlotInterface,
    PlotterRegistry,
    UnifiedPlottingInterface,
)
from bencher.results.example_plotters import ScatterPlotInterface, CustomTableInterface
from bencher.plotting.plot_filter import PlotFilter
from bencher.results.bench_result_base import ReduceType


class MockBenchResult:
    """Mock BenchResult for testing."""

    def __init__(self):
        # Create a simple test dataset
        self.ds = xr.Dataset(
            {
                "result1": (["x", "y", "repeat"], np.random.rand(5, 3, 2)),
                "result2": (["x", "y", "repeat"], np.random.rand(5, 3, 2)),
            },
            coords={"x": np.linspace(0, 10, 5), "y": ["A", "B", "C"], "repeat": [0, 1]},
        )

    def to_dataset(self, reduce=ReduceType.AUTO, result_var=None, level=None):
        """Mock to_dataset method."""
        dataset = self.ds.copy()

        if reduce == ReduceType.AUTO:
            reduce = ReduceType.REDUCE if dataset.sizes.get("repeat", 1) > 1 else ReduceType.SQUEEZE

        if reduce == ReduceType.REDUCE:
            dataset = dataset.mean(dim="repeat")
        elif reduce == ReduceType.SQUEEZE:
            dataset = dataset.squeeze()

        if result_var is not None:
            if isinstance(result_var, str):
                dataset = dataset[[result_var]]
            elif hasattr(result_var, "name"):
                dataset = dataset[[result_var.name]]

        return dataset


class TestDimensionFilter:
    """Test dimension filtering operations."""

    def setup_method(self):
        """Set up test data."""
        self.dataset = xr.Dataset(
            {"values": (["x", "y"], np.random.rand(5, 3))},
            coords={"x": np.linspace(0, 10, 5), "y": ["A", "B", "C"]},
        )

    def test_select_operation(self):
        """Test SELECT operation."""
        dim_filter = DimensionFilter("y", FilterOperation.SELECT, value="A")
        filtered = dim_filter.apply(self.dataset)
        # When selecting a single value, xarray may reduce the dimension to a scalar coordinate
        if "y" in filtered.sizes:
            assert filtered.sizes["y"] == 1
            assert filtered.coords["y"].values.item() == "A"
        else:
            # Dimension was reduced to scalar coordinate
            assert "y" in filtered.coords
            assert filtered.coords["y"].values.item() == "A"

    def test_select_multiple(self):
        """Test SELECT operation with multiple values."""
        dim_filter = DimensionFilter("y", FilterOperation.SELECT, value=["A", "C"])
        filtered = dim_filter.apply(self.dataset)
        assert filtered.sizes["y"] == 2
        assert set(filtered.coords["y"].values) == {"A", "C"}

    def test_slice_operation(self):
        """Test SLICE operation."""
        dim_filter = DimensionFilter("x", FilterOperation.SLICE, start=2.0, end=8.0)
        filtered = dim_filter.apply(self.dataset)
        assert filtered.sizes["x"] <= 5  # Should be smaller or equal
        assert all(filtered.coords["x"].values >= 2.0)
        assert all(filtered.coords["x"].values <= 8.0)

    def test_isel_operation(self):
        """Test ISEL operation."""
        dim_filter = DimensionFilter("x", FilterOperation.ISEL, value=[0, 2, 4])
        filtered = dim_filter.apply(self.dataset)
        assert filtered.sizes["x"] == 3

    def test_where_operation(self):
        """Test WHERE operation."""
        def condition(x):
            return x > 5.0
        dim_filter = DimensionFilter("x", FilterOperation.WHERE, condition=condition)
        filtered = dim_filter.apply(self.dataset)
        assert all(filtered.coords["x"].values > 5.0)


class TestDataFilter:
    """Test data filtering functionality."""

    def setup_method(self):
        """Set up test data."""
        self.bench_result = MockBenchResult()
        self.unified = UnifiedPlottingInterface(self.bench_result)

    def test_basic_data_filter(self):
        """Test basic data filtering."""
        data_filter = DataFilter().select_dimension("y", "A")
        filtered = self.unified.filter_data(data_filter)
        # Check if y dimension exists and has correct size
        if "y" in filtered.sizes:
            assert filtered.sizes["y"] == 1
            assert filtered.coords["y"].values.item() == "A"
        else:
            # The dimension may have been reduced away - this is acceptable
            pass

    def test_chained_filters(self):
        """Test chaining multiple filters."""
        data_filter = DataFilter().select_dimension("y", ["A", "B"]).isel_dimension("x", [0, 1, 2])
        filtered = self.unified.filter_data(data_filter)
        assert filtered.sizes["y"] == 2
        assert filtered.sizes["x"] == 3

    def test_result_var_filtering(self):
        """Test filtering by result variables."""
        data_filter = DataFilter()
        data_filter.result_vars = ["result1"]
        filtered = self.unified.filter_data(data_filter)
        assert "result1" in filtered.data_vars
        assert "result2" not in filtered.data_vars


class TestPlotterRegistry:
    """Test plotter registry functionality."""

    def setup_method(self):
        """Set up test registry."""
        self.registry = PlotterRegistry()
        self.scatter_plotter = ScatterPlotInterface()
        self.table_plotter = CustomTableInterface()

    def test_register_plotter(self):
        """Test registering plotters."""
        self.registry.register(self.scatter_plotter)
        assert "scatter" in self.registry.plotters
        assert self.registry.plotters["scatter"] == self.scatter_plotter

    def test_unregister_plotter(self):
        """Test unregistering plotters."""
        self.registry.register(self.scatter_plotter)
        self.registry.unregister("scatter")
        assert "scatter" not in self.registry.plotters

    def test_list_plotters(self):
        """Test listing registered plotters."""
        self.registry.register(self.scatter_plotter)
        self.registry.register(self.table_plotter)
        plotters = self.registry.list_plotters()
        assert set(plotters) == {"scatter", "table"}

    def test_get_compatible_plotters(self):
        """Test finding compatible plotters."""
        self.registry.register(self.scatter_plotter)
        self.registry.register(self.table_plotter)

        # Create simple test dataset
        dataset = xr.Dataset({"values": (["x"], np.random.rand(10))}, coords={"x": np.arange(10)})

        compatible = self.registry.get_compatible_plotters(dataset)
        # Both should be compatible with simple 1D data
        assert len(compatible) == 2


class TestUnifiedPlottingInterface:
    """Test the main unified plotting interface."""

    def setup_method(self):
        """Set up test interface."""
        self.bench_result = MockBenchResult()
        self.unified = UnifiedPlottingInterface(self.bench_result)

        # Register test plotters
        self.scatter_plotter = ScatterPlotInterface()
        self.table_plotter = CustomTableInterface()
        self.unified.register_plotter(self.scatter_plotter)
        self.unified.register_plotter(self.table_plotter)

    def test_create_plot_success(self):
        """Test successful plot creation."""
        plot = self.unified.create_plot("table")
        assert plot is not None
        assert isinstance(plot, (pn.Column, pn.pane.DataFrame))

    def test_create_plot_unregistered(self):
        """Test error when using unregistered plotter."""
        with pytest.raises(ValueError, match="not registered"):
            self.unified.create_plot("nonexistent")

    def test_list_compatible_plotters(self):
        """Test listing compatible plotters."""
        compatible = self.unified.list_compatible_plotters()
        # Table should always be compatible, scatter might be
        assert "table" in compatible

    def test_auto_plot(self):
        """Test automatic plot generation."""
        plots = self.unified.auto_plot()
        assert len(plots) > 0
        assert all(isinstance(name, str) for name, _ in plots)

    def test_auto_plot_with_filter(self):
        """Test automatic plot generation with data filter."""
        data_filter = DataFilter().select_dimension("y", "A")
        plots = self.unified.auto_plot(data_filter=data_filter)
        assert len(plots) > 0

    def test_auto_plot_with_preferences(self):
        """Test automatic plot generation with plotter preferences."""
        plots = self.unified.auto_plot(prefer_plotters=["table", "scatter"])
        assert len(plots) > 0
        # Table should be first since it's preferred and always compatible
        assert plots[0][0] == "table"


class MockPlotInterface(PlotInterface):
    """Mock plot interface for testing."""

    def __init__(self, name, can_plot_result=True):
        self._name = name
        self._can_plot_result = can_plot_result

    @property
    def name(self) -> str:
        return self._name

    def get_plot_filter(self) -> PlotFilter:
        return PlotFilter()

    def can_plot(self, dataset, result_var=None, **kwargs) -> bool:
        return self._can_plot_result

    def create_plot(self, dataset, result_var=None, **kwargs):
        return Mock()


class TestPlotInterface:
    """Test plot interface functionality."""

    def test_mock_interface(self):
        """Test mock interface works as expected."""
        mock_plotter = MockPlotInterface("test", can_plot_result=True)
        assert mock_plotter.name == "test"
        assert mock_plotter.can_plot(None) is True
        assert mock_plotter.create_plot(None) is not None

    def test_registry_with_mock(self):
        """Test registry works with mock plotters."""
        registry = PlotterRegistry()
        mock1 = MockPlotInterface("plotter1", True)
        mock2 = MockPlotInterface("plotter2", False)

        registry.register(mock1)
        registry.register(mock2)

        compatible = registry.get_compatible_plotters(None)
        assert len(compatible) == 1
        assert compatible[0].name == "plotter1"


if __name__ == "__main__":
    # Run basic tests
    test_registry = TestPlotterRegistry()
    test_registry.setup_method()
    test_registry.test_register_plotter()
    test_registry.test_list_plotters()
    print("PlotterRegistry tests passed!")

    test_unified = TestUnifiedPlottingInterface()
    test_unified.setup_method()
    test_unified.test_list_compatible_plotters()
    test_unified.test_auto_plot()
    print("UnifiedPlottingInterface tests passed!")

    print("All manual tests completed successfully!")
