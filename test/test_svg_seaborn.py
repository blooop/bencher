"""The svg backend with and without seaborn: same panels either way, seaborn drawing when it imports.

Seaborn draws only in a seaborn ``svg_style``; ``plain`` draws with matplotlib.
"""

from __future__ import annotations

import builtins
import dataclasses
import logging
import re
import subprocess
import sys
import textwrap
import types
from pathlib import Path

import matplotlib as mpl
import numpy as np
import pytest
import xarray as xr

from bencher.results import svg_result
from test.test_svg_backend import _animated, _assert_embeddable, _sweep, _views

seaborn = pytest.importorskip("seaborn")

# chart, inputs, repeats, and the seaborn functions that draw its panels.
CASES = [
    ("line", ["x", "kind"], 1, {"lineplot"}),
    ("curve", ["x", "kind", "mode"], 3, {"lineplot"}),
    ("heatmap", ["x", "y"], 1, {"heatmap"}),
    ("bar", ["kind", "mode"], 1, {"barplot"}),
    ("box_whisker", ["kind", "mode", "flag"], 4, {"boxplot", "swarmplot"}),
    ("violin", ["kind", "mode"], 5, {"violinplot", "swarmplot"}),
    ("scatter_jitter", ["kind"], 5, {"swarmplot"}),
    ("scatter", ["kind", "mode"], 1, {"scatterplot"}),
    ("histogram", [], 20, {"histplot"}),
    ("band", ["x", "kind"], 3, {"lineplot", "scatterplot"}),
]


@pytest.fixture
def calls(monkeypatch) -> list[str]:
    """The names of the seaborn plotting functions called, in order."""
    called: list[str] = []
    names = {name for case in CASES for name in case[3]} | {"stripplot"}
    for name in names:
        real = getattr(seaborn, name)

        def spy(*args, _real=real, _name=name, **kwargs):
            called.append(_name)
            return _real(*args, **kwargs)

        monkeypatch.setattr(seaborn, name, spy)
    return called


def _no_seaborn(monkeypatch) -> None:
    # A None entry makes `import seaborn` raise ImportError, as on an install without it.
    monkeypatch.setitem(sys.modules, "seaborn", None)


@pytest.mark.parametrize(("chart", "inputs", "repeats", "drawers"), CASES)
def test_seaborn_draws_the_panels_when_installed(calls, chart, inputs, repeats, drawers):
    svg = _sweep(inputs, repeats=repeats).to_svgs([chart])[f"{chart}_out"]
    _assert_embeddable(svg)
    assert drawers <= set(calls)


@pytest.mark.parametrize(("chart", "inputs", "repeats", "drawers"), CASES)
def test_without_seaborn_the_same_panels_draw_with_matplotlib(
    monkeypatch, calls, chart, inputs, repeats, drawers
):
    del drawers
    res = _sweep(inputs, repeats=repeats)
    with_sns = res.to_svgs([chart])[f"{chart}_out"]
    calls.clear()
    with monkeypatch.context() as m:
        _no_seaborn(m)
        assert svg_result._seaborn() is None
        plain = res.to_svgs([chart])[f"{chart}_out"]
    assert calls == []
    _assert_embeddable(plain)
    assert _views(plain) == _views(with_sns)
    assert _animated(plain) == _animated(with_sns)
    assert plain != with_sns


@pytest.mark.parametrize("chart", ["box_whisker", "violin"])
def test_seaborn_swarm_is_deterministic(chart):
    res = _sweep(["kind", "mode"], repeats=6)
    assert res.to_svgs([chart]) == res.to_svgs([chart])


def test_seaborn_theme_does_not_leak_into_global_matplotlib_state():
    before = dict(mpl.rcParams)
    _sweep(["kind", "mode"], repeats=4).to_svgs(["box_whisker"])
    assert dict(mpl.rcParams) == before


def test_seaborn_panels_animate_as_frames(calls):
    res = _sweep(["kind", "mode", "flag"], repeats=4)
    svg = res.to_svgs(["box_whisker"], svg_layout="frames")["box_whisker_out"]
    _assert_embeddable(svg)
    assert "swarmplot" in calls
    assert _views(svg) == 2
    assert "<animate" in svg


