"""Auto-generated example: 0 Float, 0 Categorical (no repeats)."""

import bencher as bn


class BaselineCheck(bn.ParametrizedSweep):
    """Measures a fixed baseline metric with no swept parameters."""

    baseline = bn.ResultVar(units="ms", doc="Baseline latency")

    def benchmark(self):
        self.baseline = 42.0


def example_sweep_0_float_0_cat_no_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """0 Float, 0 Categorical (no repeats)."""
    bench = BaselineCheck().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=[],
        result_vars=["baseline"],
        description="A 0 float + 0 categorical parameter sweep with a single sample per combination. Bencher calculates the Cartesian product of all input variables and evaluates the benchmark function at each point. With no repeats, each combination appears exactly once -- useful for deterministic functions or quick exploration before committing to longer runs. With no input variables, this is a 0D sweep that measures a single baseline metric.",
        post_description="Each tab shows a different view of the same data: interactive plots, tabular summaries, and raw data. Use the tabs to explore the sweep results from different angles.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_0_float_0_cat_no_repeats, level=4)
