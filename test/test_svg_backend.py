"""The svg plotting backend: self-contained grids of panels, or SMIL frames, for a GitHub <img>."""

from __future__ import annotations

import logging
import math
import random
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import pandas as pd
import pytest

import bencher as bn
from bencher.optional_deps import pn
from bencher.plugins.registry import get_registry
from bencher.results import svg_result
from bencher.results.holoview_results.xy_scatter_result import xy_scatter
from bencher.results.svg_result import CHARTS, SvgPlugin
from test.helpers import assert_embeddable_svg

SVG_NS = "{http://www.w3.org/2000/svg}"


class Wave(bn.ParametrizedSweep):
    x = bn.FloatSweep(default=0, bounds=(0, 6), samples=5)
    y = bn.FloatSweep(default=0, bounds=(0, 3), samples=4)
    z = bn.FloatSweep(default=0, bounds=(0, 1), samples=3)
    kind = bn.StringSweep(["a", "b"])
    mode = bn.StringSweep(["p", "q", "r"])
    flag = bn.BoolSweep()

    out = bn.ResultFloat(units="v")
    ok = bn.ResultBool()
    note = bn.ResultString()

    phase = 0.0
    calls = 0

    def benchmark(self):
        # A small deterministic wobble per call, so repeats form a distribution.
        Wave.calls += 1
        wobble = 0.1 * math.sin(Wave.calls * 1.7)
        gain = {"a": 1.0, "b": 2.0}[self.kind] + {"p": 0, "q": 0.5, "r": 1}[self.mode]
        self.out = gain * math.sin(self.x + Wave.phase) + self.y + self.z + wobble
        self.ok = self.out > 0
        self.note = f"{self.kind}{self.mode}"


def _sweep(input_vars, result_vars=("out",), repeats=1, backend="svg") -> bn.BenchResult:
    run_cfg = bn.BenchRunCfg(
        repeats=repeats, backend=backend, cache_results=False, cache_samples=False
    )
    bench = bn.Bench(f"svg_{'_'.join(input_vars)}_{repeats}", Wave(), run_cfg=run_cfg)
    return bench.plot_sweep(
        "svg", input_vars=list(input_vars), result_vars=list(result_vars), auto_plot=False
    )


def _over_time_sweep(input_vars, steps=3, step=timedelta(days=1)) -> bn.BenchResult:
    run_cfg = bn.BenchRunCfg(over_time=True, backend="svg", cache_samples=False)
    bench = bn.Bench(f"svg_ot_{'_'.join(input_vars)}", Wave(), run_cfg=run_cfg)
    res = None
    try:
        for i in range(steps):
            Wave.phase = i * 0.5
            run_cfg.clear_cache = True
            run_cfg.clear_history = i == 0
            res = bench.plot_sweep(
                "svg_ot",
                input_vars=list(input_vars),
                result_vars=["out"],
                run_cfg=run_cfg,
                time_src=datetime(2025, 1, 1) + i * step,
                auto_plot=False,
            )
    finally:
        Wave.phase = 0.0
    assert res is not None
    return res


def test_a_panel_title_too_wide_for_its_panel_wraps_every_panel_title():
    # Times one second apart keep the time, so "over_time=<date> <time>" is too wide.
    svg = _over_time_sweep(["x", "kind"], step=timedelta(seconds=1)).to_svgs(["line"])
    svg = svg["line_out"]
    _assert_embeddable(svg)
    assert "2025-01-01 00:00:01" in svg
    # Every panel wraps alike, the one whose title would fit too.
    assert "over_time=2025-01-01" not in svg


def _frame_count(svg: str) -> int:
    return len(set(re.findall(r'id="bnframe(\d+)_\d+"', svg)))


def _panel_count(svg: str) -> int:
    return len(set(re.findall(r'id="bnpanel(\d+)"', svg)))


def _views(svg: str) -> int:
    """How many combinations of the unshown dims the SVG shows: panels, else frames."""
    return _panel_count(svg) or _frame_count(svg)


def _animated(svg: str) -> bool:
    return "<animate" in svg or "@keyframes" in svg


_assert_embeddable = assert_embeddable_svg


@pytest.fixture(scope="module")
def line_static() -> bn.BenchResult:
    return _sweep(["x"])


