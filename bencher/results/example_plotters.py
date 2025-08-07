"""Example implementations of the PlotInterface for demonstration purposes."""

from __future__ import annotations
import xarray as xr
import panel as pn
import holoviews as hv
import numpy as np

from bencher.results.unified_filter import PlotInterface
from bencher.plotting.plot_filter import PlotFilter, VarRange
from bencher.variables.results import ResultVar


class ScatterPlotInterface(PlotInterface):
    """Example scatter plot implementation."""

    @property
    def name(self) -> str:
        return "scatter"

    def get_plot_filter(self) -> PlotFilter:
        """Scatter plots work best with 1-2 input dimensions and numeric data."""
        return PlotFilter(
            float_range=VarRange(0, 2),  # 0-2 float variables
            cat_range=VarRange(0, 2),  # 0-2 categorical variables
            input_range=VarRange(1, 3),  # 1-3 input dimensions
            result_vars=VarRange(1, 1),  # exactly 1 result variable
        )

    def can_plot(self, dataset: xr.Dataset, result_var: ResultVar = None, **kwargs) -> bool:
        """Check if we can create a scatter plot from this data."""
        # Need at least 1 dimension and 1 data variable
        if len(dataset.dims) < 1 or len(dataset.data_vars) < 1:
            return False

        # Should have some data points in the dataset
        total_size = 1
        for dim_size in dataset.sizes.values():
            total_size *= dim_size
        if total_size == 0:
            return False

        return True

    def create_plot(
        self, dataset: xr.Dataset, result_var: ResultVar = None, **kwargs
    ) -> pn.pane.HoloViews:
        """Create a scatter plot from the dataset."""
        # Get the result variable to plot
        if result_var is not None:
            var_name = result_var.name if hasattr(result_var, "name") else str(result_var)
        else:
            var_name = list(dataset.data_vars)[0]

        # Convert to HoloViews dataset
        hv_ds = hv.Dataset(dataset)

        # Create scatter plot
        dims = list(dataset.dims)
        if len(dims) >= 2:
            scatter = hv_ds.to(hv.Scatter, kdims=dims[:2], vdims=[var_name])
        else:
            # 1D case - use index vs value
            scatter = hv_ds.to(hv.Scatter, kdims=dims[0], vdims=[var_name])

        return pn.pane.HoloViews(
            scatter.opts(
                width=kwargs.get("width", 600),
                height=kwargs.get("height", 400),
                title=f"Scatter: {var_name}",
                **kwargs,
            )
        )


class LinePlotInterface(PlotInterface):
    """Example line plot implementation."""

    @property
    def name(self) -> str:
        return "line"

    def get_plot_filter(self) -> PlotFilter:
        """Line plots work best with 1-2 input dimensions."""
        return PlotFilter(
            float_range=VarRange(1, 2),  # 1-2 float variables
            cat_range=VarRange(0, 1),  # 0-1 categorical variables
            input_range=VarRange(1, 2),  # 1-2 input dimensions
            result_vars=VarRange(1, 3),  # 1-3 result variables
        )

    def can_plot(self, dataset: xr.Dataset, result_var: ResultVar = None, **kwargs) -> bool:
        """Check if we can create a line plot from this data."""
        # Need at least 1 dimension and some ordered data
        if len(dataset.dims) < 1 or len(dataset.data_vars) < 1:
            return False

        # Works best with numeric dimensions that can be ordered
        numeric_dims = []
        for dim in dataset.dims:
            if dataset.coords[dim].dtype in [np.float64, np.float32, np.int64, np.int32]:
                numeric_dims.append(dim)

        return len(numeric_dims) >= 1

    def create_plot(
        self, dataset: xr.Dataset, result_var: ResultVar = None, **kwargs
    ) -> pn.pane.HoloViews:
        """Create a line plot from the dataset."""
        # Get the result variable to plot
        if result_var is not None:
            var_name = result_var.name if hasattr(result_var, "name") else str(result_var)
        else:
            var_name = list(dataset.data_vars)[0]

        # Convert to HoloViews dataset
        hv_ds = hv.Dataset(dataset)

        # Create line plot
        dims = list(dataset.dims)
        if len(dims) >= 1:
            curve = hv_ds.to(hv.Curve, kdims=dims[0], vdims=[var_name])
        else:
            # Fallback for edge cases
            curve = hv_ds.to(hv.Curve, vdims=[var_name])

        return pn.pane.HoloViews(
            curve.opts(
                width=kwargs.get("width", 600),
                height=kwargs.get("height", 400),
                title=f"Line: {var_name}",
                **kwargs,
            )
        )


