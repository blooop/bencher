"""Auto-generated example: 0 Float, 0 Categorical (with repeats)."""

import random

import bencher as bn


class BaselineCheck(bn.ParametrizedSweep):
    """Measures a fixed baseline metric with no swept parameters."""

    baseline = bn.ResultVar(units="ms", doc="Baseline latency")

    def benchmark(self):
        self.baseline = 42.0
        self.baseline += random.gauss(0, 0.15 * 5)


def example_sweep_0_float_0_cat_with_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """0 Float, 0 Categorical (with repeats)."""
    bench = BaselineCheck().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=[],
        result_vars=["baseline"],
        description="A 0 float + 0 categorical parameter sweep with multiple repeats per combination. Repeating measurements reveals the noise structure of your benchmark. If your function is deterministic, all repeats will be identical; if it has stochastic components, repeats let you estimate confidence intervals and distinguish signal from noise. The benchmark function must be pure -- if past calls affect future calls through side effects, the statistics will be invalid. With no input variables, this is a 0D sweep that measures a single baseline metric.",
        post_description="Swarm/violin plots show the distribution of repeated measurements. If repeat has high variance, it suggests either measurement noise or unintended side effects in the benchmark function.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_0_float_0_cat_with_repeats, level=4, repeats=10)