def test_static_line_is_one_frame_without_animation(line_static):
    svgs = line_static.to_svgs()
    assert list(svgs) == ["line_out"]
    svg = svgs["line_out"]
    _assert_embeddable(svg)
    assert "<animate" not in svg
    assert _frame_count(svg) == 1


def test_names_a_generic_font_stack_only(line_static):
    svg = line_static.to_svgs()["line_out"]
    families = set(re.findall(r"font-family: *([^;\"]+)", svg))
    assert families == {svg_result._FONT_STACK}


def test_line_draws_a_panel_per_value_of_a_second_categorical_dim():
    # kind is the hue; mode is not shown, so each of its values gets a panel.
    svg = _sweep(["x", "kind", "mode"]).to_svgs(["line"])["line_out"]
    _assert_embeddable(svg)
    assert _panel_count(svg) == 3
    assert _frame_count(svg) == 0
    assert "<animate" not in svg
    assert "mode=q" in svg


def test_grid_line_chart_draws_one_shared_legend():
    svg = _sweep(["x", "kind", "mode"]).to_svgs(["line"], svg_layout="grid")["line_out"]
    assert _panel_count(svg) == 3
    assert svg.count('<g id="legend_') == 1


def test_line_animates_over_a_second_categorical_dim_as_frames():
    svg = _sweep(["x", "kind", "mode"]).to_svgs(["line"], svg_layout="frames")["line_out"]
    root = _assert_embeddable(svg)
    assert _panel_count(svg) == 0
    assert _frame_count(svg) == 3
    animates = list(root.iter(f"{SVG_NS}animate"))
    assert animates
    assert all(a.get("calcMode") == "discrete" for a in animates)
    assert all(a.get("repeatCount") == "indefinite" for a in animates)
    assert "mode = q" in svg


def test_line_draws_a_panel_per_time_step():
    svg = _over_time_sweep(["x"]).to_svgs(["line"])["line_out"]
    _assert_embeddable(svg)
    assert _panel_count(svg) == 3
    assert "over_time=2025-01-03" in svg


def test_line_animates_over_time_as_frames():
    svg = _over_time_sweep(["x"]).to_svgs(["line"], svg_layout="frames")["line_out"]
    assert _frame_count(svg) == 3
    assert "<animate" in svg
    assert "over_time = 2025-01-03" in svg


@pytest.fixture(scope="module")
def heat4() -> bn.BenchResult:
    return _sweep(["x", "y", "z", "kind"])


def test_heatmap_panels_are_the_product_of_the_unshown_dims(heat4):
    svg = heat4.to_svgs(["heatmap"])["heatmap_out"]
    _assert_embeddable(svg)
    assert _panel_count(svg) == 3 * 2
    # One shared colour bar for every panel, and the walking highlight.
    assert svg.count('id="bnglow') == 6
    assert len(re.findall(r'<g id="axes_\d+"', svg)) == 1
    assert "@keyframes" in svg


def test_grid_walk_honours_reduced_motion(heat4):
    svg = heat4.to_svgs(["heatmap"])["heatmap_out"]
    style = re.search(r"<style>(.*?)</style>", svg).group(1)
    still, _, moving = style.partition("@media (prefers-reduced-motion:no-preference)")
    # Outside the media query nothing moves and the highlight borders are hidden.
    assert "animation" not in still
    assert "@keyframes" not in still
    assert "opacity:0" in still
    assert "@keyframes" in moving
    assert moving.count("animation:") == 2 * 6


def test_grid_is_deterministic(heat4):
    assert heat4.to_svgs(["heatmap"]) == heat4.to_svgs(["heatmap"])


@pytest.mark.parametrize(("limit", "panels", "frames"), [(6, 6, 0), (5, 0, 6)])
def test_auto_layout_switches_to_frames_past_the_panel_limit(
    heat4, monkeypatch, limit, panels, frames
):
    monkeypatch.setattr(svg_result, "MAX_SVG_PANELS", limit)
    svg = heat4.to_svgs(["heatmap"])["heatmap_out"]
    assert (_panel_count(svg), _frame_count(svg)) == (panels, frames)


def test_forced_grid_past_max_svg_frames_caps_and_says_so(heat4, monkeypatch):
    monkeypatch.setattr(svg_result, "MAX_SVG_FRAMES", 4)
    svg = heat4.to_svgs(["heatmap"], svg_layout="grid")["heatmap_out"]
    assert _panel_count(svg) == 4
    assert _frame_count(svg) == 0
    assert "first 4 of 6 panels" in svg


