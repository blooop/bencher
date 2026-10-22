"""Regression tests for the SVG Cartesian product animation renderer.

These tests lock current behavior so that performance optimizations
do not silently change the visual output.
"""

# TimelineShape._skip_labels is set directly: it is the renderer's own overlay-mode
# switch, and there is no public way to ask for a label-less strip.

from __future__ import annotations

import hashlib
import itertools
import re
import xml.etree.ElementTree as ET

import pytest

from bencher.results.manim_cartesian.cartesian_product_cfg import CartesianProductCfg, SweepVar
from bencher.results.manim_cartesian.cartesian_product_scene import (
    DIM_PALETTE,
    FILM_LABEL_H,
    Cell,
    Group,
    Shape,
    StrobeShape,
    TimelineShape,
    place_shape,
    render_animation,
)
from bencher.results.manim_cartesian.svg_canvas import SvgCanvas, SvgDefs, animated_svg

SVG_NS = "{http://www.w3.org/2000/svg}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _markup(shape: Shape) -> str:
    """Draw a shape at (10, 10) and return its markup, shared definitions first."""
    defs = SvgDefs("t-")
    canvas = SvgCanvas(defs)
    shape.draw(canvas, 10, 10)
    return defs.markup() + canvas.markup()


def _render_hash(shape: Shape) -> str:
    """MD5 of the SVG markup a shape draws: it pins every coordinate and colour."""
    return hashlib.md5(_markup(shape).encode(), usedforsecurity=False).hexdigest()


def _render(cfg: CartesianProductCfg, tmp_path, **kwargs) -> ET.Element:
    """Render to a file, check it is well-formed SVG, and return its root element."""
    kwargs = {"width": 320, "height": 200, "fps": 10, "step_frames": 2, **kwargs}
    path = render_animation(cfg, output_dir=str(tmp_path), **kwargs)
    assert path.endswith(".svg")
    root = ET.parse(path).getroot()  # noqa: S314 - parses the file this test just wrote
    assert root.tag == f"{SVG_NS}svg"
    return root


def _frames(root: ET.Element) -> list[ET.Element]:
    """The top-level frame groups, in play order."""
    return root.findall(f"{SVG_NS}g")


def _simple_cfg() -> CartesianProductCfg:
    return CartesianProductCfg(
        all_vars=[SweepVar("a", [0, 1, 2])],
        result_names=["r"],
    )


# ---------------------------------------------------------------------------
# Shape.size() — exact pixel dimensions
# ---------------------------------------------------------------------------


class TestShapeConstruction:
    """`Shape` is a sum type: `Cell` (leaf) or `Group` (one or more children)."""

    def test_empty_group_is_rejected_at_construction(self):
        """A group of nothing is not a drawable shape.

        The pre-P12b encoding was one class with `children: list | None`, so
        `Shape(children=[])` constructed happily and then died several frames into a
        render inside `max()` on an empty sequence.
        """
        with pytest.raises(ValueError, match="at least one child"):
            Group(children=[])

    def test_only_cells_are_leaves(self):
        assert Cell().is_leaf
        assert not Group(children=[Cell()]).is_leaf


class TestShapeSize:
    def test_leaf(self):
        assert Cell().size() == (20, 20)

    def test_row_3(self):
        row = Group(children=[Cell() for _ in range(3)], direction="right", depth=0)
        assert row.size() == (66, 20)  # 3*20 + 2*3

    def test_col_2(self):
        col = Group(children=[Cell() for _ in range(2)], direction="down", depth=0)
        assert col.size() == (20, 43)  # 2*20 + 1*3

    def test_grid_2x3(self):
        grid = Group(
            children=[
                Group(children=[Cell() for _ in range(3)], direction="right", depth=0)
                for _ in range(2)
            ],
            direction="down",
            depth=1,
        )
        assert grid.size() == (66, 43)

    def test_stack_3(self):
        stack = Group(children=[Cell() for _ in range(3)], direction="stack", depth=2)
        assert stack.size() == (40, 36)  # 20 + 2*10, 20 + 2*8


# ---------------------------------------------------------------------------
# Extrude
# ---------------------------------------------------------------------------


