from typing import Any
import bencher as bch

from enum import auto
from strenum import StrEnum
import random
import holoviews as hv
import math


class FunctionVariant(StrEnum):
    """A categorical variable selecting sub-function within a family"""

    alpha = auto()  # first function variant
    beta = auto()  # second function variant


class BenchableObject(bch.ParametrizedSweep):
    """A benchable object with dimension-aware math functions that produce visually distinct plots."""

    # floating point variables
    float1 = bch.FloatSweep(default=0, bounds=[0, 1.0], doc="x coordinate of the sample volume")
    float2 = bch.FloatSweep(default=0, bounds=[0, 1.0], doc="y coordinate of the sample volume")
    float3 = bch.FloatSweep(default=0, bounds=[0, 1.0], doc="z coordinate of the sample volume")

    # categorical variables
    wave = bch.BoolSweep(
        default=True, doc="Toggle between wave (trig) and peak (polynomial) function families"
    )
    variant = bch.EnumSweep(FunctionVariant, doc=FunctionVariant.__doc__)

    transform = bch.StringSweep(["normal", "inverted"])

    distance = bch.ResultVar("m", doc="The distance from the sample point to the origin")
    sample_noise = bch.ResultVar("m", doc="The amount of noise added to the distance sample")

    result_hmap = bch.ResultHmap()

    # Class attributes set by BenchMeta/BenchMetaGen before sweep
    active_dims = 0  # number of active float dimensions
    noise_scale = 0.0  # signal-proportional noise scale (0.0 = deterministic)
    _time_offset = 0.0  # offset added to output for over-time support

    def _compute_0d(self):
        """0D: distinct scalar values per category combination."""
        if self.wave:
            return 3.0 if self.variant == FunctionVariant.alpha else 7.0
        return 5.0 if self.variant == FunctionVariant.alpha else 2.0

    def _compute_1d(self):
        """1D functions of float1 (x in [0,1])."""
        x = self.float1
        if self.wave:
            if self.variant == FunctionVariant.alpha:
                return math.sin(2 * math.pi * x)
            return math.sin(2 * math.pi * x) + 0.5 * math.sin(6 * math.pi * x)
        if self.variant == FunctionVariant.alpha:
            return math.exp(-((x - 0.5) ** 2) / 0.02)
        return 4 * x * (1 - x)

    def _compute_2d(self):
        """2D functions of float1, float2 (x,y in [0,1])."""
        x, y = self.float1, self.float2
        if self.wave:
            if self.variant == FunctionVariant.alpha:
                return math.sin(2 * math.pi * x) * math.cos(2 * math.pi * y)
            return math.sin(math.pi * (x + y)) * math.cos(math.pi * (x - y))
        if self.variant == FunctionVariant.alpha:
            return math.exp(-((x - 0.5) ** 2 + (y - 0.5) ** 2) / 0.04)
        return (x - 0.5) ** 2 - (y - 0.5) ** 2

    def _compute_3d(self):
        """3D functions of float1, float2, float3 (x,y,z in [0,1])."""
        x, y, z = self.float1, self.float2, self.float3
        if self.wave:
            if self.variant == FunctionVariant.alpha:
                return (
                    math.sin(2 * math.pi * x)
                    * math.sin(2 * math.pi * y)
                    * math.sin(2 * math.pi * z)
                )
            return math.sin(math.pi * (x + y + z)) * math.cos(math.pi * (x - y))
        if self.variant == FunctionVariant.alpha:
            # Spherical shell at r=0.3 from center
            r = math.sqrt((x - 0.5) ** 2 + (y - 0.5) ** 2 + (z - 0.5) ** 2)
            return math.exp(-((r - 0.3) ** 2) / 0.01)
        # Two Gaussian blobs
        d1 = (x - 0.3) ** 2 + (y - 0.3) ** 2 + (z - 0.3) ** 2
        d2 = (x - 0.7) ** 2 + (y - 0.7) ** 2 + (z - 0.7) ** 2
        return math.exp(-d1 / 0.03) + math.exp(-d2 / 0.03)

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        dims = self.active_dims
        if dims == 0:
            self.distance = self._compute_0d()
        elif dims == 1:
            self.distance = self._compute_1d()
        elif dims == 2:
            self.distance = self._compute_2d()
        else:
            self.distance = self._compute_3d()

        # Apply transform
        if self.transform == "inverted":
            if dims == 0:
                self.distance = 10.0 - self.distance
            else:
                self.distance *= -1

        # Apply noise
        self.sample_noise = 0.0
        if self.noise_scale > 0:
            self.sample_noise = random.gauss(0, self.noise_scale * max(abs(self.distance), 0.1))
            self.distance += self.sample_noise

        # Apply time offset
        self.distance += self._time_offset

        self.result_hmap = hv.Text(
            x=0, y=0, text=f"distance:{self.distance}\nnoise:{self.sample_noise}"
        )

        return super().__call__()


class BenchMeta(bch.ParametrizedSweep):
    """This class uses bencher to display the multidimensional types bencher can represent"""

    float_vars = bch.IntSweep(
        default=0, bounds=(0, 3), doc="The number of floating point variables that are swept"
    )
    categorical_vars = bch.IntSweep(
        default=0, bounds=(0, 3), doc="The number of categorical variables that are swept"
    )
    sample_with_repeats = bch.IntSweep(default=1, bounds=(1, 10))

    sample_over_time = bch.BoolSweep(default=False)

    level = bch.IntSweep(default=2, units="level", bounds=(2, 5))

    plots = bch.ResultReference(units="int")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        run_cfg = bch.BenchRunCfg()
        run_cfg.level = self.level
        run_cfg.repeats = self.sample_with_repeats
        run_cfg.over_time = self.sample_over_time
        run_cfg.plot_size = 500

        benchable = BenchableObject()
        benchable.active_dims = self.float_vars
        if self.sample_with_repeats > 1:
            benchable.noise_scale = 0.15

        bench = bch.Bench("benchable", benchable, run_cfg=run_cfg)

        inputs_vars_float = [
            "float1",
            "float2",
            "float3",
        ]

        inputs_vars_cat = [
            "wave",
            "variant",
            "transform",
        ]

        input_vars = (
            inputs_vars_float[0 : self.float_vars] + inputs_vars_cat[0 : self.categorical_vars]
        )

        if self.sample_over_time:
            benchable.noise_scale = max(benchable.noise_scale, 0.1)
            time_events = [
                ("t0", 0.0),
                ("t1", 0.3),
                ("t2", 0.7),
                ("t3", 1.0),
            ]
            for i, (event, offset) in enumerate(time_events):
                benchable._time_offset = offset
                run_cfg.time_event = event
                run_cfg.clear_cache = True
                run_cfg.clear_history = i == 0
                res = bench.plot_sweep(
                    event,
                    input_vars=input_vars,
                    result_vars=["distance"],
                    plot_callbacks=False,
                    run_cfg=run_cfg,
                )
        else:
            res = bench.plot_sweep(
                "test",
                input_vars=input_vars,
                result_vars=["distance"],
                plot_callbacks=False,
            )

        self.plots = bch.ResultReference()
        self.plots.obj = res.to_auto()

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
            "sample_over_time",
        ],
        const_vars=[],
    )

    return bench


if __name__ == "__main__":
    example_meta().report.show()
