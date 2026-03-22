"""Auto-generated example: 0 Float, 3 Categorical."""

from typing import Any

import random

import bencher as bn


class DeploymentConfig(bn.ParametrizedSweep):
    """Full config matrix: protocol, region, and log level."""

    protocol = bn.StringSweep(["http", "grpc"], doc="Network protocol")
    region = bn.StringSweep(["us-east", "eu-west", "ap-south"], doc="Deployment region")
    log_level = bn.StringSweep(["debug", "info", "warn"], doc="Logging level")

    throughput = bn.ResultVar(units="req/s", doc="Request throughput")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        proto_factor = {"http": 1.0, "grpc": 1.8}[self.protocol]
        region_base = {"us-east": 500, "eu-west": 420, "ap-south": 350}[self.region]
        log_penalty = {"debug": 0.7, "info": 1.0, "warn": 1.0}[self.log_level]
        self.throughput = region_base * proto_factor * log_penalty + random.gauss(0, 0.15 * 50)
        return super().__call__()


def example_with_repeats_0_float_3_cat(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """0 Float, 3 Categorical."""
    bench = DeploymentConfig().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["protocol", "region", "log_level"], result_vars=["throughput"])

    return bench


if __name__ == "__main__":
    bn.run(example_with_repeats_0_float_3_cat, level=4, repeats=10)
