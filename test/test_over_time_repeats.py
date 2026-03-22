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


def _run_over_time(benchable, input_vars, result_vars, repeats=1, snapshots=3, **cfg_kwargs):
    """Helper to run a benchmark over multiple time points.

    Extra keyword arguments are forwarded as BenchRunCfg attribute overrides.
    """
    run_cfg = bn.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.repeats = repeats
    for k, v in cfg_kwargs.items():
        setattr(run_cfg, k, v)
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


class TestShowAggregatedTimeTab:
    """Tests for the show_aggregated_time_tab config parameter."""

    def _count_agg_tabs(self, plots, depth=0):
        """Count pn.Tabs instances that contain the aggregated title."""
        count = 0
        if depth > 10:
            return 0
        if isinstance(plots, pn.Tabs):
            for title in plots._names:  # pylint: disable=protected-access
                if "aggregated" in title.lower():
                    count += 1
        try:
            for child in plots:
                count += self._count_agg_tabs(child, depth + 1)
        except TypeError:
            pass
        return count

    def test_aggregated_tab_absent_by_default(self):
        """With default config (show_aggregated_time_tab=False), no aggregated tabs."""
        benchable = SimpleBench()
        res = _run_over_time(benchable, ["backend"], ["latency"], repeats=1, snapshots=3)
        plots = res.to_auto_plots()
        assert self._count_agg_tabs(plots) == 0

    def test_aggregated_tab_present_when_enabled(self):
        """With show_aggregated_time_tab=True, aggregated tab should appear."""
        benchable = SimpleBench()
        res = _run_over_time(
            benchable,
            ["backend"],
            ["latency"],
            repeats=1,
            snapshots=3,
            show_aggregated_time_tab=True,
        )
        plots = res.to_auto_plots()
        assert self._count_agg_tabs(plots) > 0

    def test_aggregated_tab_absent_when_disabled(self):
        """With show_aggregated_time_tab=False, no aggregated tabs."""
        benchable = SimpleBench()
        res = _run_over_time(
            benchable,
            ["backend"],
            ["latency"],
            repeats=1,
            snapshots=3,
            show_aggregated_time_tab=False,
        )
        plots = res.to_auto_plots()
        assert self._count_agg_tabs(plots) == 0

    def test_curve_aggregated_tab_absent_when_disabled(self):
        """Curve plots also respect show_aggregated_time_tab=False."""
        benchable = FloatBench()
        res = _run_over_time(
            benchable,
            ["size", "backend"],
            ["time"],
            repeats=3,
            snapshots=3,
            show_aggregated_time_tab=False,
        )
        plots = res.to_auto_plots()
        assert self._count_agg_tabs(plots) == 0


class TestMaxSliderPoints:
    """Tests for the max_slider_points config parameter."""

    def test_slider_subsampled(self):
        """With max_slider_points=2 and 5 snapshots, slider should have 2 entries."""
        benchable = SimpleBench()
        res = _run_over_time(
            benchable,
            ["backend"],
            ["latency"],
            repeats=1,
            snapshots=5,
            max_slider_points=2,
        )
        plots = res.to_auto_plots()
        widgets = _find_all_over_time_widgets(plots)
        for widget in widgets:
            if hasattr(widget, "options"):
                opts = list(
                    widget.options.values() if isinstance(widget.options, dict) else widget.options
                )
                assert len(opts) == 2, f"Expected 2 slider options, got {len(opts)}"

    def test_no_subsampling_when_below_default_max(self):
        """With default max_slider_points=10 and only 5 snapshots, all time points shown."""
        benchable = SimpleBench()
        res = _run_over_time(
            benchable,
            ["backend"],
            ["latency"],
            repeats=1,
            snapshots=5,
        )
        plots = res.to_auto_plots()
        widgets = _find_all_over_time_widgets(plots)
        for widget in widgets:
            if hasattr(widget, "options"):
                opts = list(
                    widget.options.values() if isinstance(widget.options, dict) else widget.options
                )
                assert len(opts) == 5, f"Expected 5 slider options, got {len(opts)}"

    def test_default_subsampling_caps_at_max(self):
        """With default max_slider_points=10 and 30 snapshots, slider capped at 10."""
        benchable = SimpleBench()
        res = _run_over_time(
            benchable,
            ["backend"],
            ["latency"],
            repeats=1,
            snapshots=30,
        )
        plots = res.to_auto_plots()
        widgets = _find_all_over_time_widgets(plots)
        for widget in widgets:
            if hasattr(widget, "options"):
                opts = list(
                    widget.options.values() if isinstance(widget.options, dict) else widget.options
                )
                assert len(opts) == 10, f"Expected 10 slider options, got {len(opts)}"


class TestSubsampleIndices:
    """Unit tests for subsample_indices static method."""

    def test_no_subsampling_when_none(self):
        from bencher.results.holoview_results.holoview_result import HoloviewResult

        result = list(HoloviewResult.subsample_indices(10, None))
        assert result == list(range(10))

    def test_no_subsampling_when_n_within_limit(self):
        from bencher.results.holoview_results.holoview_result import HoloviewResult

        result = list(HoloviewResult.subsample_indices(5, 10))
        assert result == list(range(5))

    def test_subsampling_includes_first_and_last(self):
        from bencher.results.holoview_results.holoview_result import HoloviewResult

        result = list(HoloviewResult.subsample_indices(20, 3))
        assert result[0] == 0
        assert result[-1] == 19
        assert len(result) == 3

    def test_subsampling_correct_count(self):
        from bencher.results.holoview_results.holoview_result import HoloviewResult

        result = list(HoloviewResult.subsample_indices(100, 5))
        assert len(result) == 5
        assert result[0] == 0
        assert result[-1] == 99
