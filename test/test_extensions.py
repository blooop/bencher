"""
Tests for the Bencher extension system.
"""

import pytest
from unittest.mock import Mock, patch
import panel as pn

from bencher.extensions import (
    ExtensionMetadata,
    get_registry,
    result_extension,
    DynamicBenchResult,
    reset_registry,
)
from bencher.extensions.extension_interface import ResultExtensionBase
from bencher.bench_cfg import BenchCfg
from bencher.variables.results import ResultVar
from bencher.variables.inputs import FloatSweep


class TestExtensionRegistry:
    """Test the extension registry functionality."""

    def setup_method(self):
        """Reset registry before each test."""
        reset_registry()
        self.registry = get_registry()

    def teardown_method(self):
        """Clean up after each test."""
        reset_registry()

    def test_registry_singleton(self):
        """Test that get_registry returns the same instance."""
        registry1 = get_registry()
        registry2 = get_registry()
        assert registry1 is registry2

    def test_register_extension(self):
        """Test registering an extension."""

        class TestExtension(ResultExtensionBase):
            metadata = ExtensionMetadata(name="test_ext", description="Test extension")

            def to_plot(self, **kwargs):
                return pn.pane.Markdown("Test plot")

        self.registry.register(TestExtension)

        # Check extension is registered
        assert "test_ext" in self.registry.list_extension_names()
        assert self.registry.get_extension("test_ext") is TestExtension

    def test_unregister_extension(self):
        """Test unregistering an extension."""

        class TestExtension(ResultExtensionBase):
            metadata = ExtensionMetadata(name="test_ext")

            def to_plot(self, **kwargs):
                return None

        # Register then unregister
        self.registry.register(TestExtension)
        assert "test_ext" in self.registry.list_extension_names()

        self.registry.unregister("test_ext")
        assert "test_ext" not in self.registry.list_extension_names()
        assert self.registry.get_extension("test_ext") is None

    def test_extension_instance_creation(self):
        """Test creating extension instances."""

        class TestExtension(ResultExtensionBase):
            metadata = ExtensionMetadata(name="test_ext")

            def __init__(self, bench_cfg=None):
                super().__init__(bench_cfg)
                self.initialized = True

            def to_plot(self, **kwargs):
                return pn.pane.Markdown("Test")

        self.registry.register(TestExtension)

        # Create instance
        mock_cfg = Mock()
        instance = self.registry.get_extension_instance("test_ext", mock_cfg)

        assert instance is not None
        assert hasattr(instance, "initialized")
        assert instance.initialized is True


class TestExtensionDecorator:
    """Test the extension decorator."""

    def setup_method(self):
        reset_registry()

    def teardown_method(self):
        reset_registry()

    def test_result_extension_decorator(self):
        """Test the @result_extension decorator."""

        @result_extension(
            name="decorated_ext",
            version="2.0.0",
            description="Decorated test extension",
            dependencies=["test_lib>=1.0"],
            auto_register=True,
        )
        class DecoratedExtension(ResultExtensionBase):
            def to_plot(self, **kwargs):
                return pn.pane.Markdown("Decorated plot")

        # Check metadata was added
        assert hasattr(DecoratedExtension, "metadata")
        assert DecoratedExtension.metadata.name == "decorated_ext"
        assert DecoratedExtension.metadata.version == "2.0.0"
        assert DecoratedExtension.metadata.description == "Decorated test extension"
        assert "test_lib>=1.0" in DecoratedExtension.metadata.dependencies

        # Check auto-registration worked
        registry = get_registry()
        assert "decorated_ext" in registry.list_extension_names()


