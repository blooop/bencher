"""Base class for rerun visualization backends"""

from __future__ import annotations
from typing import List, Optional
import panel as pn
from param import Parameter
import numpy as np

try:
    import rerun as rr

    RERUN_AVAILABLE = True
except ImportError:
    RERUN_AVAILABLE = False

from bencher.results.bench_result_base import BenchResultBase


class RerunResultBase(BenchResultBase):
    """Base class for rerun visualization backends

    This class provides common functionality for all rerun-based visualizations,
    following the same pattern as HoloviewResult.
    """

    def __init__(self, bench_cfg):
        super().__init__(bench_cfg)
        self._rerun_initialized = False
        self._entity_counter = 0

    def _ensure_rerun_initialized(self):
        """Initialize rerun if not already done"""
        if not RERUN_AVAILABLE:
            raise ImportError("Rerun is not available. Please install with: pip install rerun-sdk")

        if not self._rerun_initialized:
            app_id = f"bencher_{self.bench_cfg.bench_name or 'benchmark'}"
            rr.init(app_id, spawn=True)
            self._rerun_initialized = True

    def _convert_coords_to_numeric(self, coords, var=None):
        """Convert coordinate values to numeric, handling categorical data"""
        if hasattr(coords, "dtype") and coords.dtype.kind in [
            "U",
            "S",
            "O",
        ]:  # String or object dtype
            # Categorical data - map to numeric indices
            unique_values = list(set(coords))
            value_to_index = {val: i for i, val in enumerate(unique_values)}
            numeric_coords = np.array([value_to_index[val] for val in coords])
            return numeric_coords, unique_values
        # Already numeric
        return coords, None

    def _create_entity_path(self, result_var: Parameter, plot_type: str = "default") -> str:
        """Create a hierarchical entity path for rerun logging"""
        base_path = f"bencher/{plot_type}"
        if result_var:
            base_path += f"/{result_var.name}"
        return base_path

    def _log_metadata(
        self, entity_path: str, result_var: Parameter, input_vars: List[Parameter], data_info: dict
    ):
        """Log metadata information for a visualization"""
        metadata_lines = [f"Variable: {result_var.name}"]

        for i, var in enumerate(input_vars):
            if var.name in data_info and "categorical_labels" in data_info[var.name]:
                labels = data_info[var.name]["categorical_labels"]
                metadata_lines.append(f"Input {i + 1}: {var.name} (categorical: {labels})")
            else:
                units = getattr(var, "units", "dimensionless")
                metadata_lines.append(f"Input {i + 1}: {var.name} ({units})")

        result_units = getattr(result_var, "units", "dimensionless")
        metadata_lines.append(f"Output: {result_var.name} ({result_units})")

        if "data_points" in data_info:
            metadata_lines.append(f"Data points: {data_info['data_points']}")

        rr.log(f"{entity_path}/info", rr.TextDocument("\n".join(metadata_lines)))

    @staticmethod
    def matches_dataset(dataset, **match_criteria) -> bool:
        """Check if dataset matches criteria for this visualization type

        This method should be overridden by subclasses to define when
        they are appropriate for a given dataset.

        Args:
            dataset: The dataset to check
            **match_criteria: Additional criteria (unused in base class)
        """
        # Base implementation always returns True - subclasses should override
        _ = dataset, match_criteria  # Acknowledge unused args
        return True

    def to_plot(
        self, result_var: Parameter = None, override: bool = False, **kwargs
    ) -> Optional[pn.panel]:
        """Main plotting method - should be overridden by subclasses

        Args:
            result_var: Variable to plot (unused in base class)
            override: Override normal behavior (unused in base class)
            **kwargs: Additional arguments (unused in base class)
        """
        # Acknowledge unused args
        _ = result_var, override, kwargs

        if not RERUN_AVAILABLE:
            return pn.pane.Markdown(
                "⚠️ Rerun visualization unavailable - install with `pip install rerun-sdk`"
            )

        # This base implementation returns a placeholder
        return pn.pane.Markdown("Base RerunResultBase - override to_plot in subclass")

    def to_rerun_panel(self, result_var: Parameter = None, **kwargs) -> pn.pane.Markdown:
        """Convert to rerun visualization and return info panel"""
        if not RERUN_AVAILABLE:
            return pn.pane.Markdown(
                "⚠️ Rerun visualization unavailable - install with `pip install rerun-sdk`"
            )

        self._ensure_rerun_initialized()

        try:
            # Subclasses should implement the actual visualization logic
            self._create_rerun_visualization(result_var, **kwargs)

            return pn.pane.Markdown(
                f"✅ **Rerun {self.__class__.__name__} Created**\n\n"
                f"📊 Interactive visualization launched in Rerun viewer\n\n"
                f"💡 Check the Rerun viewer window for the visualization"
            )

        except Exception as e:
            return pn.pane.Markdown(f"⚠️ Error creating rerun visualization: {e}")

    def _create_rerun_visualization(self, result_var: Parameter = None, **kwargs):
        """Create the actual rerun visualization - override in subclasses"""
        raise NotImplementedError("Subclasses must implement _create_rerun_visualization")
