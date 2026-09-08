"""Auto-generated example: Rerun Timeline — scrub a 1-D sweep on the time axis."""

import math

import rerun as rr

import bencher as bn


class ArmPoseSweep(bn.ParametrizedSweep):
    """Forward kinematics of a two-link planar arm.

    Each sample logs one static pose -- there is no time inside a sample, so the
    only thing worth scrubbing is the sweep itself.
    """

    shoulder = bn.FloatSweep(
        default=0.0, bounds=[0.0, 2.4], doc="Shoulder joint angle", units="rad", samples=13
    )

    out_reach = bn.ResultFloat(units="m", doc="Distance from the base to the tool tip")
    out_rerun = bn.ResultRerun(width=900, height=520)

    def benchmark(self):
        upper, fore = 1.0, 1.0
        elbow = self.shoulder * 1.7
        joint = (upper * math.cos(self.shoulder), upper * math.sin(self.shoulder))
        tip = (
            joint[0] + fore * math.cos(self.shoulder + elbow),
            joint[1] + fore * math.sin(self.shoulder + elbow),
        )
        self.out_reach = math.hypot(*tip)

        recording = rr.RecordingStream("arm_pose_sample", make_default=False)
        recording.log("arm/links", rr.LineStrips2D([[(0.0, 0.0), joint, tip]], radii=0.03))
        recording.log("arm/joints", rr.Points2D([(0.0, 0.0), joint], radii=0.06))
        recording.log("arm/tip", rr.Points2D([tip], radii=0.08, colors=[240, 140, 90]))
        self.out_rerun = bn.capture_rerun_rrd(recording)
        return super().benchmark()


def example_rerun_timeline_1d(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Timeline — scrub a 1-D sweep on the time axis."""
    bench = ArmPoseSweep().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["shoulder"],
        result_vars=["out_reach", "out_rerun"],
        description="Every sample records its own ``.rrd`` holding one static pose, so the "
        "per-sample viewers have nothing to play and ``rerun_summary`` has nothing "
        "to splice.  ``rerun_timeline`` instead makes the swept parameter itself the "
        "time axis: all 13 poses are written to ONE recording at the same entity "
        "paths, indexed by a rerun timeline named ``shoulder`` carrying the "
        "parameter's own values.  Dragging the time cursor sweeps the arm.",
        post_description="A numeric sweep variable is encoded as a duration index, one second per "
        "unit, so the axis reads back the parameter values and keeps their spacing "
        "even when the sweep is not uniform.  Pass "
        "``index=bn.TimelineIndex.sequence`` to number the samples 0, 1, 2 instead -- "
        "which is what a categorical sweep gets automatically.",
        plot_callbacks=[bn.BenchResult.to_rerun_timeline],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_timeline_1d)
