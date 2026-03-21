"""Tests for sweep timing instrumentation."""

import math

import bencher as bch
from bencher.sweep_timings import SweepTimings, phase_timer


def test_phase_timer():
    """phase_timer context manager returns positive elapsed time."""
    with phase_timer() as elapsed:
        _ = sum(range(1000))
    assert elapsed() > 0


def test_sweep_timings_summary():
    """SweepTimings.summary() returns all fields as a dict."""
    t = SweepTimings(total_ms=42.0, cache_check_ms=1.5)
    s = t.summary()
    assert s["total_ms"] == 42.0
    assert s["cache_check_ms"] == 1.5
    assert "dataset_setup_ms" in s


class TrivialSweep(bch.ParametrizedSweep):
    theta = bch.FloatSweep(default=0, bounds=[0, math.pi], samples=5)
    out = bch.ResultVar(units="v", doc="output")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out = math.sin(self.theta)
        return super().__call__(**kwargs)


def test_bench_result_has_timings():
    """After plot_sweep(), the BenchResult should have populated timings."""
    run_cfg = bch.BenchRunCfg()
    run_cfg.auto_plot = False
    bench = TrivialSweep().to_bench(run_cfg)
    bench.plot_sweep()

    res = bench.results[-1]
    assert res.timings is not None
    assert isinstance(res.timings, SweepTimings)
    assert res.timings.total_ms > 0
    assert res.timings.dataset_setup_ms >= 0
    assert res.timings.job_submission_ms >= 0
    assert res.timings.job_execution_ms >= 0

    # total_ms should equal the sum of all phase timings
    t = res.timings
    expected_total = (
        t.cache_check_ms
        + t.sample_cache_init_ms
        + t.dataset_setup_ms
        + t.job_submission_ms
        + t.job_execution_ms
        + t.history_merge_ms
        + t.post_setup_ms
    )
    assert t.total_ms == expected_total


def test_timings_accessible_via_public_api():
    """SweepTimings should be importable from the top-level bencher package."""
    assert hasattr(bch, "SweepTimings")
    assert bch.SweepTimings is SweepTimings
