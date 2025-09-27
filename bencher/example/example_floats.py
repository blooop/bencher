# pylint: disable=duplicate-code


import bencher as bch

# All the examples will be using the data structures and benchmark function defined in this file
from bencher.example.benchmark_data import ExampleBenchCfg


def example_floats(run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None) -> bch.Bench:
    """Example of how to perform a parameter sweep for floating point variables

    Args:
        run_cfg (BenchRunCfg): configuration of how to perform the param sweep

    Returns:
        Bench: results of the parameter sweep
    """
    bench = bch.Bench("Bencher_Example_Floats", ExampleBenchCfg(), report=report, run_cfg=run_cfg)

    with open("README.md", "r", encoding="utf-8") as file:
        readme = file.read()

    bench.report.append(readme, "Intro")

    bench.plot_sweep(
        input_vars=["theta"],
        result_vars=["out_sin"],
        title="Float 1D Example",
        description="""Bencher is a tool to make it easy to explore how input parameter affect a range of output metrics.  In these examples we are going to benchmark an example function which has been selected to show the features of bencher.
        The example function takes an input theta and returns the absolute value of sin(theta) and cos(theta) +- various types of noise.

        def bench_function(cfg: ExampleBenchCfg) -> dict:
            "Takes an ExampleBenchCfg and returns a dict output"
            return cfg()
            noise = calculate_noise(cfg)
            offset = 0.0

            postprocess_fn = abs if cfg.postprocess_fn == PostprocessFn.absolute else negate_fn

            out.out_sin = postprocess_fn(offset + math.sin(cfg.theta) + noise)
            out.out_cos = postprocess_fn(offset + math.cos(cfg.theta) + noise)
            return out

    The following examples will show how to perform parameter sweeps to characterise the behavior of the function.  The idea is that the benchmarking can be used to gain understanding of an unknown function. 
        """,
        post_description="Here you can see the output plot of sin theta between 0 and pi.  In the tabs at the top you can also view 3 tabular representations of the data",
    )

    bench.plot_sweep(
        input_vars=["theta", "noisy"],
        result_vars=["out_sin"],
        title="Float 1D and Bool Example",
        description="""Following from the previous example lets add another input parameter to see how that affects the output.  We pass the boolean  'noisy' and keep the other parameters the same""",
        post_description="Now the plot has two lines, one for each of the boolean values where noisy=true and noisy=false.",
    )

    bench.plot_sweep(
        input_vars=["theta", "noisy"],
        result_vars=["out_sin", "out_cos"],
        title="Float 1D and Bool Example with multiple outputs",
        description="""Following from the previous example here the second output is added to the result variables""",
        post_description="Another column is added for the result variable that shows cos(theta)",
    )

    bench.plot_sweep(
        input_vars=[
            "theta",
            "noisy",
            "postprocess_fn",
        ],
        result_vars=[
            "out_sin",
            "out_cos",
        ],
        title="Float 1D, Bool and Categorical Example",
        description="""Following from the previous example lets add another input parameter to see how that affects the output.  We add the 'postprocess_fn' categorical enum value which either takes the absolute value or negates the output of the function.""",
        post_description="This generates two rows of results, one for each of the category options.",
    )

    return bench


if __name__ == "__main__":
    bench_ex = example_floats(bch.BenchRunCfg(repeats=2))
    bench_ex.report.save_index()
    bench_ex.report.show()
