"""This file has some examples for how to perform basic benchmarking parameter sweeps"""

import bencher as bch

# All the examples will be using the data structures and benchmark function defined in this file
from bencher.example.benchmark_data import ExampleBenchCfgIn, ExampleBenchCfgOut, bench_function


def example_1D_float(
    run_cfg: bch.BenchRunCfg = bch.BenchRunCfg(), report: bch.BenchReport = bch.BenchReport()
) -> bch.Bench:
    """This example shows how to sample a 1 dimensional float variable and plot the result of passing that parameter sweep to the benchmarking function"""

    bench = bch.Bench(
        "benchmarking_example_float1D",
        bench_function,
        ExampleBenchCfgIn,
        run_cfg=run_cfg,
        report=report,
    )

    # here we sample the input variable theta and plot the value of output1. The (noisy) function is sampled 20 times so you can see the distribution
    bench.plot_sweep(
        title="Example 1D Float",
        input_vars=[ExampleBenchCfgIn.param.theta],
        result_vars=[ExampleBenchCfgOut.param.out_sin],
        description=example_1D_float.__doc__,
    )

    res = bench.get_result()

    import holoviews as hv

    # print(res.to_hv_dataset().data)
    # print("new")
    # print(res.to_hv_dataset_new().data)

    bench.report.append(res.to_hv_dataset().data)
    bench.report.append(res.to_hv_dataset_old().data)
        

    # report.append(res.to_hv_container(hv.Area))

    # report.append(res.ds)
    # report.append(res.to_dataset(ExampleBenchCfgOut.param.out_sin))
    # print(res.ds)

    # report.append(res.to_line())

    # print(res.to_dataset())
    # print(res.to_hv_dataset())
    # report.append(res.to_dataset())
    return bench


if __name__ == "__main__":
    ex_run_cfg = bch.BenchRunCfg()
    ex_run_cfg.repeats = 2
    # ex_run_cfg.over_time = True

    example_1D_float(ex_run_cfg).report.show()
