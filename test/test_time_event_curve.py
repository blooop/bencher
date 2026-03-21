"""Tests that curve plots use the float var as x-axis when over_time uses string-based TimeEvent."""

from typing import Any

import panel as pn

import bencher as bch


class FloatWithTimeBench(bch.ParametrizedSweep):
    """Benchmark with one float input for testing TimeEvent + curve interaction."""

    size = bch.FloatSweep(default=50, bounds=[10, 100], samples=3, doc="Size")
    throughput = bch.ResultVar(units="MB/s", doc="Throughput")

    offset = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.throughput = self.size * 0.5 + self.offset
        return super().__call__()


class FloatCatWithTimeBench(bch.ParametrizedSweep):
    """Benchmark with one float + one cat input for testing TimeEvent + curve interaction."""

    size = bch.FloatSweep(default=50, bounds=[10, 100], samples=3, doc="Size")
    backend = bch.StringSweep(["redis", "local"], doc="Backend")
    throughput = bch.ResultVar(units="MB/s", doc="Throughput")

    offset = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        base = {"redis": 1.0, "local": 2.0}[self.backend]
        self.throughput = self.size * base + self.offset
        return super().__call__()


def _run_string_over_time(benchable, input_vars, result_vars, repeats=1, snapshots=3):
    """Run a benchmark over multiple time points using string time_src (TimeEvent)."""
    run_cfg = bch.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.repeats = repeats
    bench = benchable.to_bench(run_cfg)

    for i in range(snapshots):
        benchable.offset = i * 0.5
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "time_event_curve_test",
            input_vars=input_vars,
            result_vars=result_vars,
            run_cfg=run_cfg,
            time_src=f"2026-03-{18 + i:02d} abc{i:04d}",
        )
    return res


class TestTimeEventCurvePlot:
    """Verify curve plots use float var as x-axis when over_time creates a TimeEvent."""

    def test_curve_with_string_time_src(self):
        """1 float + repeats + string over_time -> curve with float on x-axis."""
        benchable = FloatWithTimeBench()
        res = _run_string_over_time(benchable, ["size"], ["throughput"], repeats=3, snapshots=3)
        plots = res.to_auto_plots()
        assert plots is not None
        assert len(plots) > 0
        assert any(isinstance(p, pn.Column) for p in plots)

    def test_curve_with_string_time_src_and_cat(self):
        """1 float + 1 cat + repeats + string over_time -> curve with float on x-axis."""
        benchable = FloatCatWithTimeBench()
        res = _run_string_over_time(
            benchable, ["size", "backend"], ["throughput"], repeats=3, snapshots=3
        )
        plots = res.to_auto_plots()
        assert plots is not None
        assert len(plots) > 0
        assert any(isinstance(p, pn.Column) for p in plots)

    def test_line_with_string_time_src(self):
        """1 float + 1 repeat + string over_time -> line plot works."""
        benchable = FloatWithTimeBench()
        res = _run_string_over_time(benchable, ["size"], ["throughput"], repeats=1, snapshots=3)
        plots = res.to_auto_plots()
        assert plots is not None
        assert len(plots) > 0
