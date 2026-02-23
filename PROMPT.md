# Task: Full Architecture Mapping of Bencher Package

Map the complete software architecture of the `bencher` Python package (published as `holobench`) and write structured specification documents to `/specs/`.

## Context

This is a benchmarking framework built on `param`, `xarray`, `holoviews`, and `panel`. The main package source is in `bencher/`. Configuration is in `pyproject.toml` and `ruff.toml`. Read `CLAUDE.md` for project conventions.

## Instructions

Follow the steps below **in order**. For each step, read the relevant source files thoroughly, then write the output file. After writing each file, move to the next step.

**Important rules:**
- Read actual source code for every claim. Do not guess.
- Include file paths and line numbers for all class/function references.
- Use Mermaid syntax for all diagrams.
- Flag ambiguities with `> **NOTE:**` callouts.
- Do NOT modify any source code. Only write files under `/specs/`.

---

### Step 1: Package Overview → write `/specs/01_overview.md`

Read `pyproject.toml`, `CLAUDE.md`, `README.md`.

Document:
- Package name, version, Python version constraints
- One-paragraph description of purpose
- Full dependency list grouped by function (visualization, caching, optimization, data, etc.)
- Build system details (hatchling)
- Development toolchain (pixi tasks, ruff, pylint, pytest, coverage)

---

### Step 2: Directory Structure → write `/specs/02_directory_structure.md`

Walk `bencher/` and list every directory and `.py` file with a one-line description.

Document:
- Full annotated tree using indented markdown
- Organization principles (by dimension, by result type, etc.)

---

### Step 3: Core Data Flow → write `/specs/03_data_flow.md`

Trace end-to-end: user defines `ParametrizedSweep` subclass → `Bench.__call__` → parameter expansion → job creation → execution (with caching) → result collection → xarray dataset → plot deduction → rendering.

Document:
- Numbered step-by-step flow with class, method, file path for each step
- Mermaid sequence or flow diagram
- Key decision points (cache hit/miss, plot type selection)

---

### Step 4: Class Hierarchy → write `/specs/04_class_hierarchy.md`

Enumerate every class in `bencher/` (exclude `bencher/example/`).

Document:
- Classes grouped by subsystem (core, config, variables, results, plotting, utilities)
- Inheritance chains with file paths
- Mermaid class diagram
- Protocol classes (`BenchableV1`, `BenchableV2`) documented separately
- Special attention to `BenchResult` multiple inheritance

---

### Step 5: Parameter System → write `/specs/05_parameter_system.md`

Read all files in `bencher/variables/`.

Document:
- `SweepBase` and all sweep types (`IntSweep`, `FloatSweep`, `BoolSweep`, `StringSweep`, `EnumSweep`, `YamlSweep`)
- `ParametrizedSweep`: parameter discovery, sweep combination building, hash-based caching
- All result types (`ResultVar`, `ResultBool`, `ResultVec`, `ResultHmap`, `ResultPath`, `ResultVideo`, `ResultImage`, `ResultString`, `ResultContainer`, `ResultReference`, `ResultDataSet`, `ResultVolume`)
- Time variables (`TimeSnapshot`, `TimeEvent`)
- Table: parameter type → compatible result types → default plot type

---

### Step 6: Results & Visualization → write `/specs/06_results_system.md`

Read all files in `bencher/results/` and `bencher/plotting/`.

Document:
- `BenchResult` inheritance diagram (Mermaid)
- Each visualization type: data shape, output format
- `ComposableContainer` variants (Panel, DataFrame, Video)
- `PlotFilter` and plot matching logic
- `ReduceType` enum and its effects
- Plot deduction algorithm

---

### Step 7: Caching Architecture → write `/specs/07_caching.md`

Read `bencher/caching.py`, `bencher/job.py`, caching code in `bencher/bencher.py`.

Document:
- Each caching layer: what it caches, key structure, storage backend
- Cache hit/miss flow
- `WorkerJob` caching metadata
- Configuration options

---

### Step 8: Execution Model → write `/specs/08_execution_model.md`

Read `bencher/sweep_executor.py`, `bencher/job.py`, `bencher/worker_job.py`, `bencher/worker_manager.py`.

Document:
- Job lifecycle: creation → scheduling → execution → result capture
- `Executors` enum and executor types
- `WorkerManager` function wrapping
- `SweepExecutor` sweep expansion
- `ResultCollector` and xarray assembly
- `SampleOrder` effect on execution

---

### Step 9: Configuration System → write `/specs/09_configuration.md`

Read `bencher/bench_cfg.py` thoroughly.

Document:
- `BenchPlotSrvCfg` → `BenchRunCfg` → `BenchCfg` inheritance chain
- Every parameter with description, default, and effect
- `DimsCfg` role in dimensionality tracking

---

### Step 10: Integrations → write `/specs/10_integrations.md`

Document:
- Optuna integration (`optuna_conversions.py`, `optuna_result.py`)
- Rerun integration (`utils_rerun.py`)
- Panel/HoloViews server (`bench_plot_server.py`, `flask_server.py`)
- Report generation & GitHub Pages (`bench_report.py`)
- Video generation (`video_writer.py`)

---

### Step 11: Module Dependency Graph → write `/specs/11_dependency_graph.md`

For every `.py` in `bencher/` (excluding examples), extract intra-package imports.

Document:
- Mermaid dependency diagram
- Layered view: foundation → mid-tier → top-level
- Circular dependency analysis (especially `factories.py`)
- External dependency usage map

---

### Step 12: Examples & Doc Generation → write `/specs/12_examples_and_docs.md`

Read `bencher/example/meta/generate_examples.py` and example structure.

Document:
- Example registration process
- Doc generation pipeline
- Gallery organization by input dimensionality
- How to add a new example

---

### Step 13: Architecture Summary → write `/specs/13_architecture_summary.md`

Synthesize all findings.

Document:
- High-level Mermaid architecture diagram showing all subsystems
- Key patterns (multiple inheritance, protocols, factories, delegation, caching)
- Design trade-offs and rationale
- Complexity areas / technical debt
- Suggested reading order for new developers

---

### Step 14: Index → write `/specs/README.md`

Create navigable index:
- Table of contents linking all 13 spec documents
- Brief description of each
- Suggested reading order
- Package version analyzed

---

## Completion

After writing all 14 files, verify every `.py` file in `bencher/` (excluding `bencher/example/`) is referenced in at least one spec document. Then output:

RESEARCH_COMPLETE
