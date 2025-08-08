# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

The project uses Pixi for package management and task automation. Key commands:

### Development Tasks
- `pixi run ci` - Run complete CI pipeline (format, lint, test with coverage)
- `pixi run test` - Run pytest test suite
- `pixi run format` - Format code with ruff
- `pixi run lint` - Run ruff linting and pylint
- `pixi run coverage` - Run tests with coverage reporting
- `pixi run generate-docs` - Generate documentation from examples
- `pixi run demo` - Run demo example (example_image.py)

### AI Agent Integration
- `pixi run agent-iterate` - Full CI cycle for AI agents (includes docs, tests, commits, and fixes)

### Testing Individual Examples
To test a specific example: `python bencher/example/example_simple_float.py`

## Code Architecture

Bencher is a benchmarking framework built around these core concepts:

### Core Components
- **Bench**: Main benchmarking class that orchestrates parameter sweeps and result collection
- **BenchRunner**: Higher-level interface for managing multiple benchmark runs
- **BenchCfg/BenchRunCfg**: Configuration classes for benchmark setup and execution
- **ParametrizedSweep**: Base class for defining parameter sweep configurations

### Parameter System
- Uses the `param` library for parameter definitions with metadata
- **Sweep Classes**: `IntSweep`, `FloatSweep`, `StringSweep`, `EnumSweep`, `BoolSweep`
- Parameters define search spaces with bounds and sampling strategies
- Results stored in N-dimensional xarray structures

### Results System
- **BenchResult**: Container for benchmark results and visualizations
- **HoloviewResult**: Base class for interactive plots (scatter, line, heatmap, etc.)
- **ComposableContainer**: Framework for combining multiple result types
- **Video/Image Results**: Support for multimedia outputs
- Results automatically cached using diskcache based on parameter hashes

### Data Flow
1. Define parameter sweep configuration class inheriting from ParametrizedSweep
2. Implement benchmark function that takes config instance, returns metrics dict
3. Bench calculates cartesian product of all parameter combinations
4. Each combination executed (with caching), results stored in N-D tensor
5. Automatic plot type deduction based on parameter/result types
6. Results cached persistently for reuse

### Key Directories
- `bencher/` - Main package source
- `bencher/example/` - Comprehensive examples organized by input dimensions
- `bencher/variables/` - Parameter sweep and result variable definitions
- `bencher/results/` - Result containers and visualization classes
- `test/` - Test suite

### Configuration Files
- `pyproject.toml` - Project dependencies and Pixi task definitions
- `ruff.toml` - Code formatting/linting configuration (100 char line length)
- Line length limit: 100 characters (configured in ruff.toml)

### Testing Strategy
- Uses pytest framework
- Coverage reporting with coverage.py
- Examples serve as integration tests
- Meta-generated examples in `bencher/example/meta/`
