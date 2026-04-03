"""Auto-generated example: Result String: 1D input."""

import math

import bencher as bn


class LogFormatter(bn.ParametrizedSweep):
    """Formats a structured log report string."""

    level = bn.StringSweep(["info", "warn", "error"], doc="Log severity level")
    verbosity = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Output verbosity")

    report = bn.ResultString(doc="Formatted log report")

    def benchmark(self):
        detail = int(math.ceil(self.verbosity * 5))
        text = f"Level: {self.level}\n\tVerbosity: {self.verbosity:.2f}\n\tDetail depth: {detail}"
        self.report = bn.tabs_in_markdown(text)


def example_result_string_1d(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Result String: 1D input."""
    bench = LogFormatter().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["level", "verbosity"],
        result_vars=["report"],
        description="Demonstrates a formatted markdown string with 1D input sweep.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_result_string_1d, level=3)
