"""Tests for over_time + repeats support in bar and distribution plots."""

import random
from datetime import datetime, timedelta
from typing import Any

import holoviews as hv
import panel as pn

import bencher as bn


class SimpleBench(bn.ParametrizedSweep):
    """Minimal benchmark for testing over_time + repeats."""

    backend = bn.StringSweep(["redis", "local"], doc="Backend")
    latency = bn.ResultVar(units="ms", doc="Latency")

    offset = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        base = {"redis": 1.2, "local": 0.3}[self.backend]
        self.latency = base + self.offset + random.gauss(0, 0.05)
        return super().__call__()


class FloatBench(bn.ParametrizedSweep):
    """Benchmark with one float input for curve tests."""

    size = bn.FloatSweep(default=50, bounds=[10, 100], samples=3, doc="Size")
    backend = bn.StringSweep(["redis", "local"], doc="Backend")
    time = bn.ResultVar(units="ms", doc="Duration")

    offset = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        base = {"redis": 1.0, "local": 0.5}[self.backend]
        self.time = base * self.size * 0.01 + self.offset + random.gauss(0, 0.02)
        return super().__call__()


def _run_over_time(benchable, input_vars, result_vars, repeats=1, snapshots=3):
    """Helper to run a benchmark over multiple time points."""
    run_cfg = bn.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.repeats = repeats
    bench = benchable.to_bench(run_cfg)
    base_time = datetime(2000, 1, 1)

    for i in range(snapshots):
        benchable.offset = i * 0.5
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


def _has_holomap_column(plots):
    """Check if plots contain a pn.Column wrapping a HoloMap (slider layout)."""
    for p in plots:
        if isinstance(p, pn.Column):
            # Check children for HoloMap-based pane (rendered as HoloViews pane)
            for child in p:
                if isinstance(child, pn.pane.HoloViews):
                    if isinstance(child.object, hv.HoloMap):
                        return True
    return False


def _find_over_time_widget(obj, depth=0):
    """Recursively find the over_time widget from a Panel layout, or None."""
    if isinstance(obj, pn.widgets.Widget) and getattr(obj, "name", None) == "over_time":
        return obj
    if depth > 8:
        return None
    try:
        for child in obj:
            result = _find_over_time_widget(child, depth + 1)
            if result is not None:
                return result
    except TypeError:
        pass
    return None


def _find_all_over_time_widgets(obj, depth=0):
    """Recursively collect *all* over_time widgets from a Panel layout."""
    found = []
    if isinstance(obj, pn.widgets.Widget) and getattr(obj, "name", None) == "over_time":
        found.append(obj)
        return found
    if depth > 8:
        return found
    try:
        for child in obj:
            found.extend(_find_all_over_time_widgets(child, depth + 1))
    except TypeError:
        pass
    return found


class ZeroDimBench(bn.ParametrizedSweep):
    """Benchmark with no input vars — 0D numeric result for over_time regression test."""

    value = bn.ResultVar(units="m", doc="Value")

    offset = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.value = 2.844 + self.offset
        return super().__call__()


class TestNumericOverTimeNotRoutedToImageSlider:
    """Regression tests: numeric ResultVar must not be routed to _pane_over_time_slider.

    Commit 9279dd32 unconditionally routed all result types through the image/video
    slider when over_time was active.  Numeric values (e.g. 2.844) were then treated
    as file paths, causing FileNotFoundError and ValueError.
    """

    def test_0d_numeric_over_time_no_file_error(self):
        """0 input + numeric result + over_time must not raise FileNotFoundError."""
        benchable = ZeroDimBench()
        res = _run_over_time(benchable, [], ["value"], repeats=1, snapshots=3)
        plots = res.to_auto_plots()
        assert plots is not None
        assert len(plots) > 0

    def test_0d_numeric_over_time_with_repeats(self):
        """0 input + numeric result + repeats + over_time must not raise ValueError."""
        benchable = ZeroDimBench()
        res = _run_over_time(benchable, [], ["value"], repeats=2, snapshots=3)
        plots = res.to_auto_plots()
        assert plots is not None
        assert len(plots) > 0


