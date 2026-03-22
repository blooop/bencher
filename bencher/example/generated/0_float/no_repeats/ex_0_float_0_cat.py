"""Auto-generated example: 0 Float, 0 Categorical."""

from typing import Any

import bencher as bn


class BaselineCheck(bn.ParametrizedSweep):
    """Measures a fixed baseline metric with no swept parameters."""

    baseline = bn.ResultVar(units="ms", doc="Baseline latency")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.baseline = 42.0
        return super().__call__()


def example_no_repeats_0_float_0_cat(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """0 Float, 0 Categorical."""
    bench = BaselineCheck().to_bench(run_cfg)
    bench.plot_sweep(input_vars=[], result_vars=["baseline"])

    return bench


if __name__ == "__main__":
    bn.run(example_no_repeats_0_float_0_cat, level=4)