class TestExtrude:
    def test_child_count(self):
        ext = Cell().extrude(4, "right", color_index=2)
        assert len(ext.children) == 4

    def test_depth_increment(self):
        ext = Cell().extrude(3, "down")
        assert ext.depth == 1

    def test_color_propagation(self):
        ext = Cell().extrude(3, "right", color_index=2)
        for child in ext.children:
            assert child.color_index == 2

    def test_size_after_extrude(self):
        ext = Cell().extrude(4, "right", color_index=2)
        assert ext.size() == (89, 20)  # 4*20 + 3*3

    def test_copy_independence(self):
        """Mutating an extruded copy must not affect the original."""
        original = Cell(color_index=0)
        ext = original.extrude(2, "right", color_index=3)
        ext.children[0].color_index = 99
        assert original.color_index == 0

    def test_nested_extrude(self):
        """Two successive extrusions produce correct nesting."""
        line = Cell().extrude(3, "right", color_index=0)
        grid = line.extrude(2, "down", color_index=1)
        assert len(grid.children) == 2
        assert len(grid.children[0].children) == 3
        assert grid.depth == 2


# ---------------------------------------------------------------------------
# TimelineShape / StrobeShape sizes
# ---------------------------------------------------------------------------


class TestTimelineShapeSize:
    def test_size(self):
        tl = TimelineShape(Cell(), 3)
        assert tl.size() == (404, 166)

    def test_not_leaf(self):
        tl = TimelineShape(Cell(), 2)
        assert not tl.is_leaf


class TestStrobeShapeSize:
    def test_size(self):
        st = StrobeShape(Cell(), 5, _simple_cfg())
        assert st.size() == (44, 60)

    def test_not_leaf(self):
        st = StrobeShape(Cell(), 1, _simple_cfg())
        assert not st.is_leaf


# ---------------------------------------------------------------------------
# Draw regression (MD5 of the SVG markup)
# ---------------------------------------------------------------------------


class TestDrawRegression:
    """Markup checksums: every coordinate, colour and shared definition.

    If an optimization changes rendering output, these will fail — which
    is the point.  Update golden hashes only after visually confirming the
    new output is acceptable.
    """

    def test_leaf(self):
        assert _render_hash(Cell()) == "f1facfadf7faf2e57601406678cf9463"

    def test_row3(self):
        row = Group(children=[Cell() for _ in range(3)], direction="right", depth=0)
        assert _render_hash(row) == "9cfebacd30323f501074cce0eaa24490"

    def test_grid(self):
        grid = Group(
            children=[
                Group(children=[Cell() for _ in range(3)], direction="right", depth=0)
                for _ in range(2)
            ],
            direction="down",
            depth=1,
        )
        assert _render_hash(grid) == "8ca46b73d20192bc67f5dd773664e45e"

    def test_stack(self):
        stack = Group(children=[Cell() for _ in range(3)], direction="stack", depth=2)
        assert _render_hash(stack) == "921fcdac900e9459ee71e468c5583a13"

    def test_strobe_with_flash(self):
        row = Group(children=[Cell() for _ in range(3)], direction="right", depth=0)
        st = StrobeShape(row, 3, _simple_cfg(), flash=0.8)
        assert _render_hash(st) == "b220672664d234100c9babe8b3b00b7d"

    def test_timeline(self):
        """Hashed with the frame labels off: the film chrome is what the hash is for,
        and ``test_timeline_labels_stay_in_the_label_band`` covers the labels.
        """
        tl = TimelineShape(Cell(), 3)
        tl._skip_labels = True
        assert _render_hash(tl) == "8050ddaacfaa66179e78cfafa6982a89"

    def test_timeline_labels_stay_in_the_label_band(self):
        """Turning labels off must remove the labels and change nothing else.

        Every label must also sit inside the band ``size()`` reserves for it
        (``FILM_LABEL_H``): one that overflowed upwards would paint over the frames.
        """
        markup = {}
        for skip in (False, True):
            tl = TimelineShape(Cell(), 3)
            tl._skip_labels = skip
            markup[skip] = _markup(tl)

        label_re = r"<text [^>]*>t=\d+</text>"
        labels = re.findall(label_re, markup[False])
        assert len(labels) == 3
        assert re.sub(label_re, "", markup[False]) == markup[True]

        _, total_h = TimelineShape(Cell(), 3).size()
        band_top = 10 + total_h - FILM_LABEL_H
        for label in labels:
            baseline = float(re.search(r' y="([\d.]+)"', label).group(1))
            assert band_top < baseline <= band_top + FILM_LABEL_H


