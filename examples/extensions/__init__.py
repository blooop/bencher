"""
Example extensions for the Bencher result system.

This package demonstrates how to create and use third-party extensions.
"""

# Import extensions to trigger registration
from . import example_plotly_extension

__all__ = ["example_plotly_extension"]
