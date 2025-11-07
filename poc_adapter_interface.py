"""
Proof of Concept: Visualization Adapter Interface

This demonstrates the proposed adapter pattern for decoupling
visualization from core bencher functionality.

This is NOT production code, just a sketch to show the concept.
"""

from __future__ import annotations
from typing import Protocol, List, Any, Optional, Dict, Type, Literal
from dataclasses import dataclass
from abc import abstractmethod
from datetime import datetime

# Mock xarray and pandas for demonstration purposes
# In actual implementation, would import: import xarray as xr, import pandas as pd


class MockDataset:
    """Mock xarray.Dataset for demonstration"""

    def __init__(self):
        self.dims = {"x": 10, "y": 10, "repeat": 3}
        self.data_vars = ["time", "accuracy"]

    def mean(self, dim, skipna=True):
        return self

    def squeeze(self):
        return self

    def to_dataframe(self):
        return MockDataFrame()

    def to_dict(self):
        return {"mock": "data"}

    def sel(self, **kwargs):
        return self


class MockDataFrame:
    """Mock pandas.DataFrame for demonstration"""

    def reset_index(self):
        return self


xr = type("xr", (), {"Dataset": MockDataset})()
pd = type("pd", (), {"DataFrame": MockDataFrame})()


# ============================================================================
# CORE COMPONENTS (bencher-core package)
# ============================================================================


@dataclass
class ResultMetadata:
    """Metadata about benchmark results - no visualization dependencies"""

    bench_name: str
    input_vars: List[str]
    result_vars: List[str]
    dimensions: Dict[str, int]
    units: Dict[str, str]
    timestamp: datetime
    repeats: int
    over_time: bool


class BenchResultData:
    """Pure data container with NO visualization dependencies

    This replaces BenchResultBase but contains ONLY data operations.
    No Panel, no HoloViews, no plotting methods.
    """

    def __init__(self, metadata: ResultMetadata) -> None:
        self.metadata = metadata
        self.ds = MockDataset()  # Core data structure (would be xr.Dataset)
        self.object_references = []  # For non-array data (images, videos, etc.)
        self.datasets = []  # For ResultDataSet types

    # ===== Data Access Methods (no visualization) =====

    def to_xarray(self):
        """Return underlying xarray dataset"""
        return self.ds

    def to_pandas(self, flatten: bool = False):
        """Convert to pandas DataFrame"""
        if flatten:
            return self.ds.to_dataframe().reset_index()
        return self.ds.to_dataframe()

    def to_dict(self) -> Dict[str, Any]:
        """Export to dictionary format"""
        return {
            "metadata": self.metadata.__dict__,
            "data": self.ds.to_dict(),
        }

    # ===== Data Operations (no visualization) =====

    def reduce(self, reduce_type: str = "mean"):
        """Apply reduction operations (mean, std, squeeze, etc.)"""
        # Implementation would go here
        if reduce_type == "mean":
            return self.ds.mean(dim="repeat", skipna=True)
        elif reduce_type == "squeeze":
            return self.ds.squeeze()
        return self.ds

    def aggregate(self, dims: List[str], agg_fn: Literal["mean", "sum", "max", "min"] = "mean"):
        """Aggregate over specified dimensions"""
        return getattr(self.ds, agg_fn)(dim=dims)

    def filter_dims(self, **dim_filters) -> BenchResultData:
        """Filter dataset by dimension values"""
        filtered_ds = self.ds.sel(**dim_filters)
        new_result = BenchResultData(self.metadata)
        new_result.ds = filtered_ds
        return new_result


# ============================================================================
# VISUALIZATION PLUGIN INTERFACE (bencher-core package)
# ============================================================================


