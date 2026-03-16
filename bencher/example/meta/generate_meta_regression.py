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
        imports = "import bencher as bch\nfrom datetime import datetime, timedelta"
        class_code = '''\
class DegradingBenchmark(bch.ParametrizedSweep):
    """A benchmark whose latency degrades over successive runs."""

    latency = bch.ResultVar(units="ms", direction=bch.OptDir.minimize)
    throughput = bch.ResultVar(units="ops/s", direction=bch.OptDir.maximize)

    _time_offset = 0.0  # set externally per snapshot

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.latency = 10.0 + self._time_offset * 5.0
        self.throughput = 100.0 - self._time_offset * 15.0
        return super().__call__()'''
        body = """\
run_cfg = run_cfg or bch.BenchRunCfg()
run_cfg.over_time = True
run_cfg.repeats = 2
run_cfg.regression_detection = True
run_cfg.regression_method = "percentage"
run_cfg.regression_fail = False

benchable = DegradingBenchmark()
bench = benchable.to_bench(run_cfg)

base_time = datetime(2024, 1, 1)
for i, offset in enumerate([0.0, 1.0, 2.0, 3.0, 4.0]):
    benchable._time_offset = offset
    run_cfg.clear_cache = True
    run_cfg.clear_history = i == 0
    run_cfg.auto_plot = False
    bench.plot_sweep(
        "regression_detection",
        input_vars=[],
        result_vars=["latency", "throughput"],
        run_cfg=run_cfg,
        time_src=base_time + timedelta(seconds=i),
    )

res = bench.results[-1]

# Append auto plots from the final accumulated result (all 5 time points)
bench.report.append(res.to_auto_plots())

report = res.regression_report
if report is not None:
    print("\\n" + report.summary())
    print(f"\\nRegressed variables: {[r.variable for r in report.regressed_variables]}")
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
