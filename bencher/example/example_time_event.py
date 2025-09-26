"""This file has some examples for how to perform basic benchmarking parameter sweeps"""

# pylint: disable=duplicate-code

import bencher as bch

# All the examples will be using the data structures and benchmark function defined in this file
from bencher.example.benchmark_data import ExampleBenchCfgIn, ExampleBenchCfgOut, bench_function


def example_time_event(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """This example shows how to manually set time events as a string so that progress can be monitored over time"""

    bencher = bch.Bench(
        "benchmarking_example_categorical1D",
        bench_function,
        ExampleBenchCfgIn,
        run_cfg=run_cfg,
    )

    ExampleBenchCfgIn.param.offset.bounds = [0, 100]

    # manually override the default value based on the time event string so that the graphs are not all just straight lines
    ExampleBenchCfgIn.param.offset.default = int(str(hash(run_cfg.time_event))[-1])

    # here we sample the input variable theta and plot the value of output1. The (noisy) function is sampled 20 times so you can see the distribution
    bencher.plot_sweep(
        title="Example 1D Categorical",
        input_vars=[ExampleBenchCfgIn.param.postprocess_fn],
        result_vars=[ExampleBenchCfgOut.param.out_cos],
        description=example_time_event.__doc__,
        run_cfg=run_cfg,
    )
    return bencher


def run_example_time_event(ex_run_cfg):
    ex_run_cfg.repeats = 1
    ex_run_cfg.print_pandas = True
    ex_run_cfg.over_time = True

    ex_run_cfg.clear_cache = True
    ex_run_cfg.clear_history = True

    ex_run_cfg.time_event = "-first_event"
    example_time_event(ex_run_cfg)

    ex_run_cfg.clear_cache = False
    ex_run_cfg.clear_history = False
    ex_run_cfg.time_event = "_second_event"
    example_time_event(ex_run_cfg)

    ex_run_cfg.time_event = (
        "*third_event has a very very long label to demonstrate automatic text wrapping"
    )
    return example_time_event(ex_run_cfg)


if __name__ == "__main__":
    run_example_time_event(bch.BenchRunCfg()).report.show()
