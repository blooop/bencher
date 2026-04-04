from datetime import datetime, timedelta

import bencher as bn

from enum import auto
from strenum import StrEnum
import random
import holoviews as hv
import math


class FunctionVariant(StrEnum):
    """A categorical variable selecting sub-function within a family"""

    alpha = auto()  # first function variant
    beta = auto()  # second function variant


class BenchableObject(bn.ParametrizedSweep):
    """A benchable object with a single parametric function that produces visually distinct plots.

    Categories control the function's frequency and phase. The same formula is evaluated regardless
    of how many float dimensions are swept - unused dimensions stay at their defaults, naturally
    slicing the function at different dimensionalities.
    """

    # floating point variables
    float1 = bn.FloatSweep(default=0, bounds=[0, 1.0], doc="x coordinate of the sample volume")
    float2 = bn.FloatSweep(default=0, bounds=[0, 1.0], doc="y coordinate of the sample volume")
    float3 = bn.FloatSweep(default=0, bounds=[0, 1.0], doc="z coordinate of the sample volume")

    # categorical variables
    wave = bn.BoolSweep(
        default=True, doc="High frequency oscillation (True) vs low frequency smooth (False)"
    )
    variant = bn.EnumSweep(FunctionVariant, doc=FunctionVariant.__doc__)

    transform = bn.StringSweep(["normal", "inverted"])

    distance = bn.ResultFloat("m", doc="The distance from the sample point to the origin")
    sample_noise = bn.ResultFloat("m", doc="The amount of noise added to the distance sample")

    result_hmap = bn.ResultHmap()

    noise_scale = bn.FloatSweep(
        default=0.0, bounds=[0.0, 1.0], doc="Signal-proportional noise scale (0 = deterministic)"
    )
    _time_offset = 0.0  # offset added to output for over-time support

    def benchmark(self):
        x, y, z = self.float1, self.float2, self.float3

        # Map categoricals to continuous parameters that shape the function.
        # _time_offset acts as a phase shift so over-time plots show genuinely
        # different patterns rather than a constant vertical offset.
        freq = 3.0 if self.wave else 1.0
        phase = (0.0 if self.variant == FunctionVariant.alpha else math.pi / 2) + self._time_offset

        # Single parametric function - categories control freq and phase,
        # dimensionality is just which floats get swept vs held at default.
        # The freq coefficient on the first term ensures distinct values even at (0,0,0).
        self.distance = (
            freq * math.sin(freq * math.pi * x + phase + 0.5)
            + math.cos(freq * 0.7 * math.pi * y + phase * 1.3 + 0.3)
            + 0.7 * math.sin(freq * 0.5 * math.pi * z + phase * 0.7 + 0.7)
            + 0.3 * math.sin(freq * math.pi * (x * y + z * 0.5) + phase * 0.5)
        )

        if self.transform == "inverted":
            self.distance *= -1

        # Apply noise
        self.sample_noise = 0.0
        if self.noise_scale > 0:
            self.sample_noise = random.gauss(0, self.noise_scale * max(abs(self.distance), 0.1))
            self.distance += self.sample_noise

        self.result_hmap = hv.Text(
            x=0, y=0, text=f"distance:{self.distance}\nnoise:{self.sample_noise}"
        )


class BenchMeta(bn.ParametrizedSweep):
    """This class uses bencher to display the multidimensional types bencher can represent"""

    float_vars = bn.IntSweep(
        default=0, bounds=(0, 3), doc="The number of floating point variables that are swept"
    )
    categorical_vars = bn.IntSweep(
        default=0, bounds=(0, 3), doc="The number of categorical variables that are swept"
    )
    sample_with_repeats = bn.IntSweep(default=1, bounds=(1, 10))

    sample_over_time = bn.BoolSweep(default=False)

    level = bn.IntSweep(default=2, units="level", bounds=(2, 5))

    plots = bn.ResultReference(units="int")

    def benchmark(self):
        run_cfg = bn.BenchRunCfg()
        run_cfg.level = self.level
        run_cfg.repeats = self.sample_with_repeats
        run_cfg.over_time = self.sample_over_time
        run_cfg.plot_size = 500

        benchable = BenchableObject()
        noise = 0.15 if self.sample_with_repeats > 1 else 0.0

        bench = bn.Bench("benchable", benchable, run_cfg=run_cfg)

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
            noise = max(noise, 0.1)
            time_offsets = [0.0, 0.3, 0.7, 1.0]
            base_time = datetime(2000, 1, 1)
            for i, offset in enumerate(time_offsets):
                benchable._time_offset = offset  # pylint: disable=protected-access
                run_cfg.clear_cache = True
                run_cfg.clear_history = i == 0
                res = bench.plot_sweep(
                    "over_time",
                    input_vars=input_vars,
                    result_vars=["distance"],
                    const_vars=dict(noise_scale=noise),
                    plot_callbacks=False,
                    run_cfg=run_cfg,
                    time_src=base_time + timedelta(seconds=i),
                )
        else:
            res = bench.plot_sweep(
                "test",
                input_vars=input_vars,
                result_vars=["distance"],
                const_vars=dict(noise_scale=noise),
                plot_callbacks=False,
            )

        self.plots = bn.ResultReference()
        self.plots.obj = res.to_auto()


def example_meta(
    run_cfg: bn.BenchRunCfg | None = None, sample_repeats_values: list[int] | None = None
) -> bn.Bench:
    if sample_repeats_values is None:
        sample_repeats_values = [1, 10]
    sample_repeats_values = tuple(sample_repeats_values)

    bench = BenchMeta().to_bench(run_cfg)

    bench.plot_sweep(
        title="0 Float Inputs",
        description="""Categorical-only sweeps with 0 float variables.
Each category combination produces a distinct scalar value from the unified function evaluated at
the default float point (0,0,0).""",
        input_vars=[
            "categorical_vars",
            bn.sweep("sample_with_repeats", sample_repeats_values),
            "sample_over_time",
        ],
        const_vars=dict(float_vars=0),
    )

    bench.plot_sweep(
        title="1 Float Input",
        description="""Sweeps over float1, producing 1D line/curve plots.
Categories shift the frequency and phase of the underlying function, producing visually distinct
curves.""",
        input_vars=[
            "categorical_vars",
            bn.sweep("sample_with_repeats", sample_repeats_values),
            "sample_over_time",
        ],
        const_vars=dict(float_vars=1),
    )

    bench.plot_sweep(
        title="2 Float Inputs",
        description="""Sweeps over float1 and float2, producing 2D heatmap/surface plots.
The unified function creates interesting 2D patterns that vary with category selection.""",
        input_vars=[
            "categorical_vars",
            bn.sweep("sample_with_repeats", sample_repeats_values),
            "sample_over_time",
        ],
        const_vars=dict(float_vars=2),
    )

    bench.plot_sweep(
        title="3 Float Inputs",
        description="""Sweeps over all three float variables, producing 3D volume plots.
The full 3D function with all cross-coupling terms active.""",
        input_vars=[
            "categorical_vars",
            bn.sweep("sample_with_repeats", sample_repeats_values),
            "sample_over_time",
        ],
        const_vars=dict(float_vars=3),
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta)
