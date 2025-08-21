"""Line plot visualization using rerun backend"""

from __future__ import annotations
from typing import Optional
import panel as pn
from param import Parameter
import numpy as np

try:
    import rerun as rr

    RERUN_AVAILABLE = True
except ImportError:
    RERUN_AVAILABLE = False

from bencher.results.rerun_results.rerun_result import RerunResultBase


class LineRerunResult(RerunResultBase):
    """Line plot visualization using rerun backend

    Creates 1D line plots and time series visualizations in rerun.
    Suitable for data with one continuous input variable.
    """

    @staticmethod
    def matches_dataset(dataset, **match_criteria) -> bool:
        """Check if dataset is suitable for line plot visualization"""
        # Line plots work best with 1D continuous data
        if hasattr(dataset, "dims"):
            # Count non-singleton dimensions (excluding 'repeat')
            significant_dims = [
                dim for dim in dataset.dims if dim != "repeat" and dataset.sizes[dim] > 1
            ]
            return len(significant_dims) == 1
        return False

    def to_plot(
        self, result_var: Parameter = None, override: bool = False, **kwargs
    ) -> Optional[pn.panel]:
        """Create line plot visualization"""
        if not RERUN_AVAILABLE:
            return pn.pane.Markdown(
                "⚠️ Rerun visualization unavailable - install with `pip install rerun-sdk`"
            )

        # Filter dataset for the specific result variable
        dataset = self.filter_dataset_for_result(result_var)
        if dataset is None:
            return None

        # Check if suitable for line plot
        if not override and not self.matches_dataset(dataset):
            return None

        return self.to_rerun_panel(result_var, **kwargs)

    def filter_dataset_for_result(self, result_var: Parameter):
        """Filter dataset to get data for specific result variable"""
        if result_var is None:
            result_vars = self.bench_cfg.result_vars
            if not result_vars:
                return None
            result_var = result_vars[0]

        # Get the dataset for this result variable
        if hasattr(self, "ds") and result_var.name in self.ds.data_vars:
            return self.ds[result_var.name]
        return None

    def _create_rerun_visualization(self, result_var: Parameter = None, **kwargs):
        """Create line plot visualization in rerun"""
        dataset = self.filter_dataset_for_result(result_var)
        if dataset is None:
            return

        # Get input variable (should be single dimension for line plot)
        input_vars = [
            var
            for var in self.bench_cfg.input_vars
            if var.name in dataset.dims and dataset.sizes[var.name] > 1
        ]

        if not input_vars:
            return

        input_var = input_vars[0]
        entity_path = self._create_entity_path(result_var, "line")

        # Get coordinate values and data
        x_coords = dataset.coords[input_var.name].values
        y_values = dataset.values

        # Handle multidimensional data by flattening properly
        if y_values.ndim > 1:
            # Create coordinate pairs for all data points
            x_flat = []
            y_flat = []

            for idx in np.ndindex(y_values.shape):
                coord_values = {}
                for i, dim in enumerate(dataset.dims):
                    coord_values[dim] = dataset.coords[dim].values[idx[i]]

                x_val = coord_values[input_var.name]
                y_val = y_values[idx]

                x_flat.append(x_val)
                y_flat.append(y_val)

            x_coords = np.array(x_flat)
            y_values = np.array(y_flat)

        # Convert categorical data to numeric if needed
        x_numeric, x_labels = self._convert_coords_to_numeric(x_coords, input_var)

        # Remove any invalid data points
        valid_mask = np.ones(len(x_numeric), dtype=bool)
        if y_values.dtype.kind in "fc":  # floating point or complex
            valid_mask = valid_mask & ~np.isnan(y_values)

        x_clean = x_numeric[valid_mask]
        y_clean = y_values[valid_mask]

        if len(x_clean) == 0:
            return

        # Log as time series scalars
        for i, (x, y) in enumerate(zip(x_clean, y_clean)):
            rr.set_time_sequence("step", int(i))
            rr.set_time_seconds("x_value", float(x))
            rr.log(f"{entity_path}/scalar", rr.Scalars(float(y)))

        # Also create line plot visualization
        points = np.column_stack([x_clean, y_clean])
        rr.log(f"{entity_path}/line", rr.LineStrips2D([points]))

        # Log metadata
        data_info = {
            "data_points": len(x_clean),
        }
        if x_labels:
            data_info[input_var.name] = {"categorical_labels": x_labels}

        self._log_metadata(entity_path, result_var, [input_var], data_info)
