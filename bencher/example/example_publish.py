"""This file has an example of how to publish a report to github pages"""

import math
import bencher as bn


class SimpleFloat(bn.ParametrizedSweep):
    theta = bn.FloatSweep(
        default=0, bounds=[0, math.pi], doc="Input angle", units="rad", samples=30
    )
    out_sin = bn.ResultVar(units="v", doc="sin of theta")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out_sin = math.sin(self.theta)
        return super().__call__(**kwargs)


if __name__ == "__main__":
    # publish from report
    bench = SimpleFloat().to_bench()
    bench.plot_sweep()
    bench.report.publish_gh_pages(github_user="blooop", repo_name="reports", folder_name="r5")
    # TODO DON'T OVERWRITE ^ EXAMPLE WHEN RUNNING CODE BELOW

    # publish from benchrunner
    bench_r = bn.BenchRunner("SimpleFloat", publisher=bn.GithubPagesCfg("blooop", "reports", "r6"))
    bench_r.add_bench(SimpleFloat())
    bench_r.run(level=3, show=True, publish=True)
