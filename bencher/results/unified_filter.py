"""Unified data filtering and plotting interface for Bencher results.

This module provides a consistent API for selecting dimensionality, filtering data,
and applying custom plotting methods that conform to a standard interface.
"""

from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum, auto
import xarray as xr
from abc import ABC, abstractmethod

from bencher.variables.results import ResultVar
from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import PlotFilter


class FilterOperation(Enum):
    """Types of filtering operations that can be applied to data."""

    SELECT = auto()  # Select specific coordinates
    SLICE = auto()  # Slice a range of coordinates
    ISEL = auto()  # Select by integer position
    WHERE = auto()  # Filter by condition


@dataclass
class DimensionFilter:
    """Configuration for filtering a single dimension."""

    dim_name: str
    operation: FilterOperation
    value: Any = None
    start: Any = None
    end: Any = None
    condition: Optional[Callable] = None

    def apply(self, dataset: xr.Dataset) -> xr.Dataset:
        """Apply this filter to a dataset."""
        # Check if dimension exists in dataset
        if self.dim_name not in dataset.dims:
            return dataset  # Skip filtering if dimension doesn't exist

        match self.operation:
            case FilterOperation.SELECT:
                if isinstance(self.value, (list, tuple)):
                    return dataset.sel({self.dim_name: list(self.value)})
                return dataset.sel({self.dim_name: self.value})
            case FilterOperation.SLICE:
                return dataset.sel({self.dim_name: slice(self.start, self.end)})
            case FilterOperation.ISEL:
                if isinstance(self.value, (list, tuple)):
                    return dataset.isel({self.dim_name: list(self.value)})
                return dataset.isel({self.dim_name: self.value})
            case FilterOperation.WHERE:
                if self.condition is not None and self.dim_name in dataset.coords:
                    return dataset.where(self.condition(dataset[self.dim_name]), drop=True)
                return dataset
        return dataset


@dataclass
class DataFilter:
    """Configuration for filtering the entire dataset."""

    dimension_filters: List[DimensionFilter] = field(default_factory=list)
    result_vars: Optional[List[Union[str, ResultVar]]] = None
    reduce_type: ReduceType = ReduceType.AUTO
    level: Optional[int] = None

    def add_dimension_filter(self, dim_filter: DimensionFilter) -> DataFilter:
        """Add a dimension filter to this data filter."""
        self.dimension_filters.append(dim_filter)
        return self

    def select_dimension(self, dim_name: str, value: Any) -> DataFilter:
        """Add a dimension selection filter."""
        self.dimension_filters.append(
            DimensionFilter(dim_name, FilterOperation.SELECT, value=value)
        )
        return self

    def slice_dimension(self, dim_name: str, start: Any = None, end: Any = None) -> DataFilter:
        """Add a dimension slice filter."""
        self.dimension_filters.append(
            DimensionFilter(dim_name, FilterOperation.SLICE, start=start, end=end)
        )
        return self

    def isel_dimension(self, dim_name: str, indices: Union[int, List[int]]) -> DataFilter:
        """Add a dimension integer selection filter."""
        self.dimension_filters.append(
            DimensionFilter(dim_name, FilterOperation.ISEL, value=indices)
        )
        return self

    def where_dimension(self, dim_name: str, condition: Callable) -> DataFilter:
        """Add a conditional dimension filter."""
        self.dimension_filters.append(
            DimensionFilter(dim_name, FilterOperation.WHERE, condition=condition)
        )
        return self


class PlotInterface(ABC):
    """Abstract interface that all custom plotting methods must implement."""

    @abstractmethod
    def can_plot(self, dataset: xr.Dataset, result_var: ResultVar = None, **kwargs) -> bool:
        """Check if this plotter can handle the given dataset and parameters.

        Args:
            dataset: The xarray dataset to plot
            result_var: The specific result variable to plot
            **kwargs: Additional plotting parameters

        Returns:
            True if this plotter can handle the data, False otherwise
        """
        pass

    @abstractmethod
    def create_plot(self, dataset: xr.Dataset, result_var: ResultVar = None, **kwargs) -> Any:
        """Create a plot from the given dataset.

        Args:
            dataset: The xarray dataset to plot
            result_var: The specific result variable to plot
            **kwargs: Additional plotting parameters

        Returns:
            The created plot object (Panel, HoloViews, etc.)
        """
        pass

    @abstractmethod
    def get_plot_filter(self) -> PlotFilter:
        """Get the PlotFilter that defines what data this plotter can handle.

        Returns:
            PlotFilter defining the acceptable data dimensions and types
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Name identifier for this plotter."""
        pass


