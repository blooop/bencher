# 01 - Package Overview

## Package Identity

| Field | Value |
|-------|-------|
| **Package name** | `holobench` |
| **Version** | `1.61.0` |
| **License** | MIT |
| **Python** | `>=3.10, <3.14` |
| **Repository** | https://github.com/blooop/bencher |

## Purpose

Bencher is a benchmarking framework that measures the interactions between input parameters to an algorithm and its resulting performance metrics. It calculates the Cartesian product of a set of input variables, executes a user-defined benchmark function for each combination, stores results in N-dimensional xarray structures, and automatically produces interactive visualizations based on parameter and result types. Results are persistently cached using diskcache so historical performance can be tracked over time.

## Dependencies by Function

| Category | Packages |
|----------|----------|
| **Visualization** | `holoviews`, `hvplot`, `panel`, `plotly` |
| **Data** | `numpy`, `xarray`, `pandas` |
| **Parameters** | `param`, `strenum` |
| **Caching** | `diskcache` |
| **Optimization** | `optuna`, `scikit-learn` |
| **Multimedia** | `moviepy` |
| **Optional: Rerun** | `rerun-sdk`, `rerun-notebook`, `flask`, `flask-cors` |

> Development/test toolchain (pixi, ruff, pylint, pytest, coverage, hypothesis) is documented in `CLAUDE.md` and `pyproject.toml`.
