"""Configuration for benchmark output and reporting settings."""

from __future__ import annotations

import param


class DisplayCfg(param.Parameterized):
    """Output and reporting: console printing and web serving options."""

    summarise_constant_inputs: bool = param.Boolean(
        True, doc="Print the inputs that are kept constant when describing the sweep parameters"
    )

    print_bench_inputs: bool = param.Boolean(
        True, doc="Print the inputs to the benchmark function every time it is called"
    )

    print_bench_results: bool = param.Boolean(
        True, doc="Print the results of the benchmark function every time it is called"
    )

    print_pandas: bool = param.Boolean(
        False, doc="Print a pandas summary of the results to the console."
    )

    print_xarray: bool = param.Boolean(
        False, doc="Print an xarray summary of the results to the console"
    )

    serve_pandas: bool = param.Boolean(
        False,
        doc="Serve a pandas summary on the results webpage. If you have a large dataset "
        "consider setting this to false if the page loading is slow",
    )

    serve_pandas_flat: bool = param.Boolean(
        True,
        doc="Serve a flattened pandas summary on the results webpage. If you have a large "
        "dataset consider setting this to false if the page loading is slow",
    )

    serve_xarray: bool = param.Boolean(
        False,
        doc="Serve an xarray summary on the results webpage. If you have a large dataset "
        "consider setting this to false if the page loading is slow",
    )