def test_grid_of_five_panels_drops_the_spare_axes(heat4, monkeypatch):
    monkeypatch.setattr(svg_result, "MAX_SVG_FRAMES", 5)
    svg = heat4.to_svgs(["heatmap"], svg_layout="grid")["heatmap_out"]
    assert _panel_count(svg) == 5
    # The only axes that is not a panel is the shared colour bar.
    assert len(re.findall(r'<g id="axes_\d+"', svg)) == 1


@pytest.mark.parametrize(
    ("count", "shape"),
    [(2, (1, 2)), (4, (2, 2)), (5, (2, 3)), (9, (3, 3)), (10, (3, 4)), (12, (3, 4)), (17, (4, 5))],
)
def test_grid_shape(count, shape):
    assert svg_result._grid_shape(count) == shape


@pytest.mark.parametrize(("layout", "panels", "frames"), [("grid", 6, 0), ("frames", 0, 6)])
def test_svg_layout_forces_a_grid_or_frames(heat4, monkeypatch, layout, panels, frames):
    monkeypatch.setattr(svg_result, "MAX_SVG_PANELS", 2)
    svg = heat4.to_svgs(["heatmap"], svg_layout=layout)["heatmap_out"]
    assert (_panel_count(svg), _frame_count(svg)) == (panels, frames)


def test_run_cfg_svg_layout_is_the_default():
    run_cfg = bn.BenchRunCfg(
        backend="svg", svg_layout="frames", cache_results=False, cache_samples=False
    )
    bench = bn.Bench("svg_layout_cfg", Wave(), run_cfg=run_cfg)
    res = bench.plot_sweep("svg", input_vars=["x", "kind", "mode"], auto_plot=False)
    assert _frame_count(res.to_svgs(["line"])["line_out"]) == 3
    assert _panel_count(res.to_svgs(["line"], svg_layout="grid")["line_out"]) == 3
    svg = _svg_panes(pn.Column(*res.to_auto_plots()))[0].object
    assert _frame_count(svg) == 3


def test_unknown_svg_layout_is_an_error(line_static):
    with pytest.raises(ValueError, match="svg_layout"):
        line_static.to_svgs(svg_layout="tiles")


def test_empty_svg_layout_is_an_error(line_static):
    with pytest.raises(ValueError, match="svg_layout"):
        line_static.to_svgs(svg_layout="")


def test_curve_reduces_repeats_and_draws_one_panel_per_unshown_dim():
    res = _sweep(["x", "kind", "mode"], repeats=2)
    svgs = res.to_svgs()
    assert set(svgs) == {"curve_out"}
    assert _panel_count(svgs["curve_out"]) == 3


def test_bar_draws_categorical_sweeps():
    svg = _sweep(["kind", "mode"]).to_svgs()["bar_out"]
    _assert_embeddable(svg)
    assert _frame_count(svg) == 1


def test_frames_are_capped_with_a_warning(monkeypatch, caplog):
    monkeypatch.setattr(svg_result, "MAX_SVG_FRAMES", 4)
    res = _sweep(["x", "y", "z", "kind"])
    with caplog.at_level(logging.WARNING, logger="bencher.results.svg_result"):
        svg = res.to_svgs(["heatmap"], svg_layout="frames")["heatmap_out"]
    assert _frame_count(svg) == 4
    assert "first 4 of 6 frames" in svg
    assert any("6 frames" in r.getMessage() for r in caplog.records)


def test_to_svg_files_writes_one_file_per_chart(tmp_path, line_static):
    paths = line_static.to_svg_files(tmp_path, prefix="demo_")
    assert [p.name for p in paths] == ["demo_line_out.svg"]
    ET.fromstring(paths[0].read_text())  # noqa: S314 - an SVG this test just drew


def test_unknown_chart_is_an_error(line_static):
    with pytest.raises(ValueError, match="Unknown svg charts"):
        line_static.to_svgs(["nope"])


# ---------------------------------------------------------------- selection


def _chosen(res: bn.BenchResult, backend: str | None) -> dict[str, str]:
    data = res.to_bench_data()
    return {p.name: p.backend for p in get_registry().select(data, backend=backend)}