def test_crowded_swarm_falls_back_to_the_jitter_strip(calls):
    # 2000 repeats in one column cannot sit side by side; every one is still a dot.
    repeats = 2000
    svg = _sweep(["kind"], repeats=repeats).to_svgs(["scatter_jitter"])["scatter_jitter_out"]
    _assert_embeddable(svg)
    assert "swarmplot" not in calls
    assert "stripplot" not in calls
    assert svg.count("<use") >= 2 * repeats


def test_roomy_swarm_is_a_beeswarm(calls):
    svg = _sweep(["kind"], repeats=40).to_svgs(["scatter_jitter"])["scatter_jitter_out"]
    _assert_embeddable(svg)
    assert "swarmplot" in calls


def test_heatmap_writes_values_in_big_cells_and_keeps_an_image_for_small_ones(monkeypatch, calls):
    res = _sweep(["x", "y"])
    big = res.to_svgs(["heatmap"])["heatmap_out"]
    assert "heatmap" in calls
    # 5 x 4 cells, each with its value written in it, besides the tick labels.
    plain_texts = 0
    with monkeypatch.context() as m:
        m.setattr(svg_result, "_SNS_HEATMAP_CELL", 1e6)
        small = res.to_svgs(["heatmap"])["heatmap_out"]
        plain_texts = small.count("<text")
    # The matplotlib heatmap is one inline image, besides the colour bar's.
    assert small.count("<image") == big.count("<image") + 1
    assert big.count("<text") >= plain_texts + 5 * 4


def _render_keeping_artists(name, da, cats, floats=(), svg_style="seaborn"):
    """Render ``name`` on ``da`` and return the artists its draw returned."""
    chart = svg_result.CHARTS[name]
    # The tabular charts draw a table sample with another signature; these tests take the value kind.
    assert isinstance(chart, svg_result.SvgChart)
    layout = chart.layout(list(floats), list(cats), da)
    kept = []

    def draw(ax, frame, std, layout, ctx, _draw=chart.draw):
        artists = _draw(ax, frame, std, layout, ctx)
        kept.extend(artists)
        return artists

    svg_result.render_svg(
        dataclasses.replace(chart, draw=draw), da, layout, title="t", svg_style=svg_style
    )
    return kept


def test_seaborn_boxes_sit_on_their_dots_when_the_chart_has_a_hue():
    from matplotlib.collections import PathCollection
    from matplotlib.patches import PathPatch

    rng = np.random.default_rng(0)
    da = xr.DataArray(
        rng.normal(size=(2, 2, 8)),
        dims=("kind", "mode", "repeat"),
        coords={"kind": ["a", "b"], "mode": ["p", "q"], "repeat": range(8)},
        name="out",
    )
    artists = _render_keeping_artists("box_whisker", da, ["kind", "mode"])
    # Two x levels, two hue levels: _groups puts each hue 0.2 either side of its x level.
    positions = [-0.2, 0.2, 0.8, 1.2]
    boxes = sorted(
        (v[:, 0].min() + v[:, 0].max()) / 2
        for v in (a.get_path().vertices for a in artists if isinstance(a, PathPatch))
    )
    dots = sorted(
        float(np.mean(a.get_offsets()[:, 0])) for a in artists if isinstance(a, PathCollection)
    )
    assert boxes == pytest.approx(positions)
    assert dots == pytest.approx(positions, abs=0.02)


@pytest.mark.parametrize("style", ["seaborn", "seaborn-ticks"])
def test_seaborn_styles_leave_the_font_family_alone(style):
    # The seaborn styles list Arial first, so the text would change with the fonts a host has.
    rc = svg_result._resolve_style(style).rc
    assert [k for k in rc if k.startswith("font.") and k != "font.size"] == []
    svg = _sweep(["kind", "mode"], repeats=4).to_svgs(["box_whisker"], svg_style=style)
    families = set(re.findall(r"font-family: *([^;\"]+)", svg["box_whisker_out"]))
    assert families <= {svg_result._FONT_STACK}


