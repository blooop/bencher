"""Auto-generated example: Rerun Sweep — control system response across damping ratios."""

import bencher as bn
from bencher.example.example_rerun_over_time import ControlSystemSweep


def example_rerun_sweep(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Sweep — control system response across damping ratios."""
    bench = ControlSystemSweep().to_bench(run_cfg)
    bench.plot_sweep(
        # input_vars=["damping_ratio"],
        input_vars=[],
        result_vars=["out_overshoot", "out_settling_time", "out_rerun"],
        description="Sweep the damping ratio of a second-order control system and "
        "visualise each step response in the rerun viewer.  Low damping causes "
        "overshoot and ringing; high damping is sluggish but stable.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_sweep, level=3, over_time=True)
