"""
Built-in plot types that wrap existing result classes.

These provide discoverable plot types for the existing functionality.
"""

from typing import Optional, TYPE_CHECKING
from .plot_types import PlotType, plot_type

if TYPE_CHECKING:
    import panel as pn
    from bencher.results.bench_result_base import BenchResultBase


@plot_type(
    name="Bar",
    description="Bar chart visualization",
    target_dimensions=[1, 2]
)
class BarPlot(PlotType):
    """Bar chart plot type."""
    
    def can_handle(self, result_instance: 'BenchResultBase') -> bool:
        """Check if we can create a bar chart."""
        try:
            return hasattr(result_instance, 'to_plot') and len(result_instance.bench_cfg.result_vars) > 0
        except:
            return False
    
    def create_plot(self, result_instance: 'BenchResultBase', **kwargs) -> Optional['pn.panel']:
        """Create bar chart using BarResult."""
        try:
            from bencher.results.holoview_results.bar_result import BarResult
            if hasattr(result_instance, 'to'):
                return result_instance.to(BarResult, **kwargs, **self.opts)
            return None
        except Exception:
            return None


@plot_type(
    name="Line", 
    description="Line plot visualization",
    target_dimensions=[1, 2]
)
class LinePlot(PlotType):
    """Line plot type."""
    
    def can_handle(self, result_instance: 'BenchResultBase') -> bool:
        """Check if we can create a line plot."""
        try:
            return hasattr(result_instance, 'to_plot') and len(result_instance.bench_cfg.input_vars) > 0
        except:
            return False
    
    def create_plot(self, result_instance: 'BenchResultBase', **kwargs) -> Optional['pn.panel']:
        """Create line plot using LineResult."""
        try:
            from bencher.results.holoview_results.line_result import LineResult
            if hasattr(result_instance, 'to'):
                return result_instance.to(LineResult, **kwargs, **self.opts)
            return None
        except Exception:
            return None


@plot_type(
    name="Scatter",
    description="Scatter plot visualization", 
    target_dimensions=[2]
)
class ScatterPlot(PlotType):
    """Scatter plot type."""
    
    def can_handle(self, result_instance: 'BenchResultBase') -> bool:
        """Check if we can create a scatter plot."""
        try:
            return hasattr(result_instance, 'to_plot') and len(result_instance.bench_cfg.input_vars) >= 1
        except:
            return False
    
    def create_plot(self, result_instance: 'BenchResultBase', **kwargs) -> Optional['pn.panel']:
        """Create scatter plot using ScatterResult."""
        try:
            from bencher.results.holoview_results.scatter_result import ScatterResult
            if hasattr(result_instance, 'to'):
                return result_instance.to(ScatterResult, **kwargs, **self.opts)
            return None
        except Exception:
            return None


@plot_type(
    name="Heatmap",
    description="Heatmap visualization",
    target_dimensions=[2]
)
class HeatmapPlot(PlotType):
    """Heatmap plot type."""
    
    def can_handle(self, result_instance: 'BenchResultBase') -> bool:
        """Check if we can create a heatmap."""
        try:
            return hasattr(result_instance, 'to_plot') and len(result_instance.bench_cfg.input_vars) >= 2
        except:
            return False
    
    def create_plot(self, result_instance: 'BenchResultBase', **kwargs) -> Optional['pn.panel']:
        """Create heatmap using HeatmapResult."""
        try:
            from bencher.results.holoview_results.heatmap_result import HeatmapResult
            if hasattr(result_instance, 'to'):
                return result_instance.to(HeatmapResult, **kwargs, **self.opts)
            return None
        except Exception:
            return None


@plot_type(
    name="Curve",
    description="Curve plot visualization",
    target_dimensions=[1, 2]
)
class CurvePlot(PlotType):
    """Curve plot type."""
    
    def can_handle(self, result_instance: 'BenchResultBase') -> bool:
        """Check if we can create a curve plot."""
        try:
            return hasattr(result_instance, 'to_plot') and len(result_instance.bench_cfg.input_vars) >= 1
        except:
            return False
    
    def create_plot(self, result_instance: 'BenchResultBase', **kwargs) -> Optional['pn.panel']:
        """Create curve plot using CurveResult."""
        try:
            from bencher.results.holoview_results.curve_result import CurveResult
            if hasattr(result_instance, 'to'):
                return result_instance.to(CurveResult, **kwargs, **self.opts)
            return None
        except Exception:
            return None


