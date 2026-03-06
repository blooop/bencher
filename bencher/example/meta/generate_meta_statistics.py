"""Meta-generator: Statistics & Repeats.

Shows progression from single sample to error bars to distributions.
"""

import textwrap
from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "statistics"

NOISY_TIMER_CLASS = textwrap.dedent("""\
    class NoisyTimer(bch.ParametrizedSweep):
        \"\"\"Simulates request timing with configurable measurement noise.\"\"\"

        endpoint = bch.StringSweep(["api/users", "api/orders", "api/search"], doc="API endpoint")
        load = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Server load factor")

        latency = bch.ResultVar(units="ms", doc="Request latency")

        noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Measurement noise")

        def __call__(self, **kwargs):
            self.update_params_from_kwargs(**kwargs)
            base = {"api/users": 45, "api/orders": 80, "api/search": 120}[self.endpoint]
            self.latency = base * (1 + 2 * self.load) + 5 * math.sin(math.pi * self.load * 3)
            if self.noise_scale > 0:
                self.latency += __import__('random').gauss(0, self.noise_scale * base * 0.3)
            return super().__call__()\
""")


class MetaStatistics(MetaGeneratorBase):
    """Generate Python examples demonstrating repeat-based statistics."""

    repeats = bch.IntSweep(default=1, bounds=(1, 100), doc="Number of repeats")
    input_dims = bch.IntSweep(default=0, bounds=(0, 1), doc="0 = categorical only, 1 = float sweep")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        dim_label = "0d_categorical" if self.input_dims == 0 else "1d_float"
        filename = f"stats_{dim_label}_repeats_{self.repeats}"
        function_name = f"example_stats_{dim_label}_repeats_{self.repeats}"
        title = (
            f"Statistics: {self.repeats} repeat(s), "
            f"{'categorical' if self.input_dims == 0 else '1D float'}"
        )

        input_vars_code = '["endpoint"]' if self.input_dims == 0 else '["load"]'
        const_vars = "dict(noise_scale=0.15)" if self.repeats > 1 else None

        run_kwargs = {"level": 3}
        if self.repeats > 1:
            run_kwargs["repeats"] = self.repeats

        self.generate_sweep_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            function_name=function_name,
            benchable_class="NoisyTimer",
            benchable_module=None,
            input_vars=input_vars_code,
            result_vars='["latency"]',
            class_code=NOISY_TIMER_CLASS,
            const_vars=const_vars,
            extra_imports=["import math"],
            run_kwargs=run_kwargs,
        )

        return super().__call__()


def example_meta_statistics(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = MetaStatistics().to_bench(run_cfg)

    bench.plot_sweep(
        title="Statistics: categorical only",
        input_vars=[bch.p("repeats", [1, 5, 20]), bch.p("input_dims", [0])],
    )
    bench.plot_sweep(
        title="Statistics: 1D float sweep",
        input_vars=[bch.p("repeats", [1, 5, 20]), bch.p("input_dims", [1])],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_meta_statistics)