@dataclass
class PlotterRegistry:
    """Registry for managing custom plotting interfaces."""

    plotters: Dict[str, PlotInterface] = field(default_factory=dict)

    def register(self, plotter: PlotInterface) -> None:
        """Register a new plotter."""
        self.plotters[plotter.name] = plotter

    def unregister(self, name: str) -> None:
        """Unregister a plotter by name."""
        if name in self.plotters:
            del self.plotters[name]

    def get_compatible_plotters(
        self, dataset: xr.Dataset, result_var: ResultVar = None, **kwargs
    ) -> List[PlotInterface]:
        """Get all plotters that can handle the given dataset."""
        compatible = []
        for plotter in self.plotters.values():
            if plotter.can_plot(dataset, result_var, **kwargs):
                compatible.append(plotter)
        return compatible

    def list_plotters(self) -> List[str]:
        """Get names of all registered plotters."""
        return list(self.plotters.keys())


class UnifiedPlottingInterface:
    """Unified interface for data filtering and plotting."""

    def __init__(self, bench_result):
        """Initialize with a benchmark result object."""
        self.bench_result = bench_result
        self.plotter_registry = PlotterRegistry()

    def filter_data(self, data_filter: DataFilter) -> xr.Dataset:
        """Apply data filters to get a filtered dataset.

        Args:
            data_filter: Configuration specifying how to filter the data

        Returns:
            Filtered xarray Dataset
        """
        # Start with the base dataset
        dataset = self.bench_result.to_dataset(
            reduce=data_filter.reduce_type,
            result_var=None if not data_filter.result_vars else data_filter.result_vars[0],
            level=data_filter.level,
        )

        # Apply dimension filters
        for dim_filter in data_filter.dimension_filters:
            dataset = dim_filter.apply(dataset)

        # Filter result variables if specified
        if data_filter.result_vars:
            var_names = []
            for var in data_filter.result_vars:
                if isinstance(var, str):
                    var_names.append(var)
                else:
                    var_names.append(var.name)

            # Only keep specified result variables
            dataset = dataset[var_names]

        return dataset

    def create_plot(
        self,
        plotter_name: str,
        data_filter: DataFilter = None,
        result_var: ResultVar = None,
        **kwargs,
    ) -> Any:
        """Create a plot using a specific plotter and data filter.

        Args:
            plotter_name: Name of the registered plotter to use
            data_filter: Optional data filter to apply before plotting
            result_var: Specific result variable to plot
            **kwargs: Additional plotting parameters

        Returns:
            The created plot object
        """
        if plotter_name not in self.plotter_registry.plotters:
            raise ValueError(f"Plotter '{plotter_name}' not registered")

        plotter = self.plotter_registry.plotters[plotter_name]

        if data_filter is not None:
            dataset = self.filter_data(data_filter)
        else:
            dataset = self.bench_result.to_dataset()

        if not plotter.can_plot(dataset, result_var, **kwargs):
            raise ValueError(f"Plotter '{plotter_name}' cannot handle this data")

        return plotter.create_plot(dataset, result_var, **kwargs)

    def auto_plot(
        self,
        data_filter: DataFilter = None,
        result_var: ResultVar = None,
        prefer_plotters: List[str] = None,
        **kwargs,
    ) -> List[Tuple[str, Any]]:
        """Automatically select and create plots that can handle the filtered data.

        Args:
            data_filter: Optional data filter to apply before plotting
            result_var: Specific result variable to plot
            prefer_plotters: List of plotter names to prefer (in order)
            **kwargs: Additional plotting parameters

        Returns:
            List of tuples containing (plotter_name, plot_object) for successful plots
        """
        if data_filter is not None:
            dataset = self.filter_data(data_filter)
        else:
            dataset = self.bench_result.to_dataset()

        compatible_plotters = self.plotter_registry.get_compatible_plotters(
            dataset, result_var, **kwargs
        )

        # Sort by preference if specified
        if prefer_plotters:

            def sort_key(plotter):
                try:
                    return prefer_plotters.index(plotter.name)
                except ValueError:
                    return len(prefer_plotters)  # Put non-preferred at end

            compatible_plotters.sort(key=sort_key)

        plots = []
        for plotter in compatible_plotters:
            try:
                plot = plotter.create_plot(dataset, result_var, **kwargs)
                plots.append((plotter.name, plot))
            except Exception as e:
                # Log error but continue with other plotters
                print(f"Error creating plot with {plotter.name}: {e}")

        return plots

    def register_plotter(self, plotter: PlotInterface) -> None:
        """Register a new plotter."""
        self.plotter_registry.register(plotter)

    def list_compatible_plotters(
        self, data_filter: DataFilter = None, result_var: ResultVar = None, **kwargs
    ) -> List[str]:
        """List all plotters compatible with the (optionally filtered) data.

        Args:
            data_filter: Optional data filter to apply before checking compatibility
            result_var: Specific result variable to check
            **kwargs: Additional plotting parameters

        Returns:
            List of plotter names that can handle the data
        """
        if data_filter is not None:
            dataset = self.filter_data(data_filter)
        else:
            dataset = self.bench_result.to_dataset()

        compatible = self.plotter_registry.get_compatible_plotters(dataset, result_var, **kwargs)
        return [p.name for p in compatible]
