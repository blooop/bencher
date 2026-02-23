# 01 - Package Overview

## Package Identity

| Field | Value |
|-------|-------|
| **Package name** | `holobench` |
| **Version** | `1.61.0` |
| **Author** | Austin Gregg-Smith (blooop@gmail.com) |
| **License** | MIT |
| **Python** | `>=3.10, <3.14` |
| **Repository** | https://github.com/blooop/bencher |
| **Documentation** | https://bencher.readthedocs.io/en/latest/ |
| **PyPI** | https://pypi.org/project/holobench/ |

## Purpose

Bencher is a benchmarking framework that makes it easy to measure the interactions between input parameters to an algorithm and its resulting performance on a set of metrics. It calculates the Cartesian product of a set of input variables, executes a user-defined benchmark function for each combination, stores results in N-dimensional xarray structures, and automatically produces interactive visualizations based on parameter and result types. Results are persistently cached using diskcache so historical performance can be tracked over time.

## Dependencies

### Core Dependencies (`pyproject.toml:12-26`)

#### Visualization
| Package | Version Range | Purpose |
|---------|--------------|---------|
| `holoviews` | `>=1.15, <=1.22.1` | Interactive data visualization (core plotting engine) |
| `hvplot` | `>=0.12.0, <=0.12.2` | High-level plotting API for HoloViews |
| `panel` | `>=1.3.6, <=1.8.7` | Dashboard/app framework, web server, report generation |
| `plotly` | `>=5.15, <=6.5.2` | 3D plots (volume, surface) |

#### Data
| Package | Version Range | Purpose |
|---------|--------------|---------|
| `numpy` | `>=1.0, <=2.4.1` | Numerical arrays |
| `xarray` | `>=2023.7, <=2025.6.1` | N-dimensional labeled arrays for result storage |
| `pandas` | `>=2.0, <=3.0.0` | Tabular data manipulation |

#### Configuration & Parameters
| Package | Version Range | Purpose |
|---------|--------------|---------|
| `param` | `>=1.13.0, <=2.3.2` | Declarative parameter definitions with metadata |
| `strenum` | `>=0.4.0, <=0.4.15` | String-based enumerations |

#### Caching
| Package | Version Range | Purpose |
|---------|--------------|---------|
| `diskcache` | `>=5.6, <=5.6.3` | Persistent disk-based result caching |

#### Optimization
| Package | Version Range | Purpose |
|---------|--------------|---------|
| `optuna` | `>=3.2, <=4.7.0` | Hyperparameter optimization with Bayesian sampling |
| `scikit-learn` | `>=1.2, <=1.7.2` | Machine learning utilities (used by Optuna) |

#### Multimedia
| Package | Version Range | Purpose |
|---------|--------------|---------|
| `moviepy` | `>=2.1.2, <=2.2.1` | Video generation from image sequences |

### Optional Dependencies

#### Rerun Integration (`pyproject.toml:76`)
| Package | Version Range | Purpose |
|---------|--------------|---------|
| `rerun-sdk` | `>=0.29.2` | 3D/2D visualization SDK |
| `rerun-notebook` | `>=0.29.2` | Jupyter notebook integration for Rerun |
| `flask` | - | Local file serving for Rerun viewer |
| `flask-cors` | - | CORS support for Flask server |

#### Test Dependencies (`pyproject.toml:60-73`)
| Package | Version Range | Purpose |
|---------|--------------|---------|
| `pytest` | `>=7.4, <=9.0.2` | Test framework |
| `pytest-cov` | `>=4.1, <=7.0.0` | Coverage plugin for pytest |
| `coverage` | `>=7.5.4, <=7.13.4` | Coverage measurement |
| `pylint` | `>=3.2.5, <=4.0.4` | Static analysis |
| `ruff` | `>=0.5.0, <=0.15.1` | Fast Python linter/formatter |
| `hypothesis` | `>=6.104.2, <=6.151.9` | Property-based testing |
| `ty` | `>=0.0.13, <=0.0.17` | Type checker |
| `nbformat` | - | Jupyter notebook format parsing |
| `ipykernel` | - | Jupyter kernel for notebook execution |
| `jupyter_bokeh` | - | Bokeh rendering in Jupyter |
| `prek` | `>=0.2.28, <0.4.0` | Pre-commit hook management |

## Build System

- **Build backend**: `hatchling` (`pyproject.toml:82-83`)
- **Build includes**: `bencher`, `CHANGELOG.md` (`pyproject.toml:85-86`)
- **Editable install**: via Pixi PyPI dependencies (`pyproject.toml:56-57`)

## Development Toolchain

### Package Manager: Pixi
- **Channels**: `conda-forge`, `https://prefix.dev/blooop` (`pyproject.toml:34`)
- **Platforms**: `linux-64` (`pyproject.toml:35`)
- **Python environments**: 3.10, 3.11, 3.12, 3.13 (`pyproject.toml:47-54`)

### Key Pixi Tasks (`pyproject.toml:96-157`)

| Task | Command/Dependencies | Purpose |
|------|---------------------|---------|
| `ci` | format, ruff-lint, pylint, ty, coverage, coverage-report | Full CI pipeline |
| `test` | `pytest` | Run test suite |
| `format` | `ruff format .` | Code formatting |
| `ruff-lint` | `ruff check . --fix` | Linting with auto-fix |
| `pylint` | `pylint $(git ls-files '*.py')` | Static analysis |
| `ty` | `ty check --respect-ignore-files .` | Type checking |
| `coverage` | `coverage run -m pytest && coverage xml` | Coverage measurement |
| `generate-docs` | `python bencher/example/meta/generate_examples.py` | Generate gallery notebooks |
| `agent-iterate` | generate-docs, ci, git-commit-all, fix-commit-push | Full AI agent cycle |

### Code Style (`ruff.toml:1-16`)
- **Line length**: 100 characters
- **Ignored rules**: E501 (line length), F841 (unused variables during development)
- **Per-file ignores**: E402, F401 in `__init__.py`; E402 in tests/docs/tools

### Pylint Configuration (`pyproject.toml:160-167`)
- **Jobs**: 16 (parallel)
- **Ignored paths**: `docs/*`
- **Disabled**: Most convention checks (C), many structural warnings (too-many-*, cyclic-import, duplicate-code)
