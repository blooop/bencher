"""Auto-generated example: Share Axis — independent y-axis scaling per result variable."""

import bencher as bn


class StartupShutdown(bn.ParametrizedSweep):
    """Benchmarks with very different magnitude results.

    When result variables have different scales (e.g. startup ~60-100s vs
    shutdown ~5-15s), shared y-axes make the smaller result hard to read.
    Setting share_axis=False on a ResultFloat gives each plot its own
    independent y-axis range.
    """

    node = bn.StringSweep(["node_A", "node_B", "node_C"], doc="Cluster node")

    startup = bn.ResultFloat(units="s", share_axis=False, doc="Startup time")
    shutdown = bn.ResultFloat(units="s", share_axis=False, doc="Shutdown time")

    def benchmark(self):
        base_startup = {"node_A": 62, "node_B": 85, "node_C": 74}
        base_shutdown = {"node_A": 5, "node_B": 12, "node_C": 8}
        self.startup = base_startup[self.node]
        self.shutdown = base_shutdown[self.node]


def example_advanced_share_axis(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Share Axis — independent y-axis scaling per result variable."""
    bench = StartupShutdown().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["node"],
        result_vars=["startup", "shutdown"],
        description="share_axis=False gives each result variable its own y-axis scale. "
        "Without it, the shutdown bars (~5-15s) would be nearly flat next to "
        "startup (~60-85s).",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_advanced_share_axis, level=3)