@plot_type(
    name="BoxWhisker",
    description="Box and whisker plot",
    target_dimensions=[1, 2]
)
class BoxWhiskerPlot(PlotType):
    """Box and whisker plot type."""
    
    def can_handle(self, result_instance: 'BenchResultBase') -> bool:
        """Check if we can create a box plot."""
        try:
            return hasattr(result_instance, 'to_plot') and result_instance.bench_cfg.repeats > 1
        except:
            return False
    
    def create_plot(self, result_instance: 'BenchResultBase', **kwargs) -> Optional['pn.panel']:
        """Create box plot using BoxWhiskerResult."""
        try:
            from bencher.results.holoview_results.distribution_result.box_whisker_result import BoxWhiskerResult
            if hasattr(result_instance, 'to'):
                return result_instance.to(BoxWhiskerResult, **kwargs, **self.opts)
            return None
        except Exception:
            return None


@plot_type(
    name="Violin",
    description="Violin plot visualization", 
    target_dimensions=[1, 2]
)
class ViolinPlot(PlotType):
    """Violin plot type."""
    
    def can_handle(self, result_instance: 'BenchResultBase') -> bool:
        """Check if we can create a violin plot.""" 
        try:
            return hasattr(result_instance, 'to_plot') and result_instance.bench_cfg.repeats > 1
        except:
            return False
    
    def create_plot(self, result_instance: 'BenchResultBase', **kwargs) -> Optional['pn.panel']:
        """Create violin plot using ViolinResult."""
        try:
            from bencher.results.holoview_results.distribution_result.violin_result import ViolinResult
            if hasattr(result_instance, 'to'):
                return result_instance.to(ViolinResult, **kwargs, **self.opts)
            return None
        except Exception:
            return None


@plot_type(
    name="Histogram",
    description="Histogram visualization",
    target_dimensions=[1]
)
class HistogramPlot(PlotType):
    """Histogram plot type."""
    
    def can_handle(self, result_instance: 'BenchResultBase') -> bool:
        """Check if we can create a histogram."""
        try:
            return hasattr(result_instance, 'to_plot') and len(result_instance.bench_cfg.result_vars) > 0
        except:
            return False
    
    def create_plot(self, result_instance: 'BenchResultBase', **kwargs) -> Optional['pn.panel']:
        """Create histogram using HistogramResult."""
        try:
            from bencher.results.histogram_result import HistogramResult
            if hasattr(result_instance, 'to'):
                return result_instance.to(HistogramResult, **kwargs, **self.opts)
            return None
        except Exception:
            return None


@plot_type(
    name="Surface",
    description="3D surface plot using Plotly",
    dependencies=["plotly>=5.0"],
    target_dimensions=[3]
)
class SurfacePlot(PlotType):
    """3D surface plot type."""
    
    def can_handle(self, result_instance: 'BenchResultBase') -> bool:
        """Check if we can create a surface plot."""
        try:
            return (hasattr(result_instance, 'to_plot') and 
                   len(result_instance.bench_cfg.input_vars) >= 2 and
                   self.validate_dependencies())
        except:
            return False
    
    def create_plot(self, result_instance: 'BenchResultBase', **kwargs) -> Optional['pn.panel']:
        """Create surface plot using SurfaceResult."""
        try:
            from bencher.results.holoview_results.surface_result import SurfaceResult
            if hasattr(result_instance, 'to'):
                return result_instance.to(SurfaceResult, **kwargs, **self.opts)
            return None
        except Exception:
            return None


@plot_type(
    name="Volume",
    description="3D volume visualization",
    dependencies=["plotly>=5.0"],
    target_dimensions=[3]
)
class VolumePlot(PlotType):
    """3D volume plot type."""
    
    def can_handle(self, result_instance: 'BenchResultBase') -> bool:
        """Check if we can create a volume plot."""
        try:
            return (hasattr(result_instance, 'to_plot') and 
                   len(result_instance.bench_cfg.input_vars) >= 3 and
                   self.validate_dependencies())
        except:
            return False
    
    def create_plot(self, result_instance: 'BenchResultBase', **kwargs) -> Optional['pn.panel']:
        """Create volume plot using VolumeResult."""
        try:
            from bencher.results.volume_result import VolumeResult
            if hasattr(result_instance, 'to'):
                return result_instance.to(VolumeResult, **kwargs, **self.opts)
            return None
        except Exception:
            return None