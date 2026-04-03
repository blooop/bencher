"""Auto-generated example: Multiple Sweeps — progressive report with tabs."""

import math
import bencher as bn


class DataPipeline(bn.ParametrizedSweep):
    """Simulates a data processing pipeline with configurable stages."""

    batch_size = bn.FloatSweep(default=100, bounds=[10, 1000], doc="Batch size", units="rows")
    parallelism = bn.FloatSweep(default=4, bounds=[1, 16], doc="Worker threads")
    storage = bn.StringSweep(["ssd", "hdd", "network"], doc="Storage backend")

    throughput = bn.ResultFloat(units="rows/s", doc="Processing throughput")
    latency = bn.ResultFloat(units="ms", doc="Per-batch latency")

    def benchmark(self):
        storage_factor = {"ssd": 1.0, "hdd": 0.4, "network": 0.25}[self.storage]
        self.throughput = self.batch_size * math.sqrt(self.parallelism) * storage_factor * 0.5
        self.latency = 1000 * self.batch_size / max(self.throughput, 1)


def example_workflow_multi_sweep(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Multiple Sweeps — progressive report with tabs."""
    bench = DataPipeline().to_bench(run_cfg)

    # Sweep 1: Vary only batch_size — produces a 1D line plot
    bench.plot_sweep(
        title="Batch Size Sweep",
        input_vars=["batch_size"],
        result_vars=["throughput", "latency"],
        description="Sweep the batch size while keeping other parameters at defaults. "
        "This shows how batch size affects both throughput and latency.",
    )

    # Sweep 2: Vary batch_size and parallelism — produces a 2D heatmap
    bench.plot_sweep(
        title="Batch Size + Parallelism Sweep",
        input_vars=["batch_size", "parallelism"],
        result_vars=["throughput"],
        description="Sweep both batch size and parallelism to see their combined effect "
        "on throughput. The heatmap reveals optimal configurations.",
    )

    # Sweep 3: Compare storage backends at fixed configuration
    bench.plot_sweep(
        title="Storage Backend Comparison",
        input_vars=["storage"],
        result_vars=["latency"],
        const_vars=dict(batch_size=500, parallelism=4),
        description="Compare latency across storage backends at a fixed configuration. "
        "const_vars pins batch_size and parallelism so only storage varies.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_workflow_multi_sweep, level=3)