@pytest.mark.parametrize("style", ["seaborn", "seaborn-ticks"])
def test_seaborn_styles_text_is_at_least_the_floor(style):
    # 9 pt on a 6.4 in figure: 15 px when the SVG shows 800 px wide.
    rc = svg_result._resolve_style(style).rc
    for key in ("font.size", "axes.labelsize", "axes.titlesize", "xtick.labelsize"):
        assert rc[key] >= svg_result._MIN_FONT
    assert svg_result._resolve_style(style).font >= svg_result._MIN_FONT


DEEP = ("#4c72b0", "#dd8452", "#55a868")
TAB10 = ("#1f77b4", "#ff7f0e", "#2ca02c")


@pytest.mark.parametrize("chart", ["line", "box_whisker", "table"])
def test_seaborn_styles_use_seaborns_deep_palette(chart):
    # The line takes one value per point; the others every repeat.
    res = _sweep(["x", "kind"]) if chart == "line" else _sweep(["kind", "mode"], repeats=4)
    plain = res.to_svgs([chart], svg_style="plain")[f"{chart}_out"]
    for style in ("seaborn", "seaborn-ticks"):
        svg = res.to_svgs([chart], svg_style=style)[f"{chart}_out"]
        _assert_embeddable(svg)
        assert svg != plain
        if chart != "table":
            assert DEEP[0] in svg
            assert DEEP[1] in svg
            assert not any(c in svg for c in TAB10)
    if chart != "table":
        assert TAB10[0] in plain
        assert TAB10[1] in plain


def test_past_ten_hues_the_seaborn_palette_does_not_repeat():
    style = svg_result._resolve_style("seaborn")
    assert style.palette == svg_result._sns_palette(seaborn, "deep", 10)
    assert style.palette[:3] == DEEP
    assert len({style.colour(i, 10) for i in range(10)}) == 10
    many = [style.colour(i, 14) for i in range(14)]
    assert len(set(many)) == 14
    assert all(re.fullmatch(r"#[0-9a-f]{6}", c) for c in many)


def test_ten_hues_are_the_deep_palette():
    style = svg_result._resolve_style("seaborn")
    assert [style.colour(i, 10) for i in range(10)] == list(style.palette)


def test_darkgrid_draws_the_grey_face_and_a_white_grid():
    svg = _sweep(["x", "kind"]).to_svgs(["line"], svg_style="seaborn")["line_out"]
    assert "fill: #eaeaf2" in svg
    # The grid lines are white strokes over the face.
    assert re.search(r'id="ytick_\d+".*?stroke: #ffffff', svg, re.DOTALL)
    ticks = _sweep(["x", "kind"]).to_svgs(["line"], svg_style="seaborn-ticks")["line_out"]
    assert "#eaeaf2" not in ticks


@pytest.mark.parametrize(
    ("style", "spines"), [("seaborn-ticks", False), ("seaborn", True), ("plain", True)]
)
def test_the_ticks_style_despines(style, spines):
    rng = np.random.default_rng(0)
    da = xr.DataArray(
        rng.normal(size=(2, 2, 8)),
        dims=("kind", "mode", "repeat"),
        coords={"kind": ["a", "b"], "mode": ["p", "q"], "repeat": range(8)},
        name="out",
    )
    artists = _render_keeping_artists("box_whisker", da, ["kind", "mode"], svg_style=style)
    ax = artists[0].axes
    assert ax.spines["top"].get_visible() is spines
    assert ax.spines["right"].get_visible() is spines
    assert ax.spines["left"].get_visible()


