"""Meta-generator: Rerun visualization integration examples.

Generates three rerun examples:
- capture_window: basic rerun capture in a single sweep
- regression: 0 input vars, 3 over-time snapshots with regression on the 3rd
- sweep: 1 input var (damping_ratio), single sweep, no over_time
"""

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "rerun"

RERUN_EXAMPLES = [
    "capture_window",
    "regression",
    "sweep",
]


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
            run_kwargs={"level": 3},
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
        result_vars=["out_overshoot", "out_settling_time"],
        run_cfg=run_cfg,
        time_src=base_time + timedelta(days=i),
    )

# Show rerun captures as a grid (slider does not work for rerun iframes)
bench.plot_sweep(
    "rerun_captures",
    input_vars=[],
    result_vars=["out_rerun"],
)

res = bench.results[-2]
report = res.regression_report
if report is not None:
    print("\\n" + report.summary())
    report.append_to_report(bench.report)
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
        """1 input var (damping_ratio), single sweep, no over_time."""
        imports = (
            "import bencher as bn\n"
            "from bencher.example.example_rerun_over_time import ControlSystemSweep"
        )
        body = """\
bench = ControlSystemSweep().to_bench(run_cfg)
bench.plot_sweep(
    input_vars=["damping_ratio"],
    result_vars=["out_overshoot", "out_settling_time", "out_rerun"],
    description="Sweep the damping ratio of a second-order control system and "
    "visualise each step response in the rerun viewer.  Low damping causes "
    "overshoot and ringing; high damping is sluggish but stable.",
)
"""
        self.generate_example(
            title="Rerun Sweep — control system response across damping ratios",
            output_dir=OUTPUT_DIR,
            filename="example_rerun_sweep",
            function_name="example_rerun_sweep",
            imports=imports,
            body=body,
            run_kwargs={"level": 3},
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
