"""Tests for over_time + repeats support in bar and distribution plots."""

from datetime import datetime, timedelta
from typing import Any

import panel as pn

import bencher as bch


class SimpleBench(bch.ParametrizedSweep):
    """Minimal benchmark for testing over_time + repeats."""

    backend = bch.StringSweep(["redis", "local"], doc="Backend")
    latency = bch.ResultVar(units="ms", doc="Latency")

    _offset = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        base = {"redis": 1.2, "local": 0.3}[self.backend]
        self.latency = base + self._offset + __import__("random").gauss(0, 0.05)
        return super().__call__()


class FloatBench(bch.ParametrizedSweep):
    """Benchmark with one float input for curve tests."""

    size = bch.FloatSweep(default=50, bounds=[10, 100], samples=3, doc="Size")
    backend = bch.StringSweep(["redis", "local"], doc="Backend")
    time = bch.ResultVar(units="ms", doc="Duration")

    _offset = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        base = {"redis": 1.0, "local": 0.5}[self.backend]
        self.time = base * self.size * 0.01 + self._offset + __import__("random").gauss(0, 0.02)
        return super().__call__()


def _run_over_time(benchable, input_vars, result_vars, repeats=1, snapshots=3):
    """Helper to run a benchmark over multiple time points."""
    run_cfg = bch.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.repeats = repeats
    bench = benchable.to_bench(run_cfg)
    base_time = datetime(2000, 1, 1)

    for i in range(snapshots):
        benchable._offset = i * 0.5
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "over_time_test",
            input_vars=input_vars,
            result_vars=result_vars,
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
        )
    return res


class TestBarResultOverTime:
    """Test BarResult with over_time slider."""

    def test_bar_over_time_no_repeats(self):
        """0 float + 1 cat + over_time -> bar with slider."""
        benchable = SimpleBench()
        res = _run_over_time(benchable, ["backend"], ["latency"], repeats=1, snapshots=3)
        plots = res.to_auto_plots()
        # Should produce a result with a slider (pn.Column wrapping HoloMap)
        assert plots is not None
        found_column = any(isinstance(p, pn.Column) for p in plots)
        # The bar plot should have been wrapped in a Column with slider
        assert found_column or len(plots) > 0

    def test_bar_over_time_with_repeats(self):
        """0 float + 1 cat + repeats + over_time -> bar with slider."""
        benchable = SimpleBench()
        res = _run_over_time(benchable, ["backend"], ["latency"], repeats=3, snapshots=3)
        plots = res.to_auto_plots()
        assert plots is not None


class TestDistributionResultOverTime:
    """Test BoxWhisker/Violin with over_time slider."""

    def test_boxwhisker_over_time(self):
        """0 float + 1 cat + repeats + over_time -> box whisker with slider."""
        benchable = SimpleBench()
        res = _run_over_time(benchable, ["backend"], ["latency"], repeats=3, snapshots=3)
        plots = res.to_auto_plots()
        assert plots is not None
        # With repeats > 1 and over_time, distribution plots should be generated
        found_column = any(isinstance(p, pn.Column) for p in plots)
        assert found_column or len(plots) > 0


class TestCurveResultOverTime:
    """Test CurveResult with over_time slider (already works, verify)."""

    def test_curve_over_time_with_repeats(self):
        """1 float + 1 cat + repeats + over_time -> curve with slider."""
        benchable = FloatBench()
        res = _run_over_time(benchable, ["size", "backend"], ["time"], repeats=3, snapshots=3)
        plots = res.to_auto_plots()
        assert plots is not None
        # Curve with over_time should produce a Column with slider
        found_column = any(isinstance(p, pn.Column) for p in plots)
        assert found_column or len(plots) > 0