class TestDynamicBenchResult:
    """Test the dynamic result class."""

    def setup_method(self):
        reset_registry()
        self.registry = get_registry()

        # Create mock bench config
        self.bench_cfg = Mock(spec=BenchCfg)
        self.bench_cfg.result_vars = [Mock(spec=ResultVar)]
        self.bench_cfg.input_vars = [Mock(spec=FloatSweep)]

    def teardown_method(self):
        reset_registry()

    def test_dynamic_result_initialization(self):
        """Test DynamicBenchResult initialization."""
        dynamic_result = DynamicBenchResult(self.bench_cfg)

        assert dynamic_result.bench_cfg is self.bench_cfg
        assert hasattr(dynamic_result, "_loaded_extensions")
        assert hasattr(dynamic_result, "_extension_callbacks")

    def test_extension_loading(self):
        """Test extension loading in DynamicBenchResult."""

        # Register a test extension
        class TestExtension(ResultExtensionBase):
            metadata = ExtensionMetadata(name="test_ext")

            def can_handle(self, bench_cfg):
                return True  # Always can handle

            def to_plot(self, **kwargs):
                return pn.pane.Markdown("Test extension plot")

            def get_plot_callbacks(self):
                return [self.to_plot]

        self.registry.register(TestExtension)

        # Create dynamic result
        dynamic_result = DynamicBenchResult(self.bench_cfg)

        # Check extension was loaded
        assert "test_ext" in dynamic_result.list_loaded_extensions()

        # Check callbacks were added
        callbacks = dynamic_result.get_extension_plot_callbacks()
        assert len(callbacks) > 0

    def test_extension_filtering(self):
        """Test that extensions are filtered based on can_handle."""

        # Register extensions with different can_handle logic
        class AlwaysHandleExtension(ResultExtensionBase):
            metadata = ExtensionMetadata(name="always_handle")

            def can_handle(self, bench_cfg):
                return True

            def to_plot(self, **kwargs):
                return pn.pane.Markdown("Always handles")

        class NeverHandleExtension(ResultExtensionBase):
            metadata = ExtensionMetadata(name="never_handle")

            def can_handle(self, bench_cfg):
                return False

            def to_plot(self, **kwargs):
                return pn.pane.Markdown("Never handles")

        self.registry.register(AlwaysHandleExtension)
        self.registry.register(NeverHandleExtension)

        # Create dynamic result
        dynamic_result = DynamicBenchResult(self.bench_cfg)

        # Check only the "always handle" extension was loaded
        loaded = dynamic_result.list_loaded_extensions()
        assert "always_handle" in loaded
        assert "never_handle" not in loaded


class TestExtensionInterface:
    """Test extension interface compliance."""

    def test_extension_base_class(self):
        """Test ResultExtensionBase provides required functionality."""

        class TestExtension(ResultExtensionBase):
            metadata = ExtensionMetadata(name="base_test")

            def to_plot(self, **kwargs):
                return pn.pane.Markdown("Base test plot")

        mock_cfg = Mock(spec=BenchCfg)
        mock_cfg.result_vars = []

        extension = TestExtension(mock_cfg)

        # Test default implementations
        extension.setup()
        assert extension._initialized is True

        extension.teardown()
        assert extension._initialized is False

        # Test callback retrieval
        callbacks = extension.get_plot_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == extension.to_plot

        # Test dependency validation (should pass with no dependencies)
        assert extension.validate_dependencies() is True


class TestExtensionIntegration:
    """Integration tests for the extension system."""

    def setup_method(self):
        reset_registry()

    def teardown_method(self):
        reset_registry()

    @patch("importlib.metadata.entry_points")
    def test_entry_point_discovery(self, mock_entry_points):
        """Test extension discovery via entry points."""
        # Mock entry points
        mock_entry_point = Mock()
        mock_entry_point.name = "test_extension"
        mock_entry_point.load.return_value = Mock()

        # Handle both old and new entry_points API
        mock_eps = Mock()
        mock_eps.select.return_value = [mock_entry_point]
        mock_entry_points.return_value = mock_eps

        registry = get_registry()
        registry.discover_extensions()

        # Verify discovery was attempted
        mock_entry_points.assert_called_once()

    def test_extension_error_handling(self):
        """Test error handling in extension system."""

        class BrokenExtension(ResultExtensionBase):
            metadata = ExtensionMetadata(name="broken_ext")

            def to_plot(self, **kwargs):
                raise RuntimeError("Extension is broken")

        registry = get_registry()
        registry.register(BrokenExtension)

        mock_cfg = Mock(spec=BenchCfg)
        mock_cfg.result_vars = []
        mock_cfg.input_vars = []

        # DynamicBenchResult should handle broken extensions gracefully
        dynamic_result = DynamicBenchResult(mock_cfg)

        # Should not raise an exception despite broken extension
        assert isinstance(dynamic_result, DynamicBenchResult)


if __name__ == "__main__":
    pytest.main([__file__])
