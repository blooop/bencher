"""This file has some examples for how to perform basic benchmarking parameter sweeps"""

# pylint: disable=duplicate-code

import bencher as bn

# All the examples will be using the data structures and benchmark function defined in this file
from bencher.example.benchmark_data import ExampleBenchCfg


def example_time_event(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """This example shows how to manually set time events as a string so that progress can be monitored over time"""

    bencher = bn.Bench(
        "benchmarking_example_categorical1D",
        ExampleBenchCfg(),
        run_cfg=run_cfg,
    )

    ExampleBenchCfg.param.offset.bounds = [0, 100]

    # manually override the default value based on the time event string so that the graphs are not all just straight lines
    ExampleBenchCfg.param.offset.default = int(str(hash(run_cfg.time_event))[-1])

    # here we sample the input variable theta and plot the value of output1. The (noisy) function is sampled 20 times so you can see the distribution
    bencher.plot_sweep(
        title="Example 1D Categorical",
        input_vars=["postprocess_fn"],
        result_vars=["out_cos"],
        description=example_time_event.__doc__,
        run_cfg=run_cfg,
    )
    return bencher


def run_example_time_event(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    if run_cfg is None:
        run_cfg = bn.BenchRunCfg()
    run_cfg.repeats = 1
    run_cfg.print_pandas = True
    run_cfg.over_time = True

    run_cfg.clear_cache = True
    run_cfg.clear_history = True

    run_cfg.time_event = "-first_event"
    example_time_event(run_cfg)

    run_cfg.clear_cache = False
    run_cfg.clear_history = False
    run_cfg.time_event = "_second_event"
    example_time_event(run_cfg)

    run_cfg.time_event = (
        "*third_event has a very very long label to demonstrate automatic text wrapping"
    )
    return example_time_event(run_cfg)


if __name__ == "__main__":
    bn.run(run_example_time_event)