# ---------------------------------------------------------------------------
# render_animation integration
# ---------------------------------------------------------------------------


class TestRenderAnimation:
    """Integration tests for the full render pipeline.

    We verify that output is a well-formed animated SVG with the expected
    structure.  Frame counts are checked loosely (>= minimum unique)
    since the dedup strategy may change.
    """

    def test_2d(self, tmp_path):
        cfg = CartesianProductCfg(
            all_vars=[SweepVar("x", [0, 1, 2]), SweepVar("y", [0, 1])],
            result_names=["r"],
        )
        root = _render(cfg, tmp_path)
        # Must have at least a few unique frames
        assert len(_frames(root)) >= 3

    def test_fps_above_1000_renders(self, tmp_path):
        root = _render(_simple_cfg(), tmp_path, fps=1001)
        assert len(_frames(root)) >= 1

    def test_3d_with_repeat(self, tmp_path):
        cfg = CartesianProductCfg(
            all_vars=[
                SweepVar("a", [0, 1]),
                SweepVar("b", [0, 1]),
                SweepVar("repeat", [1, 2, 3]),
            ],
            result_names=["r"],
        )
        root = _render(cfg, tmp_path)
        assert len(_frames(root)) >= 5

    def test_2d_with_over_time(self, tmp_path):
        cfg = CartesianProductCfg(
            all_vars=[SweepVar("x", [0, 1, 2]), SweepVar("over_time", [0, 1, 2])],
            result_names=["r"],
        )
        root = _render(cfg, tmp_path)
        assert len(_frames(root)) >= 5

    def test_empty_config(self, tmp_path):
        cfg = CartesianProductCfg(all_vars=[], result_names=["r"])
        root = _render(cfg, tmp_path)
        assert len(_frames(root)) >= 1

    def test_single_dim_size_1(self, tmp_path):
        cfg = CartesianProductCfg(
            all_vars=[SweepVar("x", [42])],
            result_names=["r"],
        )
        root = _render(cfg, tmp_path)
        assert len(_frames(root)) >= 1

    def test_5d_full(self, tmp_path):
        cfg = CartesianProductCfg(
            all_vars=[
                SweepVar("a", [0, 1, 2]),
                SweepVar("b", [0, 1, 2]),
                SweepVar("c", [0, 1, 2]),
                SweepVar("repeat", [1, 2]),
                SweepVar("over_time", [1, 2]),
            ],
            result_names=["r"],
        )
        root = _render(cfg, tmp_path, width=640, height=360, fps=15, step_frames=4)
        assert len(_frames(root)) >= 10


# ---------------------------------------------------------------------------
# SVG document structure
# ---------------------------------------------------------------------------


def _ids_and_refs(root: ET.Element) -> tuple[set[str], list[str]]:
    ids = {ref for el in root.iter() if (ref := el.get("id"))}
    refs = [el.get("href", "")[1:] for el in root.iter(f"{SVG_NS}use")]
    return ids, refs


