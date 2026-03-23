"""Auto-generated example: Sampling: Levels."""

from typing import Any

import math
import bencher as bn


class LevelDemo(bn.ParametrizedSweep):
    """Demonstrates how sampling level affects resolution."""

    resolution = bn.IntSweep(default=2, bounds=(2, 5), doc="Sampling resolution level")
    points = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Sample point")

    value = bn.ResultVar(units="ul")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.value = math.sin(self.points * math.pi * self.resolution) + self.resolution * 0.1
        return super().__call__()


def example_sampling_levels(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Sampling: Levels."""
    bench = LevelDemo().to_bench(run_cfg)
    bench.plot_sweep(
        title="Level-based sampling resolution",
        input_vars=[
            "points",
            bn.p("resolution", [2, 3, 4, 5]),
        ],
        result_vars=["value"],
        description="Sample levels let you perform parameter sweeps without having to decide how many samples to take when defining the class. If you perform a sweep at level 2, all those points are reused when sampling at level 3. Higher levels reuse the points from lower levels to avoid recomputing potentially expensive samples. This enables a workflow where you quickly see results at low resolution to sense-check the code, then run at a high level for full fidelity. When calling a sweep at a high level you can publish intermediate lower-level results as computation continues, letting you track progress and end the sweep early when you have sufficient resolution.",
        post_description="Each column shows the same function sampled at a different resolution level. Notice how lower-level sample points are a subset of higher-level points -- no work is wasted.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sampling_levels, level=3)
