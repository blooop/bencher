# Bencher Result Extension System Specification

## Overview

This specification defines a generic extension system for Bencher result types, enabling third-party packages to add new visualization and processing capabilities without being included in the core repository. The system aims to provide the same capabilities and interface as built-in result types while being easily distributable as separate packages.

## Current System Analysis

### Existing Architecture
- **Multiple Inheritance Pattern**: `BenchResult` inherits from all result types
- **Static Callback Lists**: `default_plot_callbacks()` provides hardcoded plot functions
- **Filter System**: Complex filtering determines plot applicability based on data characteristics
- **Mixin Pattern**: Each result type adds specific functionality via inheritance

### Limitations of Current System
1. **Tight Coupling**: All result types must be known at compile time
2. **Monolithic**: Heavy dependencies (3D rendering, video processing) bundled in core
3. **No Discovery**: Manual registration required for new result types
4. **Extension Complexity**: Requires modifying core inheritance hierarchy

## Goals

### Primary Goals
1. **Modular Architecture**: Enable splitting heavy result types into separate packages
2. **Dynamic Discovery**: Automatically discover and register extensions
3. **Interface Compatibility**: Extensions have same capabilities as built-in results
4. **Third-party Friendly**: Easy to create and distribute extensions
5. **Backward Compatibility**: Existing code continues to work unchanged

### Secondary Goals
1. **Performance**: No significant overhead compared to current system
2. **Type Safety**: Full typing support for extensions
3. **Documentation**: Extensions provide rich metadata and help
4. **Configuration**: User can control which extensions are loaded

## Architecture Design

### Core Components

#### 1. Extension Registry (`ResultExtensionRegistry`)
```python
class ResultExtensionRegistry:
    """Central registry for result extensions."""
    
    def register(self, extension_class: type, metadata: ExtensionMetadata) -> None
    def unregister(self, name: str) -> None
    def get_extension(self, name: str) -> Optional[type]
    def list_extensions(self) -> List[ExtensionMetadata]
    def discover_extensions(self) -> None
```

#### 2. Extension Interface (`ResultExtension`)
```python
class ResultExtension(Protocol):
    """Protocol defining the interface for result extensions."""
    
    @property
    def metadata(self) -> ExtensionMetadata: ...
    def can_handle(self, bench_cfg: BenchCfg) -> bool: ...
    def to_plot(self, **kwargs) -> Optional[pn.panel]: ...
    def get_plot_callbacks(self) -> List[Callable]: ...
```

#### 3. Extension Metadata (`ExtensionMetadata`)
```python
@dataclass
class ExtensionMetadata:
    name: str
    version: str
    description: str
    author: str
    dependencies: List[str]
    result_types: List[str]
    plot_types: List[str]
    target_dimensions: List[int]
    filter_criteria: PlotFilter
```

#### 4. Dynamic Result Factory (`DynamicBenchResult`)
```python
class DynamicBenchResult(BenchResultBase):
    """Dynamic result class that composes extensions at runtime."""
    
    def __init__(self, bench_cfg: BenchCfg):
        self._extensions = []
        self._load_extensions(bench_cfg)
    
    def to_plot(self, **kwargs) -> Optional[pn.panel]:
        # Delegate to appropriate extension
    
    def get_all_plot_callbacks(self) -> List[Callable]:
        # Aggregate callbacks from all extensions
```

### Extension Discovery

#### 1. Entry Points (setuptools)
```python
# setup.py or pyproject.toml
entry_points = {
    'bencher.result_extensions': [
        'plotly_3d = bencher_plotly:Plotly3DExtension',
        'vtk_volume = bencher_vtk:VTKVolumeExtension',
    ]
}
```

#### 2. Decorator Registration
```python
@result_extension(
    name="plotly_3d",
    description="3D plotting with Plotly",
    dependencies=["plotly>=5.0"],
    result_types=["Volume", "Surface"],
    target_dimensions=[3]
)
class Plotly3DExtension(ResultExtension):
    pass
```

#### 3. Configuration-based Loading
```yaml
# bencher_config.yaml
extensions:
  enabled:
    - plotly_3d
    - vtk_volume
  disabled:
    - heavy_extension
  auto_discover: true
```

## Public Interface

### Extension Developer Interface

#### Base Extension Class
```python
from bencher.extensions import ResultExtension, result_extension, ExtensionMetadata

@result_extension(
    name="my_extension",
    description="Custom visualization extension",
    dependencies=["custom_lib>=1.0"],
    result_types=["Custom"],
    plot_types=["custom_plot", "interactive_widget"],
    target_dimensions=[2, 3]
)
class MyResultExtension(ResultExtension):
    def can_handle(self, bench_cfg: BenchCfg) -> bool:
        # Check if this extension can handle the data
        return any(isinstance(rv, CustomResultVar) for rv in bench_cfg.result_vars)
    
    def to_plot(self, **kwargs) -> Optional[pn.panel]:
        # Main plotting method
        return self.to_custom_plot(**kwargs)
    
    def to_custom_plot(self, **kwargs) -> Optional[pn.panel]:
        # Custom plotting implementation
        pass
    
    def get_plot_callbacks(self) -> List[Callable]:
        # Return list of available plot methods
        return [self.to_custom_plot, self.to_interactive_widget]
```

#### Packaging and Distribution
```python
# pyproject.toml for extension package
[project.entry-points."bencher.result_extensions"]
my_extension = "my_package:MyResultExtension"

[project]
name = "bencher-my-extension"
dependencies = ["holobench", "custom_lib>=1.0"]
```

### End User Interface