class TestSvgDocument:
    """Properties the SVG encoding must keep, whatever the shapes look like."""

    def _cube(self, n: int) -> CartesianProductCfg:
        return CartesianProductCfg(
            all_vars=[SweepVar(name, list(range(n))) for name in ("x", "y", "z")],
            result_names=["r"],
        )

    def test_every_use_resolves_to_a_definition(self, tmp_path):
        root = _render(self._cube(4), tmp_path)
        ids, refs = _ids_and_refs(root)
        assert refs
        assert set(refs) <= ids

    def test_identical_copies_are_defined_once(self, tmp_path):
        """A 10x10x10 cube shows 1000 cells but draws far fewer rectangles.

        Without sharing, the last frame alone would hold 1000 ``<rect>``; every
        extrusion copy is a ``<use>`` of one definition instead.
        """
        root = _render(self._cube(10), tmp_path)
        rects = len(list(root.iter(f"{SVG_NS}rect")))
        assert rects < 100

    def test_only_the_last_frame_is_visible_without_animation(self, tmp_path):
        """A viewer without SMIL shows the finished product, not a blank canvas."""
        frames = _frames(_render(self._cube(3), tmp_path))
        assert len(frames) > 1
        assert [g.get("visibility") for g in frames] == ["hidden"] * (len(frames) - 1) + ["visible"]

    def test_frames_tile_one_loop(self, tmp_path):
        """Each frame is visible for one slot; the slots cover the loop with no overlap."""
        frames = _frames(_render(self._cube(3), tmp_path))
        durs = {g.find(f"{SVG_NS}animate").get("dur") for g in frames}
        assert len(durs) == 1
        slots = []
        for g in frames:
            anim = g.find(f"{SVG_NS}animate")
            times = [float(t) for t in anim.get("keyTimes").split(";")] + [1.0]
            i = anim.get("values").split(";").index("visible")
            slots.append((times[i], times[i + 1]))
        assert slots[0][0] == 0
        assert slots[-1][1] == 1
        assert all(a[1] == b[0] for a, b in itertools.pairwise(slots))

    def test_frame_slots_keep_their_durations(self):
        """Each slot lasts as long as its frames did, duplicates and end hold included."""
        frames = [("a", 100), ("b", 200), ("b", 300), ("c", 400), ("c", 1500)]
        svg = animated_svg(
            SvgDefs("t-"),
            [(f"<text>{name}</text>", ms) for name, ms in frames],
            10,
            10,
            (0, 0, 0),
        )
        root = ET.fromstring(svg)  # noqa: S314 - parses markup this test just built
        held = {}
        for g in _frames(root):
            anim = g.find(f"{SVG_NS}animate")
            dur_ms = float(anim.get("dur").removesuffix("s")) * 1000
            times = [float(t) for t in anim.get("keyTimes").split(";")] + [1.0]
            i = anim.get("values").split(";").index("visible")
            held[g.find(f"{SVG_NS}text").text] = (times[i + 1] - times[i]) * dur_ms
        assert held == pytest.approx({"a": 100, "b": 500, "c": 1900}, abs=1)

    def test_id_prefix_differs_between_animations(self, tmp_path):
        """Two animations inlined in one report page must not share ids."""
        ids_a, _ = _ids_and_refs(_render(self._cube(2), tmp_path))
        ids_b, _ = _ids_and_refs(_render(self._cube(3), tmp_path))
        assert ids_a.isdisjoint(ids_b)

    def test_long_1d_sweep_grows_linearly(self, tmp_path):
        """Each growth frame of a row adds one cell, so it must cost O(1) new markup.

        Writing every drawn cell again in each frame makes the file grow with the
        square of the value count: 300 values gave a 1.9 MB SVG.
        """

        def uses(n: int) -> int:
            cfg = CartesianProductCfg(all_vars=[SweepVar("x", list(range(n)))], result_names=["r"])
            return len(list(_render(cfg, tmp_path / str(n)).iter(f"{SVG_NS}use")))

        assert uses(240) < 3 * uses(120)

    def test_labels_are_escaped(self, tmp_path):
        cfg = CartesianProductCfg(all_vars=[SweepVar("a<b&c", [0, 1])], result_names=["r"])
        texts = [t.text for t in _render(cfg, tmp_path).iter(f"{SVG_NS}text")]
        assert "a<b&c" in texts


class TestAnimatedSvgTiming:
    """``animated_svg`` turns ``(markup, duration_ms)`` frames into SMIL slots."""

    @staticmethod
    def _groups(frames: list[tuple[str, int]]) -> list[ET.Element]:
        svg = animated_svg(SvgDefs("t-"), frames, 10, 10, (255, 255, 255))
        root = ET.fromstring(svg)  # noqa: S314 - parses markup this test just built
        return _frames(root)

    def test_slot_lengths_follow_durations_and_merge_repeats(self):
        """Two identical frames in a row merge into one slot holding both durations."""
        groups = self._groups([("<a/>", 100), ("<b/>", 100), ("<b/>", 100), ("<c/>", 300)])
        assert len(groups) == 3
        anims = [g.find(f"{SVG_NS}animate") for g in groups]
        assert {a.get("dur") for a in anims} == {"0.600s"}
        assert [(a.get("keyTimes"), a.get("values")) for a in anims] == [
            ("0;0.1667", "visible;hidden"),
            ("0;0.1667;0.5", "hidden;visible;hidden"),
            ("0;0.5", "hidden;visible"),
        ]

    def test_single_frame_is_static(self):
        """One frame (here two identical ones, merged) needs no animation at all."""
        groups = self._groups([("<a/>", 100), ("<a/>", 100)])
        assert len(groups) == 1
        assert groups[0].find(f"{SVG_NS}animate") is None
        assert groups[0].get("visibility") != "hidden"


