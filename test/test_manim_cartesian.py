"""Tests for the Cartesian product animation module.

Tests that exercise the data model (no external dependencies required).
Render tests are in test_cartesian_pil_renderer.py.
"""

from __future__ import annotations

import itertools


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
# Render tests are in test_cartesian_pil_renderer.py
# ---------------------------------------------------------------------------
