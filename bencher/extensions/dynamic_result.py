"""
Dynamic result class that composes extensions at runtime.
"""

from __future__ import annotations
from typing import List, Optional, Callable, Any
import logging
import panel as pn

from bencher.results.bench_result_base import BenchResultBase
from bencher.bench_cfg import BenchCfg
from .extension_registry import get_registry

logger = logging.getLogger(__name__)


class DynamicBenchResult(BenchResultBase):
    """
    Dynamic result class that loads and composes extensions at runtime.

    This class provides the bridge between the existing BenchResult system
    and the new extension architecture. It discovers applicable extensions
    for the given benchmark configuration and delegates plotting calls to them.
    """

    def __init__(self, bench_cfg: BenchCfg):
        """
        Initialize with benchmark configuration and discover applicable extensions.

        Args:
            bench_cfg: Benchmark configuration
        """
        super().__init__(bench_cfg)
        self._registry = get_registry()
        self._loaded_extensions: List[str] = []
        self._extension_callbacks: List[Callable] = []
        self._load_extensions()

    def _load_extensions(self) -> None:
        """Load extensions applicable to the current benchmark configuration."""
        try:
            # Get applicable extensions
            applicable = self._registry.get_applicable_extensions(self.bench_cfg)

            # Load extension instances and get callbacks
            for ext_name in applicable:
                try:
                    instance = self._registry.get_extension_instance(ext_name, self.bench_cfg)
                    if instance:
                        callbacks = instance.get_plot_callbacks()
                        self._extension_callbacks.extend(callbacks)
                        self._loaded_extensions.append(ext_name)
                        logger.debug(f"Loaded extension: {ext_name}")
                except Exception as e:
                    logger.warning(f"Failed to load extension {ext_name}: {e}")

            if self._loaded_extensions:
                logger.info(
                    f"Loaded {len(self._loaded_extensions)} extensions: {self._loaded_extensions}"
                )

        except Exception as e:
            logger.warning(f"Error loading extensions: {e}")

    def get_extension_plot_callbacks(self) -> List[Callable]:
        """
        Get plot callbacks from all loaded extensions.

        Returns:
            List of plot callback functions from extensions
        """
        return self._extension_callbacks.copy()

    def get_all_plot_callbacks(self) -> List[Callable]:
        """
        Get all plot callbacks including extensions and default callbacks.

        Returns:
            Combined list of all available plot callbacks
        """
        callbacks = []

        # Add extension callbacks
        callbacks.extend(self._extension_callbacks)

        # Add default callbacks if available
        try:
            default_callbacks = self.default_plot_callbacks()
            callbacks.extend(default_callbacks)
        except (AttributeError, TypeError):
            # No default callbacks available
            pass

        return callbacks

    def to_plot_with_extensions(
        self, prefer_extensions: Optional[List[str]] = None, fallback: bool = True, **kwargs
    ) -> Optional[pn.panel]:
        """
        Create plot using extensions with optional fallback.

        Args:
            prefer_extensions: List of extension names to prefer (in order)
            fallback: Whether to fallback to other methods if extensions fail
            **kwargs: Plotting options

        Returns:
            Panel containing the plot or None
        """
        # Try preferred extensions first
        if prefer_extensions:
            for ext_name in prefer_extensions:
                if ext_name in self._loaded_extensions:
                    try:
                        instance = self._registry.get_extension_instance(ext_name, self.bench_cfg)
                        if instance:
                            result = instance.to_plot(**kwargs)
                            if result is not None:
                                return result
                    except Exception as e:
                        logger.warning(f"Extension {ext_name} failed: {e}")

        # Try all loaded extensions
        for ext_name in self._loaded_extensions:
            if prefer_extensions and ext_name in prefer_extensions:
                continue  # Already tried above

            try:
                instance = self._registry.get_extension_instance(ext_name, self.bench_cfg)
                if instance:
                    result = instance.to_plot(**kwargs)
                    if result is not None:
                        return result
            except Exception as e:
                logger.debug(f"Extension {ext_name} failed: {e}")

        # Fallback to default behavior if enabled
        if fallback and hasattr(super(), "to_plot"):
            try:
                return super().to_plot(**kwargs)
            except Exception as e:
                logger.debug(f"Default to_plot failed: {e}")

        return None

    def list_loaded_extensions(self) -> List[str]:
        """
        Get list of loaded extension names.

        Returns:
            List of extension names that were successfully loaded
        """
        return self._loaded_extensions.copy()

    def get_extension_metadata(self, name: str) -> Optional[Any]:
        """
        Get metadata for a loaded extension.

        Args:
            name: Extension name

        Returns:
            Extension metadata or None if not found
        """
        if name in self._loaded_extensions:
            return self._registry._metadata.get(name)
        return None

    def reload_extensions(self) -> None:
        """Reload extensions (useful for development/testing)."""
        self._loaded_extensions.clear()
        self._extension_callbacks.clear()
        self._registry.discover_extensions(force=True)
        self._load_extensions()

    def validate_extensions(self) -> dict:
        """
        Validate all loaded extensions.

        Returns:
            Dictionary mapping extension names to validation results
        """
        results = {}
        for ext_name in self._loaded_extensions:
            try:
                instance = self._registry.get_extension_instance(ext_name)
                if instance and hasattr(instance, "validate_dependencies"):
                    results[ext_name] = instance.validate_dependencies()
                else:
                    results[ext_name] = True  # Assume valid if no validation method
            except Exception as e:
                results[ext_name] = False
                logger.warning(f"Extension validation failed for {ext_name}: {e}")

        return results
