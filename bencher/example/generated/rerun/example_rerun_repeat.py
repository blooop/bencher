"""Auto-generated example: Rerun Repeat — one recording per repeat, all visible in the report."""

import rerun as rr
import bencher as bn


class RerunRepeatSweep(bn.ParametrizedSweep):
    """Sweep that produces a rerun recording for each repeat.

    Each call to ``benchmark()`` logs a box whose size varies with the
    repeat index (via a class counter) so the recordings are visually
    distinct.  With ``repeats > 1`` and no input sweep, the report
    should display a grid of labelled recordings — one per repeat.
    """

    out_val = bn.ResultFloat(units="v", doc="box half-size used")
    out_rerun = bn.ResultRerun(width=400, height=400)

    _call_count = 0

    def benchmark(self):
        RerunRepeatSweep._call_count += 1
        size = float(self._call_count)
        self.out_val = size
        rr.log("boxes", rr.Boxes2D(half_sizes=[size, 1]))
        self.out_rerun = bn.capture_rerun_window()


def example_rerun_repeat(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Repeat — one recording per repeat, all visible in the report."""
    RerunRepeatSweep._call_count = 0
    bench = RerunRepeatSweep().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=[],
        result_vars=["out_val", "out_rerun"],
        description="Demonstrates that ``ResultRerun`` works correctly with "
        "``repeats > 1``.  Each repeat produces a distinct recording "
        "and the report renders all of them as a labelled grid.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_repeat, repeats=3)