class TestSvgDocumentIds:
    def test_ids_are_unique_and_prefixed(self, tmp_path):
        root = _render(
            CartesianProductCfg(
                all_vars=[SweepVar(n, list(range(4))) for n in ("x", "y", "z")],
                result_names=["r"],
            ),
            tmp_path,
        )
        ids = [ref for el in root.iter() if (ref := el.get("id"))]
        assert len(ids) == len(set(ids))
        assert all(re.fullmatch(r"c[0-9a-f]{6}-[0-9a-f]+", i) for i in ids)


def test_shrunk_strobe_keeps_its_tally_at_full_size(tmp_path):
    """A grid too big for the canvas is scaled down, but its tally marks are not.

    The marks are drawn after the scaled group, as direct children of the frame,
    so they keep their pixel size however much the grid shrinks.
    """
    cfg = CartesianProductCfg(
        all_vars=[
            SweepVar("x", list(range(10))),
            SweepVar("y", list(range(10))),
            SweepVar("repeat", [1, 2, 3]),
        ],
        result_names=["r"],
    )
    frames = _frames(_render(cfg, tmp_path))
    assert len(frames) >= 5
    tally = "#{:02x}{:02x}{:02x}".format(*cfg.strobe_color)

    def shrunk_with_tally(frame: ET.Element) -> bool:
        scaled = [g for g in frame.findall(f"{SVG_NS}g") if "scale(" in (g.get("transform") or "")]
        marks = [
            r
            for r in frame.findall(f"{SVG_NS}rect")
            if r.get("fill") == tally and r.get("fill-opacity") is None
        ]
        return bool(scaled) and bool(marks)

    assert any(shrunk_with_tally(f) for f in frames)


def test_close_alphas_with_different_colours_do_not_share_a_definition():
    """Two layer shades 1e-6 apart can still fall on two sides of a colour step."""
    channel = DIM_PALETTE[0][0]
    lighter = 100 / channel  # int(channel * lighter) == 100
    darker = lighter - 1e-6  # int(channel * darker) == 99
    assert round(lighter, 4) == round(darker, 4)
    defs = SvgDefs("t-")
    canvas = SvgCanvas(defs)
    place_shape(canvas, Cell(), 0, 0, lighter)
    place_shape(canvas, Cell(), 0, 0, darker)
    assert defs.markup().count("<g id=") == 2


def test_animations_that_draw_differently_get_different_files(tmp_path):
    """A shared path lets one render overwrite another, and their ids would clash."""

    def path(values, **kwargs) -> str:
        cfg = CartesianProductCfg(all_vars=[SweepVar("x", values)], result_names=["r"])
        return render_animation(cfg, output_dir=str(tmp_path), width=320, height=200, **kwargs)

    paths = [path([1, 2, 3]), path([1, "...", 3]), path([1, 2, 3], fps=10)]
    assert len(set(paths)) == 3
    assert path(["a", "b", "c"]) == paths[0]  # the values themselves are not drawn


def test_strobe_settings_and_step_frames_change_the_file(tmp_path):
    def path(strobe_pad=12, **kwargs) -> str:
        cfg = CartesianProductCfg(
            all_vars=[SweepVar("x", [1, 2, 3])], result_names=["r"], strobe_pad=strobe_pad
        )
        return render_animation(cfg, output_dir=str(tmp_path), width=320, height=200, **kwargs)

    assert path(strobe_pad=12) != path(strobe_pad=20)
    assert path(step_frames=2) != path(step_frames=4)
