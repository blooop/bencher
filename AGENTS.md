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

## Ralph Orchestrator

This repo supports [ralph-orchestrator](https://github.com/blooop/ralph) for autonomous multi-step agent workflows.

### How It Works
- **`ralph.yml`**: Configuration file in the repo root. Defines the event loop, backend (`claude`), hats (agent roles), completion promise, and iteration limits.
- **`PROMPT.md`**: The task prompt file. Ralph reads this to know what to do. Write your full task here.
- **`/specs/`**: Default output directory for research/analysis results (configured via `core.specs_dir` in `ralph.yml`).
- **`.ralph/`**: Runtime directory (agent scratchpad, logs, lock files). Gitignored.

### Writing a Ralph Prompt (`PROMPT.md`)

When creating a `PROMPT.md` for ralph:

1. **Start with a clear task title** as an H1 heading (e.g., `# Task: Analyze Authentication Flow`).
2. **Provide context** about the codebase/area being targeted so the agent can orient quickly.
3. **Break the work into numbered steps**, each with:
   - A specific action (read, analyze, document, etc.)
   - Which files/directories to examine
   - An explicit output file path (e.g., `→ write /specs/01_overview.md`)
4. **Specify output format expectations**: Mermaid diagrams, tables, file path + line number references, etc.
5. **Include rules/constraints**: e.g., "Do NOT modify source code", "Include line numbers for all references".
6. **End with the completion promise** that matches `ralph.yml` (e.g., `RESEARCH_COMPLETE`). The agent outputs this string when done.

### Useful Presets

Initialize `ralph.yml` from a preset: `ralph init --preset <name> [--force]`

| Preset | Use Case |
|--------|----------|
| `research` | Codebase analysis, architecture review, read-only exploration |
| `spec-driven` | Write specs first, then implement |
| `code-assist` | TDD implementation from specs or descriptions |
| `feature` | Feature development with integrated review |
| `bugfix` | Bug reproduction, fix, and verification |
| `refactor` | Code refactoring workflows |
| `docs` | Documentation generation |
| `gap-analysis` | Gap analysis and planning |

List all presets: `ralph init --list-presets`

### Running Ralph

```bash
ralph clean                        # Clean stale artifacts from previous runs
ralph preflight                    # Validate config and environment
ralph run --autonomous             # Run headless/autonomous (for CI or background use)
ralph run                          # Run with TUI observation mode
```

**Important**: Ralph spawns `claude` CLI as a subprocess. It cannot run from inside an existing Claude Code session (nested sessions are blocked). Run `ralph` from a **separate terminal**, not from within Claude Code.

### Key Config Options (`ralph.yml`)

```yaml
event_loop:
  prompt_file: "PROMPT.md"           # Task prompt file
  completion_promise: "RESEARCH_COMPLETE"  # String agent outputs when done
  max_iterations: 30                 # Max agent loop iterations
  max_runtime_seconds: 3600          # Timeout

cli:
  backend: "claude"                  # Agent backend

core:
  specs_dir: "./specs/"              # Output directory for specs
```
