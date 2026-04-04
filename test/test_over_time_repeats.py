"""Tests for over_time + repeats support in bar and distribution plots."""

# pylint: disable=redefined-outer-name

import random
from datetime import datetime, timedelta

import panel as pn
import plotly.graph_objects as go
import pytest

import bencher as bn


class SimpleBench(bn.ParametrizedSweep):
    """Minimal benchmark for testing over_time + repeats."""

    backend = bn.StringSweep(["redis", "local"], doc="Backend")
    latency = bn.ResultFloat(units="ms", doc="Latency")

    offset = 0.0

    def benchmark(self):
        base = {"redis": 1.2, "local": 0.3}[self.backend]
        self.latency = base + self.offset + random.gauss(0, 0.05)


class FloatBench(bn.ParametrizedSweep):
    """Benchmark with one float input for curve tests."""

    size = bn.FloatSweep(default=50, bounds=[10, 100], samples=3, doc="Size")
    backend = bn.StringSweep(["redis", "local"], doc="Backend")
    time = bn.ResultFloat(units="ms", doc="Duration")

    offset = 0.0

    def benchmark(self):
        base = {"redis": 1.0, "local": 0.5}[self.backend]
        self.time = base * self.size * 0.01 + self.offset + random.gauss(0, 0.02)


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


def _find_plotly_figures(obj, depth=0):
    """Recursively find all Plotly go.Figure objects in a Panel layout."""
    found = []
    if depth > 10:
        return found
    if isinstance(obj, pn.pane.Plotly):
        fig = obj.object
        if isinstance(fig, go.Figure):
            found.append(fig)
        return found
    if isinstance(obj, go.Figure):
        found.append(obj)
        return found
    try:
        for child in obj:
            found.extend(_find_plotly_figures(child, depth + 1))
    except TypeError:
        pass
    return found


def _find_plotly_time_dropdowns(obj):
    """Find all Plotly figures that have over_time dropdown menus."""
    figures = _find_plotly_figures(obj)
    return [fig for fig in figures if fig.layout.updatemenus and len(fig.layout.updatemenus) > 0]


class ZeroDimBench(bn.ParametrizedSweep):
    """Benchmark with no input vars — 0D numeric result for over_time regression test."""

    value = bn.ResultFloat(units="m", doc="Value")

    offset = 0.0

    def benchmark(self):
        self.value = 2.844 + self.offset


# Module-scoped fixtures for shared benchmark results to reduce test execution time
@pytest.fixture(scope="module")
def simple_bench_repeats3_snapshots3():
    """SimpleBench result with repeats=3, snapshots=3 for multiple test classes."""
    benchable = SimpleBench()
    return _run_over_time(benchable, ["backend"], ["latency"], repeats=3, snapshots=3)


@pytest.fixture(scope="module")
def simple_bench_repeats1_snapshots3():
    """SimpleBench result with repeats=1, snapshots=3 for multiple test classes."""
    benchable = SimpleBench()
    return _run_over_time(benchable, ["backend"], ["latency"], repeats=1, snapshots=3)


@pytest.fixture(scope="module")
def float_bench_repeats3_snapshots3():
    """FloatBench result with repeats=3, snapshots=3 for multiple test classes."""
    benchable = FloatBench()
    return _run_over_time(benchable, ["size", "backend"], ["time"], repeats=3, snapshots=3)


