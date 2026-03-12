"""Auto-generated example: Result String: 1D input."""

from typing import Any

import math
import bencher as bch


class LogFormatter(bch.ParametrizedSweep):
    """Formats a structured log report string."""

    level = bch.StringSweep(["info", "warn", "error"], doc="Log severity level")
    verbosity = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Output verbosity")

    report = bch.ResultString(doc="Formatted log report")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        detail = int(math.ceil(self.verbosity * 5))
        text = f"Level: {self.level}\n\tVerbosity: {self.verbosity:.2f}\n\tDetail depth: {detail}"
        self.report = bch.tabs_in_markdown(text)
        return super().__call__()


def example_result_string_1d(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Result String: 1D input."""
    bench = LogFormatter().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["level", "verbosity"],
        result_vars=["report"],
        description="Demonstrates a formatted markdown string with 1D input sweep.",
    )

    return bench


if __name__ == "__main__":
    bch.run(example_result_string_1d, level=3)
