"""
Core interfaces and protocols for the Bencher extension system.
"""

from __future__ import annotations
from typing import Protocol, Optional, List, Callable
from dataclasses import dataclass
import panel as pn

from bencher.bench_cfg import BenchCfg
from bencher.plotting.plot_filter import PlotFilter


@dataclass
class ExtensionMetadata:
    """Metadata describing a result extension."""

    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    dependencies: List[str] = None
    result_types: List[str] = None
    plot_types: List[str] = None
    target_dimensions: List[int] = None
    filter_criteria: PlotFilter = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.result_types is None:
            self.result_types = []
        if self.plot_types is None:
            self.plot_types = []
        if self.target_dimensions is None:
            self.target_dimensions = []


class ResultExtension(Protocol):
    """Protocol defining the interface that all result extensions must implement."""

    @property
    def metadata(self) -> ExtensionMetadata:
        """Return metadata describing this extension."""
        ...

    def can_handle(self, bench_cfg: BenchCfg) -> bool:
        """
        Check if this extension can handle the given benchmark configuration.

        Args:
            bench_cfg: The benchmark configuration to check

        Returns:
            True if this extension can process the configuration
        """
        ...

    def to_plot(self, **kwargs) -> Optional[pn.panel]:
        """
        Create the primary plot/visualization for this extension.

        Args:
            **kwargs: Plotting options and parameters

        Returns:
            Panel containing the visualization, or None if not applicable
        """
        ...

    def get_plot_callbacks(self) -> List[Callable]:
        """
        Return list of available plotting methods for this extension.

        Returns:
            List of callable plotting methods
        """
        ...


class ExtensionCapability(Protocol):
    """Additional capabilities that extensions may implement."""

    def setup(self) -> None:
        """Initialize the extension (called once after loading)."""
        ...

    def teardown(self) -> None:
        """Clean up the extension (called before unloading)."""
        ...

    def validate_dependencies(self) -> bool:
        """Check if all required dependencies are available."""
        ...

    def get_configuration_schema(self) -> dict:
        """Return JSON schema for extension configuration."""
        ...


class ResultExtensionBase:
    """
    Base class providing common functionality for result extensions.

    Extensions can inherit from this class to get default implementations
    of common methods, or implement the ResultExtension protocol directly.
    """

    def __init__(self, bench_cfg: BenchCfg = None):
        """Initialize the extension with optional benchmark configuration."""
        self.bench_cfg = bench_cfg
        self._initialized = False

    def setup(self) -> None:
        """Default setup implementation - override in subclasses."""
        self._initialized = True

    def teardown(self) -> None:
        """Default teardown implementation - override in subclasses."""
        self._initialized = False

    def validate_dependencies(self) -> bool:
        """
        Default dependency validation - checks if modules can be imported.

        Returns:
            True if all dependencies in metadata are importable
        """
        try:
            for dep in self.metadata.dependencies:
                # Simple dependency format: "package>=version" -> "package"
                package_name = dep.split(">=")[0].split("==")[0].split(">")[0].split("<")[0]
                __import__(package_name)
            return True
        except ImportError:
            return False

    def get_configuration_schema(self) -> dict:
        """Return empty configuration schema by default."""
        return {}

    def can_handle(self, bench_cfg: BenchCfg) -> bool:
        """
        Default implementation checks if any result variables match supported types.

        Args:
            bench_cfg: Benchmark configuration to check

        Returns:
            True if extension can handle this configuration
        """
        if not self.metadata.result_types:
            return True  # No restrictions specified

        for result_var in bench_cfg.result_vars:
            if type(result_var).__name__ in self.metadata.result_types:
                return True
        return False

    def get_plot_callbacks(self) -> List[Callable]:
        """
        Default implementation returns the to_plot method.

        Returns:
            List containing the to_plot method
        """
        return [self.to_plot]


class ExtensionError(Exception):
    """Base exception for extension-related errors."""

    pass


class ExtensionLoadError(ExtensionError):
    """Raised when an extension fails to load."""

    pass


class ExtensionValidationError(ExtensionError):
    """Raised when an extension fails validation."""

    pass
