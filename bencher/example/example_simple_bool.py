"""This file has some examples for how to perform basic benchmarking parameter sweeps"""

import bencher as bn

# All the examples will be using the data structures and benchmark function defined in this file
from bencher.example.benchmark_data import ExampleBenchCfg


def example_1D_bool(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Sample a 1D boolean input and visualise the resulting success metric."""

    if run_cfg is None:
        run_cfg = bn.BenchRunCfg()

    bench = bn.Bench(
        "benchmarking_example_categorical1D",
        ExampleBenchCfg(),
    )

    # here we sample the input variable theta and plot the value of output1. The (noisy) function is sampled 20 times so you can see the distribution
    bench.plot_sweep(
        title="Example 1D Bool",
        input_vars=["noisy"],
        result_vars=["out_sin"],
        description=example_1D_bool.__doc__,
        run_cfg=run_cfg,
    )
    bench.add(bn.BarResult)

    return bench


if __name__ == "__main__":
    bn.run(example_1D_bool, repeats=20)
