"""Tests for the Cartesian product animation module.

Tests that exercise the data model run without manim installed.
Tests that render scenes are skipped when manim is not available.
"""

from __future__ import annotations

import itertools

import pytest

from bencher.results.manim_cartesian import MANIM_AVAILABLE
from bencher.results.manim_cartesian.cartesian_product_cfg import (
    CartesianProductCfg,
    SweepVar,
    from_bench_cfg,
)

# ---------------------------------------------------------------------------
# Data-model tests (no manim required)
# ---------------------------------------------------------------------------


class TestSweepVar:
    def test_basic(self):
        v = SweepVar("x", [1, 2, 3])
        assert v.name == "x"
        assert v.values == [1, 2, 3]

    def test_empty(self):
        v = SweepVar("empty", [])
        assert v.values == []


class TestCartesianProductCfg:
    def test_ndim(self):
        cfg = CartesianProductCfg(
            all_vars=[SweepVar("a", [1, 2]), SweepVar("b", [3, 4, 5])],
            result_names=["r"],
        )
        assert cfg.ndim == 2

    def test_shape(self):
        cfg = CartesianProductCfg(
            all_vars=[SweepVar("a", [1, 2]), SweepVar("b", [3, 4, 5])],
            result_names=["r"],
        )
        assert cfg.shape == (2, 3)

    def test_total_cells(self):
        cfg = CartesianProductCfg(
            all_vars=[
                SweepVar("a", [1, 2]),
                SweepVar("b", [3, 4, 5]),
                SweepVar("c", [0, 1]),
            ],
            result_names=["r"],
        )
        assert cfg.total_cells == 12

    def test_total_cells_1d(self):
        cfg = CartesianProductCfg(
            all_vars=[SweepVar("x", [0, 1, 2, 3, 4])],
            result_names=["y"],
        )
        assert cfg.total_cells == 5

    def test_empty(self):
        cfg = CartesianProductCfg()
        assert cfg.ndim == 0
        assert cfg.shape == ()
        assert cfg.total_cells == 1  # empty product = 1


class TestFromBenchCfg:
    """Test from_bench_cfg with a mock BenchCfg-like object."""

    class _MockVar:
        def __init__(self, name, vals):
            self.name = name
            self._vals = vals

        def values(self):
            return self._vals

    class _MockBenchCfg:
        def __init__(self, all_vars, result_vars):
            self.all_vars = all_vars
            self.result_vars = result_vars

    def test_conversion(self):
        bench_cfg = self._MockBenchCfg(
            all_vars=[
                self._MockVar("theta", [0.0, 1.57, 3.14]),
                self._MockVar("repeat", [1]),
            ],
            result_vars=[self._MockVar("out_sin", [])],
        )
        cfg = from_bench_cfg(bench_cfg)
        assert cfg.ndim == 2
        assert cfg.all_vars[0].name == "theta"
        assert cfg.all_vars[1].name == "repeat"
        assert cfg.result_names == ["out_sin"]

    def test_includes_meta_vars(self):
        """repeat and over_time must be included as full dimensions."""
        bench_cfg = self._MockBenchCfg(
            all_vars=[
                self._MockVar("x", [0, 1]),
                self._MockVar("repeat", [1, 2, 3]),
                self._MockVar("over_time", ["t0", "t1"]),
            ],
            result_vars=[self._MockVar("r", [])],
        )
        cfg = from_bench_cfg(bench_cfg)
        assert cfg.ndim == 3
        names = [v.name for v in cfg.all_vars]
        assert "repeat" in names
        assert "over_time" in names


class TestCellIndexIteration:
    """Verify that itertools.product produces the expected lexicographic order."""

    def test_2d_order(self):
        dims = [SweepVar("a", [0, 1]), SweepVar("b", [0, 1, 2])]
        combos = list(itertools.product(*[range(len(v.values)) for v in dims]))
        expected = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]
        assert combos == expected

    def test_3d_order_rightmost_fastest(self):
        dims = [SweepVar("a", [0, 1]), SweepVar("b", [0, 1]), SweepVar("c", [0, 1])]
        combos = list(itertools.product(*[range(len(v.values)) for v in dims]))
        # Rightmost (c) varies fastest
        assert combos[0] == (0, 0, 0)
        assert combos[1] == (0, 0, 1)
        assert combos[2] == (0, 1, 0)
        assert combos[3] == (0, 1, 1)
        assert len(combos) == 8


