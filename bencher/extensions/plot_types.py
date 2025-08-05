"""
Plot type classes for the Bencher extension system.

This module provides discoverable plot types that can be used with the .to(PlotType) interface,
similar to HoloViews. Plot types can be built-in or provided by extensions.
"""

from __future__ import annotations
from typing import Type, Dict, List, Optional, Any, TYPE_CHECKING
from abc import ABC, abstractmethod
import logging

if TYPE_CHECKING:
    import panel as pn
    from bencher.results.bench_result_base import BenchResultBase

logger = logging.getLogger(__name__)


class PlotType(ABC):
    """
    Base class for all plot types.
    
    This provides the interface that all plot types (built-in and extensions) must implement.
    Plot types are discoverable through autocomplete and can be used with .to(PlotType).
    """
    
    name: str = ""
    description: str = ""
    dependencies: List[str] = []
    target_dimensions: List[int] = []
    
    def __init__(self, **opts):
        """Initialize plot type with options."""
        self.opts = opts
    
    @abstractmethod
    def can_handle(self, result_instance: BenchResultBase) -> bool:
        """Check if this plot type can handle the given result instance."""
        ...
    
    @abstractmethod
    def create_plot(self, result_instance: BenchResultBase, **kwargs) -> Optional[pn.panel]:
        """Create the plot from the result instance."""
        ...
    
    @classmethod
    def validate_dependencies(cls) -> bool:
        """Check if all required dependencies are available."""
        try:
            for dep in cls.dependencies:
                package_name = dep.split(">=")[0].split("==")[0].split(">")[0].split("<")[0]
                __import__(package_name)
            return True
        except ImportError:
            return False


class PlotTypeRegistry:
    """Registry for managing discoverable plot types."""
    
    def __init__(self):
        self._plot_types: Dict[str, Type[PlotType]] = {}
        self._built_in_registered = False
    
    def register(self, plot_type_class: Type[PlotType]) -> None:
        """Register a plot type class."""
        name = plot_type_class.name or plot_type_class.__name__
        self._plot_types[name] = plot_type_class
        logger.debug(f"Registered plot type: {name}")
    
    def unregister(self, name: str) -> None:
        """Unregister a plot type."""
        if name in self._plot_types:
            del self._plot_types[name]
            logger.debug(f"Unregistered plot type: {name}")
    
    def get_plot_type(self, name: str) -> Optional[Type[PlotType]]:
        """Get a plot type class by name."""
        self._ensure_built_in_registered()
        return self._plot_types.get(name)
    
    def list_plot_types(self) -> Dict[str, Type[PlotType]]:
        """List all registered plot types."""
        self._ensure_built_in_registered()
        return self._plot_types.copy()
    
    def get_applicable_plot_types(self, result_instance: BenchResultBase) -> List[str]:
        """Get plot types that can handle the given result instance."""
        self._ensure_built_in_registered()
        applicable = []
        
        for name, plot_type_class in self._plot_types.items():
            try:
                # Create instance with default options to test
                instance = plot_type_class()
                if instance.can_handle(result_instance):
                    applicable.append(name)
            except Exception as e:
                logger.debug(f"Plot type {name} cannot handle result: {e}")
        
        return applicable
    
    def _ensure_built_in_registered(self) -> None:
        """Ensure built-in plot types are registered."""
        if not self._built_in_registered:
            self._register_built_in_plot_types()
            self._built_in_registered = True
    
    def _register_built_in_plot_types(self) -> None:
        """Register built-in plot types from existing result classes."""
        # Import here to avoid circular imports
        try:
            from .builtin_plot_types import (
                BarPlot, LinePlot, ScatterPlot, HeatmapPlot, CurvePlot,
                BoxWhiskerPlot, ViolinPlot, HistogramPlot, SurfacePlot, VolumePlot
            )
            
            built_in_types = [
                BarPlot, LinePlot, ScatterPlot, HeatmapPlot, CurvePlot,
                BoxWhiskerPlot, ViolinPlot, HistogramPlot, SurfacePlot, VolumePlot
            ]
            
            for plot_type in built_in_types:
                self.register(plot_type)
                
        except ImportError as e:
            logger.warning(f"Could not import built-in plot types: {e}")


# Global registry instance
_plot_type_registry = None


def get_plot_type_registry() -> PlotTypeRegistry:
    """Get the global plot type registry."""
    global _plot_type_registry
    if _plot_type_registry is None:
        _plot_type_registry = PlotTypeRegistry()
    return _plot_type_registry


def register_plot_type(plot_type_class: Type[PlotType]) -> None:
    """Register a plot type globally."""
    get_plot_type_registry().register(plot_type_class)


def plot_type(
    name: str = "",
    description: str = "",
    dependencies: List[str] = None,
    target_dimensions: List[int] = None
):
    """
    Decorator to register a plot type class.
    
    Example:
        @plot_type(
            name="Plotly3D",
            description="3D scatter plot using Plotly",
            dependencies=["plotly>=5.0"],
            target_dimensions=[3]
        )
        class Plotly3DPlot(PlotType):
            def can_handle(self, result_instance):
                return len(result_instance.bench_cfg.input_vars) >= 2
            
            def create_plot(self, result_instance, **kwargs):
                # Implementation here
                pass
    """
    def decorator(cls):
        cls.name = name or cls.__name__
        cls.description = description
        cls.dependencies = dependencies or []
        cls.target_dimensions = target_dimensions or []
        
        # Auto-register
        register_plot_type(cls)
        
        return cls
    
    return decorator


# Create module-level plot type classes for discoverability
class PlotTypes:
    """
    Container for discoverable plot types.
    
    This allows users to do: results.to(PlotTypes.Bar) or results.to(PlotTypes.Plotly3D)
    and get full autocomplete support.
    """
    
    def __init__(self):
        self._registry = get_plot_type_registry()
    
    def __getattr__(self, name: str) -> Type[PlotType]:
        """Get plot type by attribute access for autocomplete."""
        plot_type = self._registry.get_plot_type(name)
        if plot_type is None:
            available = list(self._registry.list_plot_types().keys())
            raise AttributeError(f"Plot type '{name}' not found. Available: {available}")
        return plot_type
    
    def __dir__(self) -> List[str]:
        """Return list of available plot types for autocomplete."""
        return list(self._registry.list_plot_types().keys())
    
    def list_all(self) -> Dict[str, Type[PlotType]]:
        """List all available plot types."""
        return self._registry.list_plot_types()


# Global instance for discoverability
plot_types = PlotTypes()