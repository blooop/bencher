"""Regression test: report.save() with over_time should be faster when aggregated tab is off."""

import tempfile
import time
from datetime import datetime, timedelta

import bencher as bn


class MultiResultBench(bn.ParametrizedSweep):
    """Benchmark with multiple result vars to amplify save cost."""

    x = bn.FloatSweep(default=1.0, bounds=[0, 2], samples=3, doc="x")
    r1 = bn.ResultFloat(units="s", doc="r1")
    r2 = bn.ResultFloat(units="s", doc="r2")
    r3 = bn.ResultFloat(units="s", doc="r3")

    offset = 0.0

    def benchmark(self):
        self.r1 = self.x + self.offset
        self.r2 = self.x * 2 + self.offset
        self.r3 = self.x * 3 + self.offset


def _run_and_save(show_agg: bool) -> float:
    """Run an over_time benchmark and return report.save() wall-clock time in seconds."""
    benchable = MultiResultBench()
    run_cfg = bn.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.repeats = 2
    run_cfg.show_aggregated_time_tab = show_agg
    bench = benchable.to_bench(run_cfg)
    base = datetime(2000, 1, 1)

    for i in range(2):
        benchable.offset = i * 0.1
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        bench.plot_sweep(
            "save_perf_test",
            input_vars=["x"],
            result_vars=["r1", "r2", "r3"],
            run_cfg=run_cfg,
            time_src=base + timedelta(seconds=i),
        )

    with tempfile.TemporaryDirectory() as td:
        t0 = time.perf_counter()
        bench.report.save(directory=td, in_html_folder=False)
        return time.perf_counter() - t0


def test_save_faster_without_aggregated_tab():
    """report.save() should be meaningfully faster with show_aggregated_time_tab=False."""
    time_with_agg = _run_and_save(show_agg=True)
    time_without_agg = _run_and_save(show_agg=False)

    # The aggregated tab roughly doubles the embed cost.  Assert at least
    # 20% improvement to allow for noise while still catching regressions.
    assert time_without_agg < time_with_agg, (
        f"Expected save without aggregated tab ({time_without_agg:.2f}s) to be faster "
        f"than with aggregated tab ({time_with_agg:.2f}s)"
    )


def test_report_save_ms_field_exists():
    """SweepTimings should expose report_save_ms for downstream instrumentation."""
    t = bn.SweepTimings()
    assert hasattr(t, "report_save_ms")
    assert t.report_save_ms == 0.0
    # Verify it appears in summary
    assert "report_save_ms" in t.summary()
