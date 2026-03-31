"""Auto-generated example: 0 Float, 2 Categorical (no repeats)."""

import bencher as bn


class NetworkConfig(bn.ParametrizedSweep):
    """Measures throughput across protocol and region combinations."""

    protocol = bn.StringSweep(["http", "grpc"], doc="Network protocol")
    region = bn.StringSweep(["us-east", "eu-west", "ap-south"], doc="Deployment region")

    throughput = bn.ResultVar(units="req/s", doc="Request throughput")

    def benchmark(self):
        proto_factor = {"http": 1.0, "grpc": 1.8}[self.protocol]
        region_base = {"us-east": 500, "eu-west": 420, "ap-south": 350}[self.region]
        self.throughput = region_base * proto_factor


def example_sweep_0_float_2_cat_no_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """0 Float, 2 Categorical (no repeats)."""
    bench = NetworkConfig().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["protocol", "region"],
        result_vars=["throughput"],
        description="A 0 float + 2 categorical parameter sweep with a single sample per combination. Bencher calculates the Cartesian product of all input variables and evaluates the benchmark function at each point. With no repeats, each combination appears exactly once -- useful for deterministic functions or quick exploration before committing to longer runs. Categorical-only sweeps produce bar/swarm plots comparing discrete settings.",
        post_description="Each tab shows a different view of the same data: interactive plots, tabular summaries, and raw data. Use the tabs to explore the sweep results from different angles.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_0_float_2_cat_no_repeats, level=4)