@pytest.mark.parametrize(
    ("inputs", "repeats", "chart"),
    [(["x"], 1, "line"), (["x"], 2, "curve"), (["x", "y"], 1, "heatmap"), (["kind"], 1, "bar")],
)
def test_backend_svg_selects_the_svg_twin(inputs, repeats, chart):
    res = _sweep(inputs, repeats=repeats)
    assert _chosen(res, "svg")[chart] == "svg"
    # Without the preference the holoviews twin keeps winning.
    assert _chosen(res, None)[chart] == "holoviews"


def test_shapes_svg_does_not_draw_fall_back_to_holoviews():
    # 0-D over_time: the holoviews line draws a time series; the svg line needs a float.
    chosen = _chosen(_over_time_sweep([]), "svg")
    assert chosen.get("line") == "holoviews"
    # Bool results with repeats: holoviews draws a bar of the rate; svg does not.
    chosen = _chosen(_sweep(["kind"], result_vars=["ok"], repeats=2), "svg")
    assert chosen.get("bar") == "holoviews"
    # Chart types svg does not implement stay where they are.
    chosen = _chosen(_sweep(["x"], repeats=2), "svg")
    assert chosen["histogram"] == "holoviews"


def test_matching_shape_with_no_drawable_result_hands_over_to_the_twin():
    # A string result: the shape matches the svg heatmap, the result type does not.
    res = _sweep(["x", "y"], result_vars=["note"])
    sentinel = pn.pane.Markdown("twin")

    class Twin:
        def render(self, data):
            del data
            return sentinel

    plugin = SvgPlugin(chart=CHARTS["heatmap"], priority=0, fallback=Twin())  # ty: ignore[invalid-argument-type]
    assert plugin.render(res.to_bench_data()) is sentinel


def _twin_backend(name: str) -> str:
    return "plotly" if name in ("surface", "volume") else "holoviews"


def test_registered_svg_priorities_sit_just_below_their_twins():
    reg = get_registry()
    for name in CHARTS:
        twin = _twin_backend(name)
        assert reg.get(name).backend == twin
        assert reg.get(name, "svg").priority == reg.get(name, twin).priority - 1


def _svg_panes(pane) -> list[pn.pane.SVG]:
    found = []

    def walk(p):
        if isinstance(p, pn.pane.SVG):
            found.append(p)
        for child in getattr(p, "objects", None) or []:
            walk(child)

    walk(pane)
    return found


def test_run_cfg_backend_svg_is_a_backend_swap_end_to_end():
    svg_report = pn.Column(*_sweep(["x"]).to_auto_plots())
    panes = _svg_panes(svg_report)
    assert len(panes) == 1
    _assert_embeddable(panes[0].object)
    default_report = pn.Column(*_sweep(["x"], backend="panel").to_auto_plots())
    assert _svg_panes(default_report) == []


def test_line_draws_a_datetime_x_axis():
    """A time-typed input counts as a float var, so the line's x can be datetime64."""
    import numpy as np
    import xarray as xr

    from bencher.results.svg_result import _Layout, render_svg

    times = np.array(["2026-01-01", "2026-01-02", "2026-01-03"], dtype="datetime64[s]")
    da = xr.DataArray(
        [[1.0], [2.0], [1.5]], dims=("t", "repeat"), coords={"t": times, "repeat": [1]}
    )
    da.name = "v"
    svg = render_svg(CHARTS["line"], da, _Layout(x="t"))
    _assert_embeddable(svg)
    assert _frame_count(svg) == 1


def test_single_sample_line_and_all_nan_heatmap_render():
    import numpy as np
    import xarray as xr

    from bencher.results.svg_result import _Layout, render_svg

    one = xr.DataArray([3.0], dims=("x",), coords={"x": [0.5]}, name="v")
    _assert_embeddable(render_svg(CHARTS["line"], one, _Layout(x="x")))
    nan = xr.DataArray(
        np.full((2, 3), np.nan), dims=("x", "y"), coords={"x": [0, 1], "y": [0, 1, 2]}, name="v"
    )
    _assert_embeddable(render_svg(CHARTS["heatmap"], nan, _Layout(x="x", y="y")))


# ---------------------------------------------------------------- tier 1 parity charts


