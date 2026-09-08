"""Meta-generator: Rerun visualization integration examples.

Generates rerun examples for:
- capture_window: basic rerun capture in a single sweep
- regression: 0 input vars, 3 over-time snapshots with regression on the 3rd
- sweep: 1 input var (damping_ratio), single sweep, no over_time
- composable_{right,down,sequence,overlay}: combine two complete recordings, each
  animated over a ``time_s`` timeline so the composition modes are distinguishable
- summary: 2 input vars, every per-sample recording merged into ONE viewer
- timeline_1d: 1 input var mapped onto a named rerun timeline, scrubbable
- timeline_2d: the same, with the second input var peeled onto the entity tree
- backend: backend="rerun", scalars and recordings in one all-rerun report
"""

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "rerun"

RERUN_EXAMPLES = [
    "capture_window",
    "regression",
    "sweep",
    "composable_right",
    "composable_down",
    "composable_sequence",
    "composable_overlay",
    "summary",
    "timeline_1d",
    "timeline_2d",
    "backend",
]

# What each composition mode does to the two recordings, appended to the
# generated example's description.
COMPOSE_DESCRIPTIONS = {
    "right": "``right`` gives each recording its own view side by side, both driven "
    "by the same timeline, so the two responses animate together.",
    "down": "``down`` stacks the per-recording views vertically, both driven by the "
    "same timeline, so the two responses animate together.",
    "sequence": "``sequence`` splices the recordings end to end: the second "
    "recording's ``time_s`` values are offset to start where the first one ends, and "
    "each recording is cleared as the next begins.  Scrubbing or playing the single "
    "shared view therefore runs the reference response first, then the candidate.",
    "overlay": "``overlay`` puts both recordings in one shared view at their original "
    "times, so the two responses are drawn on top of each other for direct comparison.",
}


