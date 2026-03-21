"""Auto-generated example: BenchRunner — run multiple benchmarks in one session."""

from typing import Any

import math
import bencher as bn


class SineWave(bn.ParametrizedSweep):
    """A sine wave — one of two benchmarks combined by BenchRunner."""

    theta = bn.FloatSweep(default=0, bounds=[0, math.pi], doc="Input angle", units="rad")
    out_sin = bn.ResultVar(units="V", doc="Sine output")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.out_sin = math.sin(self.theta)
        return super().__call__()


def example_workflow_bench_runner(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """BenchRunner — run multiple benchmarks in one session."""
    # This example shows the building block that BenchRunner orchestrates.
    # To combine multiple independent benchmarks into one session, use:
    #
    #   runner = bn.BenchRunner("comparison")
    #   runner.add(sine_benchmark_fn)    # each fn returns a Bench
    #   runner.add(cosine_benchmark_fn)
    #   runner.run(level=3)              # runs all, collects reports
    #
    # BenchRunner is useful when you have separate benchmark functions
    # that you want to run together and compare side by side.

    bench = SineWave().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["theta"],
        result_vars=["out_sin"],
        description="BenchRunner lets you manage multiple benchmark functions in a "
        "single session. Each added function produces its own tab in the combined "
        "report. This example shows one such benchmark function.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_workflow_bench_runner, level=3)
