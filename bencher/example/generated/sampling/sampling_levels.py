"""Auto-generated example: Sampling: Levels."""

import math
import bencher as bch


class LevelDemo(bch.ParametrizedSweep):
    """Demonstrates how sampling level affects resolution."""

    resolution = bch.IntSweep(default=2, bounds=(2, 5), doc="Sampling resolution level")
    points = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Sample point")

    value = bch.ResultVar(units="ul")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.value = math.sin(self.points * math.pi * self.resolution) + self.resolution * 0.1
        return super().__call__()


def example_sampling_levels(run_cfg=None):
    """Sampling: Levels."""
    bench = LevelDemo().to_bench(run_cfg)
    bench.plot_sweep(
        title="Level-based sampling resolution",
        input_vars=[
            "points",
            bch.p("resolution", [2, 3, 4, 5]),
        ],
        result_vars=["value"],
        description="The level parameter controls how many samples are taken along each axis. Higher levels give finer resolution but take longer.",
    )

    return bench


if __name__ == "__main__":
    bch.run(example_sampling_levels, level=3)
