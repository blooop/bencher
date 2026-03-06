"""Auto-generated example: 0 Float, 0 Categorical."""

import bencher as bch


class BaselineCheck(bch.ParametrizedSweep):
    """Measures a fixed baseline metric with no swept parameters."""

    baseline = bch.ResultVar(units="ms", doc="Baseline latency")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.baseline = 42.0
        self.baseline += __import__("random").gauss(0, 0.15 * 5)
        return super().__call__()


def example_with_repeats_0_float_0_cat(run_cfg=None):
    """0 Float, 0 Categorical."""
    bench = BaselineCheck().to_bench(run_cfg)
    bench.plot_sweep(input_vars=[], result_vars=["baseline"])

    return bench


if __name__ == "__main__":
    bch.run(example_with_repeats_0_float_0_cat, level=4, repeats=10)
