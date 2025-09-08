"""Example of how to perform a parameter sweep for categorical variables"""

import bencher as bch


# All the examples will be using the data structures and benchmark function defined in this file
from bencher.example.benchmark_data import ExampleBenchCfgIn, ExampleBenchCfgOut, bench_function


def example_float_cat(run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None) -> bch.Bench:
    """Example of how to perform a parameter sweep for categorical variables

    Args:
        run_cfg (BenchRunCfg): configuration of how to perform the param sweep

    Returns:
        Bench: results of the parameter sweep
    """
    bench = bch.Bench(
        "Bencher_Example_Float_Cat",
        bench_function,
        ExampleBenchCfgIn,
        run_cfg=run_cfg,
        report=report,
    )

    bench.plot_sweep(
        input_vars=[
            ExampleBenchCfgIn.param.theta,
            ExampleBenchCfgIn.param.offset,
            ExampleBenchCfgIn.param.postprocess_fn,
        ],
        result_vars=[ExampleBenchCfgOut.param.out_sin],
        const_vars=[ExampleBenchCfgIn.param.noisy.with_const(True)],
        title="Float 2D Cat 1D Example",
        description="""Following from the previous example lets add another input parameter to see how that affects the output.  We pass the boolean  'noisy' and keep the other parameters the same""",
        post_description="Now the plot has two lines, one for each of the boolean values where noisy=true and noisy=false.",
    )

    bench.plot_sweep(
        input_vars=[ExampleBenchCfgIn.param.theta],
        result_vars=[ExampleBenchCfgOut.param.out_sin],
        const_vars=[ExampleBenchCfgIn.param.noisy.with_const(True)],
        title="Float 1D Cat 1D  Example",
        description="""Following from the previous example lets add another input parameter to see how that affects the output.  We pass the boolean  'noisy' and keep the other parameters the same""",
        post_description="Now the plot has two lines, one for each of the boolean values where noisy=true and noisy=false.",
        plot_callbacks=False,
    )

    # report.append(bench.get_result().to_curve())

    # # this does not work yet because it tries to find min and max of categorical values
    # bench.plot_sweep(
    #     input_vars=[ExampleBenchCfgIn.param.theta, ExampleBenchCfgIn.param.postprocess_fn],
    #     result_vars=[ExampleBenchCfgOut.param.out_sin],
    #     const_vars=[ExampleBenchCfgIn.param.noisy.with_const(True)],
    #     title="Float 1D Cat 1D  Example",
    #     description="""Following from the previous example lets add another input parameter to see how that affects the output.  We pass the boolean  'noisy' and keep the other parameters the same""",
    #     post_description="Now the plot has two lines, one for each of the boolean values where noisy=true and noisy=false.",
    #     run_cfg=run_cfg,
    # )

    return bench


def run_example_float_cat(ex_run_cfg: bch.BenchRunCfg | None = None) -> None:
    if ex_run_cfg is None:
        ex_run_cfg = bch.BenchRunCfg()
    ex_run_cfg.repeats = 2
    ex_run_cfg.over_time = True
    ex_run_cfg.clear_cache = True
    ex_run_cfg.clear_history = True
    ex_run_cfg.level = 3
    # ex_run_cfg.time_event = "run 1"
    # ex_run_cfg.use_optuna = True

    example_float_cat(ex_run_cfg)

    # ex_run_cfg.repeats = 2
    # ex_run_cfg.over_time = True
    ex_run_cfg.clear_cache = False
    ex_run_cfg.clear_history = False
    # ex_run_cfg.time_event = "run 2"
    # ex_run_cfg.use_optuna = True

    # example_float_cat(ex_run_cfg)

    # ex_run_cfg.clear_cache = False
    # ex_run_cfg.clear_history = False
    # ex_run_cfg.time_event = "run 2"

    # example_float_cat(ex_run_cfg)

    # ex_run_cfg.time_event = "run 3"
    return example_float_cat(ex_run_cfg)


if __name__ == "__main__":
    run_example_float_cat().report.show()
