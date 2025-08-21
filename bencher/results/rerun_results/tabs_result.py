"""Tabs visualization using rerun blueprint system for higher dimensions"""

from __future__ import annotations
from typing import Optional
import panel as pn
from param import Parameter
import numpy as np

try:
    import rerun as rr
    import rerun.blueprint as rrb

    RERUN_AVAILABLE = True
except ImportError:
    RERUN_AVAILABLE = False

from bencher.results.rerun_results.rerun_result import RerunResultBase


class TabsRerunResult(RerunResultBase):
    """Tabs visualization using rerun blueprint system

    Creates tabbed interface for higher dimensional data using rerun's blueprint system.
    Suitable for data with 3 or more input variables.
    """

    @staticmethod
    def matches_dataset(dataset, **match_criteria) -> bool:
        """Check if dataset is suitable for tabs visualization"""
        # Tabs work for higher dimensional data (3+ dimensions)
        if hasattr(dataset, "dims"):
            # Count non-singleton dimensions (excluding 'repeat')
            significant_dims = [
                dim for dim in dataset.dims if dim != "repeat" and dataset.sizes[dim] > 1
            ]
            return len(significant_dims) >= 3
        return False

    def to_plot(
        self, result_var: Parameter = None, override: bool = False, **kwargs
    ) -> Optional[pn.panel]:
        """Create tabs visualization"""
        if not RERUN_AVAILABLE:
            return pn.pane.Markdown(
                "⚠️ Rerun visualization unavailable - install with `pip install rerun-sdk`"
            )

        # Filter dataset for the specific result variable
        dataset = self.filter_dataset_for_result(result_var)
        if dataset is None:
            return None

        # Check if suitable for tabs (or override)
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
        """Create tabs visualization in rerun using blueprint system"""
        dataset = self.filter_dataset_for_result(result_var)
        if dataset is None:
            return

        # Get input variables
        input_vars = [
            var
            for var in self.bench_cfg.input_vars
            if var.name in dataset.dims and dataset.sizes[var.name] > 1
        ]

        if len(input_vars) < 3:
            # Fall back to simpler visualization for fewer dimensions
            self._create_fallback_visualization(dataset, result_var, input_vars)
            return

        # For 3D+ data, organize into tabs based on the third dimension
        primary_vars = input_vars[:2]  # Use first two for main plot
        tab_var = input_vars[2]  # Use third for tabs

        entity_base = f"bencher/tabs/{result_var.name}"

        # Get coordinate values for tab dimension
        tab_coords = dataset.coords[tab_var.name].values
        tab_numeric, tab_labels = self._convert_coords_to_numeric(tab_coords, tab_var)

        # Create a tab for each value of the tab dimension
        tab_views = []

        for i, tab_value in enumerate(tab_coords):
            # Filter data for this tab value
            tab_data = dataset.sel({tab_var.name: tab_value})

            # Create entity path for this tab
            tab_entity = f"{entity_base}/tab_{i}"

            # Create visualization for this tab (2D visualization)
            self._create_2d_visualization_for_tab(
                tab_data, result_var, primary_vars, tab_entity, tab_value, tab_var
            )

            # Create tab view for blueprint
            tab_name = f"{tab_var.name}={tab_value}"
            tab_views.append((tab_name, tab_entity))

        # Create blueprint with tabs
        self._create_tabs_blueprint(tab_views, result_var)

        # Log metadata
        data_info = {
            "tabs": len(tab_coords),
            "tab_dimension": tab_var.name,
        }
        if tab_labels:
            data_info[tab_var.name] = {"categorical_labels": tab_labels}

        self._log_metadata(entity_base, result_var, input_vars, data_info)

    def _create_2d_visualization_for_tab(
        self, tab_data, result_var, primary_vars, entity_path, tab_value, tab_var
    ):
        """Create 2D visualization for a single tab"""
        if len(primary_vars) == 1:
            # 1D data - create line plot
            x_var = primary_vars[0]
            x_coords = tab_data.coords[x_var.name].values
            y_values = tab_data.values

            x_numeric, x_labels = self._convert_coords_to_numeric(x_coords, x_var)

            # Log as time series
            for i, (x, y) in enumerate(zip(x_numeric, y_values.flatten())):
                rr.set_time_sequence("step", int(i))
                rr.set_time_seconds("x_value", float(x))
                rr.log(f"{entity_path}/scalar", rr.Scalars(float(y)))

            # Also create line plot
            points = np.column_stack([x_numeric, y_values.flatten()])
            rr.log(f"{entity_path}/line", rr.LineStrips2D([points]))

        elif len(primary_vars) == 2:
            # 2D data - create heatmap/scatter
            x_var, y_var = primary_vars[0], primary_vars[1]

            x_coords_raw = tab_data.coords[x_var.name].values
            y_coords_raw = tab_data.coords[y_var.name].values

            x_coords, x_labels = self._convert_coords_to_numeric(x_coords_raw, x_var)
            y_coords, y_labels = self._convert_coords_to_numeric(y_coords_raw, y_var)

            z_values = tab_data.values

            # Create scatter plot
            points = []
            values = []

            if z_values.ndim >= 2:
                for i, x in enumerate(x_coords):
                    for j, y in enumerate(y_coords):
                        if i < z_values.shape[0] and j < z_values.shape[1]:
                            z_val = z_values[i, j] if z_values.ndim == 2 else z_values[i, j, 0]
                            if not (
                                np.isnan(z_val)
                                if np.issubdtype(type(z_val), np.floating)
                                else False
                            ):
                                points.append([float(x), float(y)])
                                values.append(float(z_val))

            if points:
                rr.log(f"{entity_path}/scatter", rr.Points2D(points, colors=values))

                # If it's grid-like data, also try heatmap
                if z_values.ndim >= 2:
                    z_2d = np.squeeze(z_values)
                    if z_2d.ndim == 2:
                        rr.log(f"{entity_path}/heatmap", rr.DepthImage(z_2d))

    def _create_fallback_visualization(self, dataset, result_var, input_vars):
        """Create fallback visualization for fewer than 3 dimensions"""
        entity_path = self._create_entity_path(result_var, "fallback")

        if len(input_vars) == 1:
            # 1D - create line plot
            x_var = input_vars[0]
            x_coords = dataset.coords[x_var.name].values
            y_values = dataset.values

            x_numeric, _ = self._convert_coords_to_numeric(x_coords, x_var)

            for i, (x, y) in enumerate(zip(x_numeric, y_values.flatten())):
                rr.set_time_sequence("step", int(i))
                rr.log(f"{entity_path}/scalar", rr.Scalars(float(y)))

        elif len(input_vars) == 2:
            # 2D - create scatter plot
            points = []
            values = []

            # Handle different data structures
            coords_dict = {dim: dataset.coords[dim].values for dim in dataset.dims}

            for idx in np.ndindex(dataset.values.shape):
                coord_values = {}
                for i, dim in enumerate(dataset.dims):
                    coord_values[dim] = coords_dict[dim][idx[i]]

                x_val = coord_values.get(input_vars[0].name)
                y_val = coord_values.get(input_vars[1].name)
                z_val = dataset.values[idx]

                if x_val is not None and y_val is not None:
                    # Convert categorical if needed
                    x_num, _ = self._convert_coords_to_numeric(np.array([x_val]), input_vars[0])
                    y_num, _ = self._convert_coords_to_numeric(np.array([y_val]), input_vars[1])

                    points.append([float(x_num[0]), float(y_num[0])])
                    values.append(float(z_val))

            if points:
                rr.log(f"{entity_path}/scatter", rr.Points2D(points, colors=values))

    def _create_tabs_blueprint(self, tab_views, result_var):
        """Create blueprint with tabs using rerun's blueprint system"""
        try:
            # Create tab containers
            tabs = []
            for tab_name, entity_path in tab_views:
                tab_container = rrb.Spatial2DView(origin=entity_path, name=tab_name)
                tabs.append(tab_container)

            # Create tabs container
            tabs_container = rrb.Tabs(*tabs, name=f"{result_var.name} Tabs")

            # Send blueprint
            blueprint = rrb.Blueprint(tabs_container)
            rr.send_blueprint(blueprint)

        except Exception as e:
            # Fallback if blueprint creation fails
            rr.log("bencher/blueprint_error", rr.TextDocument(f"Blueprint creation failed: {e}"))
