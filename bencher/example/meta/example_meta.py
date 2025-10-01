from typing import Any
import bencher as bch
import numpy as np

from enum import auto
from strenum import StrEnum
import random
import holoviews as hv
import math


class NoiseDistribution(StrEnum):
    """A categorical variable describing the types of random noise"""

    uniform = auto()  # uniform random noiase
    gaussian = auto()  # gaussian noise

    @staticmethod
    def calculate_noise(noisy, noise_distribution, sigma) -> float:
        if noisy:
            match noise_distribution:
                case NoiseDistribution.uniform:
                    return random.uniform(-sigma / 2.0, sigma / 2)
                case NoiseDistribution.gaussian:
                    return random.gauss(0, sigma)
        return 0.0


class BenchableObject(bch.ParametrizedSweep):
    """A class to represent a 3D point in space."""

    # floating point variables
    float1 = bch.FloatSweep(default=0, bounds=[0, 1.0], doc="x coordinate of the sample volume")
    float2 = bch.FloatSweep(default=0, bounds=[0, 1.0], doc="y coordinate of the sample volume")
    float3 = bch.FloatSweep(default=0, bounds=[0, 1.0], doc="z coordinate of the sample volume")

    sigma = bch.FloatSweep(default=0.2, bounds=[0, 10], doc="standard deviation of the added noise")

    # categorial variables
    noisy = bch.BoolSweep(
        default=False, doc="Optionally add random noise to the output of the function"
    )
    noise_distribution = bch.EnumSweep(NoiseDistribution, doc=NoiseDistribution.__doc__)

    negate_output = bch.StringSweep(["positive", "negative"])

    distance = bch.ResultVar("m", doc="The distance from the sample point to the origin")
    sample_noise = bch.ResultVar("m", doc="The amount of noise added to the distance sample")
    is_far_from_origin = bch.ResultBool(doc="Whether the distance from origin exceeds threshold")

    result_hmap = bch.ResultHmap()
    # result_im
    ##todo all var types

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        # distance to origin
        self.distance = math.pow(
            np.linalg.norm(np.array([self.float1, self.float2, self.float3])), 2
        )
        self.sample_noise = NoiseDistribution.calculate_noise(
            self.noisy, self.noise_distribution, self.sigma
        )

        self.distance += self.sample_noise

        if self.negate_output == "negative":
            self.distance *= -1

        # Boolean result: consider "far" if distance > 0.5
        self.is_far_from_origin = abs(self.distance) > 0.5

        self.result_hmap = hv.Text(
            x=0,
            y=0,
            text=f"distance:{self.distance}\nnoise:{self.sample_noise}\nfar:{self.is_far_from_origin}",
        )

        return super().__call__()


class BenchMeta(bch.ParametrizedSweep):
    """This class uses bencher to display the multidimensional types bencher can represent"""

    float_vars = bch.IntSweep(
        default=0, bounds=(0, 4), doc="The number of floating point variables that are swept"
    )
    categorical_vars = bch.IntSweep(
        default=0, bounds=(0, 3), doc="The number of categorical variables that are swept"
    )
    sample_with_repeats = bch.IntSweep(default=1, bounds=(1, 10))

    sample_over_time = bch.BoolSweep(default=False)

    level = bch.IntSweep(default=2, units="level", bounds=(2, 5))

    # plots = bch.ResultHmap()
    # plots = bch.ResultContainer()
    plots = bch.ResultReference(units="int")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        run_cfg = bch.BenchRunCfg()
        run_cfg.level = self.level
        run_cfg.repeats = self.sample_with_repeats
        run_cfg.over_time = self.sample_over_time
        run_cfg.plot_size = 500

        bench = bch.Bench("benchable", BenchableObject(), run_cfg=run_cfg)

        inputs_vars_float = [
            "float1",
            "float2",
            "float3",
            "sigma",
        ]

        inputs_vars_cat = [
            "noisy",
            "noise_distribution",
            "negate_output",
        ]

        input_vars = (
            inputs_vars_float[0 : self.float_vars] + inputs_vars_cat[0 : self.categorical_vars]
        )

        res = bench.plot_sweep(
            "test",
            input_vars=input_vars,
            result_vars=["distance", "is_far_from_origin"],
            # result_vars=["distance", "sample_noise"],
            # result_vars=["sample_noise"],
            # result_vars=["result_hmap"],
            plot_callbacks=False,
        )

        self.plots = bch.ResultReference()
        self.plots.obj = res.to_auto()

        # self.plots.obj = res.to_heatmap_multi()

        # self.plots.obj = res.to_line_multi(width=500, height=300)

        return super().__call__()


def example_meta(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = BenchMeta().to_bench(run_cfg)

    bench.plot_sweep(
        title="Meta Bench",
        description="""## All Combinations of Variable Sweeps and Resulting Plots
This uses bencher to display all the combinations of plots bencher is able to produce""",
        input_vars=[
            bch.p("float_vars", [0, 1, 2, 3]),
            "categorical_vars",
            bch.p("sample_with_repeats", [1, 2]),
            # "sample_over_time",
        ],
        const_vars=[
            # ("float_vars", 1),
            # ("sample_with_repeats", 2),
            # ("categorical_vars", 2),
            # ("sample_over_time", True),
        ],
    )

    return bench


if __name__ == "__main__":
    example_meta().report.show()
