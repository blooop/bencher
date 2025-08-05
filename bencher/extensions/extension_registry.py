"""
Extension registry for managing and discovering result extensions.
"""

from __future__ import annotations
import logging
import importlib
import importlib.metadata
from typing import Dict, List, Optional, Type, Callable
from threading import Lock

from .extension_interface import (
    ResultExtension,
    ExtensionMetadata,
    ExtensionValidationError,
)

logger = logging.getLogger(__name__)


class ResultExtensionRegistry:
    """Central registry for managing result extensions."""

    def __init__(self):
        self._extensions: Dict[str, Type[ResultExtension]] = {}
        self._instances: Dict[str, ResultExtension] = {}
        self._metadata: Dict[str, ExtensionMetadata] = {}
        self._lock = None  # Initialize lazily to avoid pickle issues
        self._auto_discover = True
        self._discovered = False

    @property
    def _get_lock(self) -> Lock:
        """Get or create the thread lock lazily to avoid pickle issues."""
        if self._lock is None:
            self._lock = Lock()
        return self._lock

    def register(
        self, extension_class: Type[ResultExtension], metadata: ExtensionMetadata = None
    ) -> None:
        """
        Register a result extension class.

        Args:
            extension_class: The extension class to register
            metadata: Optional metadata (will be extracted from class if not provided)

        Raises:
            ExtensionValidationError: If extension fails validation
        """
        with self._get_lock:
            if metadata is None:
                if hasattr(extension_class, "metadata"):
                    metadata = extension_class.metadata
                else:
                    # Create default metadata
                    metadata = ExtensionMetadata(
                        name=extension_class.__name__, description=extension_class.__doc__ or ""
                    )

            # Validate extension
            self._validate_extension(extension_class, metadata)

            name = metadata.name
            if name in self._extensions:
                logger.warning(f"Extension '{name}' already registered, overriding")

            self._extensions[name] = extension_class
            self._metadata[name] = metadata

            logger.info(f"Registered extension: {name} v{metadata.version}")

    def unregister(self, name: str) -> None:
        """
        Unregister an extension.

        Args:
            name: Name of the extension to unregister
        """
        with self._get_lock:
            if name in self._extensions:
                # Clean up instance if exists
                if name in self._instances:
                    instance = self._instances[name]
                    if hasattr(instance, "teardown"):
                        try:
                            instance.teardown()
                        except Exception as e:
                            logger.warning(f"Error during teardown of {name}: {e}")
                    del self._instances[name]

                del self._extensions[name]
                del self._metadata[name]
                logger.info(f"Unregistered extension: {name}")
            else:
                logger.warning(f"Extension '{name}' not found for unregistration")

    def get_extension(self, name: str) -> Optional[Type[ResultExtension]]:
        """
        Get an extension class by name.

        Args:
            name: Name of the extension

        Returns:
            Extension class or None if not found
        """
        self._ensure_discovered()
        return self._extensions.get(name)

    def get_extension_instance(self, name: str, *args, **kwargs) -> Optional[ResultExtension]:
        """
        Get or create an extension instance.

        Args:
            name: Name of the extension
            *args, **kwargs: Arguments to pass to extension constructor

        Returns:
            Extension instance or None if not found
        """
        with self._get_lock:
            if name in self._instances:
                return self._instances[name]

            extension_class = self.get_extension(name)
            if extension_class is None:
                return None

            try:
                instance = extension_class(*args, **kwargs)
                if hasattr(instance, "setup"):
                    instance.setup()
                self._instances[name] = instance
                return instance
            except Exception as e:
                logger.error(f"Failed to create instance of {name}: {e}")
                return None

    def list_extensions(self) -> List[ExtensionMetadata]:
        """
        List all registered extensions.

        Returns:
            List of extension metadata
        """
        self._ensure_discovered()
        return list(self._metadata.values())

    def list_extension_names(self) -> List[str]:
        """
        List names of all registered extensions.

        Returns:
            List of extension names
        """
        self._ensure_discovered()
        return list(self._extensions.keys())

    def discover_extensions(self, force: bool = False) -> None:
        """
        Discover extensions using entry points.

        Args:
            force: Force rediscovery even if already discovered
        """
        if self._discovered and not force:
            return

        logger.info("Discovering result extensions...")
        discovered_count = 0

        try:
            # Discover using entry points (setuptools/pip installed packages)
            entry_points = importlib.metadata.entry_points()

            # Handle both old and new entry_points API
            if hasattr(entry_points, "select"):
                # New API (Python 3.10+)
                extension_points = entry_points.select(group="bencher.result_extensions")
            else:
                # Old API
                extension_points = entry_points.get("bencher.result_extensions", [])

            for entry_point in extension_points:
                try:
                    extension_class = entry_point.load()
                    self.register(extension_class)
                    discovered_count += 1
                except Exception as e:
                    logger.warning(f"Failed to load extension {entry_point.name}: {e}")

        except Exception as e:
            logger.warning(f"Error during extension discovery: {e}")

        self._discovered = True
        logger.info(f"Extension discovery complete. Found {discovered_count} extensions.")

    def get_applicable_extensions(self, bench_cfg, **kwargs) -> List[str]:
        """
        Get list of extension names that can handle the given configuration.

        Args:
            bench_cfg: Benchmark configuration
            **kwargs: Additional filtering criteria

        Returns:
            List of applicable extension names
        """
        self._ensure_discovered()
        applicable = []

        for name, extension_class in self._extensions.items():
            try:
                # Check if we can create an instance
                instance = self.get_extension_instance(name, bench_cfg)
                if instance and instance.can_handle(bench_cfg):
                    applicable.append(name)
            except Exception as e:
                logger.debug(f"Extension {name} cannot handle configuration: {e}")

        return applicable

    def get_plot_callbacks(self, bench_cfg, extension_names: List[str] = None) -> List[Callable]:
        """
        Get plot callbacks from applicable extensions.

        Args:
            bench_cfg: Benchmark configuration
            extension_names: Specific extensions to use (None for all applicable)

        Returns:
            List of plot callback functions
        """
        if extension_names is None:
            extension_names = self.get_applicable_extensions(bench_cfg)

        callbacks = []
        for name in extension_names:
            instance = self.get_extension_instance(name, bench_cfg)
            if instance:
                try:
                    callbacks.extend(instance.get_plot_callbacks())
                except Exception as e:
                    logger.warning(f"Error getting callbacks from {name}: {e}")

        return callbacks

    def clear(self) -> None:
        """Clear all registered extensions."""
        with self._get_lock:
            # Clean up instances
            for name, instance in self._instances.items():
                if hasattr(instance, "teardown"):
                    try:
                        instance.teardown()
                    except Exception:
                        pass

            self._extensions.clear()
            self._instances.clear()
            self._metadata.clear()
            self._discovered = False

    def set_auto_discover(self, enabled: bool) -> None:
        """
        Enable or disable automatic extension discovery.

        Args:
            enabled: Whether to enable auto-discovery
        """
        self._auto_discover = enabled

    def _ensure_discovered(self) -> None:
        """Ensure extensions have been discovered if auto-discovery is enabled."""
        if self._auto_discover and not self._discovered:
            self.discover_extensions()

    def _validate_extension(
        self, extension_class: Type[ResultExtension], metadata: ExtensionMetadata
    ) -> None:
        """
        Validate that an extension class implements the required interface.

        Args:
            extension_class: Extension class to validate
            metadata: Extension metadata

        Raises:
            ExtensionValidationError: If validation fails
        """
        required_methods = ["can_handle", "to_plot", "get_plot_callbacks"]

        for method_name in required_methods:
            if not hasattr(extension_class, method_name):
                raise ExtensionValidationError(
                    f"Extension {metadata.name} missing required method: {method_name}"
                )

        # Validate metadata
        if not metadata.name:
            raise ExtensionValidationError("Extension must have a name")


# Global registry instance
_global_registry = None
_registry_lock = Lock()


def get_registry() -> ResultExtensionRegistry:
    """
    Get the global extension registry instance.

    Returns:
        Global ResultExtensionRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        with _registry_lock:
            if _global_registry is None:
                _global_registry = ResultExtensionRegistry()
    return _global_registry


def reset_registry() -> None:
    """Reset the global registry (primarily for testing)."""
    global _global_registry
    with _registry_lock:
        if _global_registry:
            _global_registry.clear()
        _global_registry = None
