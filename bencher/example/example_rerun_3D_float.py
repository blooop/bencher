"""Rerun backend: 3D float sweep example.

Demonstrates three FloatSweep dimensions mapped to three independent rerun
timelines. Each axis can be scrubbed independently, slicing through the
3D scalar field.
"""

import numpy as np
import bencher as bch


class Rerun3DFloat(bch.ParametrizedSweep):
    x = bch.FloatSweep(default=0, bounds=[-1.0, 1.0], doc="x coordinate", samples=4)
    y = bch.FloatSweep(default=0, bounds=[-1.0, 1.0], doc="y coordinate", samples=5)
    z = bch.FloatSweep(default=0, bounds=[-1.0, 1.0], doc="z coordinate", samples=6)

    distance = bch.ResultVar("ul", doc="Distance to the origin")
    field = bch.ResultVar("ul", doc="sin(pi*x)*cos(pi*z)*sin(pi*y)")

    def __call__(self, **kwargs) -> dict:
        self.update_params_from_kwargs(**kwargs)
        self.distance = float(np.linalg.norm([self.x, self.y, self.z]))
        self.field = float(np.sin(np.pi * self.x) * np.cos(np.pi * self.z) * np.sin(np.pi * self.y))
        return super().__call__(**kwargs)


def example_rerun_3D_float(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """3D float sweep → rerun: x, y, z become three independent timelines."""
    bench = Rerun3DFloat().to_bench(run_cfg)
    bench.plot_sweep(
        title="Rerun 3D Float Example",
        result_vars=["distance", "field"],
    )
    return bench


if __name__ == "__main__":
    bch.run_flask_in_thread()
    bench = example_rerun_3D_float(bch.BenchRunCfg(level=3))
    bench.get_result().to_rerun().show()
