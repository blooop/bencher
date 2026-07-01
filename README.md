# Bencher
 
 ## Continuous Integration Status

[![Ci](https://github.com/blooop/bencher/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/blooop/bencher/actions/workflows/ci.yml?query=branch%3Amain)
![Read the Docs](https://img.shields.io/readthedocs/bencher)
[![Codecov](https://codecov.io/gh/blooop/bencher/branch/main/graph/badge.svg?token=Y212GW1PG6)](https://codecov.io/gh/blooop/bencher)
[![GitHub issues](https://img.shields.io/github/issues/blooop/bencher.svg)](https://GitHub.com/blooop/bencher/issues/)
[![GitHub pull-requests merged](https://badgen.net/github/merged-prs/blooop/bencher)](https://github.com/blooop/bencher/pulls?q=is%3Amerged)
[![PyPI](https://img.shields.io/pypi/v/holobench)](https://pypi.org/project/holobench/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/holobench)](https://pypistats.org/packages/holobench)
[![License](https://img.shields.io/pypi/l/bencher)](https://opensource.org/license/mit/)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.13-blue)](https://www.python.org/downloads/)
[![Pixi Badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/prefix-dev/pixi/main/assets/badge/v0.json)](https://pixi.sh)

## Install

```bash
pip install holobench
```

## Intro

Bencher is a tool to make it easy to benchmark the interactions between the input parameters to your algorithm and its resulting performance on a set of metrics.  It calculates the [cartesian product](https://en.wikipedia.org/wiki/Cartesian_product) of a set of variables

Parameters for bencher are defined using the [param](https://param.holoviz.org/) library  as a config class with extra metadata that describes the bounds of the search space you want to measure.  You must define a benchmarking function that accepts an instance of the config class and return a dictionary with string metric names and float values.

Parameters are benchmarked by passing in a list N parameters, and an N-Dimensional tensor is returned.   You can optionally sample each point multiple times to get back a distribution and also track its value over time.  By default the data will be plotted automatically based on the types of parameters you are sampling (e.g, continuous, discrete), but you can also pass in a callback to customize plotting.

The data is stored in a persistent database so that past performance is tracked.

## Assumptions

The input types should also be of one of the basic datatypes (bool, int, float, str, enum, datetime) so that the data can be easily hashed, cached and stored in the database and processed with seaborn and xarray plotting functions. You can use class inheritance to define hierarchical parameter configuration class types that can be reused in a bigger configuration classes.

Bencher is designed to work with stochastic pure functions with no side effects.  It assumes that when the objective function is given the same inputs, it will return the same output +- random noise.  This is because the function must be called multiple times to get a good statistical distribution of it and so each call must not be influenced by anything or the results will be corrupted.

### Pseudocode of bencher

    Enumerate a list of all input parameter combinations
    for each set of input parameters:
        pass the inputs to the objective function and store results in the N-D array

        get unique hash for the set of inputs parameters
        look up previous results for that hash
        if it exists:
            load historical data
            combine latest data with historical data
        
        store the results using the input hash as a key
    deduce the type of plot based on the input and output types
    return data and plot
    

## Resource Management with `sampling_context`

If your benchmark holds external resources (DB pools, GPU handles, simulators) you
may want to release them *before* the interactive result viewer starts. Wrapping
the entire `bn.run()` call in a `with` block won't work — the context stays open
while the Panel/Bokeh server blocks:

```python
# Anti-pattern: resources held during the entire viewing session
with gpu_context():
    bn.run(my_bench, show=True)
```

Instead, pass the context manager as `sampling_context`. It wraps only the sampling
phase; its `__exit__` runs before the server starts:

```python
bn.run(my_bench, show=True, sampling_context=gpu_context())
```

`save` and `publish` still execute inside the context (during sampling), so results
are persisted before the resource is released.

## Demo

if you have [pixi](https://github.com/prefix-dev/pixi/) installed you can run a demo example with:

```bash
pixi run demo
```

An example of the type of output bencher produces can be seen here:

https://blooop.github.io/bencher/ 


## Examples

Most features are demonstrated in the auto-generated examples under `bencher/example/generated/`.

Run `pixi run generate-docs` to regenerate the full example gallery. Key sections include:
- `generated/N_float/` — Parameter sweeps with 0–3 float inputs, with/without repeats and over-time tracking
- `generated/plot_types/` — All supported plot types (scatter, line, heatmap, surface, etc.)
- `generated/result_types/` — Result types: images, videos, strings, booleans, paths, datasets
- `generated/composable_containers/` — Combining results with different composition strategies
- `generated/sampling/` — Custom values, levels, uniform, int vs float
- `generated/optimization/` — Single and multi-objective optimization with Optuna
- `generated/advanced/` — Time events, caching, aggregation over time
- `generated/regression/` — Performance regression detection
- `generated/statistics/` — Error bands, distributions, repeats comparison

A few hand-written examples remain for unique functionality:
- `example_simple_float.py` — Minimal getting-started example
- `example_image.py` / `example_video.py` — Image and video result types
- `example_self_benchmark.py` — Bencher self-introspection
- `example_workflow.py` — Multi-stage optimization workflow


## Documentation

- [Examples Documentation](https://bencher.readthedocs.io/reference/index.html)
- [API documentation](https://bencher.readthedocs.io/autoapi/bencher/index.html)

More documentation is needed for the examples and general workflow.