@pytest.mark.parametrize(
    ("chart", "inputs", "repeats", "frames"),
    [
        ("box_whisker", ["kind", "mode"], 3, 1),
        ("box_whisker", ["kind", "mode", "flag"], 3, 2),
        ("box_whisker", [], 4, 1),
        ("violin", ["kind", "mode", "flag"], 4, 2),
        ("scatter_jitter", ["kind"], 3, 1),
        ("histogram", [], 8, 1),
        ("scatter", ["kind", "mode", "flag"], 1, 2),
        ("band", ["x", "kind"], 2, 1),
        ("table", ["kind", "mode", "flag"], 1, 1),
    ],
)
def test_parity_chart_draws_an_embeddable_svg(chart, inputs, repeats, frames):
    svgs = _sweep(inputs, repeats=repeats).to_svgs([chart])
    assert list(svgs) == [f"{chart}_out"]
    svg = svgs[f"{chart}_out"]
    _assert_embeddable(svg)
    assert _views(svg) == frames
    assert _animated(svg) == (frames > 1)


def test_scatter_jitter_keeps_its_twins_one_cat_limit():
    assert _sweep(["kind", "mode"], repeats=5).to_svgs(["scatter_jitter"]) == {}


def test_distribution_charts_draw_every_repeat_as_a_dot():
    # 2 kinds x 5 repeats: one dot marker per sample.
    svg = _sweep(["kind"], repeats=5).to_svgs(["scatter_jitter"])["scatter_jitter_out"]
    root = _assert_embeddable(svg)
    assert len(list(root.iter(f"{SVG_NS}use"))) >= 2 * 5


def test_histogram_draws_a_panel_per_time_step():
    svg = _over_time_sweep([]).to_svgs(["histogram"])["histogram_out"]
    _assert_embeddable(svg)
    assert _panel_count(svg) == 3
    assert "over_time=2025-01-03" in svg


def test_band_pools_over_time_instead_of_animating():
    svg = _over_time_sweep(["kind"]).to_svgs(["band"])["band_out"]
    _assert_embeddable(svg)
    assert _frame_count(svg) == 1
    assert not _animated(svg)
    assert "over_time" in svg


def test_table_lists_every_sample_and_cuts_long_tables(monkeypatch):
    res = _sweep(["kind", "mode"])
    svg = res.to_svgs(["table"])["table_out"]
    _assert_embeddable(svg)
    assert all(word in svg for word in ("kind", "mode", "out"))
    monkeypatch.setattr(svg_result, "MAX_TABLE_ROWS", 4)
    svg = res.to_svgs(["table"])["table_out"]
    assert "... 2 more rows" in svg


def test_parity_charts_keep_text_at_least_15px_at_800px():
    """Every font size in a new chart is >= 9 pt on a 6.4 in figure (15.6 px at 800 px)."""
    for chart, inputs, repeats in [
        ("box_whisker", ["kind", "mode"], 3),
        ("histogram", [], 6),
        ("band", ["x"], 2),
        ("table", ["kind"], 1),
    ]:
        svg = _sweep(inputs, repeats=repeats).to_svgs([chart])[f"{chart}_out"]
        width_pt = float(re.search(r'<svg[^>]* width="([\d.]+)pt"', svg).group(1))
        sizes = [float(s) for s in re.findall(r"font-size: *([\d.]+)px", svg)]
        assert sizes, chart
        # matplotlib writes sizes in pt-sized px against a width in pt.
        assert min(sizes) * 800 / width_pt >= 15, (chart, min(sizes))


def test_default_to_svgs_skips_named_only_charts():
    svgs = _sweep(["kind"], repeats=3).to_svgs()
    assert set(svgs) == {"box_whisker_out"}


@pytest.mark.parametrize(
    ("chart", "inputs", "repeats"),
    [(["box_whisker"], ["kind"], 2), (["histogram"], [], 3)],
)
def test_backend_svg_selects_the_auto_parity_charts(chart, inputs, repeats):
    res = _sweep(inputs, repeats=repeats)
    assert _chosen(res, "svg")[chart[0]] == "svg"
    assert _chosen(res, None)[chart[0]] == "holoviews"


def _chosen_named(res: bn.BenchResult, name: str, backend: str | None) -> str:
    data = res.to_bench_data()
    (plugin,) = get_registry().select(data, include=[name], backend=backend)
    return plugin.backend


