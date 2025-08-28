"""This file has some examples for how to perform basic benchmarking parameter sweeps"""

import bencher as bch

# All the examples will be using the data structures and benchmark function defined in this file
from bencher.example.benchmark_data import ExampleBenchCfgIn, ExampleBenchCfgOut, bench_function


def example_1D_bool(run_cfg: bch.BenchRunCfg, report: bch.BenchReport) -> bch.Bench:
    """This example shows how to sample a 1 dimensional categorical variable and plot the result of passing that parameter sweep to the benchmarking function"""

    bench = bch.Bench(
        "benchmarking_example_categorical1D",
        bench_function,
        ExampleBenchCfgIn,
        report=report,
    )

    # here we sample the input variable theta and plot the value of output1. The (noisy) function is sampled 20 times so you can see the distribution
    bench.plot_sweep(
        title="Example 1D Bool",
        input_vars=[ExampleBenchCfgIn.param.noisy],
        result_vars=[ExampleBenchCfgOut.param.out_sin],
        description=example_1D_bool.__doc__,
        run_cfg=run_cfg,
    )
    bench.add(bch.BarResult)

    return bench


if __name__ == "__main__":
    br = bch.BenchRunner()
    br.add(example_1D_bool)
    br.run(repeats=20, show=True)
