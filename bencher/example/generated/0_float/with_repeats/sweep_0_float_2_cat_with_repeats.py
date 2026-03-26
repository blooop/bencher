"""Auto-generated example: 0 Float, 2 Categorical (with repeats)."""

from typing import Any

import random

import bencher as bn


class NetworkConfig(bn.ParametrizedSweep):
    """Measures throughput across protocol and region combinations."""

    protocol = bn.StringSweep(["http", "grpc"], doc="Network protocol")
    region = bn.StringSweep(["us-east", "eu-west", "ap-south"], doc="Deployment region")

    throughput = bn.ResultVar(units="req/s", doc="Request throughput")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        proto_factor = {"http": 1.0, "grpc": 1.8}[self.protocol]
        region_base = {"us-east": 500, "eu-west": 420, "ap-south": 350}[self.region]
        self.throughput = region_base * proto_factor + random.gauss(0, 0.15 * 50)
        return super().__call__()


def example_sweep_0_float_2_cat_with_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """0 Float, 2 Categorical (with repeats)."""
    bench = NetworkConfig().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["protocol", "region"],
        result_vars=["throughput"],
        description=(
            "A 0 float + 2 categorical parameter sweep with multiple repeats per combination. "
            "Repeating measurements reveals the noise structure of your benchmark. If your "
            "function is deterministic, all repeats will be identical; if it has stochastic "
            "components, repeats let you estimate confidence intervals and distinguish signal "
            "from noise. The benchmark function must be pure -- if past calls affect future "
            "calls through side effects, the statistics will be invalid. Categorical-only "
            "sweeps produce bar/swarm plots comparing discrete settings."
        ),
        post_description=(
            "Swarm/violin plots show the distribution of repeated measurements. If repeat has "
            "high variance, it suggests either measurement noise or unintended side effects "
            "in the benchmark function."
        ),
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_0_float_2_cat_with_repeats, level=4, repeats=10)