class TestNumericOverTimeNotRoutedToImageSlider:
    """Regression tests: numeric ResultFloat must not be routed to _pane_over_time_slider.

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

    def test_bar_over_time_no_repeats(self, simple_bench_repeats1_snapshots3):
        """0 float + 1 cat + over_time -> bar with slider."""
        plots = simple_bench_repeats1_snapshots3.to_auto_plots()
        assert plots is not None
        assert len(plots) > 0
        # With multiple time points, bar should be wrapped in a Column with slider
        assert any(isinstance(p, pn.Column) for p in plots)

    def test_bar_over_time_with_repeats(self, simple_bench_repeats3_snapshots3):
        """0 float + 1 cat + repeats + over_time -> bar with slider."""
        plots = simple_bench_repeats3_snapshots3.to_auto_plots()
        assert plots is not None
        assert len(plots) > 0


class TestDistributionResultOverTime:
    """Test BoxWhisker/Violin with over_time slider."""

    def test_boxwhisker_over_time(self, simple_bench_repeats3_snapshots3):
        """0 float + 1 cat + repeats + over_time -> box whisker with slider."""
        plots = simple_bench_repeats3_snapshots3.to_auto_plots()
        assert plots is not None
        assert len(plots) > 0
        # With repeats > 1 and over_time, distribution plots should produce slider columns
        assert any(isinstance(p, pn.Column) for p in plots)


class TestCurveResultOverTime:
    """Test CurveResult with over_time slider."""

    def test_curve_over_time_with_repeats(self, float_bench_repeats3_snapshots3):
        """1 float + 1 cat + repeats + over_time -> curve with slider."""
        plots = float_bench_repeats3_snapshots3.to_auto_plots()
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

    def test_heatmap_over_time_with_repeats(self, float_bench_repeats3_snapshots3):
        """1 float + 1 cat + repeats + over_time -> heatmap with slider."""
        plots = float_bench_repeats3_snapshots3.to_auto_plots()
        assert plots is not None
        assert len(plots) > 0
        assert any(isinstance(p, pn.Column) for p in plots)


class TestOptunaResultOverTime:
    """Test OptunaResult with over_time (pandas Timestamp handling)."""

    def test_optuna_plots_over_time(self, float_bench_repeats3_snapshots3):
        """to_optuna_plots() must not crash when over_time=True (pandas Timestamps)."""
        optuna_plots = float_bench_repeats3_snapshots3.to_optuna_plots()
        assert optuna_plots is not None


class TestOverTimePlotlyDropdown:
    """Verify over_time uses Plotly dropdown menus."""

    def test_bar_over_time_uses_plotly_dropdown(self):
        """Over-time plots must have Plotly updatemenus dropdown controls."""
        benchable = SimpleBench()
        res = _run_over_time(benchable, ["backend"], ["latency"], repeats=1, snapshots=3)
        plots = res.to_auto_plots()
        figs_with_dropdown = _find_plotly_time_dropdowns(plots)
        assert len(figs_with_dropdown) > 0, (
            "Expected at least one Plotly figure with an over_time dropdown"
        )
        for fig in figs_with_dropdown:
            menu = fig.layout.updatemenus[0]
            assert menu.type == "dropdown"
            assert len(menu.buttons) > 1, "Dropdown should have multiple time entries"


class TestShowAggregatedTimeTab:
    """Tests for the show_aggregated_time_tab config parameter."""

    def _count_agg_entries(self, plots):
        """Count Plotly dropdown buttons that contain 'aggregated' in the label."""
        count = 0
        for fig in _find_plotly_figures(plots):
            if not fig.layout.updatemenus:
                continue
            for menu in fig.layout.updatemenus:
                if not menu.buttons:
                    continue
                for btn in menu.buttons:
                    if btn.label and "aggregated" in btn.label.lower():
                        count += 1
        return count

    def test_aggregated_tab_absent_by_default(self):
        """With default config (show_aggregated_time_tab=False), no aggregated entries."""
        benchable = SimpleBench()
        res = _run_over_time(benchable, ["backend"], ["latency"], repeats=1, snapshots=3)
        plots = res.to_auto_plots()
        assert self._count_agg_entries(plots) == 0

    def test_aggregated_tab_present_when_enabled(self):
        """With show_aggregated_time_tab=True, aggregated dropdown entry should appear."""
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
        assert self._count_agg_entries(plots) > 0

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
        assert self._count_agg_entries(plots) == 0


class TestMaxSliderPoints:
    """Tests for the max_slider_points config parameter."""

    def test_slider_subsampled(self):
        """With max_slider_points=2 and 5 snapshots, dropdown should have 2 entries."""
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
        figs = _find_plotly_time_dropdowns(plots)
        for fig in figs:
            n_buttons = len(fig.layout.updatemenus[0].buttons)
            assert n_buttons == 2, f"Expected 2 dropdown entries, got {n_buttons}"

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
        figs = _find_plotly_time_dropdowns(plots)
        for fig in figs:
            n_buttons = len(fig.layout.updatemenus[0].buttons)
            assert n_buttons == 5, f"Expected 5 dropdown entries, got {n_buttons}"

    def test_default_subsampling_caps_at_max(self):
        """With default max_slider_points=10 and 12 snapshots, dropdown capped at 10."""
        benchable = SimpleBench()
        res = _run_over_time(
            benchable,
            ["backend"],
            ["latency"],
            repeats=1,
            snapshots=12,
        )
        plots = res.to_auto_plots()
        figs = _find_plotly_time_dropdowns(plots)
        for fig in figs:
            n_buttons = len(fig.layout.updatemenus[0].buttons)
            assert n_buttons == 10, f"Expected 10 dropdown entries, got {n_buttons}"


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
