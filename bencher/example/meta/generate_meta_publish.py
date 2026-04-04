"""Meta-generator: Publishing examples.

Demonstrates how to publish benchmark reports to GitHub Pages using both
the BenchReport API and BenchRunner publisher integration.
"""

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "publishing"

PUBLISH_EXAMPLES = [
    "report_publish",
    "runner_publish",
]


class MetaPublish(MetaGeneratorBase):
    """Generate Python examples demonstrating report publishing."""

    example = bn.StringSweep(PUBLISH_EXAMPLES, doc="Which publishing example to generate")

    def benchmark(self):
        if self.example == "report_publish":
            self._generate_report_publish()
        elif self.example == "runner_publish":
            self._generate_runner_publish()

    def _generate_report_publish(self):
        """Publish a single benchmark report to GitHub Pages."""
        imports = "import math\nimport bencher as bn"
        class_code = '''\
class SimpleFloat(bn.ParametrizedSweep):
    """A simple sine-wave benchmark used to demonstrate publishing."""

    theta = bn.FloatSweep(
        default=0, bounds=[0, math.pi], doc="Input angle", units="rad", samples=30
    )
    out_sin = bn.ResultFloat(units="v", doc="sin of theta")

    def benchmark(self):
        self.out_sin = math.sin(self.theta)'''
        body = """\
bench = SimpleFloat().to_bench(run_cfg)
bench.plot_sweep(
    input_vars=["theta"],
    result_vars=["out_sin"],
    description="This example demonstrates how to publish a benchmark report to "
    "GitHub Pages. After running your sweep, call "
    "bench.report.publish_gh_pages() with your GitHub username and a "
    "target repository. The report HTML is committed to the gh-pages "
    "branch and served at https://<user>.github.io/<repo>/<folder>/.",
    post_description="To actually publish, uncomment the publish_gh_pages call below "
    "and provide your own GitHub username and repository name.",
)

# Uncomment to publish:
# bench.report.publish_gh_pages(
#     github_user="your_username",
#     repo_name="your_reports_repo",
#     folder_name="my_benchmark",
# )
"""
        self.generate_example(
            title="Publish Report to GitHub Pages",
            output_dir=OUTPUT_DIR,
            filename="example_publish_report_gh_pages",
            function_name="example_publish_report_gh_pages",
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"level": 3},
        )

    def _generate_runner_publish(self):
        """Publish via BenchRunner with GithubPagesCfg."""
        imports = "import math\nimport bencher as bn"
        class_code = '''\
class WaveBenchmark(bn.ParametrizedSweep):
    """A simple wave benchmark used to demonstrate BenchRunner publishing."""

    theta = bn.FloatSweep(
        default=0, bounds=[0, math.pi], doc="Input angle", units="rad", samples=30
    )
    amplitude = bn.FloatSweep(default=1.0, bounds=[0.5, 2.0], doc="Wave amplitude")

    out_wave = bn.ResultFloat(units="v", doc="Wave output")

    def benchmark(self):
        self.out_wave = self.amplitude * math.sin(self.theta)'''
        body = """\
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
    "Example:\\n"
    "  runner = bn.BenchRunner('my_benchmarks', "
    "publisher=bn.GithubPagesCfg('user', 'repo', 'folder'))\\n"
    "  runner.add(my_benchmark_fn)\\n"
    "  runner.run(level=3, publish=True)",
)

# Uncomment to publish via BenchRunner:
# runner = bn.BenchRunner(
#     "wave_benchmarks",
#     publisher=bn.GithubPagesCfg("your_username", "your_reports_repo", "waves"),
# )
# runner.add_bench(WaveBenchmark())
# runner.run(level=3, show=True, publish=True)
"""
        self.generate_example(
            title="BenchRunner Publishing with GithubPagesCfg",
            output_dir=OUTPUT_DIR,
            filename="example_publish_runner_gh_pages",
            function_name="example_publish_runner_gh_pages",
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"level": 3},
        )


def example_meta_publish(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = MetaPublish().to_bench(run_cfg)

    bench.plot_sweep(
        title="Publishing Patterns",
        input_vars=[bn.sweep("example", PUBLISH_EXAMPLES)],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_publish)
