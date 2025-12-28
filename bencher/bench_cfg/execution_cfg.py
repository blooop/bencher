"""Configuration for benchmark execution settings."""

from __future__ import annotations

import param

from bencher.job import Executors


class ExecutionCfg(param.Parameterized):
    """Execution settings: sampling, parallelization, and run modes."""

    repeats: int = param.Integer(1, doc="The number of times to sample the inputs")

    level: int = param.Integer(
        default=0,
        bounds=[0, 12],
        doc="The level parameter is a method of defining the number samples to sweep over in a "
        "variable agnostic way, i.e you don't need to specify the number of samples for each "
        "variable as they are calculated dynamically from the sampling level. See example_level.py "
        "for more information.",
    )

    executor = param.Selector(
        objects=list(Executors),
        doc="The function can be run serially or in parallel with different futures executors",
    )

    nightly: bool = param.Boolean(
        False, doc="Run a more extensive set of tests for a nightly benchmark"
    )

    headless: bool = param.Boolean(False, doc="Run the benchmarks headlessly")
