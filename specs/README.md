# Bencher Architecture Specifications

**Package**: `holobench` v1.61.0

## Table of Contents

| # | Document | Description |
|---|----------|-------------|
| 01 | [Package Overview](01_overview.md) | Package identity, dependencies, purpose |
| 02 | [Directory Structure](02_directory_structure.md) | High-level layout and organization principles |
| 03 | [Core Data Flow & Execution](03_data_flow.md) | End-to-end trace from parameter definition to rendered plot, executors, worker management |
| 04 | [Class Hierarchy](04_class_hierarchy.md) | Key inheritance patterns (especially BenchResult MI) |
| 05 | [Parameter System](05_parameter_system.md) | Sweep types, result types, ParametrizedSweep framework |
| 06 | [Results & Visualization](06_results_system.md) | Plot types, PlotFilter matching, plot deduction algorithm |
| 07 | [Caching Architecture](07_caching.md) | Two-tier diskcache system: sample cache and benchmark cache |
| 09 | [Configuration System](09_configuration.md) | BenchPlotSrvCfg → BenchRunCfg → BenchCfg hierarchy |
| 10 | [Integrations](10_integrations.md) | Optuna, Rerun, Panel server, reports, video generation |
| 11 | [Module Architecture](11_dependency_graph.md) | Layered architecture, circular dependency analysis |
| 12 | [Examples & Doc Generation](12_examples_and_docs.md) | Example registration, gallery organization, how to add examples |
| 13 | [Architecture Summary](13_architecture_summary.md) | High-level patterns, trade-offs, technical debt |

## By Topic

- **"How do I add a new parameter type?"** → [05](05_parameter_system.md), [04](04_class_hierarchy.md)
- **"How does caching work?"** → [07](07_caching.md)
- **"How do I add a new plot type?"** → [06](06_results_system.md), [04](04_class_hierarchy.md)
- **"How do I add a new example?"** → [12](12_examples_and_docs.md)
- **"What is the overall architecture?"** → [13](13_architecture_summary.md), [03](03_data_flow.md)
- **"Where is the code for X?"** → [02](02_directory_structure.md)
