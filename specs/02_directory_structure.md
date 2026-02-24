# 02 - Directory Structure

> The full file tree is best discovered via `glob`/`find`. This document captures the **organizational principles** that aren't obvious from file names alone.

## High-Level Layout

```
bencher/
├── *.py                    # Core framework (~19 files): orchestration, config, execution, caching
├── variables/              # Parameter sweep and result variable definitions (7 files)
├── results/                # Result containers and visualization classes (29 files)
│   ├── holoview_results/   #   HoloViews-based interactive plots
│   │   └── distribution_result/  # Statistical distribution visualizations
│   └── composable_container/     # Multi-result composition framework
├── plotting/               # Plot configuration and type matching (3 files)
└── example/                # Comprehensive examples (~120 files)
    ├── inputs_0D/ through inputs_3_float/  # Organized by dimensionality
    ├── meta/               # Meta-example generators and doc generation
    ├── optuna/             # Optimization examples
    ├── experimental/       # WIP examples
    └── shelved/            # Archived examples
```

## Organization Principles

1. **Core root files by architectural role**: orchestration (`bencher.py`), configuration (`bench_cfg.py`), execution (`job.py`, `sweep_executor.py`, `worker_*.py`), reporting (`bench_report.py`), integration (`optuna_conversions.py`, `utils_rerun.py`).

2. **Variables by concern**: inputs (sweep parameter types) vs results (output variable types) vs time (temporal variables) vs base framework (`parametrised_sweep.py`, `sweep_base.py`).

3. **Results by visualization backend**: HoloViews plots, video results, composable containers, statistical distributions.

4. **Examples by input dimensionality**: `inputs_0D` through `inputs_3_float`. Naming convention `example_{N}_float_{M}_cat_in_{K}_out.py` encodes the input/output configuration.

## Key Entry Points

| Purpose | File |
|---------|------|
| Main orchestrator | `bencher/bencher.py` — `Bench` class |
| User-facing base class | `bencher/variables/parametrised_sweep.py` — `ParametrizedSweep` |
| Multi-run manager | `bencher/bench_runner.py` — `BenchRunner` |
| Public API exports | `bencher/__init__.py` |
| Recommended starting example | `bencher/example/example_simple_float.py` |
