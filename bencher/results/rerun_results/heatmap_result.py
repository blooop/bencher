"""Heatmap visualization using rerun backend"""

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


class HeatmapRerunResult(RerunResultBase):
    """Heatmap visualization using rerun backend

    Creates 2D heatmap and scatter plot visualizations in rerun.
    Suitable for data with two input variables.
    """

    @staticmethod
    def matches_dataset(dataset, **match_criteria) -> bool:
        """Check if dataset is suitable for heatmap visualization"""
        # Heatmaps work best with 2D data
        if hasattr(dataset, "dims"):
            # Count non-singleton dimensions (excluding 'repeat')
            significant_dims = [
                dim for dim in dataset.dims if dim != "repeat" and dataset.sizes[dim] > 1
            ]
            return len(significant_dims) == 2
        return False

    def to_plot(
        self, result_var: Parameter = None, override: bool = False, **kwargs
    ) -> Optional[pn.panel]:
        """Create heatmap visualization"""
        if not RERUN_AVAILABLE:
            return pn.pane.Markdown(
                "⚠️ Rerun visualization unavailable - install with `pip install rerun-sdk`"
            )

        # Filter dataset for the specific result variable
        dataset = self.filter_dataset_for_result(result_var)
        if dataset is None:
            return None

        # Check if suitable for heatmap
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
        """Create heatmap visualization in rerun"""
        dataset = self.filter_dataset_for_result(result_var)
        if dataset is None:
            return

        # Get input variables (should be two dimensions for heatmap)
        input_vars = [
            var
            for var in self.bench_cfg.input_vars
            if var.name in dataset.dims and dataset.sizes[var.name] > 1
        ]

        if len(input_vars) < 2:
            return

        x_var, y_var = input_vars[0], input_vars[1]
        entity_path = self._create_entity_path(result_var, "heatmap")

        # Get coordinate arrays and convert categorical to numeric
        x_coords_raw = dataset.coords[x_var.name].values
        y_coords_raw = dataset.coords[y_var.name].values

        x_coords, x_labels = self._convert_coords_to_numeric(x_coords_raw, x_var)
        y_coords, y_labels = self._convert_coords_to_numeric(y_coords_raw, y_var)

        z_values = dataset.values

        # Create visualization based on data structure
        if len(x_coords) > 1 and len(y_coords) > 1 and z_values.ndim >= 2:
            # Grid data - use depth image for heatmap
            z_2d = np.squeeze(z_values)
            if z_2d.ndim == 2:
                rr.log(f"{entity_path}/heatmap", rr.DepthImage(z_2d))

        # Also create scatter plot representation
        points = []
        values = []

        # Handle different data structures
        if z_values.ndim > 1:
            # Grid-like data
            for i, x in enumerate(x_coords):
                for j, y in enumerate(y_coords):
                    if i < z_values.shape[0] and j < z_values.shape[1]:
                        z_val = z_values[i, j] if z_values.ndim == 2 else z_values[i, j, 0]
                        if not (
                            np.isnan(z_val) if np.issubdtype(type(z_val), np.floating) else False
                        ):
                            points.append([float(x), float(y)])
                            values.append(float(z_val))
        else:
            # 1D data that needs to be mapped to 2D coordinates
            coords_dict = {dim: dataset.coords[dim].values for dim in dataset.dims}

            for idx in np.ndindex(z_values.shape):
                coord_values = {}
                for i, dim in enumerate(dataset.dims):
                    coord_values[dim] = coords_dict[dim][idx[i]]

                x_val = coord_values.get(x_var.name)
                y_val = coord_values.get(y_var.name)
                z_val = z_values[idx]

                if x_val is not None and y_val is not None:
                    # Convert categorical values to numeric
                    if isinstance(x_val, str) and x_labels:
                        x_val = x_labels.index(x_val)
                    if isinstance(y_val, str) and y_labels:
                        y_val = y_labels.index(y_val)

                    points.append([float(x_val), float(y_val)])
                    values.append(float(z_val))

        if points:
            rr.log(f"{entity_path}/scatter", rr.Points2D(points, colors=values))

        # Log metadata
        data_info = {
            "data_points": len(points),
        }
        if x_labels:
            data_info[x_var.name] = {"categorical_labels": x_labels}
        if y_labels:
            data_info[y_var.name] = {"categorical_labels": y_labels}

        self._log_metadata(entity_path, result_var, [x_var, y_var], data_info)
