"""Auto-generated example: Publish Report to GitHub Pages."""

import math
import bencher as bn


class SimpleFloat(bn.ParametrizedSweep):
    """A simple sine-wave benchmark used to demonstrate publishing."""

    theta = bn.FloatSweep(
        default=0, bounds=[0, math.pi], doc="Input angle", units="rad", samples=30
    )
    out_sin = bn.ResultVar(units="v", doc="sin of theta")

    def benchmark(self):
        self.out_sin = math.sin(self.theta)


def example_publish_report_gh_pages(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Publish Report to GitHub Pages."""
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

    return bench


if __name__ == "__main__":
    bn.run(example_publish_report_gh_pages, level=3)
