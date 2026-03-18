"""Auto-generated example: 0 Float, 2 Categorical."""

from typing import Any

import bencher as bch

class NetworkConfig(bch.ParametrizedSweep):
    """Measures throughput across protocol and region combinations."""

    protocol = bch.StringSweep(["http", "grpc"], doc="Network protocol")
    region = bch.StringSweep(["us-east", "eu-west", "ap-south"], doc="Deployment region")

    throughput = bch.ResultVar(units="req/s", doc="Request throughput")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        proto_factor = {"http": 1.0, "grpc": 1.8}[self.protocol]
        region_base = {"us-east": 500, "eu-west": 420, "ap-south": 350}[self.region]
        self.throughput = region_base * proto_factor
        return super().__call__()


def example_no_repeats_0_float_2_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """0 Float, 2 Categorical."""
    bench = NetworkConfig().to_bench(run_cfg)
    bench.plot_sweep(input_vars=['protocol', 'region'], result_vars=['throughput'])

    return bench


if __name__ == "__main__":
    bch.run(example_no_repeats_0_float_2_cat, level=4)
