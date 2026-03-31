"""Auto-generated example: Report Customization — saving and appending content."""

import bencher as bn


class QuadraticFit(bn.ParametrizedSweep):
    """A simple quadratic function for demonstrating report features."""

    x = bn.FloatSweep(default=0, bounds=[-2, 2], doc="Input value")
    y = bn.ResultVar(units="ul", doc="Quadratic output")

    def benchmark(self):
        self.y = self.x**2 - 1


def example_advanced_report_save(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Report Customization — saving and appending content."""
    bench = QuadraticFit().to_bench(run_cfg)

    # First sweep: standard plot
    bench.plot_sweep(
        input_vars=["x"],
        result_vars=["y"],
        description="A simple quadratic curve. Each call to plot_sweep adds a new "
        "tab to the report. You can call plot_sweep multiple times with different "
        "input subsets to build a comprehensive report.",
    )

    # bench.report gives access to the Panel report object.
    # You can append custom markdown or HTML content:
    bench.report.append_markdown(
        "## Custom Section\n\nYou can add **markdown** content "
        "directly to the report using `bench.report.append_markdown()`.",
        name="Custom Content",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_advanced_report_save, level=3)
