# Bencher Architecture Specifications

**Package**: `holobench` v1.61.0
**Repository**: https://github.com/blooop/bencher
**Analysis Date**: 2026-02-23

## Table of Contents

| # | Document | Description |
|---|----------|-------------|
| 01 | [Package Overview](01_overview.md) | Package identity, dependencies, build system, development toolchain |
| 02 | [Directory Structure](02_directory_structure.md) | Full annotated file tree with organization principles |
| 03 | [Core Data Flow](03_data_flow.md) | End-to-end trace from parameter definition to rendered plot |
| 04 | [Class Hierarchy](04_class_hierarchy.md) | All classes grouped by subsystem with inheritance chains |
| 05 | [Parameter System](05_parameter_system.md) | Sweep types, result types, ParametrizedSweep framework |
| 06 | [Results & Visualization](06_results_system.md) | BenchResult inheritance, plot types, composable containers |
| 07 | [Caching Architecture](07_caching.md) | Two-tier diskcache system: sample cache and benchmark cache |
| 08 | [Execution Model](08_execution_model.md) | Job lifecycle, executors, worker management, result collection |
| 09 | [Configuration System](09_configuration.md) | BenchPlotSrvCfg → BenchRunCfg → BenchCfg hierarchy |
| 10 | [Integrations](10_integrations.md) | Optuna, Rerun, Panel server, reports, video generation |
| 11 | [Module Dependency Graph](11_dependency_graph.md) | Intra-package imports, layered architecture, circular dependency analysis |
| 12 | [Examples & Doc Generation](12_examples_and_docs.md) | Example registration, gallery organization, notebook pipeline |
| 13 | [Architecture Summary](13_architecture_summary.md) | High-level diagram, patterns, trade-offs, technical debt |

## Suggested Reading Order

### Quick Overview (30 min)
1. [01 - Package Overview](01_overview.md) - What is bencher?
2. [03 - Core Data Flow](03_data_flow.md) - How does it work end-to-end?
3. [13 - Architecture Summary](13_architecture_summary.md) - Key patterns and trade-offs

### Deep Dive (2-3 hours)
1. [01 - Package Overview](01_overview.md)
2. [02 - Directory Structure](02_directory_structure.md)
3. [05 - Parameter System](05_parameter_system.md)
4. [03 - Core Data Flow](03_data_flow.md)
5. [08 - Execution Model](08_execution_model.md)
6. [07 - Caching Architecture](07_caching.md)
7. [06 - Results & Visualization](06_results_system.md)
8. [09 - Configuration System](09_configuration.md)
9. [04 - Class Hierarchy](04_class_hierarchy.md)
10. [11 - Module Dependency Graph](11_dependency_graph.md)
11. [10 - Integrations](10_integrations.md)
12. [12 - Examples & Doc Generation](12_examples_and_docs.md)
13. [13 - Architecture Summary](13_architecture_summary.md)

### By Topic
- **"How do I add a new parameter type?"** → [05](05_parameter_system.md), [04](04_class_hierarchy.md)
- **"How does caching work?"** → [07](07_caching.md), [08](08_execution_model.md)
- **"How do I add a new plot type?"** → [06](06_results_system.md), [04](04_class_hierarchy.md)
- **"How do I add a new example?"** → [12](12_examples_and_docs.md)
- **"What are the dependencies?"** → [01](01_overview.md), [11](11_dependency_graph.md)
- **"Where is the code for X?"** → [02](02_directory_structure.md), [04](04_class_hierarchy.md)