@pytest.mark.parametrize(
    ("chart", "inputs", "repeats", "backend"),
    [
        ("violin", ["kind"], 3, "svg"),
        ("scatter_jitter", ["kind"], 3, "svg"),
        ("scatter", ["kind"], 1, "svg"),
        ("band", ["x"], 2, "svg"),
        ("table", ["x"], 1, "svg"),
        # Outside the svg chart's rule: the holoviews twin draws it.
        ("violin", ["x"], 3, "holoviews"),
        ("scatter_jitter", ["kind", "mode"], 3, "holoviews"),
        ("scatter", ["kind"], 2, "holoviews"),
        ("xy_scatter", ["x"], 1, "holoviews"),
    ],
)
def test_named_only_parity_charts_select_by_shape(chart, inputs, repeats, backend):
    res = _sweep(inputs, repeats=repeats)
    assert _chosen_named(res, chart, "svg") == backend
    assert _chosen_named(res, chart, None) == "holoviews"


def test_named_only_svg_charts_are_never_auto_selected():
    reg = get_registry()
    for name, chart in CHARTS.items():
        assert reg.get(name, "svg").auto == chart.auto == reg.get(name, _twin_backend(name)).auto


# ---------------------------------------------------------------- tabular charts


class SvgCloud(bn.ParametrizedSweep):
    """Each sample measures a cloud of landing points, stored as a table."""

    wind = bn.FloatSweep(default=0, bounds=(0, 3), samples=4, units="m/s", doc="Cross wind")

    landings = bn.ResultDataSet(doc="One row per landing: dx, dy and the time of flight")

    def benchmark(self):
        rng = random.Random(int(self.wind * 10))  # noqa: S311 - test data, not crypto
        rows = [
            {
                "dx_mm": rng.gauss(self.wind * 4, 1.0 + self.wind * 0.5),
                "dy_mm": rng.gauss(0, 1.5),
                "t_s": 1.0 + 0.2 * rng.random(),
                "shot": i,
            }
            for i in range(120)
        ]
        self.landings = bn.ResultDataSet(pd.DataFrame(rows))


@pytest.fixture(scope="module")
def cloud() -> bn.BenchResult:
    run_cfg = bn.BenchRunCfg(backend="svg", cache_results=False, cache_samples=False)
    return (
        SvgCloud().to_bench(run_cfg).plot_sweep("svg_cloud", input_vars=["wind"], auto_plot=False)
    )


@pytest.mark.parametrize(
    ("chart", "options"),
    [
        ("xy_scatter", {"x": "dx_mm", "y": "dy_mm"}),
        ("xy_scatter", {"x": "dx_mm", "y": "dy_mm", "color": "t_s"}),
        ("xy_curve", {"x": "shot", "y": ["dx_mm", "dy_mm"], "markers": True}),
        ("xy_histogram", {"column": ["dx_mm", "dy_mm"], "bins": 12}),
        ("xy_hexbin", {"x": "dx_mm", "y": "dy_mm", "gridsize": 10}),
    ],
)
def test_tabular_chart_draws_one_panel_per_sample(cloud, chart, options):
    svgs = cloud.to_svgs([chart], **options)
    svg = svgs[f"{chart}_landings"]
    _assert_embeddable(svg)
    assert _panel_count(svg) == 4
    assert "wind=3" in svg


def test_tabular_chart_bad_column_hands_over_to_the_twin(cloud):
    assert cloud.to_svgs(["xy_scatter"], x="nope", y="dy_mm") == {}


class Declared(bn.ParametrizedSweep):
    """A ResultDataSet whose x/y spec is declared on the result var."""

    k = bn.IntSweep(default=1, bounds=(1, 2))
    pts = bn.ResultDataSet(container=xy_scatter(x="b", y="a", title="declared"))

    def benchmark(self):
        self.pts = bn.ResultDataSet(pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, float(self.k)]}))


def test_tabular_chart_reads_the_declared_container_spec():
    run_cfg = bn.BenchRunCfg(backend="svg", cache_results=False, cache_samples=False)
    res = Declared().to_bench(run_cfg).plot_sweep("declared", input_vars=["k"], auto_plot=False)
    svg = res.to_svgs(["xy_scatter"])["xy_scatter_pts"]
    _assert_embeddable(svg)
    assert "declared" in svg
    assert _panel_count(svg) == 2


