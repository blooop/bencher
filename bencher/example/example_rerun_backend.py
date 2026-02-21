"""Demonstrate the rerun rendering backend for N-dimensional benchmark data.

This example shows how benchmark sweep results are automatically mapped into rerun's
entity hierarchy and timeline system:
- Categorical dimensions become entity path branches in the tree
- Float dimensions become rerun timelines (scrubable)
- Result variables become scalar leaf entities (rendered as time series)
"""

import math
import bencher as bch


class RerunBackendSweep(bch.ParametrizedSweep):
    """A benchmark with 1 float + 1 categorical input and 2 scalar outputs."""

    theta = bch.FloatSweep(
        default=0.0, bounds=[0, 2 * math.pi], doc="Input angle", units="rad", samples=30
    )
    category = bch.StringSweep(["sin", "cos"], doc="Trig function to evaluate")

    result = bch.ResultVar(units="ul", doc="Function output value")
    abs_result = bch.ResultVar(units="ul", doc="Absolute value of result")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        if self.category == "sin":
            self.result = math.sin(self.theta)
        else:
            self.result = math.cos(self.theta)
        self.abs_result = abs(self.result)
        return super().__call__(**kwargs)


def example_rerun_backend(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Demonstrate the rerun backend with a 1-float + 1-categorical sweep.

    The rerun viewer will show:
    - Entity tree: /category/sin/ and /category/cos/ branches
    - Timeline scrubber for theta
    - Scalar line plots for result and abs_result under each branch

    Args:
        run_cfg: Optional benchmark run configuration.

    Returns:
        The completed Bench object.
    """
    bench = RerunBackendSweep().to_bench(run_cfg)
    bench.plot_sweep(
        title="Rerun Backend Demo",
        description="Mapping N-dimensional sweep results to rerun entity hierarchy and timelines",
    )
    return bench


if __name__ == "__main__":
    bch.run_flask_in_thread()
    bench = example_rerun_backend(bch.BenchRunCfg(level=3))
    result = bench.get_result()
    pane = result.to_rerun()
    pane.show()