@pytest.mark.parametrize("style", ["seaborn-ticks", "seaborn", "plain"])
def test_only_the_outer_grid_edges_carry_ticks(style):
    """In a 2x2 grid the inner edges have no tick labels; the ticks style pulls their
    spines flush and drops their tick marks, so no bare ticks hang on a detached line."""
    rng = np.random.default_rng(0)
    da = xr.DataArray(
        rng.normal(size=(5, 2, 4, 3)),
        dims=("x", "kind", "day", "repeat"),
        coords={"x": np.arange(5.0), "kind": ["p", "q"], "day": list("abcd"), "repeat": range(3)},
        name="out",
    )
    artists = _render_keeping_artists("line", da, ["kind", "day"], ["x"], svg_style=style)
    panels = list(dict.fromkeys(a.axes for a in artists))
    assert [ax.get_title() for ax in panels] == [f"day={d}" for d in "abcd"]
    offset = 5 if style == "seaborn-ticks" else 0
    for i, ax in enumerate(panels):
        for edge, axis, outer in (("bottom", ax.xaxis, i >= 2), ("left", ax.yaxis, i % 2 == 0)):
            tick = axis.get_major_ticks()[0]
            assert tick.label1.get_visible() is outer
            assert ax.spines[edge].get_position() == ("outward", offset if outer else 0)
            if style == "seaborn-ticks":
                assert tick.tick1line.get_visible() is outer


@pytest.mark.parametrize("style", ["seaborn", "seaborn-ticks"])
def test_seaborn_styles_are_the_same_bytes_in_two_processes(style):
    script = textwrap.dedent(
        f"""
        import hashlib
        from test.test_svg_backend import _sweep
        svgs = _sweep(["kind", "mode"], repeats=6).to_svgs(
            ["box_whisker", "violin", "heatmap", "table"], svg_style={style!r}
        )
        svgs.update(_sweep(["x", "y"]).to_svgs(["heatmap"], svg_style={style!r}))
        print(hashlib.sha256("".join(svgs.values()).encode()).hexdigest())
        """
    )
    root = Path(__file__).resolve().parent.parent
    digests = {
        subprocess.run(
            [sys.executable, "-c", script], cwd=root, check=True, capture_output=True, text=True
        ).stdout.split()[-1]
        for _ in range(2)
    }
    assert len(digests) == 1


@pytest.mark.parametrize("style", svg_result.SVG_STYLES)
def test_no_style_leaks_into_global_state(style):
    before = dict(mpl.rcParams)
    _sweep(["kind", "mode"], repeats=4).to_svgs(["box_whisker", "table"], svg_style=style)
    _sweep(["x", "y"]).to_svgs(["surface"], svg_style=style)
    assert dict(mpl.rcParams) == before
    assert svg_result._style() is svg_result._PLAIN


def test_without_seaborn_every_style_draws_plain_with_one_warning(monkeypatch, caplog):
    res = _sweep(["kind", "mode"], repeats=4)
    plain = res.to_svgs(["box_whisker", "violin", "table"], svg_style="plain")
    monkeypatch.setattr(svg_result, "_warned_no_seaborn", False)
    caplog.set_level(logging.WARNING, logger=svg_result.log.name)
    with monkeypatch.context() as m:
        _no_seaborn(m)
        for style in ("seaborn", "seaborn-ticks"):
            assert res.to_svgs(["box_whisker", "violin", "table"], svg_style=style) == plain
    warnings = [r for r in caplog.records if "svg_style" in r.getMessage()]
    assert len(warnings) == 1


def test_the_run_config_svg_style_is_the_default():
    import bencher as bn

    assert tuple(bn.BenchRunCfg.param.svg_style.objects) == bn.SVG_STYLES
    assert bn.BenchRunCfg().svg_style == "seaborn-ticks"
    res = _sweep(["kind", "mode"])
    assert res.to_svgs(["bar"]) == res.to_svgs(["bar"], svg_style="seaborn-ticks")
    res.bench_cfg.svg_style = "plain"
    assert res.to_svgs(["bar"]) == res.to_svgs(["bar"], svg_style="plain")
    assert res.to_svgs(["bar"]) != res.to_svgs(["bar"], svg_style="seaborn")


def _grid_da(dims, shape):
    return xr.DataArray(
        np.arange(float(np.prod(shape))).reshape(shape),
        dims=dims,
        coords={d: np.arange(float(n)) for d, n in zip(dims, shape, strict=True)},
        name="out",
    )


