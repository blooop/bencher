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


# Retries before declaring a perf regression; see comment in the test body.
PERF_COMPARE_ATTEMPTS = 3


def test_save_faster_without_aggregated_tab():
    """report.save() should be meaningfully faster with show_aggregated_time_tab=False."""
    # Wall-clock comparison of two single runs is noisy on shared CI runners
    # (observed 1.94s vs 1.86s false failures); a real regression makes the
    # no-agg save consistently slower, so retry before declaring one. The
    # measurement order alternates between attempts so cache warmup or a
    # transient load spike cannot consistently bias one side.
    attempts = []
    for i in range(PERF_COMPARE_ATTEMPTS):
        if i % 2 == 0:
            time_with_agg = _run_and_save(show_agg=True)
            time_without_agg = _run_and_save(show_agg=False)
        else:
            time_without_agg = _run_and_save(show_agg=False)
            time_with_agg = _run_and_save(show_agg=True)
        if time_without_agg < time_with_agg:
            return
        attempts.append(f"{time_without_agg:.2f}s vs {time_with_agg:.2f}s")

    raise AssertionError(
        "Expected save without aggregated tab to be faster than with aggregated tab "
        f"in at least one of {PERF_COMPARE_ATTEMPTS} attempts (without vs with): "
        f"{', '.join(attempts)}"
    )


def test_report_save_ms_field_exists():
    """SweepTimings should expose report_save_ms for downstream instrumentation."""
    t = bn.SweepTimings()
    assert hasattr(t, "report_save_ms")
    assert t.report_save_ms == 0.0
    # Verify it appears in summary
    assert "report_save_ms" in t.summary()
