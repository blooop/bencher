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
To test a specific example: `pixi run python bencher/example/example_simple_float.py`

### Important
- **ALWAYS use the pixi environment for every command.** Never run raw `python`, `pytest`, `ruff`, or any other tool directly — always prefix with `pixi run` (e.g. `pixi run python ...`, `pixi run pytest ...`). This ensures the correct dependencies and environment are used.

### Updating Examples & Docs
1. Add or modify the example implementation under `bencher/example/`.
2. Register the example in `bencher/example/meta/generate_examples.py` so the documentation generator emits a notebook (pick an appropriate gallery subdirectory).
3. Run `pixi run generate-docs` to regenerate gallery notebooks.
4. Update relevant user docs (for instance `docs/intro.md` or gallery sections) to mention the new example.
5. Make sure conf.py includes the docs that are added
6. Execute `pixi run ci` before committing to ensure formatting, linting, and tests all pass.

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
3. Bench calculates the Cartesian product of all parameter combinations
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

### Generated Example Naming Convention

All auto-generated examples live under `bencher/example/generated/`. Each filename must
be **globally unique** across the entire generated tree — no two files may share a basename
even if they are in different subdirectories. This is required because the documentation
build uses filenames as RST page stems and thumbnail identifiers.

**Pattern:** `{section}_{descriptive_dimensions}.py`

Every filename starts with a short **section prefix** that identifies which generator
produced it, followed by all varying dimensions encoded in the name. The section prefixes
are:

| Section Prefix | Output Directory | Varying Dimensions |
|---|---|---|
| `sweep_` | `{N}_float/{variant}/` | float count, cat count, variant |
| `plot_` | `plot_types/` | plot type |
| `bool_plot_` | `bool_plot_types/` | plot type |
| `result_` | `result_types/result_{type}/` | result type, input dims |
| `composable_` | `composable_containers/` | backend, compose type |
| `sampling_` | `sampling/` | strategy |
| `stats_` | `statistics/` | variant |
| `const_vars_` | `const_vars/` | example |
| `optim_` | `optimization*/` | objectives, dims, over_time |
| `advanced_` | `advanced/` | example |
| `workflow_` | `workflows/` | example |
| `perf_` | `performance/` | variant |
| `regression_` | `regression/` | variant |
| `yaml_` | `yaml/` | format |
| `publish_` | `publishing/` | example |
| `rerun_` | `rerun/` | example |
| `agg_` | `aggregation/` | aggregation form, agg_fn |

**Rules for adding new generators:**
1. Pick a short, unique section prefix that does not collide with existing prefixes.
2. Encode **every** varying dimension in the filename — never rely on the folder path alone.
3. The Python function inside the generated file must start with `example_` (the test
   harness and doc builder use this prefix for discovery).
4. Register the generator in `generate_examples.py:generate_python_files()` and add
   corresponding entries to `SECTION_GROUPS` for gallery placement.