@pytest.mark.parametrize(
    ("chart", "dims", "shape", "cell", "cmap"),
    [
        ("heatmap", ("y", "x"), (4, 5), None, "rocket"),
        ("heatmap", ("y", "x"), (4, 5), 1e6, "rocket"),
        ("surface", ("y", "x"), (4, 5), None, "mako"),
        ("volume", ("z", "y", "x"), (3, 4, 5), None, "mako"),
    ],
)
def test_seaborn_styles_use_seaborns_colour_maps(monkeypatch, chart, dims, shape, cell, cmap):
    # A huge cell floor sends the heatmap to its matplotlib image, not seaborn's mesh.
    if cell is not None:
        monkeypatch.setattr(svg_result, "_SNS_HEATMAP_CELL", cell)
    da = _grid_da(dims, shape)
    floats = ["x", "y", "z"][: len(dims)]

    def cmaps(style):
        artists = _render_keeping_artists(chart, da, [], floats=floats, svg_style=style)
        return {a.get_cmap().name for a in artists if hasattr(a, "get_cmap")}

    assert cmap in cmaps("seaborn")
    assert cmap not in cmaps("plain")


def test_a_draw_that_raises_puts_back_the_plain_style():
    chart = svg_result.CHARTS["bar"]

    def boom(*args, **kwargs):
        assert svg_result._style().name == "seaborn"
        raise RuntimeError("boom")

    da = xr.DataArray([1.0, 2.0], dims=("kind",), coords={"kind": ["a", "b"]}, name="out")
    layout = chart.layout([], ["kind"], da)
    with pytest.raises(RuntimeError, match="boom"):
        svg_result.render_svg(
            dataclasses.replace(chart, draw=boom), da, layout, svg_style="seaborn"
        )
    assert svg_result._style() is svg_result._PLAIN


def test_render_svg_rejects_an_unknown_svg_style():
    chart = svg_result.CHARTS["bar"]
    da = xr.DataArray([1.0, 2.0], dims=("kind",), coords={"kind": ["a", "b"]}, name="out")
    with pytest.raises(ValueError, match="svg_style"):
        svg_result.render_svg(chart, da, chart.layout([], ["kind"], da), svg_style="pastel")


def test_unknown_svg_style_is_an_error():
    with pytest.raises(ValueError, match="svg_style"):
        _sweep(["kind"]).to_svgs(["bar"], svg_style="pastel")


def _import_raises(monkeypatch) -> None:
    # As seaborn 0.12 does on matplotlib 3.9: the import fails with no ImportError.
    real = builtins.__import__

    def broken(name, *args, **kwargs):
        if name == "seaborn" or name.startswith("seaborn."):
            raise AttributeError("module 'matplotlib.cm' has no attribute 'register_cmap'")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken)


def _too_old(monkeypatch) -> None:
    old = types.ModuleType("seaborn")
    old.__version__ = "0.12.2"
    monkeypatch.setitem(sys.modules, "seaborn", old)


@pytest.mark.parametrize("unusable", [_import_raises, _too_old])
def test_an_unusable_seaborn_falls_back_to_matplotlib(monkeypatch, calls, unusable):
    res = _sweep(["kind", "mode"], repeats=4)
    with monkeypatch.context() as m:
        unusable(m)
        assert svg_result._seaborn() is None
        svgs = res.to_svgs(["table", "bar", "box_whisker"])
    assert calls == []
    for svg in svgs.values():
        _assert_embeddable(svg)


def test_seaborn_panels_do_not_log_matplotlib_category_info(caplog):
    # bencher logs at INFO; seaborn's categorical plots trip matplotlib.category's notice.
    caplog.set_level(logging.INFO)
    _sweep(["kind", "mode", "flag"], repeats=4).to_svgs(["box_whisker", "violin", "bar"])
    assert [r for r in caplog.records if r.name == "matplotlib.category"] == []


