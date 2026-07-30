"""Meta-generator: Rerun visualization integration examples.

Generates rerun examples for:
- capture_window: basic rerun capture in a single sweep
- regression: 0 input vars, 3 over-time snapshots with regression on the 3rd
- sweep: 1 input var (damping_ratio), single sweep, no over_time
- composable_{right,down,sequence,overlay}: combine two complete recordings, each
  animated over a ``time_s`` timeline so the composition modes are distinguishable
- summary: 2 input vars, every per-sample recording merged into ONE viewer
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

    def _generate_capture_window(self):
        """Capture a rerun viewer window as a Panel widget inside a sweep."""
        imports = "import math\nimport rerun as rr\nimport bencher as bn"
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