#### Automatic Discovery and Loading
```python
# Extensions automatically discovered and loaded
import bencher as bch

# Works the same as before - extensions add capabilities transparently
bench = bch.Bench("my_benchmark", cfg)
results = bench.plot_sweep()  # May use extension plots automatically
```

#### Manual Extension Control
```python
from bencher.extensions import get_registry

# List available extensions
registry = get_registry()
print(registry.list_extensions())

# Load specific extension
registry.load_extension("plotly_3d")

# Configure extension behavior
results.to_plot(prefer_extensions=["plotly_3d"], fallback=True)
```

## Migration Strategy

### Phase 1: Core Infrastructure
1. Implement extension registry and discovery
2. Create base extension interfaces
3. Add dynamic result factory
4. Maintain backward compatibility with existing inheritance

### Phase 2: Extension Conversion
1. Convert heavy result types (VTK, 3D plotting) to extensions
2. Create example third-party extensions
3. Update documentation and examples

### Phase 3: Optimization
1. Remove converted types from core inheritance
2. Optimize extension loading and caching
3. Add configuration and user control features

### Backward Compatibility
```python
# Old code continues to work
class BenchResult(
    # Built-in lightweight results
    BarResult,
    LineResult,
    HeatmapResult,
    # Dynamic extension loading
    DynamicBenchResult,
):
    pass
```

## Implementation Details

### Extension Loading
1. **Lazy Loading**: Extensions loaded only when needed
2. **Dependency Checking**: Verify dependencies before loading
3. **Error Handling**: Graceful fallback when extensions unavailable
4. **Caching**: Cache loaded extensions for performance

### Filter Integration
```python
class ExtensionFilter(PlotFilter):
    """Enhanced filter that considers extension capabilities."""
    
    def matches_extension(self, extension: ResultExtension, bench_cfg: BenchCfg) -> bool:
        # Check if extension can handle the data characteristics
        return (
            extension.can_handle(bench_cfg) and
            self.matches_criteria(extension.metadata.filter_criteria)
        )
```

### Type Safety
```python
# Extensions provide full typing information
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bencher_plotly import Plotly3DExtension

# Runtime extension access with typing
def get_plotly_extension() -> 'Plotly3DExtension':
    return get_registry().get_extension("plotly_3d")
```

## Security Considerations

1. **Code Execution**: Extensions execute arbitrary code - user responsibility
2. **Dependency Management**: Clear dependency declarations required
3. **Sandboxing**: Future consideration for restricted execution environments
4. **Validation**: Extension metadata validation and verification

## Performance Considerations

1. **Import Overhead**: Lazy imports to avoid loading unused extensions
2. **Registration Cost**: Minimize overhead of extension discovery
3. **Memory Usage**: Extensions loaded on-demand, unloaded when not needed
4. **Caching**: Cache extension instances and capabilities

## Testing Strategy

1. **Extension Interface Tests**: Verify all extensions implement protocol correctly
2. **Discovery Tests**: Test various discovery mechanisms
3. **Integration Tests**: Verify extensions work with core system
4. **Mock Extensions**: Test framework extensions for CI/CD
5. **Performance Tests**: Ensure no significant overhead

## Documentation Requirements

1. **Extension Developer Guide**: How to create and distribute extensions
2. **API Reference**: Complete interface documentation
3. **Migration Guide**: How to convert existing result types
4. **User Guide**: How to install and use extensions
5. **Example Extensions**: Reference implementations

## Editor Completion and .pyi Stub Generation

To maximize discoverability and editor autocompletion, Bencher should automatically generate `.pyi` stub files for all extension interfaces and registry methods. This enables IDEs to provide accurate completion for available plot types, extension methods, and options.

### Stub Generation Strategy

1. **Automatic Stub Generation**: During build or extension registration, generate `.pyi` files for all extension classes and registry interfaces.
2. **Extension Registry Stubs**: The registry should expose all discovered extensions and their plot methods in the stub, e.g.:
    ```python
    class ResultExtensionRegistry:
        def get_extension(self, name: str) -> ResultExtension: ...
        def list_extensions(self) -> List[ExtensionMetadata]: ...
        # Autogenerated stubs for each extension:
        def plotly_3d(self) -> Plotly3DExtension: ...
        def vtk_volume(self) -> VTKVolumeExtension: ...
    ```
3. **Extension Class Stubs**: Each extension should have a `.pyi` stub exposing its plot methods and options:
    ```python
    class Plotly3DExtension(ResultExtension):
        def to_plot(self, **kwargs) -> pn.panel: ...
        def to_surface(self, **kwargs) -> pn.panel: ...
        def opts(self, **kwargs) -> pn.panel: ...
    ```
4. **Dynamic Method Exposure**: For dynamic result factories, expose all available plot types as stub methods, e.g. `results.to_plotly_3d()`, `results.to_vtk_volume()`.
5. **Type Hints and Docstrings**: Ensure all stub methods include type hints and docstrings for IDE help.
6. **Stub Update Mechanism**: Stubs should be regenerated whenever extensions are added/removed.

### Example Workflow

1. User installs a new extension package.
2. Bencher discovers the extension and generates/updates the `.pyi` stub.
3. IDE autocompletion now shows new plot types and options via `results.to_<extension>()` and `.opts()`.

### Benefits

- **Discoverability**: Users see all available plot types and options in their editor.
- **Type Safety**: Stubs provide accurate type information for all extension methods.
- **Third-party Support**: Extension authors can provide their own `.pyi` files for richer completion.

This approach ensures Bencher's extension system is as discoverable and user-friendly as HoloViews, with modern editor support for autocompletion and type checking.

This specification provides a foundation for a robust, extensible result system that maintains backward compatibility while enabling modular, third-party extensible architecture similar to HoloViews' approach.