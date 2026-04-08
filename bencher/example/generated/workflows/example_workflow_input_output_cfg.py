"""Auto-generated example: InputCfg/OutputCfg — separated input and output classes."""

import math
import bencher as bn


class ServerMetrics(bn.ParametrizedSweep):
    """Output metrics from the server benchmark."""

    throughput = bn.ResultFloat(
        units="req/s", direction=bn.OptDir.maximize, doc="Request throughput"
    )
    latency = bn.ResultFloat(units="ms", direction=bn.OptDir.minimize, doc="Response latency")


class ServerConfig(bn.ParametrizedSweep):
    """Server configuration parameters.

    The static bench_function method takes a ServerConfig instance and
    returns a ServerMetrics instance. This separation makes it clear
    which variables are inputs and which are outputs.
    """

    worker_count = bn.FloatSweep(default=4, bounds=[1, 32], doc="Number of worker threads")
    cache_size = bn.StringSweep(["small", "medium", "large"], doc="Cache tier size")

    @staticmethod
    def bench_function(cfg: "ServerConfig") -> ServerMetrics:
        """Simulate a server benchmark with the given configuration."""
        output = ServerMetrics()
        size_factor = {"small": 0.7, "medium": 1.0, "large": 1.3}[cfg.cache_size]
        output.throughput = 100 * math.sqrt(cfg.worker_count) * size_factor
        output.latency = 500 / max(output.throughput, 1)
        return output


def example_workflow_input_output_cfg(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """InputCfg/OutputCfg — separated input and output classes."""
    # The Bench constructor accepts the static function and the ServerConfig class.
    # This is an alternative to the ParametrizedSweep.benchmark() pattern.
    bench = bn.Bench("input_output_example", ServerConfig.bench_function, ServerConfig, run_cfg)
    bench.plot_sweep(
        input_vars=[ServerConfig.param.worker_count],
        result_vars=[ServerMetrics.param.throughput, ServerMetrics.param.latency],
        description="The InputCfg/OutputCfg pattern separates input parameters from "
        "result metrics into distinct classes. The benchmark function is a static "
        "method on ServerConfig that returns a ServerMetrics instance.",
    )
    bench.plot_sweep(
        input_vars=[ServerConfig.param.worker_count, ServerConfig.param.cache_size],
        result_vars=[ServerMetrics.param.throughput],
        description="A 2D sweep combining a continuous and categorical input. "
        "Each cache size produces a different throughput curve over worker counts.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_workflow_input_output_cfg, level=3)