class VisualizationAdapter(Protocol):
    """Protocol (interface) that all visualization backends must implement

    This defines the contract that visualization plugins must follow.
    Plugins can be in separate repositories and implement this interface.
    """

    @staticmethod
    def name() -> str:
        """Backend identifier (e.g., 'holoviews', 'plotly', 'matplotlib')"""
        ...

    @staticmethod
    def supported_plot_types() -> List[str]:
        """Return list of supported plot types (e.g., ['scatter', 'line', 'bar'])"""
        ...

    def render(self, result_data: BenchResultData, plot_type: str, **kwargs) -> Any:
        """Render a specific plot type

        Args:
            result_data: The benchmark result data to visualize
            plot_type: Type of plot (e.g., 'scatter', 'line', 'heatmap')
            **kwargs: Additional rendering options

        Returns:
            Plot object (type depends on backend)
        """
        ...

    def auto_plot(
        self, result_data: BenchResultData, plot_types: Optional[List[str]] = None, **kwargs
    ) -> Any:
        """Automatically generate suitable plots based on data structure

        Args:
            result_data: The benchmark result data to visualize
            plot_types: Optional list of plot types to generate
            **kwargs: Additional rendering options

        Returns:
            Composed layout with multiple plots
        """
        ...

    def compose_layout(self, plots: List[Any], layout_type: str = "column") -> Any:
        """Compose multiple plots into a layout

        Args:
            plots: List of plot objects to compose
            layout_type: Type of layout ('column', 'row', 'grid')

        Returns:
            Composed layout object
        """
        ...


class VisualizationRegistry:
    """Global registry for visualization backends (plugin system)

    This allows visualization adapters to register themselves and be
    discovered by the core BenchResult class.
    """

    _adapters: Dict[str, Type[VisualizationAdapter]] = {}
    _default_adapter: Optional[str] = None

    @classmethod
    def register(cls, adapter_class: Type[VisualizationAdapter]) -> None:
        """Register a visualization adapter

        Args:
            adapter_class: Class implementing VisualizationAdapter protocol
        """
        name = adapter_class.name()
        cls._adapters[name] = adapter_class
        # First registered becomes default
        if cls._default_adapter is None:
            cls._default_adapter = name
        print(f"✓ Registered visualization backend: {name}")

    @classmethod
    def get_adapter(cls, name: Optional[str] = None) -> VisualizationAdapter:
        """Get adapter instance by name (or default)

        Args:
            name: Backend name or None for default

        Returns:
            Instantiated adapter

        Raises:
            ValueError: If adapter not found
        """
        adapter_name = name or cls._default_adapter
        if adapter_name is None:
            raise ValueError("No visualization backend registered")
        if adapter_name not in cls._adapters:
            raise ValueError(
                f"Adapter '{adapter_name}' not registered. "
                f"Available: {list(cls._adapters.keys())}"
            )
        return cls._adapters[adapter_name]()

    @classmethod
    def list_adapters(cls) -> List[str]:
        """List all registered adapters"""
        return list(cls._adapters.keys())

    @classmethod
    def set_default(cls, name: str) -> None:
        """Set default visualization backend

        Args:
            name: Backend name to set as default

        Raises:
            ValueError: If adapter not found
        """
        if name not in cls._adapters:
            raise ValueError(f"Adapter '{name}' not registered")
        cls._default_adapter = name
        print(f"✓ Set default visualization backend to: {name}")


# ============================================================================
# BENCHRESULT FACADE (bencher-core package)
# ============================================================================


