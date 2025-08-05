"""
Bencher Result Extension System

This module provides a plugin architecture for extending Bencher's result visualization
and processing capabilities. Extensions can be distributed as separate packages and
automatically discovered and integrated.
"""

from .extension_interface import ResultExtension, ExtensionMetadata
from .extension_registry import ResultExtensionRegistry, get_registry, reset_registry
from .extension_decorator import result_extension
from .dynamic_result import DynamicBenchResult

__all__ = [
    "ResultExtension",
    "ExtensionMetadata",
    "ResultExtensionRegistry",
    "get_registry",
    "reset_registry",
    "result_extension",
    "DynamicBenchResult",
]