class TestBarResultOverTime:
    """Test BarResult with over_time slider."""

    def test_bar_over_time_no_repeats(self):
        """0 float + 1 cat + over_time -> bar with slider."""
        benchable = SimpleBench()
        res = _run_over_time(benchable, ["backend"], ["latency"], repeats=1, snapshots=3)
        plots = res.to_auto_plots()
        assert plots is not None
        assert len(plots) > 0
        # With multiple time points, bar should be wrapped in a Column with slider
        assert any(isinstance(p, pn.Column) for p in plots)

    def test_bar_over_time_with_repeats(self):
        """0 float + 1 cat + repeats + over_time -> bar with slider."""
        benchable = SimpleBench()
        res = _run_over_time(benchable, ["backend"], ["latency"], repeats=3, snapshots=3)
        plots = res.to_auto_plots()
        assert plots is not None
        assert len(plots) > 0


class TestDistributionResultOverTime:
    """Test BoxWhisker/Violin with over_time slider."""

    def test_boxwhisker_over_time(self):
        """0 float + 1 cat + repeats + over_time -> box whisker with slider."""
        benchable = SimpleBench()
        res = _run_over_time(benchable, ["backend"], ["latency"], repeats=3, snapshots=3)
        plots = res.to_auto_plots()
        assert plots is not None
        assert len(plots) > 0
        # With repeats > 1 and over_time, distribution plots should produce slider columns
        assert any(isinstance(p, pn.Column) for p in plots)


class TestCurveResultOverTime:
    """Test CurveResult with over_time slider."""

    def test_curve_over_time_with_repeats(self):
        """1 float + 1 cat + repeats + over_time -> curve with slider."""
        benchable = FloatBench()
        res = _run_over_time(benchable, ["size", "backend"], ["time"], repeats=3, snapshots=3)
        plots = res.to_auto_plots()
        assert plots is not None
        assert len(plots) > 0
        # Curve with over_time should produce a Column with slider
        assert any(isinstance(p, pn.Column) for p in plots)

    def test_curve_over_time_no_repeats(self):
        """1 float + 1 cat + over_time without repeats must not crash."""
        benchable = FloatBench()
        res = _run_over_time(benchable, ["size", "backend"], ["time"], repeats=1, snapshots=3)
        plots = res.to_auto_plots()
        assert plots is not None
        assert len(plots) > 0


class TestHeatmapResultOverTime:
    """Test HeatmapResult with over_time slider."""

    def test_heatmap_over_time_no_repeats(self):
        """1 float + 1 cat + over_time -> heatmap with slider, no crash."""
        benchable = FloatBench()
        res = _run_over_time(benchable, ["size", "backend"], ["time"], repeats=1, snapshots=3)
        plots = res.to_auto_plots()
        assert plots is not None
        assert len(plots) > 0

    def test_heatmap_over_time_with_repeats(self):
        """1 float + 1 cat + repeats + over_time -> heatmap with slider."""
        benchable = FloatBench()
        res = _run_over_time(benchable, ["size", "backend"], ["time"], repeats=3, snapshots=3)
        plots = res.to_auto_plots()
        assert plots is not None
        assert len(plots) > 0
        assert any(isinstance(p, pn.Column) for p in plots)


class TestOptunaResultOverTime:
    """Test OptunaResult with over_time (pandas Timestamp handling)."""

    def test_optuna_plots_over_time(self):
        """to_optuna_plots() must not crash when over_time=True (pandas Timestamps)."""
        benchable = FloatBench()
        res = _run_over_time(benchable, ["size", "backend"], ["time"], repeats=3, snapshots=3)
        optuna_plots = res.to_optuna_plots()
        assert optuna_plots is not None


class TestOverTimeWidgetIsDiscreteSlider:
    """Verify over_time uses DiscreteSlider, not a Select dropdown."""

    def test_bar_over_time_uses_discrete_slider(self):
        """All over_time widgets must be DiscreteSlider, none should be Select."""
        benchable = SimpleBench()
        res = _run_over_time(benchable, ["backend"], ["latency"], repeats=1, snapshots=3)
        plots = res.to_auto_plots()
        widgets = _find_all_over_time_widgets(plots)
        assert len(widgets) > 0, "Expected at least one over_time widget in the plots"
        for widget in widgets:
            assert isinstance(widget, pn.widgets.DiscreteSlider), (
                f"Expected DiscreteSlider, got {type(widget).__name__}"
            )
            assert not isinstance(widget, pn.widgets.Select), (
                "over_time widget must not be a Select dropdown"
            )
