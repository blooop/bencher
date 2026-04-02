"""Auto-generated example: BenchRunner Publishing with GithubPagesCfg."""

import math
import bencher as bn


class WaveBenchmark(bn.ParametrizedSweep):
    """A simple wave benchmark used to demonstrate BenchRunner publishing."""

    theta = bn.FloatSweep(
        default=0, bounds=[0, math.pi], doc="Input angle", units="rad", samples=30
    )
    amplitude = bn.FloatSweep(default=1.0, bounds=[0.5, 2.0], doc="Wave amplitude")

    out_wave = bn.ResultFloat(units="v", doc="Wave output")

    def benchmark(self):
        self.out_wave = self.amplitude * math.sin(self.theta)


def example_publish_runner_gh_pages(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """BenchRunner Publishing with GithubPagesCfg."""
    bench = WaveBenchmark().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["theta"],
        result_vars=["out_wave"],
        description="BenchRunner can automatically publish combined reports from "
        "multiple benchmarks to GitHub Pages. Pass a GithubPagesCfg to "
        "the publisher argument and call runner.run(publish=True). "
        "This is ideal for CI pipelines that publish nightly benchmark results.",
        post_description="To actually publish, create a BenchRunner with a "
        "GithubPagesCfg publisher and call runner.run(publish=True). "
        "Example:\n"
        "  runner = bn.BenchRunner('my_benchmarks', "
        "publisher=bn.GithubPagesCfg('user', 'repo', 'folder'))\n"
        "  runner.add(my_benchmark_fn)\n"
        "  runner.run(level=3, publish=True)",
    )

    # Uncomment to publish via BenchRunner:
    # runner = bn.BenchRunner(
    #     "wave_benchmarks",
    #     publisher=bn.GithubPagesCfg("your_username", "your_reports_repo", "waves"),
    # )
    # runner.add_bench(WaveBenchmark())
    # runner.run(level=3, show=True, publish=True)

    return bench


if __name__ == "__main__":
    bn.run(example_publish_runner_gh_pages, level=3)
