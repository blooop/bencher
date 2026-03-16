"""Meta-generator: Regression detection examples.

Demonstrates how to use regression detection to catch performance
regressions in over-time benchmarks.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "regression"

REGRESSION_EXAMPLES = [
    "regression_percentage",
]


class MetaRegression(MetaGeneratorBase):
    """Generate Python examples demonstrating regression detection."""

    example = bch.StringSweep(REGRESSION_EXAMPLES, doc="Which regression example to generate")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        if self.example == "regression_percentage":
            self._generate_percentage()

        return super().__call__()

    def _generate_percentage(self):
        """Percentage-based regression detection over time."""
        imports = "import bencher as bch"
        class_code = '''\
class DegradingBenchmark(bch.ParametrizedSweep):
    """A benchmark whose latency degrades over successive runs."""

    latency = bch.ResultVar(units="ms", direction=bch.OptDir.minimize)
    throughput = bch.ResultVar(units="ops/s", direction=bch.OptDir.maximize)

    run_number = 0

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.latency = 10.0 + DegradingBenchmark.run_number * 5.0
        self.throughput = 100.0 - DegradingBenchmark.run_number * 15.0
        return super().__call__(**kwargs)'''
        body = """\
run_cfg = run_cfg or bch.BenchRunCfg()
run_cfg.over_time = True
run_cfg.repeats = 2
run_cfg.regression_detection = True
run_cfg.regression_method = "percentage"
run_cfg.regression_fail = False
run_cfg.auto_plot = False
run_cfg.headless = True

bench = bch.Bench("regression_percentage", DegradingBenchmark(), run_cfg=run_cfg)

# Simulate 5 time snapshots with increasing degradation
for i in range(5):
    DegradingBenchmark.run_number = i
    res = bench.plot_sweep(plot_callbacks=False)
    bench.sample_cache = None  # reset for next run

# Print the regression report from the last result
report = res.regression_report
if report is not None:
    print("\\n" + report.summary())
    print(f"\\nRegressed variables: {[r.variable for r in report.regressed_variables]}")
else:
    print("No regression report (need at least 2 time points)")
"""
        self.generate_example(
            title="Regression detection — percentage threshold over time",
            output_dir=OUTPUT_DIR,
            filename="regression_percentage",
            function_name="example_regression_percentage",
            imports=imports,
            body=body,
            class_code=class_code,
        )


def example_meta_regression(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = MetaRegression().to_bench(run_cfg)

    bench.plot_sweep(
        title="Regression Detection",
        input_vars=[bch.p("example", REGRESSION_EXAMPLES)],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_meta_regression)