class HeatmapPlotInterface(PlotInterface):
    """Example heatmap plot implementation."""

    @property
    def name(self) -> str:
        return "heatmap"

    def get_plot_filter(self) -> PlotFilter:
        """Heatmaps need exactly 2 input dimensions."""
        return PlotFilter(
            float_range=VarRange(0, 2),  # 0-2 float variables
            cat_range=VarRange(0, 2),  # 0-2 categorical variables
            input_range=VarRange(2, 2),  # exactly 2 input dimensions
            result_vars=VarRange(1, 1),  # exactly 1 result variable
        )

    def can_plot(self, dataset: xr.Dataset, result_var: ResultVar = None, **kwargs) -> bool:
        """Check if we can create a heatmap from this data."""
        # Need exactly 2 dimensions for a proper heatmap
        non_repeat_dims = [d for d in dataset.dims if d != "repeat"]
        return len(non_repeat_dims) == 2 and len(dataset.data_vars) >= 1

    def create_plot(
        self, dataset: xr.Dataset, result_var: ResultVar = None, **kwargs
    ) -> pn.pane.HoloViews:
        """Create a heatmap from the dataset."""
        # Get the result variable to plot
        if result_var is not None:
            var_name = result_var.name if hasattr(result_var, "name") else str(result_var)
        else:
            var_name = list(dataset.data_vars)[0]

        # Convert to HoloViews dataset
        hv_ds = hv.Dataset(dataset)

        # Create heatmap - need exactly 2 dimensions
        dims = [d for d in dataset.dims if d != "repeat"]
        if len(dims) >= 2:
            heatmap = hv_ds.to(hv.HeatMap, kdims=dims[:2], vdims=[var_name])
        else:
            # Fallback - not ideal but prevents errors
            heatmap = hv_ds.to(hv.HeatMap, vdims=[var_name])

        return pn.pane.HoloViews(
            heatmap.opts(
                width=kwargs.get("width", 600),
                height=kwargs.get("height", 400),
                title=f"Heatmap: {var_name}",
                colorbar=True,
                cmap="plasma",
                **kwargs,
            )
        )


class CustomTableInterface(PlotInterface):
    """Example custom table implementation that works with any data."""

    @property
    def name(self) -> str:
        return "table"

    def get_plot_filter(self) -> PlotFilter:
        """Tables can handle any type of data."""
        return PlotFilter(
            float_range=VarRange(0, None),  # any number of float variables
            cat_range=VarRange(0, None),  # any number of categorical variables
            input_range=VarRange(0, None),  # any number of input dimensions
            result_vars=VarRange(1, None),  # at least 1 result variable
        )

    def can_plot(self, dataset: xr.Dataset, result_var: ResultVar = None, **kwargs) -> bool:
        """Tables can display any dataset with data."""
        return len(dataset.data_vars) > 0

    def create_plot(
        self, dataset: xr.Dataset, result_var: ResultVar = None, **kwargs
    ) -> pn.pane.DataFrame:
        """Create a table from the dataset."""
        # Convert to pandas DataFrame
        df = dataset.to_dataframe().reset_index()

        # Limit size if too large
        max_rows = kwargs.get("max_rows", 1000)
        if len(df) > max_rows:
            df = df.head(max_rows)
            title = f"Table (showing first {max_rows} rows of {len(dataset.to_dataframe())})"
        else:
            title = "Data Table"

        return pn.Column(
            pn.pane.Markdown(f"### {title}"),
            pn.pane.DataFrame(
                df,
                width=kwargs.get("width", 800),
                height=kwargs.get("height", 400),
                **{k: v for k, v in kwargs.items() if k not in ["width", "height"]},
            ),
        )
