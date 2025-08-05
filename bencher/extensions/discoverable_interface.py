"""
Discoverable interface for BenchResult that provides HoloViews-style .to(PlotType).opts() API.
"""

from __future__ import annotations
from typing import Type, Optional, Any, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    import panel as pn
    from bencher.results.bench_result_base import BenchResultBase

from .plot_types import PlotType, get_plot_type_registry

logger = logging.getLogger(__name__)


class PlotTypeProxy:
    """
    Proxy object that holds a plot type and its options.
    
    This enables the .to(PlotType).opts(**kwargs) pattern.
    """
    
    def __init__(self, result_instance: BenchResultBase, plot_type_class: Type[PlotType]):
        self._result_instance = result_instance
        self._plot_type_class = plot_type_class
        self._plot_type_instance = None
    
    def opts(self, **kwargs) -> PlotTypeProxy:
        """Set options for the plot type."""
        # Create plot type instance with options
        self._plot_type_instance = self._plot_type_class(**kwargs)
        return self
    
    def render(self, **kwargs) -> Optional[pn.panel]:
        """Render the plot with the configured options."""
        if self._plot_type_instance is None:
            self._plot_type_instance = self._plot_type_class()
        
        # Check if plot type can handle this result
        if not self._plot_type_instance.can_handle(self._result_instance):
            return None
        
        # Create the plot
        return self._plot_type_instance.create_plot(self._result_instance, **kwargs)
    
    def __call__(self, **kwargs) -> Optional[pn.panel]:
        """Allow direct calling to render the plot."""
        return self.render(**kwargs)


class DiscoverableResultInterface:
    """
    Mixin that adds discoverable plotting interface to BenchResult.
    
    This provides the .to(PlotType).opts() API similar to HoloViews.
    """
    
    def to(self, plot_type: Type[PlotType], **kwargs) -> PlotTypeProxy:
        """
        Convert result to a specific plot type.
        
        Args:
            plot_type: The plot type class to use
            **kwargs: Options to pass to the plot type
            
        Returns:
            PlotTypeProxy that can be further configured with .opts()
            
        Example:
            # Basic usage
            plot = results.to(PlotTypes.Bar)()
            
            # With options
            plot = results.to(PlotTypes.Heatmap).opts(colormap='viridis')()
            
            # Or combined
            plot = results.to(PlotTypes.Scatter, size=10).opts(alpha=0.7)()
        """
        proxy = PlotTypeProxy(self, plot_type)
        if kwargs:
            proxy.opts(**kwargs)
        return proxy
    
    def list_applicable_plot_types(self) -> list[str]:
        """
        List plot types that can handle this result instance.
        
        Returns:
            List of plot type names that are applicable
        """
        registry = get_plot_type_registry()
        return registry.get_applicable_plot_types(self)
    
    def auto_plot(self, prefer_types: list[str] = None) -> Optional[pn.panel]:
        """
        Automatically select and create the best plot for this result.
        
        Args:
            prefer_types: List of plot type names to prefer (in order)
            
        Returns:
            Panel with the automatically selected plot
        """
        applicable = self.list_applicable_plot_types()
        
        if not applicable:
            return None
        
        # Use preferred types if specified
        if prefer_types:
            for pref_type in prefer_types:
                if pref_type in applicable:
                    registry = get_plot_type_registry()
                    plot_type_class = registry.get_plot_type(pref_type)
                    if plot_type_class:
                        return self.to(plot_type_class)()
        
        # Otherwise use first applicable type
        registry = get_plot_type_registry()
        plot_type_class = registry.get_plot_type(applicable[0])
        if plot_type_class:
            return self.to(plot_type_class)()
        
        return None


def add_discoverable_interface(result_class):
    """
    Add discoverable interface to a result class.
    
    This can be used as a decorator or called directly.
    """
    # Add methods from DiscoverableResultInterface
    for method_name in ['to', 'list_applicable_plot_types', 'auto_plot']:
        if not hasattr(result_class, method_name):
            method = getattr(DiscoverableResultInterface, method_name)
            setattr(result_class, method_name, method)
    
    return result_class