class MetaRerun(MetaGeneratorBase):
    """Generate Python examples demonstrating rerun integration."""

    example = bn.StringSweep(RERUN_EXAMPLES, doc="Which rerun example to generate")

    def benchmark(self):
        if self.example == "capture_window":
            self._generate_capture_window()
        elif self.example == "regression":
            self._generate_regression()
        elif self.example == "sweep":
            self._generate_sweep()
        elif self.example.startswith("composable_"):
            self._generate_composable(self.example.removeprefix("composable_"))
        elif self.example == "summary":
            self._generate_summary()
        elif self.example.startswith("timeline_"):
            self._generate_timeline(self.example.removeprefix("timeline_"))
        elif self.example == "backend":
            self._generate_backend()

    def _generate_capture_window(self):
        """Capture a rerun viewer window as a Panel widget inside a sweep."""
        imports = "import math\n\nimport rerun as rr\n\nimport bencher as bn"
        class_code = '''
class RerunSweep(bn.ParametrizedSweep):
    """Sweep that logs 2D geometry to rerun for each parameter combination.

    Each call to ``benchmark()`` logs a box whose width varies with *theta*
    and captures the recording as a ``.rrd`` file.  The CDN-hosted rerun
    web viewer renders each snapshot inline in the report.
    """

    theta = bn.FloatSweep(default=1, bounds=[1, 4], doc="Box half-size", units="rad", samples=5)

    out_sin = bn.ResultFloat(units="v", doc="sin of theta")
    out_rerun = bn.ResultRerun(width=400, height=400)

    def benchmark(self):
        self.out_sin = math.sin(self.theta)
        rr.log("boxes", rr.Boxes2D(half_sizes=[self.theta, 1]))
        self.out_rerun = bn.capture_rerun_window()'''
        body = """\
bench = RerunSweep().to_bench(run_cfg)
bench.plot_sweep(
    input_vars=["theta"],
    result_vars=["out_sin", "out_rerun"],
    description="Rerun is a spatial logging library for 2D/3D visualization. "
    "Bencher integrates with rerun via ``bn.capture_rerun_window()``, which "
    "drains the current recording to a ``.rrd`` file and embeds a CDN-hosted "
    "viewer in the report.  Each sweep point gets its own interactive viewer.",
    post_description="The ``ResultRerun`` type stores ``.rrd`` file paths and "
    "renders them with the ``@rerun-io/web-viewer`` loaded from CDN.  "
    "No local viewer server or extra ports are needed.",
)
"""
        self.generate_example(
            title="Rerun Capture — embed spatial visualizations in sweep reports",
            output_dir=OUTPUT_DIR,
            filename="example_rerun_capture_window",
            function_name="example_rerun_capture_window",
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"subsampling_divisions": 3},
        )

    def _generate_regression(self):
        """0 input vars, 3 over-time snapshots, regression on the 3rd."""
        imports = (
            "from datetime import datetime, timedelta\n\n"
            "import bencher as bn\n"
            "from bencher.example.example_rerun_over_time import ControlSystemSweep"
        )
        body = """\
if run_cfg is None:
    run_cfg = bn.BenchRunCfg()
run_cfg.regression_detection = True
run_cfg.regression_method = "percentage"
run_cfg.regression_fail = False

benchable = ControlSystemSweep()
bench = benchable.to_bench(run_cfg)
base_time = datetime(2024, 1, 1)

# 3 calibration runs: stable, stable, then controller tuning degrades
degradations = [0.0, 0.0, 0.4]
for i, deg in enumerate(degradations):
    benchable._degradation = deg
    run_cfg.clear_cache = True
    run_cfg.clear_history = i == 0
    bench.plot_sweep(
        "controller_monitoring",
        input_vars=[],
        result_vars=["out_overshoot", "out_settling_time", "out_rerun"],
        run_cfg=run_cfg,
        time_src=base_time + timedelta(days=i),
    )
"""
        self.generate_example(
            title="Rerun Regression — detect controller degradation over time",
            output_dir=OUTPUT_DIR,
            filename="example_rerun_regression",
            function_name="example_rerun_regression",
            imports=imports,
            body=body,
            run_kwargs={"over_time": True},
        )

    def _generate_sweep(self):
        """2 input vars (damping_ratio, omega_n), single sweep, aggregate=True."""
        imports = (
            "import bencher as bn\n"
            "from bencher.example.example_rerun_over_time import ControlSystemSweep"
        )
        body = """\
bench = ControlSystemSweep().to_bench(run_cfg)
bench.plot_sweep(
    input_vars=["damping_ratio", "omega_n"],
    result_vars=["out_overshoot", "out_settling_time", "out_rerun"],
    description="Sweep the damping ratio and natural frequency of a second-order "
    "control system.  aggregate=True collapses omega_n so you can see the "
    "mean \\u00b1 std across frequencies for each damping ratio.",
    aggregate=True,
)
"""
        self.generate_example(
            title="Rerun Sweep — control system response across damping ratios",
            output_dir=OUTPUT_DIR,
            filename="example_rerun_sweep",
            function_name="example_rerun_sweep",
            imports=imports,
            body=body,
            run_kwargs={"subsampling_divisions": 3},
        )

    def _generate_summary(self):
        """Merge every per-sample recording of a sweep into a single viewer."""
        imports = "import rerun as rr\n\nimport bencher as bn"
        class_code = '''
class RerunSummarySweep(bn.ParametrizedSweep):
    """Record a step response per sample, then merge the whole sweep into one viewer.

    Sweeping a ``ResultRerun`` normally embeds one rerun web viewer *per sample*,
    so this 3x2 sweep would spawn six independent wasm viewers with no way to
    compare across them.  ``rerun_summary`` merges every recording into a single
    recording plus blueprint instead.
    """

    damping = bn.FloatSweep(default=0.5, bounds=[0.2, 0.9], samples=3)
    omega_n = bn.FloatSweep(default=6.0, bounds=[4.0, 8.0], samples=2)

    out_rerun = bn.ResultRerun(width=900, height=520)

    def benchmark(self):
        recording = rr.RecordingStream("rerun_summary_sample", make_default=False)
        n_steps, dt = 80, 0.025
        y, dy, trace = 0.0, 0.0, []
        for step in range(n_steps):
            # Euler integration of  y'' + 2*zeta*wn*y' + wn^2*y = wn^2
            ddy = self.omega_n**2 * (1.0 - y) - 2 * self.damping * self.omega_n * dy
            dy += ddy * dt
            y += dy * dt
            trace.append([step * dt, y])

            recording.set_time("time_s", duration=step * dt)
            recording.log("scene/trace", rr.LineStrips2D([trace]))
            recording.log("metrics/output", rr.Scalars(y))

        self.out_rerun = bn.capture_rerun_rrd(recording)
        return super().benchmark()
'''
        body = """\
bench = RerunSummarySweep().to_bench(run_cfg)
bench.plot_sweep(
    input_vars=["damping", "omega_n"],
    result_vars=["out_rerun"],
    description="Each of the six samples records its own step response to a separate "
    "``.rrd``, which is what diskcache keys on.  ``rerun_summary`` walks the result "
    "dataset afterwards and merges all six into ONE recording, re-homing each sample "
    "under its own entity-path branch and generating a Blueprint to lay them out.  "
    "The result is a single embedded viewer instead of six, and because everything "
    "shares one recording the samples can be scrubbed on a common timeline.",
    post_description="``rerun_summary`` sequences every dimension onto one timeline; "
    "``rerun_grid`` lays the dimensions out in space instead.  Both are named-only "
    "plot types because merging every recording is expensive.",
    plot_callbacks=[bn.BenchResult.to_rerun_summary],
)
"""
        self.generate_example(
            title="Rerun Summary — merge a whole sweep into one viewer",
            output_dir=OUTPUT_DIR,
            filename="example_rerun_summary",
            function_name="example_rerun_summary",
            imports=imports,
            class_code=class_code,
            body=body,
        )

    def _generate_timeline(self, dims: str):
        """A sweep whose parameter *is* the rerun timeline, in 1-D or 2-D."""
        imports = "import math\n\nimport rerun as rr\n\nimport bencher as bn"
        if dims == "2d":
            imports = (
                "import math\nfrom functools import partial\n\n"
                "import rerun as rr\n\nimport bencher as bn"
            )
        second_var = (
            ""
            if dims == "1d"
            else "\n    link_ratio = bn.FloatSweep(\n"
            "        default=0.6,\n"
            "        bounds=[0.4, 1.0],\n"
            '        doc="Forearm length as a fraction of the upper arm",\n'
            "        samples=3,\n"
            "    )"
        )
        ratio = "1.0" if dims == "1d" else "self.link_ratio"
        class_code = f'''
class ArmPoseSweep(bn.ParametrizedSweep):
    """Forward kinematics of a two-link planar arm.

    Each sample logs one static pose -- there is no time inside a sample, so the
    only thing worth scrubbing is the sweep itself.
    """

    shoulder = bn.FloatSweep(
        default=0.0, bounds=[0.0, 2.4], doc="Shoulder joint angle", units="rad", samples=13
    ){second_var}

    out_reach = bn.ResultFloat(units="m", doc="Distance from the base to the tool tip")
    out_rerun = bn.ResultRerun(width=900, height=520)

    def benchmark(self):
        upper, fore = 1.0, {ratio}
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
'''
        if dims == "1d":
            input_vars = '["shoulder"]'
            callback = "bn.BenchResult.to_rerun_timeline"
            description = (
                '"Every sample records its own ``.rrd`` holding one static pose, so the "\n'
                '    "per-sample viewers have nothing to play and ``rerun_summary`` has nothing "\n'
                '    "to splice.  ``rerun_timeline`` instead makes the swept parameter itself the "\n'
                '    "time axis: all 13 poses are written to ONE recording at the same entity "\n'
                '    "paths, indexed by a rerun timeline named ``shoulder`` carrying the "\n'
                '    "parameter\'s own values.  Dragging the time cursor sweeps the arm."'
            )
            post = (
                '"A numeric sweep variable is encoded as a duration index, one second per "\n'
                '    "unit, so the axis reads back the parameter values and keeps their spacing "\n'
                '    "even when the sweep is not uniform.  Pass "\n'
                '    "``index=bn.TimelineIndex.sequence`` to number the samples 0, 1, 2 instead -- "\n'
                '    "which is what a categorical sweep gets automatically."'
            )
        else:
            input_vars = '["shoulder", "link_ratio"]'
            callback = 'partial(bn.BenchResult.to_rerun_timeline, timeline_dim="shoulder")'
            description = (
                '"Rerun timelines are independent axes, not a joint index: a latest-at query "\n'
                '    "resolves on the timeline being viewed and ignores every other one, so two "\n'
                '    "swept variables cannot become two scrubbers.  Exactly one dimension can be "\n'
                '    "time.  Here ``shoulder`` is it, and ``link_ratio`` is peeled onto the entity "\n'
                '    "tree instead -- one branch and one Blueprint view per forearm length."'
            )
            post = (
                '"That is how the mapping scales: one dimension animates, the rest tile.  A "\n'
                '    "3-D sweep gives a grid of views over the two peeled dimensions, all driven "\n'
                '    "by the single shared cursor, so the views stay comparable frame for frame.  "\n'
                '    "The cost is spatial, not temporal -- the view count is the product of the "\n'
                '    "peeled dimensions\' sizes, while the timeline stays one sample per tick."'
            )

        body = f"""\
bench = ArmPoseSweep().to_bench(run_cfg)
bench.plot_sweep(
    input_vars={input_vars},
    result_vars=["out_reach", "out_rerun"],
    description={description},
    post_description={post},
    plot_callbacks=[{callback}],
)
"""
        self.generate_example(
            title=(
                "Rerun Timeline — scrub a 1-D sweep on the time axis"
                if dims == "1d"
                else "Rerun Timeline 2D — one dimension animates, the rest tile"
            ),
            output_dir=OUTPUT_DIR,
            filename=f"example_rerun_timeline_{dims}",
            function_name=f"example_rerun_timeline_{dims}",
            imports=imports,
            class_code=class_code,
            body=body,
        )

    def _generate_backend(self):
        """Render an entire sweep -- scalars and recordings alike -- in rerun."""
        imports = "import rerun as rr\n\nimport bencher as bn"
        class_code = '''
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
'''
        body = """\
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
"""
        self.generate_example(
            title="Rerun Backend — a whole sweep, scalars and recordings, in rerun",
            output_dir=OUTPUT_DIR,
            filename="example_rerun_backend",
            function_name="example_rerun_backend",
            imports=imports,
            body=body,
            class_code=class_code,
        )

    def _generate_composable(self, compose: str):
        """Combine complete recordings with a native Rerun Blueprint layout."""
        imports = "import rerun as rr\n\nimport bencher as bn"
        class_code = f'''
class RerunComposition(bn.ParametrizedSweep):
    """Record two step responses over time and combine them into one result.

    Each recording animates a second-order system tracking a unit step: the
    plant marker sweeps left to right as it settles, the trace grows behind it,
    and the output is logged as a scalar.  Both recordings span the same
    ``time_s`` range, which is what makes the composition modes differ — see
    the description below.
    """

    out_rerun = bn.ResultRerun(width=900, height=520)

    def benchmark(self):
        composed = bn.ComposableContainerRerun(
            compose_method=bn.ComposeType.{compose},
            name="{compose.title()} composition",
        )
        # (label, damping ratio, colour) — the reference settles cleanly, the
        # candidate is under-damped and rings.
        scenes = [
            ("Reference", 0.9, [230, 80, 80]),
            ("Candidate", 0.35, [70, 120, 235]),
        ]
        n_steps, dt, omega_n = 80, 0.025, 8.0

        for index, (label, zeta, color) in enumerate(scenes):
            recording = rr.RecordingStream(
                f"bencher_composable_{compose}_{{index}}",
                make_default=False,
            )
            y, dy, trace = 0.0, 0.0, []
            for step in range(n_steps):
                # Euler integration of  y'' + 2*zeta*wn*y' + wn^2*y = wn^2
                ddy = omega_n**2 * (1.0 - y) - 2 * zeta * omega_n * dy
                dy += ddy * dt
                y += dy * dt
                trace.append([step * dt, y])

                recording.set_time("time_s", duration=step * dt)
                recording.log(
                    "scene/plant",
                    rr.Boxes2D(
                        centers=[[step * dt, y]],
                        half_sizes=[[0.03, 0.05]],
                        colors=[color],
                        labels=[label],
                    ),
                )
                recording.log("scene/trace", rr.LineStrips2D([trace], colors=[color]))
                recording.log("metrics/output", rr.Scalars(y))

            composed.append(bn.capture_rerun_rrd(recording), label=label)

        # ResultRerun recognizes the compositor and materializes one combined
        # path-backed .rrd before the result enters Bencher's cache.
        self.out_rerun = composed'''
        body = f"""\
bench = RerunComposition().to_bench(run_cfg)
bench.plot_sweep(
    input_vars=[],
    result_vars=["out_rerun"],
    description="Two independent ``.rrd`` recordings, each animating a step response "
    "over a ``time_s`` timeline, are assigned directly to a ``ComposableContainerRerun``. "
    "Bencher namespaces their entity paths, combines their chunks into one recording, "
    "and generates a native Rerun Blueprint. {COMPOSE_DESCRIPTIONS[compose]}",
    post_description="``right`` and ``down`` place each recording in its own view on a "
    "shared timeline; ``overlay`` draws them in one view at the same times; ``sequence`` "
    "offsets the timelines so the recordings play back to back.",
)
"""
        self.generate_example(
            title=f"Rerun Composition — {compose.title()}",
            output_dir=OUTPUT_DIR,
            filename=f"example_rerun_composable_{compose}",
            function_name=f"example_rerun_composable_{compose}",
            imports=imports,
            body=body,
            class_code=class_code,
        )


def example_meta_rerun(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = MetaRerun().to_bench(run_cfg)

    bench.plot_sweep(
        title="Rerun Integration",
        input_vars=[bn.sweep("example", RERUN_EXAMPLES)],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_rerun)
