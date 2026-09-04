"""Auto-generated example: Rerun Backend — a whole sweep, scalars and recordings, in rerun."""

import rerun as rr

import bencher as bn


class RerunBackendSweep(bn.ParametrizedSweep):
    """A scalar metric and a recording per sample, both rendered in rerun.

    Each sample voxelizes one primitive on a lattice spanning a 2x2x2 box: the
    occupied fraction is the measured volume, and the occupied lattice points
    are the recorded geometry.  So the scalar and the recording are two views of
    the same sample, which is what makes them worth having in one report.
    """

    shape = bn.StringSweep(["cube", "sphere", "cone"], doc="Primitive being measured")

    out_volume = bn.ResultFloat(units="m3", doc="Voxelized volume of the primitive")
    out_rerun = bn.ResultRerun(width=900, height=420)

    def benchmark(self):
        inside = {
            "cube": lambda x, y, z: True,
            "sphere": lambda x, y, z: x * x + y * y + z * z <= 1.0,
            # Apex at z=+1, unit-radius base at z=-1.
            "cone": lambda x, y, z: x * x + y * y <= (1.0 - z) ** 2 / 4,
        }[self.shape]

        steps = 12
        axis = [2 * i / (steps - 1) - 1 for i in range(steps)]
        points = [[x, y, z] for x in axis for y in axis for z in axis if inside(x, y, z)]
        self.out_volume = 8.0 * len(points) / steps**3

        recording = rr.RecordingStream("rerun_backend_sample", make_default=False)
        recording.log(
            self.shape,
            rr.Points3D(points, radii=0.03, colors=[110, 170, 240]),
            static=True,
        )
        self.out_rerun = bn.capture_rerun_rrd(recording)
        return super().benchmark()


def example_rerun_backend(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Backend — a whole sweep, scalars and recordings, in rerun."""
    if run_cfg is None:
        run_cfg = bn.BenchRunCfg()
    run_cfg.backend = "rerun"

    bench = RerunBackendSweep().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["shape"],
        result_vars=["out_volume", "out_rerun"],
        description="Setting ``backend`` to ``rerun`` on the run config renders the "
        "whole report in the rerun viewer instead of holoviews.  ``out_volume`` is "
        "mapped onto rerun's entity tree as a BarChart over the swept categories; "
        "``out_rerun`` already *is* rerun data, so its three per-sample recordings "
        "are merged into one recording and Blueprint, the same composition "
        "``rerun_grid`` performs.",
        post_description="The two families need different machinery: everything scalar "
        "is mapped onto native archetypes, while a ``ResultRerun`` is composed from the "
        "``.rrd`` each sample cached.  Passing a recording through the scalar renderers "
        "used to drop it from the report entirely.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_backend)
