"""
Decorator for registering result extensions.
"""

from typing import List, Optional, Type, Callable

from .extension_interface import ExtensionMetadata, ResultExtension
from .extension_registry import get_registry


def result_extension(
    name: str,
    version: str = "1.0.0",
    description: str = "",
    author: str = "",
    dependencies: Optional[List[str]] = None,
    result_types: Optional[List[str]] = None,
    plot_types: Optional[List[str]] = None,
    target_dimensions: Optional[List[int]] = None,
    auto_register: bool = True,
) -> Callable[[Type], Type]:
    """
    Decorator to register a class as a result extension.

    Args:
        name: Extension name (must be unique)
        version: Extension version
        description: Extension description
        author: Extension author
        dependencies: List of required dependencies (e.g., ["plotly>=5.0"])
        result_types: List of result variable types this extension handles
        plot_types: List of plot types this extension provides
        target_dimensions: List of target dimensions this extension supports
        auto_register: Whether to automatically register with global registry

    Returns:
        Decorated class with extension metadata

    Example:
        @result_extension(
            name="plotly_3d",
            description="3D plotting with Plotly",
            dependencies=["plotly>=5.0"],
            result_types=["Volume", "Surface"],
            target_dimensions=[3]
        )
        class Plotly3DExtension(ResultExtensionBase):
            def to_plot(self, **kwargs):
                # Implementation here
                pass
    """

    def decorator(cls: Type) -> Type:
        # Create metadata
        metadata = ExtensionMetadata(
            name=name,
            version=version,
            description=description,
            author=author,
            dependencies=dependencies or [],
            result_types=result_types or [],
            plot_types=plot_types or [],
            target_dimensions=target_dimensions or [],
        )

        # Add metadata to class
        cls.metadata = metadata

        # Auto-register if requested
        if auto_register:
            try:
                get_registry().register(cls, metadata)
            except Exception as e:
                # Don't fail class creation if registration fails
                import logging

                logging.warning(f"Failed to auto-register extension {name}: {e}")

        return cls

    return decorator


def register_extension(extension_class: Type[ResultExtension]) -> None:
    """
    Manually register an extension class.

    Args:
        extension_class: Extension class to register

    Example:
        class MyExtension(ResultExtensionBase):
            metadata = ExtensionMetadata(name="my_ext", ...)

        register_extension(MyExtension)
    """
    get_registry().register(extension_class)


def unregister_extension(name: str) -> None:
    """
    Unregister an extension by name.

    Args:
        name: Name of extension to unregister
    """
    get_registry().unregister(name)
