"""Regression tests for the PIL-based Cartesian product animation renderer.

These tests lock current behavior so that performance optimizations
do not silently change the visual output.
"""

from __future__ import annotations

import hashlib

from PIL import Image, ImageDraw

from bencher.results.manim_cartesian.cartesian_product_cfg import CartesianProductCfg, SweepVar
from bencher.results.manim_cartesian.cartesian_product_scene import (
    Shape,
    StrobeShape,
    TimelineShape,
    render_animation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render_hash(shape: Shape, w: int = 200, h: int = 200) -> str:
    """Render a shape on a white canvas and return the MD5 of the pixel data."""
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    shape.draw(draw, 10, 10)
    return hashlib.md5(img.tobytes()).hexdigest()


def _simple_cfg() -> CartesianProductCfg:
    return CartesianProductCfg(
        all_vars=[SweepVar("a", [0, 1, 2])],
        result_names=["r"],
    )


# ---------------------------------------------------------------------------
# Shape.size() — exact pixel dimensions
# ---------------------------------------------------------------------------


class TestShapeSize:
    def test_leaf(self):
        assert Shape().size() == (20, 20)

    def test_row_3(self):
        row = Shape(children=[Shape() for _ in range(3)], direction="right", depth=0)
        assert row.size() == (66, 20)  # 3*20 + 2*3

    def test_col_2(self):
        col = Shape(children=[Shape() for _ in range(2)], direction="down", depth=0)
        assert col.size() == (20, 43)  # 2*20 + 1*3

    def test_grid_2x3(self):
        grid = Shape(
            children=[
                Shape(children=[Shape() for _ in range(3)], direction="right", depth=0)
                for _ in range(2)
            ],
            direction="down",
            depth=1,
        )
        assert grid.size() == (66, 43)

    def test_stack_3(self):
        stack = Shape(children=[Shape() for _ in range(3)], direction="stack", depth=2)
        assert stack.size() == (40, 36)  # 20 + 2*10, 20 + 2*8


# ---------------------------------------------------------------------------
# Extrude
# ---------------------------------------------------------------------------


class TestExtrude:
    def test_child_count(self):
        ext = Shape().extrude(4, "right", color_index=2)
        assert len(ext.children) == 4

    def test_depth_increment(self):
        ext = Shape().extrude(3, "down")
        assert ext.depth == 1

    def test_color_propagation(self):
        ext = Shape().extrude(3, "right", color_index=2)
        for child in ext.children:
            assert child.color_index == 2

    def test_size_after_extrude(self):
        ext = Shape().extrude(4, "right", color_index=2)
        assert ext.size() == (89, 20)  # 4*20 + 3*3

    def test_copy_independence(self):
        """Mutating an extruded copy must not affect the original."""
        original = Shape(color_index=0)
        ext = original.extrude(2, "right", color_index=3)
        ext.children[0].color_index = 99
        assert original.color_index == 0

    def test_nested_extrude(self):
        """Two successive extrusions produce correct nesting."""
        line = Shape().extrude(3, "right", color_index=0)
        grid = line.extrude(2, "down", color_index=1)
        assert len(grid.children) == 2
        assert len(grid.children[0].children) == 3
        assert grid.depth == 2


# ---------------------------------------------------------------------------
# TimelineShape / StrobeShape sizes
# ---------------------------------------------------------------------------


class TestTimelineShapeSize:
    def test_size(self):
        tl = TimelineShape(Shape(), 3)
        assert tl.size() == (404, 166)

    def test_not_leaf(self):
        tl = TimelineShape(Shape(), 2)
        assert not tl.is_leaf


class TestStrobeShapeSize:
    def test_size(self):
        st = StrobeShape(Shape(), 5, _simple_cfg())
        assert st.size() == (44, 60)

    def test_not_leaf(self):
        st = StrobeShape(Shape(), 1, _simple_cfg())
        assert not st.is_leaf


# ---------------------------------------------------------------------------
# Pixel-level draw regression (MD5 checksums)
# ---------------------------------------------------------------------------


class TestDrawRegression:
    """Pixel-exact checksums on a fixed canvas.

    If an optimization changes rendering output, these will fail — which
    is the point.  Update golden hashes only after visually confirming the
    new output is acceptable.
    """

    def test_leaf(self):
        assert _render_hash(Shape()) == "fb8d871ea7cb6c19f9c7e54d837c687f"

    def test_row3(self):
        row = Shape(children=[Shape() for _ in range(3)], direction="right", depth=0)
        assert _render_hash(row) == "a8c946ecb1dd581b21eed0e795e30885"

    def test_grid(self):
        grid = Shape(
            children=[
                Shape(children=[Shape() for _ in range(3)], direction="right", depth=0)
                for _ in range(2)
            ],
            direction="down",
            depth=1,
        )
        assert _render_hash(grid) == "ceae36e431bb2c991377ffcfa3006a85"

    def test_stack(self):
        stack = Shape(children=[Shape() for _ in range(3)], direction="stack", depth=2)
        assert _render_hash(stack) == "f3fd7f1df0e288ad0165027b6aa83610"

    def test_strobe_with_flash(self):
        row = Shape(children=[Shape() for _ in range(3)], direction="right", depth=0)
        st = StrobeShape(row, 3, _simple_cfg(), flash=0.8)
        assert _render_hash(st, 300, 200) == "9626250f8b66be862e0709f1c9814cad"

    def test_timeline(self):
        tl = TimelineShape(Shape(), 3)
        assert _render_hash(tl, 500, 200) == "c77e2b39b2cdc21008b7f7008955be3b"


# ---------------------------------------------------------------------------
# render_animation integration
# ---------------------------------------------------------------------------


class TestRenderAnimation:
    """Integration tests for the full render pipeline.

    We verify that output is a valid animated image with the expected
    visual content.  Frame counts are checked loosely (>= minimum unique)
    since encoding format and dedup strategy may change.
    """

    def test_2d(self, tmp_path):
        cfg = CartesianProductCfg(
            all_vars=[SweepVar("x", [0, 1, 2]), SweepVar("y", [0, 1])],
            result_names=["r"],
        )
        path = render_animation(
            cfg, width=320, height=200, fps=10, step_frames=2, output_dir=str(tmp_path)
        )
        img = Image.open(path)
        assert img.is_animated
        # Must have at least a few unique frames
        assert img.n_frames >= 3

    def test_3d_with_repeat(self, tmp_path):
        cfg = CartesianProductCfg(
            all_vars=[
                SweepVar("a", [0, 1]),
                SweepVar("b", [0, 1]),
                SweepVar("repeat", [1, 2, 3]),
            ],
            result_names=["r"],
        )
        path = render_animation(
            cfg, width=320, height=200, fps=10, step_frames=2, output_dir=str(tmp_path)
        )
        img = Image.open(path)
        assert img.is_animated
        assert img.n_frames >= 5

    def test_2d_with_over_time(self, tmp_path):
        cfg = CartesianProductCfg(
            all_vars=[SweepVar("x", [0, 1, 2]), SweepVar("over_time", [0, 1, 2])],
            result_names=["r"],
        )
        path = render_animation(
            cfg, width=320, height=200, fps=10, step_frames=2, output_dir=str(tmp_path)
        )
        img = Image.open(path)
        assert img.is_animated
        assert img.n_frames >= 5

    def test_empty_config(self, tmp_path):
        cfg = CartesianProductCfg(all_vars=[], result_names=["r"])
        path = render_animation(
            cfg, width=320, height=200, fps=10, step_frames=2, output_dir=str(tmp_path)
        )
        img = Image.open(path)
        assert img.n_frames >= 1

    def test_single_dim_size_1(self, tmp_path):
        cfg = CartesianProductCfg(
            all_vars=[SweepVar("x", [42])],
            result_names=["r"],
        )
        path = render_animation(
            cfg, width=320, height=200, fps=10, step_frames=2, output_dir=str(tmp_path)
        )
        img = Image.open(path)
        assert img.n_frames >= 1

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
        path = render_animation(
            cfg, width=640, height=360, fps=15, step_frames=4, output_dir=str(tmp_path)
        )
        img = Image.open(path)
        assert img.is_animated
        assert img.n_frames >= 10