class BenchResult:
    """Facade for benchmark results with optional visualization

    This replaces the old BenchResult with multiple inheritance.
    It delegates data operations to BenchResultData and visualization
    to registered adapters.
    """

    def __init__(self, metadata: ResultMetadata) -> None:
        self.data = BenchResultData(metadata)
        self._viz_backend: Optional[str] = None

    # ===== Data Access (delegates to BenchResultData) =====

    def to_xarray(self):
        """Return underlying xarray dataset"""
        return self.data.to_xarray()

    def to_pandas(self, flatten: bool = False):
        """Convert to pandas DataFrame"""
        return self.data.to_pandas(flatten)

    def to_dict(self) -> Dict[str, Any]:
        """Export to dictionary format"""
        return self.data.to_dict()

    # ===== Visualization Methods (uses registry) =====

    def use_backend(self, backend: str) -> BenchResult:
        """Switch visualization backend

        Args:
            backend: Backend name (e.g., 'holoviews', 'plotly')

        Returns:
            self (for chaining)
        """
        self._viz_backend = backend
        return self

    def plot(self, plot_type: str, backend: Optional[str] = None, **kwargs) -> Any:
        """Generate a specific plot type

        Args:
            plot_type: Type of plot (e.g., 'scatter', 'line', 'heatmap')
            backend: Optional backend override
            **kwargs: Additional rendering options

        Returns:
            Plot object (type depends on backend)
        """
        backend = backend or self._viz_backend
        adapter = VisualizationRegistry.get_adapter(backend)
        return adapter.render(self.data, plot_type, **kwargs)

    def auto_plot(
        self, plot_types: Optional[List[str]] = None, backend: Optional[str] = None, **kwargs
    ) -> Any:
        """Automatically generate suitable plots

        Args:
            plot_types: Optional list of plot types to generate
            backend: Optional backend override
            **kwargs: Additional rendering options

        Returns:
            Composed layout with plots
        """
        backend = backend or self._viz_backend
        adapter = VisualizationRegistry.get_adapter(backend)
        return adapter.auto_plot(self.data, plot_types, **kwargs)

    # ===== Backward Compatibility (legacy API) =====

    def to_scatter(self, **kwargs) -> Any:
        """Legacy API - delegates to plot('scatter')"""
        import warnings

        warnings.warn(
            "to_scatter() is deprecated, use plot('scatter') instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.plot("scatter", **kwargs)

    def to_line(self, **kwargs) -> Any:
        """Legacy API - delegates to plot('line')"""
        import warnings

        warnings.warn(
            "to_line() is deprecated, use plot('line') instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.plot("line", **kwargs)

    def to_auto(self, **kwargs) -> Any:
        """Legacy API - delegates to auto_plot()"""
        import warnings

        warnings.warn(
            "to_auto() is deprecated, use auto_plot() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.auto_plot(**kwargs)


# ============================================================================
# EXAMPLE PLUGIN IMPLEMENTATION (bencher-viz-holoviews package)
# ============================================================================


class HoloviewsAdapter:
    """Example adapter for HoloViews/Panel visualization

    This would live in a separate bencher-viz-holoviews package.
    """

    @staticmethod
    def name() -> str:
        return "holoviews"

    @staticmethod
    def supported_plot_types() -> List[str]:
        return [
            "scatter",
            "line",
            "bar",
            "curve",
            "heatmap",
            "surface",
            "box_whisker",
            "violin",
            "histogram",
            "table",
        ]

    def render(self, result_data: BenchResultData, plot_type: str, **kwargs) -> Any:
        """Render specific plot type using HoloViews"""
        # In real implementation, this would import holoviews, hvplot, panel
        # and create actual visualizations
        print(f"HoloviewsAdapter: Rendering {plot_type} plot")
        print(f"  Data shape: {result_data.ds.dims}")
        print(f"  Variables: {list(result_data.ds.data_vars)}")

        # Pseudo-code for actual implementation:
        # import holoviews as hv
        # hv_ds = hv.Dataset(result_data.to_xarray())
        # if plot_type == "scatter":
        #     return hv_ds.to(hv.Scatter)
        # elif plot_type == "line":
        #     return hv_ds.to(hv.Curve)
        # ...

        return f"<HoloViews {plot_type} plot>"

    def auto_plot(
        self, result_data: BenchResultData, plot_types: Optional[List[str]] = None, **kwargs
    ) -> Any:
        """Auto-generate suitable plots"""
        print(f"HoloviewsAdapter: Auto-generating plots")

        # In real implementation, would check data dimensions and types
        # to determine suitable plot types
        if plot_types is None:
            plot_types = ["scatter", "line", "bar"]

        plots = []
        for plot_type in plot_types:
            plot = self.render(result_data, plot_type, **kwargs)
            plots.append(plot)

        return self.compose_layout(plots, "column")

    def compose_layout(self, plots: List[Any], layout_type: str = "column") -> Any:
        """Compose plots into Panel layout"""
        # In real implementation:
        # import panel as pn
        # if layout_type == "column":
        #     return pn.Column(*plots)
        # elif layout_type == "row":
        #     return pn.Row(*plots)

        return f"<Panel {layout_type} with {len(plots)} plots>"


class PlotlyAdapter:
    """Example adapter for Plotly visualization

    This would live in a separate bencher-viz-plotly package.
    """

    @staticmethod
    def name() -> str:
        return "plotly"

    @staticmethod
    def supported_plot_types() -> List[str]:
        return ["scatter", "line", "bar", "surface", "volume", "heatmap"]

    def render(self, result_data: BenchResultData, plot_type: str, **kwargs) -> Any:
        """Render specific plot type using Plotly"""
        print(f"PlotlyAdapter: Rendering {plot_type} plot")
        print(f"  Data shape: {result_data.ds.dims}")

        # Pseudo-code for actual implementation:
        # import plotly.graph_objects as go
        # df = result_data.to_pandas()
        # if plot_type == "scatter":
        #     return go.Figure(data=[go.Scatter(x=df['x'], y=df['y'])])
        # elif plot_type == "surface":
        #     return go.Figure(data=[go.Surface(z=df.values)])
        # ...

        return f"<Plotly {plot_type} figure>"

    def auto_plot(
        self, result_data: BenchResultData, plot_types: Optional[List[str]] = None, **kwargs
    ) -> Any:
        """Auto-generate suitable plots"""
        print(f"PlotlyAdapter: Auto-generating plots")

        if plot_types is None:
            plot_types = ["scatter", "line"]

        plots = []
        for plot_type in plot_types:
            plot = self.render(result_data, plot_type, **kwargs)
            plots.append(plot)

        return plots  # Plotly returns list of figures

    def compose_layout(self, plots: List[Any], layout_type: str = "column") -> Any:
        """Compose plots into layout"""
        return f"<Plotly layout with {len(plots)} figures>"


# ============================================================================
# EXAMPLE USAGE
# ============================================================================


def demo_usage():
    """Demonstrate the proposed API"""

    print("=" * 70)
    print("PROOF OF CONCEPT: Visualization Adapter Pattern")
    print("=" * 70)
    print()

    # ===== Setup =====
    print("1. Register visualization adapters")
    print("-" * 70)
    VisualizationRegistry.register(HoloviewsAdapter)
    VisualizationRegistry.register(PlotlyAdapter)
    print()

    # ===== Create mock result =====
    print("2. Create benchmark result")
    print("-" * 70)
    metadata = ResultMetadata(
        bench_name="example",
        input_vars=["x", "y"],
        result_vars=["time", "accuracy"],
        dimensions={"x": 10, "y": 10, "repeat": 3},
        units={"time": "ms", "accuracy": "%"},
        timestamp=datetime.now(),
        repeats=3,
        over_time=False,
    )
    result = BenchResult(metadata)
    print(f"✓ Created BenchResult with metadata: {metadata.bench_name}")
    print()

    # ===== Use default backend =====
    print("3. Use default backend (holoviews)")
    print("-" * 70)
    plot = result.plot("scatter")
    print(f"Result: {plot}")
    print()

    # ===== Switch backend =====
    print("4. Switch to plotly backend")
    print("-" * 70)
    plot = result.use_backend("plotly").plot("scatter")
    print(f"Result: {plot}")
    print()

    # ===== Explicit backend =====
    print("5. Explicit backend selection")
    print("-" * 70)
    hv_plot = result.plot("line", backend="holoviews")
    print(f"HoloViews result: {hv_plot}")
    plotly_plot = result.plot("surface", backend="plotly")
    print(f"Plotly result: {plotly_plot}")
    print()

    # ===== Auto plot =====
    print("6. Auto-generate plots")
    print("-" * 70)
    auto_plots = result.auto_plot()
    print(f"Result: {auto_plots}")
    print()

    # ===== Backward compatibility =====
    print("7. Backward compatible API (with deprecation warning)")
    print("-" * 70)
    legacy_plot = result.to_scatter()  # Should show deprecation warning
    print(f"Result: {legacy_plot}")
    print()

    # ===== Data access (no viz dependency) =====
    print("8. Data access (no visualization dependency)")
    print("-" * 70)
    print("result.to_pandas() → pandas DataFrame")
    print("result.to_xarray() → xarray Dataset")
    print("result.to_dict() → dictionary")
    print()

    # ===== List backends =====
    print("9. List available backends")
    print("-" * 70)
    backends = VisualizationRegistry.list_adapters()
    print(f"Available backends: {backends}")
    print()

    print("=" * 70)
    print("✓ Demo complete!")
    print("=" * 70)


if __name__ == "__main__":
    demo_usage()
