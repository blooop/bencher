"""Composable rerun result that integrates all rerun plot types"""

from __future__ import annotations
from typing import List, Optional
import panel as pn
from param import Parameter

try:
    import rerun as rr
    import rerun.blueprint as rrb

    RERUN_AVAILABLE = True
except ImportError:
    RERUN_AVAILABLE = False

from bencher.results.rerun_results.rerun_result import RerunResultBase
from bencher.results.rerun_results.line_result import LineRerunResult
from bencher.results.rerun_results.heatmap_result import HeatmapRerunResult
from bencher.results.rerun_results.tabs_result import TabsRerunResult
from bencher.variables.results import ResultVar


class RerunComposableResult(LineRerunResult, HeatmapRerunResult, TabsRerunResult, RerunResultBase):
    """Composable rerun result that automatically selects appropriate visualization types

    This class combines all rerun visualization types and automatically selects
    the most appropriate one based on the data characteristics, similar to how
    HoloviewResult works in the existing codebase.
    """

    def __init__(self, bench_cfg):
        super().__init__(bench_cfg)
        self._plot_types = [
            LineRerunResult,
            HeatmapRerunResult,
            TabsRerunResult,
        ]

    def to_rerun(self, result_var: Parameter = None, **kwargs) -> pn.pane.Markdown:
        """Create rerun visualization using automatic plot type selection"""
        if not RERUN_AVAILABLE:
            return pn.pane.Markdown(
                "⚠️ Rerun visualization unavailable - install with `pip install rerun-sdk`"
            )

        self._ensure_rerun_initialized()

        try:
            # Get result variables to visualize
            result_vars = [result_var] if result_var else self.bench_cfg.result_vars
            if not result_vars:
                return pn.pane.Markdown("⚠️ No result variables found for rerun visualization")

            visualizations_created = 0

            # Create visualizations for each result variable
            for rv in result_vars:
                if isinstance(rv, ResultVar):
                    plot_type = self._select_plot_type(rv)
                    if plot_type:
                        plot_instance = plot_type(self.bench_cfg)
                        plot_instance.ds = getattr(self, "ds", None)  # Share dataset
                        plot_instance._create_rerun_visualization(rv, **kwargs)
                        visualizations_created += 1

            # Create and send adaptive blueprint
            self._create_adaptive_blueprint()

            if visualizations_created == 0:
                return pn.pane.Markdown(
                    "⚠️ No suitable rerun visualizations could be created for the data"
                )

            return pn.pane.Markdown(
                f"✅ **Rerun Visualization Created**\n\n"
                f"📊 Interactive visualization launched in Rerun viewer\n\n"
                f"🔗 Variables visualized: {', '.join([rv.name for rv in result_vars])}\n\n"
                f"📈 Visualizations created: {visualizations_created}\n\n"
                f"💡 The Rerun viewer should open automatically showing your benchmark results"
            )

        except Exception as e:
            return pn.pane.Markdown(f"⚠️ Error creating rerun visualization: {e}")

    def _select_plot_type(self, result_var: Parameter):
        """Select the most appropriate plot type for the given result variable"""
        # Get dataset for this result variable
        dataset = None
        if hasattr(self, "ds") and result_var.name in self.ds.data_vars:
            dataset = self.ds[result_var.name]

        if dataset is None:
            return None

        # Try plot types in order of preference
        for plot_type in self._plot_types:
            if plot_type.matches_dataset(dataset):
                return plot_type

        # Fallback to line plot for any data
        return LineRerunResult

    def _create_adaptive_blueprint(self):
        """Create an adaptive blueprint based on the logged data"""
        try:
            # Create a simple blueprint that organizes the visualizations
            views = []

            # Add views for different plot types
            for plot_type_name in ["line", "heatmap", "tabs"]:
                view = rrb.Spatial2DView(
                    origin=f"bencher/{plot_type_name}", name=plot_type_name.title()
                )
                views.append(view)

            if views:
                # Create tabs with different visualization types
                tabs_container = rrb.Tabs(*views, name="Bencher Results")
                blueprint = rrb.Blueprint(tabs_container)
                rr.send_blueprint(blueprint)

        except Exception:
            # If blueprint creation fails, just continue without it
            pass

    def to_plot(
        self, result_var: Parameter = None, override: bool = False, **kwargs
    ) -> Optional[pn.panel]:
        """Main plotting method that delegates to appropriate rerun visualization"""
        return self.to_rerun(result_var, **kwargs)

    @staticmethod
    def default_plot_callbacks() -> List[callable]:
        """Get the default list of rerun plot callback functions"""
        return [
            RerunComposableResult.to_rerun,
        ]

    def matches_any_dataset(self, **kwargs) -> bool:
        """Check if any rerun plot type can handle the dataset"""
        if not hasattr(self, "ds"):
            return False

        for result_var in self.bench_cfg.result_vars:
            if result_var.name in self.ds.data_vars:
                dataset = self.ds[result_var.name]
                for plot_type in self._plot_types:
                    if plot_type.matches_dataset(dataset):
                        return True

        return False
