from typing import Optional
from functools import partial

import panel as pn
from param import Parameter
import holoviews as hv
import pandas as pd

from bencher.variables.results import ResultScatter3D
from bencher.results.bench_result_base import BenchResultBase, ReduceType


class Scatter3DResult(BenchResultBase):
    """A class for creating 3D scatter plots from benchmark results.

    This class automatically renders ResultScatter3D objects as interactive 3D scatter plots
    using HoloViews and Plotly backend. The data should be stored as a pandas DataFrame
    with x, y, z coordinates and optional color/size values.
    """

    def to_plot(
        self,
        result_var: Parameter = None,
        hv_dataset=None,
        target_dimension: int = 0,
        level: int = None,
        **kwargs,
    ) -> Optional[pn.pane.panel]:
        """Create a 3D scatter plot from the data.

        Args:
            result_var: The result variable to plot
            hv_dataset: Optional holoviews dataset
            target_dimension: Target dimension for plotting
            level: Level for data reduction
            **kwargs: Additional plotting arguments

        Returns:
            Panel containing the 3D scatter plot
        """
        if hv_dataset is None:
            hv_dataset = self.to_hv_dataset(ReduceType.SQUEEZE, level=level)
        elif not isinstance(hv_dataset, hv.Dataset):
            hv_dataset = hv.Dataset(hv_dataset)

        return self.map_plot_panes(
            partial(self.scatter3d_from_dataset),
            hv_dataset=hv_dataset,
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=(ResultScatter3D,),
            **kwargs,
        )

    def to_scatter3d(
        self,
        result_var: Parameter = None,
        hv_dataset=None,
        target_dimension: int = 0,
        level: int = None,
        **kwargs,
    ) -> Optional[pn.pane.panel]:
        """Create a 3D scatter plot from the data.

        Args:
            result_var: The result variable to plot
            hv_dataset: Optional holoviews dataset
            target_dimension: Target dimension for plotting
            level: Level for data reduction
            **kwargs: Additional plotting arguments

        Returns:
            Panel containing the 3D scatter plot
        """
        if hv_dataset is None:
            hv_dataset = self.to_hv_dataset(ReduceType.SQUEEZE, level=level)
        elif not isinstance(hv_dataset, hv.Dataset):
            hv_dataset = hv.Dataset(hv_dataset)

        return self.map_plot_panes(
            partial(self.scatter3d_from_dataset),
            hv_dataset=hv_dataset,
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=(ResultScatter3D,),
            **kwargs,
        )

    def scatter3d_from_dataset(
        self, dataset=None, result_var: Parameter = None, **kwargs
    ) -> hv.Scatter3D:
        """Convert dataset to Scatter3D plot.

        Args:
            dataset: The dataset containing the scatter data
            result_var: The result variable containing the data
            **kwargs: Additional plotting options

        Returns:
            HoloViews Scatter3D plot
        """
        # Get the pandas DataFrame from the ResultScatter3D object
        if hasattr(result_var, "obj") and result_var.obj is not None:
            df = result_var.obj
        else:
            # Fallback: try to get from dataset
            df = dataset

        if not isinstance(df, pd.DataFrame):
            raise ValueError("ResultScatter3D data must be a pandas DataFrame")

        # Check for required columns
        required_cols = ["x", "y", "z"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"DataFrame missing required columns: {missing_cols}")

        # Determine color column
        color_col = None
        if "color_value" in df.columns:
            color_col = "color_value"
        elif "intensity" in df.columns:
            color_col = "intensity"
        elif "distance" in df.columns:
            color_col = "distance"

        # Create the scatter3D plot
        if color_col:
            scatter = hv.Scatter3D((df["x"], df["y"], df["z"]), vdims=[color_col]).opts(
                color=color_col, cmap="viridis", size=8, title="3D Scatter Plot", **kwargs
            )
        else:
            scatter = hv.Scatter3D((df["x"], df["y"], df["z"])).opts(
                size=8, title="3D Scatter Plot", **kwargs
            )

        return scatter
