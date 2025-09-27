"""This file has some examples for how to perform basic benchmarking parameter sweeps"""

# pylint: disable=duplicate-code

import bencher as bch

# All the examples will be using the data structures and benchmark function defined in this file
from bencher.example.benchmark_data import ExampleBenchCfg


def example_1D_cat(run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None) -> bch.Bench:
    """This example shows how to sample a 1 dimensional categorical variable and plot the result of passing that parameter sweep to the benchmarking function

    Args:
        run_cfg (BenchRunCfg): configuration of how to perform the param sweep

    Returns:
        Bench: results of the parameter sweep
    """

    explorer = ExampleBenchCfg()
    bench = bch.Bench(
        "benchmarking_example_categorical1D",
        ExampleBenchCfg(),
        run_cfg=run_cfg,
        report=report,
    )

    # here we sample the input variable theta and plot the value of output1. The (noisy) function is sampled 20 times so you can see the distribution
    bench.plot_sweep(
        title="Example 1D Categorical",
        description="""This example shows how to sample a 1 dimensional categorical variable and plot the result of passing that parameter sweep to the benchmarking function""",
        input_vars=[ExampleBenchCfg.param.postprocess_fn],
        result_vars=[ExampleBenchCfg.param.out_cos, ExampleBenchCfg.param.out_sin],
        const_vars=explorer.get_input_defaults(),
    )

    return bench


if __name__ == "__main__":
    ex_run_cfg = bch.BenchRunCfg()
    ex_run_cfg.repeats = 10

    srv1 = example_1D_cat(ex_run_cfg).report.show()
