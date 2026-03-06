"""Auto-generated example: Bar Chart — Inline Class Definition."""

import bencher as bch


class ServerBenchmark(bch.ParametrizedSweep):
    """Compares response times across different server configurations.

    This example sweeps a categorical variable (server region) and records
    a scalar metric, producing a bar chart. Define your own categories as
    a StringSweep or EnumSweep.
    """

    region = bch.StringSweep(
        ["us-east", "us-west", "eu-west", "ap-south"],
        doc="Cloud region for the deployment",
    )

    latency = bch.ResultVar(units="ms", doc="Average response latency")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        # Simulated latencies per region
        region_latency = {
            "us-east": 45.0,
            "us-west": 62.0,
            "eu-west": 120.0,
            "ap-south": 180.0,
        }
        self.latency = region_latency[self.region]
        return super().__call__()


def example_flagship_bar_chart(run_cfg=None):
    """Bar Chart — Inline Class Definition."""
    bench = ServerBenchmark().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["region"],
        result_vars=["latency"],
        description="Sweep a categorical variable to produce a bar chart. "
        "Each category is evaluated once and the result plotted as a bar.",
        post_description="US-East has the lowest latency. In a real scenario you would "
        "add repeats to capture variance across measurements.",
    )

    return bench


if __name__ == "__main__":
    bch.run(example_flagship_bar_chart, level=4)
