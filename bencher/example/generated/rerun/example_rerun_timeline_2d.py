"""Auto-generated example: Rerun Timeline 2D — one dimension animates, the rest tile."""

import math
from functools import partial

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
    link_ratio = bn.FloatSweep(
        default=0.6,
        bounds=[0.4, 1.0],
        doc="Forearm length as a fraction of the upper arm",
        samples=3,
    )

    out_reach = bn.ResultFloat(units="m", doc="Distance from the base to the tool tip")
    out_rerun = bn.ResultRerun(width=900, height=520)

    def benchmark(self):
        upper, fore = 1.0, self.link_ratio
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


def example_rerun_timeline_2d(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Timeline 2D — one dimension animates, the rest tile."""
    bench = ArmPoseSweep().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["shoulder", "link_ratio"],
        result_vars=["out_reach", "out_rerun"],
        description="Rerun timelines are independent axes, not a joint index: a latest-at query "
        "resolves on the timeline being viewed and ignores every other one, so two "
        "swept variables cannot become two scrubbers.  Exactly one dimension can be "
        "time.  Here ``shoulder`` is it, and ``link_ratio`` is peeled onto the entity "
        "tree instead -- one branch and one Blueprint view per forearm length.",
        post_description="That is how the mapping scales: one dimension animates, the rest tile.  A "
        "3-D sweep gives a grid of views over the two peeled dimensions, all driven "
        "by the single shared cursor, so the views stay comparable frame for frame.  "
        "The cost is spatial, not temporal -- the view count is the product of the "
        "peeled dimensions' sizes, while the timeline stays one sample per tick.",
        plot_callbacks=[partial(bn.BenchResult.to_rerun_timeline, timeline_dim="shoulder")],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_timeline_2d)
