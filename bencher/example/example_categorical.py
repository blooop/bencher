# pylint: disable=duplicate-code

import bencher as bch

# All the examples will be using the data structures and benchmark function defined in this file
from bencher.example.benchmark_data import ExampleBenchCfgIn, ExampleBenchCfgOut, bench_function


def example_categorical(
    run_cfg: bch.BenchRunCfg | None = None
) -> bch.Bench:
    """Example of how to perform a categorical parameter sweep

    Args:
        run_cfg (BenchRunCfg): configuration of how to perform the param sweep

    Returns:
        Bench: results of the parameter sweep
    """

    with open("README.md", "r", encoding="utf-8") as file:
        readme = file.read()

    # run_cfg.over_time = True

    bench = bch.Bench(
        "Bencher_Example_Categorical",
        bench_function,
        ExampleBenchCfgIn,
        run_cfg=run_cfg,
    )

    bench.report.append(readme, "Intro")

    bench.plot_sweep(
        input_vars=[ExampleBenchCfgIn.param.noisy],
        result_vars=[ExampleBenchCfgOut.param.out_sin],
        title="Categorical 1D Example",
        description="""This example shows how to sample categorical values. The same objective from the float examples is used but theta is kept constant with a value of 0 (as described in the ExampleBenchCfgIn class definition).

        
```
    def bench_function(cfg: ExampleBenchCfgIn) -> ExampleBenchCfgOut:
        "Takes an ExampleBenchCfgIn and returns a ExampleBenchCfgOut output"
        out = ExampleBenchCfgOut()
        noise = calculate_noise(cfg)
        offset = 0.0

        postprocess_fn = abs if cfg.postprocess_fn == PostprocessFn.absolute else negate_fn

        out.out_sin = postprocess_fn(offset + math.sin(cfg.theta) + noise)          
        return out
```
        
        """,
        post_description="The plot shows when noise=True the output has uniform random noise.",
    )

    bench.plot_sweep(
        input_vars=[ExampleBenchCfgIn.param.noisy, ExampleBenchCfgIn.param.noise_distribution],
        result_vars=[ExampleBenchCfgOut.param.out_sin],
        title="Categorical 2D Example",
        description="""Adding another categorical value creates a facet plot over that dimension""",
        post_description="The output shows swarm plots of different noise distributions",
    )

    bench.plot_sweep(
        input_vars=[
            ExampleBenchCfgIn.param.noisy,
            ExampleBenchCfgIn.param.noise_distribution,
            ExampleBenchCfgIn.param.postprocess_fn,
        ],
        result_vars=[ExampleBenchCfgOut.param.out_sin],
        title="Categorical 3D Example",
        description="""Adding another categorical value extends the facets to the right""",
        post_description="The output shows swarm plots of different noise distributions",
    )

    run_cfg.over_time = True
    bench.plot_sweep(
        input_vars=[
            ExampleBenchCfgIn.param.noisy,
            ExampleBenchCfgIn.param.noise_distribution,
            ExampleBenchCfgIn.param.postprocess_fn,
        ],
        title="Categorical 3D Example Over Time",
        result_vars=[ExampleBenchCfgOut.param.out_sin],
        description="""Lastly, what if you want to track these distributions over time? Set over_time=True and bencher will cache and display historical results alongside the latest result.  Use clear_history=True to clear that cache.""",
        post_description="The output shows faceted line plot with confidence intervals for the mean value over time.",
        run_cfg=run_cfg,
    )

    return bench


if __name__ == "__main__":
    ex_run_cfg = bch.BenchRunCfg()
    example_categorical(ex_run_cfg).report.show()