# ---------------------------------------------------------------------------
# Dimension layout tests (require manim)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not MANIM_AVAILABLE, reason="manim not installed")
class TestDimensionLayout:
    def test_1d_layout(self):
        from bencher.results.manim_cartesian.dimension_layout import build_tensor_layout

        vars_ = [SweepVar("x", [0, 1, 2])]
        group, cells = build_tensor_layout(vars_)
        assert len(cells) == 3
        assert (0,) in cells
        assert (2,) in cells

    def test_2d_layout(self):
        from bencher.results.manim_cartesian.dimension_layout import build_tensor_layout

        vars_ = [SweepVar("r", [0, 1]), SweepVar("c", [0, 1, 2])]
        group, cells = build_tensor_layout(vars_)
        assert len(cells) == 6
        assert (0, 0) in cells
        assert (1, 2) in cells

    def test_3d_layout(self):
        from bencher.results.manim_cartesian.dimension_layout import build_tensor_layout

        vars_ = [SweepVar("a", [0, 1]), SweepVar("b", [0, 1]), SweepVar("c", [0, 1])]
        group, cells = build_tensor_layout(vars_)
        assert len(cells) == 8
        assert (0, 0, 0) in cells
        assert (1, 1, 1) in cells

    def test_4d_layout(self):
        from bencher.results.manim_cartesian.dimension_layout import build_tensor_layout

        vars_ = [
            SweepVar("a", [0, 1]),
            SweepVar("b", [0, 1]),
            SweepVar("c", [0, 1]),
            SweepVar("d", [0, 1]),
        ]
        group, cells = build_tensor_layout(vars_)
        assert len(cells) == 16


# ---------------------------------------------------------------------------
# Scene render tests (require manim)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not MANIM_AVAILABLE, reason="manim not installed")
class TestSceneRenders:
    """Smoke tests: verify scenes render without error and produce video files."""

    @pytest.fixture(autouse=True)
    def _set_low_quality(self):
        from manim import config as manim_config

        manim_config.quality = "low_quality"

    def _render(self, cfg):
        from bencher.results.manim_cartesian import CartesianProductScene

        scene = CartesianProductScene(cfg, animation_speed=0.05)
        scene.render()
        path = scene.renderer.file_writer.movie_file_path
        assert path is not None
        return path

    def test_1d(self):
        cfg = CartesianProductCfg(
            all_vars=[SweepVar("x", [0, 1, 2])],
            result_names=["y"],
        )
        self._render(cfg)

    def test_2d(self):
        cfg = CartesianProductCfg(
            all_vars=[SweepVar("x", [0, 1]), SweepVar("y", [0, 1])],
            result_names=["r"],
        )
        self._render(cfg)

    def test_3d(self):
        cfg = CartesianProductCfg(
            all_vars=[
                SweepVar("a", [0, 1]),
                SweepVar("b", [0, 1]),
                SweepVar("repeat", [1, 2]),
            ],
            result_names=["r"],
        )
        self._render(cfg)

    def test_4d(self):
        cfg = CartesianProductCfg(
            all_vars=[
                SweepVar("a", [0, 1]),
                SweepVar("b", [0, 1]),
                SweepVar("c", [0, 1]),
                SweepVar("repeat", [1, 2]),
            ],
            result_names=["r"],
        )
        self._render(cfg)

    def test_5d_animated_outer(self):
        cfg = CartesianProductCfg(
            all_vars=[
                SweepVar("outer", [0, 1]),
                SweepVar("a", [0, 1]),
                SweepVar("b", [0, 1]),
                SweepVar("c", [0, 1]),
                SweepVar("repeat", [1, 2]),
            ],
            result_names=["r"],
        )
        self._render(cfg)


# ---------------------------------------------------------------------------
# Import guard test
# ---------------------------------------------------------------------------


class TestImportGuard:
    def test_manim_available_flag(self):
        """MANIM_AVAILABLE should be a bool."""
        assert isinstance(MANIM_AVAILABLE, bool)
