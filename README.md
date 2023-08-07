# Bencher

## Continuous Integration Status

[![Ci](https://github.com/dyson-ai/bencher/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/dyson-ai/bencher/actions/workflows/ci.yml?query=branch%3Amain)
[![Codecov](https://codecov.io/gh/blooop/bencher/branch/main/graph/badge.svg?token=AVFC5D5Z43)](https://codecov.io/gh/blooop/bencher)
[![GitHub issues](https://img.shields.io/github/issues/dyson-ai/bencher.svg)](https://GitHub.com/dyson-ai/bencher/issues/)
[![GitHub pull-requests merged](https://badgen.net/github/merged-prs/dyson-ai/bencher)](https://github.com/dyson-ai/bencher/pulls?q=is%3Amerged)
[![PyPI](https://img.shields.io/pypi/v/holobench)](https://pypi.org/project/holobench/)
[![GitHub release](https://img.shields.io/github/release/dyson-ai/bencher.svg)](https://GitHub.com/dyson-ai/bencher/releases/)
[![License](https://img.shields.io/pypi/l/bencher)](https://opensource.org/license/mit/)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11-blue)](https://www.python.org/downloads/release/python-310/)


## Intro

Bencher is a tool to make it easy to benchmark the interactions between the input parameters to your algorithm and its resulting performance on a set of metrics.

Parameters for bencher are defined using the param library https://param.holoviz.org/ as a config class with extra metadata that describes the bounds of the search space you want to measure.  You must define a benchmarking function that accepts an instance of the config class and return a dictionary with string metric names and float values.

Parameters are benchmarked by passing in a list N parameters, and an N-Dimensional tensor is returned.   You can optionally sample each point multiple times to get back a distribution and also track its value over time.  By default the data will be plotted automatically based on the types of parameters you are sampling (e.g, continous, discrete), but you can also pass in a callback to customize plotting.

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
    deduce the type of plot based on the input types
    return data and plot