def test_sns_artists_puts_back_the_limits_and_labels_a_seaborn_heatmap_moves():
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    try:
        ax.set_xlim(-0.5, 4.5)
        ax.set_ylim(-0.5, 3.5)
        ax.set_xlabel("XL")
        ax.set_ylabel("YL")
        svg_result._sns_artists(ax, lambda: seaborn.heatmap(np.ones((4, 5)), ax=ax, cbar=False))
        assert ax.get_xlim() == (-0.5, 4.5)
        assert ax.get_ylim() == (-0.5, 3.5)
        assert not ax.yaxis_inverted()
        assert (ax.get_xlabel(), ax.get_ylabel()) == ("XL", "YL")
    finally:
        plt.close(fig)


def test_seaborn_heatmap_cells_sit_on_the_chart_axes():
    from matplotlib.collections import QuadMesh

    da = xr.DataArray(
        np.arange(20.0).reshape(4, 5),
        dims=("y", "x"),
        coords={"y": np.arange(4.0), "x": np.arange(5.0)},
        name="out",
    )
    artists = _render_keeping_artists("heatmap", da, [], floats=["x", "y"])
    (mesh,) = [a for a in artists if isinstance(a, QuadMesh)]
    to_data = mesh.get_transform() - mesh.axes.transData
    edges = to_data.transform(mesh.get_coordinates().reshape(-1, 2))
    assert (edges[:, 0].min(), edges[:, 0].max()) == pytest.approx((-0.5, 4.5))
    assert (edges[:, 1].min(), edges[:, 1].max()) == pytest.approx((-0.5, 3.5))


def test_seaborn_heatmap_between_the_two_sizes_draws_cells_without_values(monkeypatch, calls):
    from matplotlib.collections import QuadMesh
    from matplotlib.image import AxesImage
    from matplotlib.text import Text

    monkeypatch.setattr(svg_result, "_ANNOT_CELL", (1e6, 1e6))
    da = xr.DataArray(
        np.arange(20.0).reshape(4, 5),
        dims=("y", "x"),
        coords={"y": np.arange(4.0), "x": np.arange(5.0)},
        name="out",
    )
    artists = _render_keeping_artists("heatmap", da, [], floats=["x", "y"])
    assert calls == ["heatmap"]
    assert len([a for a in artists if isinstance(a, QuadMesh)]) == 1
    assert [a for a in artists if isinstance(a, (AxesImage, Text))] == []


def test_seaborn_violin_draws_only_dots_for_a_group_with_no_spread(calls):
    from matplotlib.collections import PathCollection, PolyCollection
    from matplotlib.lines import Line2D

    rng = np.random.default_rng(0)
    values = rng.normal(size=(2, 2, 8))
    values[0, 0, :] = 1.0
    da = xr.DataArray(
        values,
        dims=("kind", "mode", "repeat"),
        coords={"kind": ["a", "b"], "mode": ["p", "q"], "repeat": range(8)},
        name="out",
    )
    artists = _render_keeping_artists("violin", da, ["kind", "mode"])
    assert "violinplot" in calls
    violins = sorted(
        float(path.vertices[:, 0].min() + path.vertices[:, 0].max()) / 2
        for a in artists
        if isinstance(a, PolyCollection)
        for path in a.get_paths()
    )
    dots = sorted(
        float(np.mean(a.get_offsets()[:, 0])) for a in artists if isinstance(a, PathCollection)
    )
    assert violins == pytest.approx([0.2, 0.8, 1.2])
    assert dots == pytest.approx([-0.2, 0.2, 0.8, 1.2], abs=0.02)
    assert [a for a in artists if isinstance(a, Line2D)] == []


def test_seaborn_band_draws_one_median_line():
    from matplotlib.lines import Line2D

    rng = np.random.default_rng(0)
    da = xr.DataArray(
        rng.normal(size=(5, 6)),
        dims=("x", "repeat"),
        coords={"x": np.arange(5.0), "repeat": range(6)},
        name="out",
    )
    artists = _render_keeping_artists("band", da, [], floats=["x"])
    medians = [a for a in artists if isinstance(a, Line2D) and a.get_label() == "median"]
    assert len(medians) == 1
    assert medians[0].axes.get_lines() == medians
