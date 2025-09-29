# pylint: disable=duplicate-code
import bencher as bch

# All the examples will be using the data structures and benchmark function defined in this file
from bencher.example.benchmark_data import NoiseDistribution, ExampleBenchCfg


def example_floats2D(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Example of how to perform a 2D floating point parameter sweep

    Args:
        run_cfg (BenchRunCfg): configuration of how to perform the param sweep

    Returns:
        Bench: results of the parameter sweep
    """
    bench = bch.Bench(
        "Bencher_Example_Floats",
        ExampleBenchCfg(),
        run_cfg=run_cfg,
    )
    run_cfg.use_optuna = True

    bench.plot_sweep(
        input_vars=["theta", "offset"],
        result_vars=["out_sin", "out_cos"],
        const_vars=dict(sigma=0.1, noise_distribution=NoiseDistribution.gaussian, noisy=True),
        title="Float 2D Example",
        description="""Bencher is a tool to make it easy to explore how input parameter affect a range of output metrics.  In these examples we are going to benchmark an example function which has been selected to show the features of bencher.
        The example function takes an input theta and returns the absolute value of sin(theta) and cos(theta) +- various types of noise.

    The following examples will show how to perform parameter sweeps to characterise the behavior of the function.  The idea is that the benchmarking can be used to gain understanding of an unknown function.
        """,
        post_description="Here you can see the output plot of sin theta between 0 and pi.  In the tabs at the top you can also view 3 tabular representations of the data",
    )

    bench.report.append(bench.get_result().to_surface())

    bench.plot_sweep(
        input_vars=["theta", "offset", "postprocess_fn"],
        result_vars=["out_sin", "out_cos"],
        const_vars=dict(sigma=0.1, noise_distribution=NoiseDistribution.gaussian, noisy=True),
        title="Float 2D with categorical Example",
        description="""Here we add plot a 2d surface and facet over a categorical variable
        """,
    )
    bench.report.append(bench.get_result().to_surface())

    bench.plot_sweep(
        input_vars=["theta", "offset", "postprocess_fn", "noise_distribution"],
        result_vars=["out_sin", "out_cos"],
        const_vars=dict(sigma=0.1, noise_distribution=NoiseDistribution.gaussian, noisy=True),
        title="Float 2D with categorical x2 Example",
        description="""Here we add plot a 2d surface and facet over two categorical variable
        """,
    )

    bench.report.append(bench.get_result().to_surface())

    return bench


if __name__ == "__main__":
    bench_runner = bch.BenchRunner()
    bench_runner.add(example_floats2D).run(repeats=2, level=3, show=True)
