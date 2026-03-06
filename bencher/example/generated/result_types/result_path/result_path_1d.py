"""Auto-generated example: Result Path: 1D input."""

import bencher as bch
import math


class ReportExporter(bch.ParametrizedSweep):
    """Writes a text report file in the requested format."""

    format_type = bch.StringSweep(["summary", "detailed", "raw"], doc="Report format")

    file_result = bch.ResultPath(doc="Generated report file")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        filename = bch.gen_path(self.format_type, suffix=".txt")
        line_count = {"summary": 5, "detailed": 20, "raw": 50}[self.format_type]
        with open(filename, "w", encoding="utf-8") as f:
            for i in range(line_count):
                f.write(f"[{self.format_type}] line {i + 1}: value={math.sin(i):.4f}\n")
        self.file_result = filename
        return super().__call__()


def example_result_path_1d(run_cfg=None):
    """Result Path: 1D input."""
    bench = ReportExporter().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["format_type"],
        result_vars=["file_result"],
        description="Demonstrates a downloadable file output with 1D input sweep.",
    )

    return bench


if __name__ == "__main__":
    bch.run(example_result_path_1d, level=3)
