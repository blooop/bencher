"""Behavioral tests for bencher/results/volume_result.py (VolumeResult)."""

# pylint: disable=redefined-outer-name  # pytest fixtures are injected by name

import math

import pytest
import panel as pn

import bencher as bn


class VolBench(bn.ParametrizedSweep):
    """3-float-input benchmark with a deterministic, axis-separable result."""

    x = bn.FloatSweep(default=0, bounds=(0.0, 1.0), samples=2, units="m")
    y = bn.FloatSweep(default=0, bounds=(0.0, 1.0), samples=2, units="s")
    z = bn.FloatSweep(default=0, bounds=(0.0, 1.0), samples=2, units="kg")

    value = bn.ResultFloat(units="ul")

    def benchmark(self):
        self.value = self.x + 10 * self.y + 100 * self.z


class VolBenchNan(VolBench):
    """Same sweep but the origin point returns NaN (missing-value default)."""

    def benchmark(self):
        if self.x == 0.0 and self.y == 0.0 and self.z == 0.0:
            self.value = float("nan")
        else:
            self.value = self.x + 10 * self.y + 100 * self.z


def _run_cfg() -> bn.BenchRunCfg:
    return bn.BenchRunCfg(cache_results=False, cache_samples=False, auto_plot=False, repeats=1)


def _sweep(bench_class, input_vars):
    bench = bn.Bench("test_volume_result", bench_class(), run_cfg=_run_cfg())
    return bench.plot_sweep("volume sweep", input_vars=input_vars, result_vars=["value"])


def _find_plotly_pane(obj) -> pn.pane.Plotly:
    """Extract the single Plotly pane from the (possibly nested) panel layout."""
    if isinstance(obj, pn.pane.Plotly):
        return obj
    assert isinstance(obj, pn.layout.ListLike), f"unexpected container type {type(obj)}"
    panes = [c for c in obj if isinstance(c, pn.pane.Plotly)]
    assert len(panes) == 1, f"expected exactly one Plotly pane, got {len(panes)}"
    return panes[0]


@pytest.fixture(scope="module")
def vol_result():
    return _sweep(VolBench, ["x", "y", "z"])


@pytest.fixture(scope="module")
def vol_pane(vol_result):
    return _find_plotly_pane(vol_result.to_volume())


class TestVolumeConstruction:
    def test_to_volume_returns_plotly_backed_pane(self, vol_result):
        out = vol_result.to_volume()
        pane = _find_plotly_pane(out)
        assert isinstance(pane, pn.pane.Plotly)
        assert pane.name == "volume_plotly"

    def test_figure_contains_single_volume_trace(self, vol_pane):
        fig = vol_pane.object
        assert set(fig.keys()) == {"data", "layout"}
        assert len(fig["data"]) == 1
        assert type(fig["data"][0]).__name__ == "Volume"

    def test_axis_titles_embed_names_and_units(self, vol_pane):
        scene = vol_pane.object["layout"].scene
        assert scene.xaxis.title.text == "x [m]"
        assert scene.yaxis.title.text == "y [s]"
        assert scene.zaxis.title.text == "z [kg]"

    def test_layout_title_names_result_and_inputs(self, vol_pane):
        assert vol_pane.object["layout"].title.text == "value vs (x vs y vs z)"

    def test_trace_values_match_worker_output(self, vol_pane):
        trace = vol_pane.object["data"][0]
        xs, ys, zs, vals = list(trace.x), list(trace.y), list(trace.z), list(trace.value)
        assert len(vals) == 8  # 2 x 2 x 2 grid
        for x, y, z, v in zip(xs, ys, zs, vals):
            assert v == pytest.approx(x + 10 * y + 100 * z)
        assert trace.isomin == pytest.approx(0.0)
        assert trace.isomax == pytest.approx(111.0)

    def test_to_plot_delegates_to_volume(self, vol_result):
        pane = _find_plotly_pane(vol_result.to_plot())
        assert isinstance(pane, pn.pane.Plotly)
        assert pane.object["layout"].title.text == "value vs (x vs y vs z)"


class TestVolumeRejection:
    def test_one_float_sweep_rejected_without_override(self):
        """An unsupported shape must not produce a volume plot.

        The documented fallback is the filter-match diagnostics: a Markdown pane
        when print_debug is enabled (the default), otherwise None — never a Plotly pane.
        """
        res = _sweep(VolBench, ["x"])
        out = res.to_volume(override=False)
        assert not isinstance(out, (pn.pane.Plotly, pn.layout.ListLike))
        assert isinstance(out, pn.pane.Markdown)
        assert "matches: False" in out.object
        assert "float" in out.object  # the float-count requirement is what failed

    def test_one_float_sweep_rejection_is_silent_without_debug(self):
        res = _sweep(VolBench, ["x"])
        res.plt_cnt_cfg.print_debug = False
        assert res.to_volume(override=False) is None

    def test_over_time_returns_none(self, vol_result):
        prev = vol_result.bench_cfg.over_time
        vol_result.bench_cfg.over_time = True
        try:
            assert vol_result.to_volume(override=True) is None
        finally:
            vol_result.bench_cfg.over_time = prev


class TestVolumeNanRobustness:
    def test_nan_point_still_builds_volume(self):
        res = _sweep(VolBenchNan, ["x", "y", "z"])
        pane = _find_plotly_pane(res.to_volume())
        trace = pane.object["data"][0]
        vals = list(trace.value)
        assert len(vals) == 8
        assert sum(1 for v in vals if math.isnan(v)) == 1
        # iso bounds are computed from the finite values only
        assert trace.isomin == pytest.approx(1.0)
        assert trace.isomax == pytest.approx(111.0)