def test_tabular_chart_renders_through_to_auto(cloud):
    report = pn.Column(
        *cloud.to_auto(plot_list=["xy_scatter"], backend="svg", x="dx_mm", y="dy_mm")
    )
    panes = _svg_panes(report)
    assert len(panes) == 1
    _assert_embeddable(panes[0].object)


# ---------------------------------------------------------------- surface and volume


def test_volume_draws_one_slice_panel_per_third_float():
    res = _sweep(["x", "y", "z"])
    svg = res.to_svgs(["volume"])["volume_out"]
    _assert_embeddable(svg)
    assert _panel_count(svg) == 3
    assert "z=0.5" in svg
    # Auto-selected under svg, like its plotly twin under the default backend.
    assert _chosen(res, "svg")["volume"] == "svg"
    assert _chosen(res, None)["volume"] == "plotly"


def test_volume_past_the_panel_limit_steps_through_slices(monkeypatch):
    monkeypatch.setattr(svg_result, "MAX_SVG_PANELS", 2)
    svg = _sweep(["x", "y", "z"]).to_svgs(["volume"])["volume_out"]
    assert _frame_count(svg) == 3


@pytest.mark.parametrize("inputs", [["x", "y"], ["x", "y", "z", "kind"]])
def test_volume_outside_its_twins_rule_falls_back(inputs):
    res = _sweep(inputs)
    assert res.to_svgs(["volume"]) == {}
    assert _chosen_named(res, "volume", "svg") == "plotly"


def test_volume_over_time_is_skipped_like_its_twin():
    import xarray as xr

    from bencher.results.svg_result import _layout_volume

    da = xr.DataArray(
        [[[[0.0, 1.0]] * 2] * 2], dims=("over_time", "x", "y", "z"), name="v"
    ).transpose("x", "y", "z", "over_time")
    assert _layout_volume(["x", "y", "z"], [], da) is None


def test_surface_draws_one_fixed_3d_view_with_every_repeat():
    res = _sweep(["x", "y"], repeats=3)
    svg = res.to_svgs(["surface"])["surface_out"]
    _assert_embeddable(svg)
    assert _views(svg) == 1
    assert not _animated(svg)
    # Every repeat over the 5 x 4 grid as a dot.
    assert len(list(ET.fromstring(svg).iter(f"{SVG_NS}use"))) >= 5 * 4 * 3  # noqa: S314
    assert _chosen_named(res, "surface", "svg") == "svg"
    assert _chosen_named(res, "surface", None) == "plotly"


def test_surface_draws_a_panel_per_category():
    svg = _sweep(["x", "y", "kind"]).to_svgs(["surface"])["surface_out"]
    _assert_embeddable(svg)
    assert _panel_count(svg) == 2
    assert "kind=b" in svg


def test_surface_is_named_only_and_falls_back_outside_its_rule():
    res = _sweep(["x", "y", "z"])
    assert "surface_out" not in res.to_svgs()
    assert res.to_svgs(["surface"]) == {}
    assert _chosen_named(res, "surface", "svg") == "plotly"


class WideTicks(bn.ParametrizedSweep):
    """Float inputs whose tick labels are wide: three fit a full chart, not a third of it."""

    block = bn.FloatSweep(default=512, bounds=(512, 65536), samples=3)
    entropy = bn.FloatSweep(default=0, bounds=(0, 1), samples=3)
    codec = bn.StringSweep(["zlib", "lz4", "zstd"])

    ratio = bn.ResultFloat()

    def benchmark(self):
        self.ratio = self.block / 65536 + self.entropy + len(self.codec)


def test_panel_tick_labels_too_wide_for_their_panel_are_thinned():
    run_cfg = bn.BenchRunCfg(backend="svg", cache_results=False, cache_samples=False)
    res = WideTicks().to_bench(run_cfg).plot_sweep("wide", auto_plot=False)
    svg = res.to_svgs(["heatmap"])["heatmap_ratio"]
    _assert_embeddable(svg)
    assert _panel_count(svg) == 3
    assert "6.554e+04" in svg
    # The middle label of three does not fit beside its neighbours in a third of the width.
    assert "3.302e+04" not in svg
