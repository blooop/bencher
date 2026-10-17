"""Evidence is text only: every metric is drawn with text GitHub renders in the PR body.

No form links an image. Two or more swept inputs get an emoji heatmap of the percent
change; a repeat-to-repeat spread as large as the change gets an xychart with pale
±1 std lines; a negative scalar or labels that collide get ``diff``-fence bars; many
categories get a table; points that only one side has get a table over the overlap
and a note. Every metric ends with a ``<details>`` block holding a CSV of what the
chart shows.
"""

from __future__ import annotations

import csv
import io
import math
import re
import warnings

import numpy as np
import pytest
import xarray as xr

import bencher as bn
from bencher.evidence import (
    MAX_HEATMAP_TABLES,
    MERMAID_AFTER_COLOR,
    BandChart,
    BeforeAfterBars,
    DiffBars,
    DiffRow,
    Heatmap,
    OverlapTable,
    _heat_legend,
    _heat_mark,
    _named,
    _Profile,
    _profile,
    data_block,
    diff_bars,
    heatmap_table,
    mermaid_chart,
    overlap_table,
    plan_chart,
)
from bencher.render import main, save_result

_JITTER = (0.6, -0.6, 0.3, -0.3)


class Rig(bn.ParametrizedSweep):
    speed = bn.FloatSweep(default=1.0, bounds=(1.0, 3.0), samples=3)
    load = bn.FloatSweep(default=1.0, bounds=(1.0, 2.0), samples=2)
    mode = bn.StringSweep(["eco", "normal", "sport"])
    robot = bn.StringSweep([f"r{i:02d}" for i in range(31)])
    gain = bn.FloatSweep(default=0.2)
    offset = bn.FloatSweep(default=0.0)
    noisy = bn.BoolSweep(default=False)
    drop_above = bn.FloatSweep(default=99.0)

    cost = bn.ResultFloat(units="m", direction=bn.OptDir.minimize)
    score = bn.ResultFloat(units="pt", direction=bn.OptDir.maximize)
    drift = bn.ResultFloat(units="m", direction=bn.OptDir.none)

    _trial = 0

    def benchmark(self):
        Rig._trial += 1
        jitter = _JITTER[Rig._trial % 4] if self.noisy else 0.0
        scale = {"eco": 1.0, "normal": 1.5, "sport": 2.0}[self.mode]
        base = self.gain * self.speed * self.load * scale + int(self.robot[1:]) * 0.01
        self.cost = math.nan if self.speed > self.drop_above else base + self.offset + jitter
        self.score = 10.0 * base
        self.drift = self.offset + jitter * 0.01


def _rig(gain, inputs=("speed",), results=("cost",), repeats=1, **const):
    consts = {"gain": gain, **const}
    bench = bn.Bench(f"rig_{gain}_{'_'.join(inputs)}_{sorted(const.items())}", Rig())
    res = bench.collect(
        input_vars=list(inputs),
        result_vars=list(results),
        const_vars=list(consts.items()),
        run_cfg=bn.BenchRunCfg(repeats=repeats),
    )
    bench.close()
    return res


def _csv(md: str, metric: str) -> list[list[str]]:
    block = re.search(
        rf"<details><summary>data: {metric}</summary>\n\n```csv\n(.*?)```\n\n</details>",
        md,
        re.DOTALL,
    )
    assert block, f"no data block for {metric}"
    return list(csv.reader(io.StringIO(block[1])))


def _no_image(md: str) -> None:
    assert "![" not in md
    assert ".png" not in md


# --- two or more swept inputs: an emoji heatmap ------------------------------------


def test_two_swept_inputs_draw_an_emoji_heatmap_of_the_percent_change():
    md = bn.evidence_markdown(_rig(0.3, ("speed", "load")), _rig(0.2, ("speed", "load")))
    _no_image(md)
    assert "| speed ↓ load → | 1 | 2 |" in md
    rows = re.findall(r"^\| (1|2|3) \| (.*) \|$", md, re.MULTILINE)
    assert [r[0] for r in rows] == ["1", "2", "3"]
    for _, cells in rows:
        # cost is minimized and fell by a third: better, the strongest color.
        assert cells.split(" | ") == ["🟦 -33.3%", "🟦 -33.3%"]
    assert "🟦 better by ≥ 20%" in md
    assert "(lower is better)" in md


def test_heatmap_colors_follow_the_direction_not_the_sign():
    # score is maximized: the same fall is worse.
    md = bn.evidence_markdown(
        _rig(0.3, ("speed", "load"), results=("score",)),
        _rig(0.2, ("speed", "load"), results=("score",)),
    )
    assert "🟥 -33.3%" in md
    assert "🟦 -" not in md
    assert "(higher is better)" in md


def test_a_heatmap_without_a_direction_shows_only_which_way_it_moved():
    md = bn.evidence_markdown(
        _rig(0.0, ("speed", "load"), results=("drift",), offset=1.0),
        _rig(0.0, ("speed", "load"), results=("drift",), offset=2.0),
    )
    assert "🟨 +100%" in md
    assert "no direction" in md


def test_a_third_swept_input_gets_one_heatmap_per_value():
    inputs = ("speed", "load", "mode")
    md = bn.evidence_markdown(_rig(0.3, inputs), _rig(0.2, inputs))
    _no_image(md)
    assert md.count("| speed ↓ load → |") == 3
    for mode in ("eco", "normal", "sport"):
        assert f"mode = {mode}" in md


def test_a_third_input_with_many_values_is_averaged_and_says_so():
    inputs = ("speed", "load", "robot")
    md = bn.evidence_markdown(_rig(0.3, inputs), _rig(0.2, inputs))
    assert md.count("| speed ↓ load → |") == 1
    assert "mean over robot" in md


def test_layer_values_that_round_alike_get_distinct_titles():
    coords = {"a": [1, 2], "b": [1, 2], "z": [1.00001, 1.00002]}
    side = _profile(xr.DataArray(np.arange(1.0, 9.0).reshape(2, 2, 2), coords=coords))
    md = heatmap_table("m", None, plan_chart(side, side))
    titles = re.findall(r"^z = (.*):$", md, re.MULTILINE)
    assert len(titles) == len(set(titles)) == 2


@pytest.mark.parametrize("direction", ["minimize", "none"])
def test_the_legend_says_n_a_also_means_before_is_zero(direction):
    coords = {"a": [1, 2], "b": [1, 2]}
    base = _profile(xr.DataArray([[0.0, 1.0], [1.0, 1.0]], coords=coords))
    cand = _profile(xr.DataArray([[5.0, 1.0], [1.0, 1.0]], coords=coords))
    md = heatmap_table("m", None, plan_chart(base, cand, direction=direction))
    assert "| 1 | n/a |" in md
    assert "n/a: no sample, or before is 0" in md


def test_sides_that_swept_the_same_inputs_in_another_order_draw_a_heatmap():
    before = xr.DataArray([[1.0, 2.0], [3.0, 4.0]], coords={"a": [1, 2], "b": [10, 20]})
    after = (before * 2).transpose("b", "a")
    plan = plan_chart(_profile(before), _profile(after))
    assert isinstance(plan, Heatmap)
    assert (plan.row_input, plan.col_input) == ("a", "b")
    assert plan.grids[0].after == ((2.0, 4.0), (6.0, 8.0))


def test_the_heatmap_data_block_has_one_row_per_cell():
    md = bn.evidence_markdown(_rig(0.3, ("speed", "load")), _rig(0.2, ("speed", "load")))
    rows = _csv(md, "cost")
    assert rows[0] == ["speed", "load", "before", "after", "change_percent"]
    assert len(rows) == 1 + 3 * 2
    assert float(rows[1][4]) == pytest.approx(-100 / 3)


def test_each_heatmap_cell_shows_the_change_at_its_own_row_and_column():
    # A square grid where every cell differs: a row/column swap prints other numbers.
    coords = {"a": [1, 2, 3, 4], "b": [10, 20, 30, 40]}
    before = np.full((4, 4), 100.0)
    after = 100.0 + np.arange(1.0, 17.0).reshape(4, 4)  # (row=3, col=1) is 114
    plan = plan_chart(
        _profile(xr.DataArray(before, coords=coords, dims=("a", "b"))),
        _profile(xr.DataArray(after, coords=coords, dims=("a", "b"))),
        margin_percent=0.0,
    )
    assert isinstance(plan, Heatmap)
    md = heatmap_table("m", None, plan)
    assert "| 4 | 🟨 +13.0% | 🟨 +14.0% | 🟨 +15.0% | 🟨 +16.0% |" in md
    assert "| 1 | 🟨 +1.0% | 🟨 +2.0% | 🟨 +3.0% | 🟨 +4.0% |" in md
    rows = _csv(data_block("m", plan), "m")
    assert ["4", "20", "100", "114", "14"] in rows
    assert ["2", "40", "100", "108", "8"] in rows


def test_each_layer_table_shows_the_change_of_its_own_layer():
    coords = {"a": [1, 2], "b": [10, 20], "mode": ["eco", "normal", "sport"]}
    dims = ("a", "b", "mode")
    before = np.full((2, 2, 3), 100.0)
    after = np.broadcast_to(np.array([110.0, 120.0, 130.0]), (2, 2, 3))
    plan = plan_chart(
        _profile(xr.DataArray(before, coords=coords, dims=dims)),
        _profile(xr.DataArray(after.copy(), coords=coords, dims=dims)),
    )
    assert isinstance(plan, Heatmap)
    md = heatmap_table("m", None, plan)
    for mode, cell in (("eco", "+10.0%"), ("normal", "+20.0%"), ("sport", "+30.0%")):
        table = re.search(rf"^mode = {mode}:\n\n(.*?)(?:\n\n|\Z)", md, re.MULTILINE | re.DOTALL)
        assert table, f"no table for mode = {mode}"
        assert table[1].count(cell) == 4, table[1]
    rows = _csv(data_block("m", plan), "m")
    assert rows[0] == ["a", "b", "mode", "before", "after", "change_percent"]
    assert ["2", "20", "sport", "100", "130", "30"] in rows


def test_a_long_numeric_heatmap_axis_is_binned_and_says_so():
    coords = {"a": list(range(31)), "b": list(range(13))}
    before = np.ones((31, 13))
    after = 1.0 + np.arange(31 * 13, dtype=float).reshape(31, 13)
    plan = plan_chart(
        _profile(xr.DataArray(before, coords=coords, dims=("a", "b"))),
        _profile(xr.DataArray(after, coords=coords, dims=("a", "b"))),
    )
    assert isinstance(plan, Heatmap)
    assert len(plan.row_labels) <= 30
    assert len(plan.col_labels) <= 12
    (grid,) = plan.grids
    assert len(grid.after) == len(plan.row_labels)
    assert all(len(r) == len(plan.col_labels) for r in grid.after)
    # The first bin averages rows 0-1 and columns 0-1.
    assert plan.row_labels[0] == plan.col_labels[0] == "0.5"
    assert grid.after[0][0] == pytest.approx(float(after[:2, :2].mean()))
    md = heatmap_table("m", None, plan)
    assert f"a is binned to {len(plan.row_labels)} groups of consecutive values." in md
    assert f"b is binned to {len(plan.col_labels)} groups of consecutive values." in md


def test_a_heatmap_of_four_inputs_averages_over_both_extra_inputs():
    coords = {"a": [1, 2], "b": [1, 2], "c": [1, 2], "d": [1, 2, 3]}
    side = _profile(xr.DataArray(np.ones((2, 2, 2, 3)), coords=coords, dims=tuple(coords)))
    plan = plan_chart(side, side)
    assert isinstance(plan, Heatmap)
    assert len(plan.grids) == 1
    assert plan.layer_input is None
    assert "Each cell is the mean over c (2 values), d (3 values)." in heatmap_table(
        "m", None, plan
    )


def test_a_third_input_past_max_heatmap_tables_is_averaged():
    coords = {"a": [1, 2], "b": [1, 2], "c": list(range(MAX_HEATMAP_TABLES + 1))}
    shape = (2, 2, MAX_HEATMAP_TABLES + 1)
    side = _profile(xr.DataArray(np.ones(shape), coords=coords, dims=tuple(coords)))
    md = heatmap_table("m", None, plan_chart(side, side))
    assert md.count("| a ↓ b → |") == 1
    assert "c = " not in md
    assert f"Each cell is the mean over c ({MAX_HEATMAP_TABLES + 1} values)." in md


@pytest.mark.parametrize(
    ("change", "direction", "mark"),
    [
        (-25.0, "minimize", "🟦"),  # better by at least 2x the margin
        (-15.0, "minimize", "🟩"),  # better, between the margin and 2x the margin
        (15.0, "minimize", "🟧"),  # worse, between the margin and 2x the margin
        (25.0, "minimize", "🟥"),
        (5.0, "minimize", "⬜"),  # inside the margin
        (-5.0, "maximize", "⬜"),
        (-15.0, "none", "🟪"),  # a fall with no direction
        (15.0, "none", "🟨"),
    ],
)
def test_heat_mark_colors(change, direction, mark):
    assert _heat_mark(change, direction, 10.0) == mark


def test_a_zero_margin_legend_says_no_change():
    assert "⬜ no change" in _heat_legend("minimize", 0.0)
    assert "⬜ no change" in _heat_legend("none", 0.0)
    assert "within" not in _heat_legend("minimize", 0.0)


# --- spread as large as the change: pale ±1 std lines ------------------------------


def test_a_spread_as_large_as_the_change_draws_pale_std_lines():
    md = bn.evidence_markdown(
        _rig(0.3, repeats=4, noisy=True), _rig(0.3, repeats=4, noisy=True, offset=-0.05)
    )
    _no_image(md)
    (chart,) = re.findall(r"```mermaid\n(.*?)```", md, re.DOTALL)
    names = re.findall(r'^    line "([^"]+)" \[', chart, re.MULTILINE)
    assert names == [
        "before",
        "after",
        "before -1 std",
        "before +1 std",
        "after -1 std",
        "after +1 std",
    ]
    # The std lines are the series colors at 40% opacity: dimmer than the means on both themes.
    assert (
        'plotColorPalette: "#8c8c8c, #2f81f7, #8c8c8c66, #8c8c8c66, #2f81f766, #2f81f766"' in chart
    )
    assert "±1 std" in chart
    rows = _csv(md, "cost")
    assert rows[0] == ["speed", "before", "before_std", "after", "after_std"]
    assert len(rows) == 4


# --- diff-fence bars ---------------------------------------------------------------


def test_the_bar_chart_sets_its_color():
    chart = mermaid_chart("m", None, BeforeAfterBars(0.3, 0.2), None)
    assert f'plotColorPalette: "{MERMAID_AFTER_COLOR}"' in chart


def test_a_negative_scalar_draws_diff_bars_from_zero():
    md = bn.evidence_markdown(
        _rig(0.0, inputs=(), results=("drift",), offset=-0.4),
        _rig(0.0, inputs=(), results=("drift",), offset=-0.2),
    )
    _no_image(md)
    fence = re.search(r"```diff\n(.*?)```", md, re.DOTALL)[1]
    before = re.search(r"^- before .*$", fence, re.MULTILINE)[0]
    after = re.search(r"^\+ after .*$", fence, re.MULTILINE)[0]
    assert "  -0.4  " in before
    assert "  -0.2  " in after
    # The bars end at one zero column; the before bar is twice as long.
    assert before.index("│") == after.index("│")
    assert before.count("█") == 2 * after.count("█")
    assert _csv(md, "drift") == [["before", "after"], ["-0.4", "-0.2"]]


def test_a_noisy_scalar_draws_diff_bars_with_the_spread():
    md = bn.evidence_markdown(
        _rig(0.3, inputs=(), repeats=4, noisy=True),
        _rig(0.3, inputs=(), repeats=4, noisy=True, offset=0.01),
    )
    _no_image(md)
    fence = re.search(r"```diff\n(.*?)```", md, re.DOTALL)[1]
    assert re.search(r"^- before +\S+ ± \S+  ", fence, re.MULTILINE)


def test_labels_that_collide_draw_diff_bars_with_distinct_labels():
    x = (1.0, 1.0 + 1e-15)
    side = _Profile(
        swept=("speed",),
        x=x,
        mean=np.array([1.0, 2.0]),
        std=np.zeros(2),
        samples=2,
        points=(np.array([1.0]), np.array([2.0])),
    )
    other = _Profile(
        swept=("speed",),
        x=x,
        mean=np.array([1.5, 2.5]),
        std=np.zeros(2),
        samples=2,
        points=(np.array([1.5]), np.array([2.5])),
    )
    plan = plan_chart(side, other)
    assert isinstance(plan, DiffBars)
    labels = [row.label for row in plan.rows]
    assert len(set(labels)) == len(labels) == 2
    fence = diff_bars("m", None, plan)
    assert fence.count("\n- ") == 2
    assert fence.count("\n+ ") == 2


def test_many_categories_get_a_table():
    md = bn.evidence_markdown(_rig(0.3, ("robot",)), _rig(0.2, ("robot",)))
    _no_image(md)
    assert "| robot | before | after | change | 95% CI |" in md
    assert len(re.findall(r"^\| r\d\d \|", md, re.MULTILINE)) == 31
    assert len(_csv(md, "cost")) == 32


# --- the overlap: what both sides measured -----------------------------------------


def test_a_point_with_no_sample_is_left_out_and_named():
    md = bn.evidence_markdown(_rig(0.3), _rig(0.2, drop_above=2.5))
    _no_image(md)
    assert "| speed | before | after | change |" in md
    assert re.findall(r"^\| (\d) \|", md, re.MULTILINE) == ["1", "2"]
    assert "Left out: speed=3 (no sample after)." in md
    assert [r[0] for r in _csv(md, "cost")] == ["speed", "1", "2"]


def test_sides_that_swept_different_values_compare_the_shared_ones():
    wide = Rig.param.speed.with_samples(5)  # 1, 1.5, 2, 2.5, 3
    bench = bn.Bench("rig_wide", Rig())
    cand = bench.collect(input_vars=[wide], result_vars=["cost"], const_vars=[("gain", 0.2)])
    bench.close()
    md = bn.evidence_markdown(_rig(0.3), cand)
    _no_image(md)
    assert re.findall(r"^\| ([\d.]+) \|", md, re.MULTILINE) == ["1", "2", "3"]
    assert "Left out: speed=1.5, 2.5 (after only)." in md


def test_sides_that_swept_different_inputs_compare_the_shared_input():
    md = bn.evidence_markdown(_rig(0.3), _rig(0.2, ("speed", "load")))
    _no_image(md)
    assert "| speed | before | after | change |" in md
    assert "load" in re.search(r"^Left out: .*$", md, re.MULTILINE)[0]


def test_sides_with_no_shared_input_compare_the_overall_means():
    md = bn.evidence_markdown(_rig(0.3, inputs=()), _rig(0.2))
    _no_image(md)
    assert "| all points |" in md
    assert "speed" in re.search(r"^Left out: .*$", md, re.MULTILINE)[0]


def test_a_heatmap_with_no_shared_point_names_what_each_side_swept():
    base = _profile(xr.DataArray([[1.0, 2.0], [3.0, 4.0]], coords={"a": [1, 2], "b": [10, 20]}))
    cand = _profile(xr.DataArray([[1.0, 2.0], [3.0, 4.0]], coords={"a": [1, 2], "b": [30, 40]}))
    plan = plan_chart(base, cand)
    assert isinstance(plan, OverlapTable)
    assert plan.rows == ()
    assert "b=10, 20 (before only)" in plan.left_out
    assert "b=30, 40 (after only)" in plan.left_out
    assert "no point has a sample on both sides" in overlap_table("m", None, plan)


def test_sides_with_no_shared_input_and_no_sample_before_give_no_row():
    base = _profile(xr.DataArray([math.nan, math.nan], coords={"a": [1, 2]}))
    cand = _profile(xr.DataArray([1.0, 2.0], coords={"b": [1, 2]}))
    plan = plan_chart(base, cand)
    assert isinstance(plan, OverlapTable)
    assert plan.rows == ()
    assert "no sample before" in plan.left_out


def test_a_scalar_with_no_sample_after_prints_no_row():
    base = _profile(xr.DataArray([1.0, 1.2], dims=("repeat",)))
    cand = _profile(xr.DataArray([math.nan, math.nan], dims=("repeat",)))
    plan = plan_chart(base, cand)
    assert isinstance(plan, OverlapTable)
    assert plan.rows == ()
    md = overlap_table("m", None, plan)
    assert "no sample after" in md
    assert not re.search(r"^\|", md, re.MULTILINE)


def test_a_long_left_out_list_names_eight_and_counts_the_rest():
    assert _named("x", list(range(11))) == "x=0, 1, 2, 3, 4, 5, 6, 7 and 3 more"
    assert _named("x", list(range(8))) == "x=0, 1, 2, 3, 4, 5, 6, 7"


def test_the_overlap_names_each_reason_a_point_was_left_out():
    base = _profile(xr.DataArray([1.0, math.nan, math.nan, 4.0], coords={"x": [1, 2, 3, 4]}))
    cand = _profile(xr.DataArray([2.0, math.nan, 5.0, 6.0], coords={"x": [2, 3, 4, 5]}))
    plan = plan_chart(base, cand)
    assert isinstance(plan, OverlapTable)
    assert [r.label for r in plan.rows] == ["4"]
    assert "x=1 (before only)" in plan.left_out
    assert "x=2 (no sample before)" in plan.left_out
    assert "x=3 (no sample on either side)" in plan.left_out
    assert "x=5 (after only)" in plan.left_out


@pytest.mark.parametrize("nan_after", [False, True])
def test_one_mismatched_point_in_a_long_sweep_bins_the_overlap_table(nan_after):
    x = np.arange(5000.0)
    cand_x = x.copy()
    after = np.linspace(2.0, 3.0, 5000)
    if nan_after:
        after[3] = math.nan
    else:
        cand_x[-1] = 99999.0
    base = _profile(xr.DataArray(np.linspace(1.0, 2.0, 5000), coords={"s": x}, dims=("s",)))
    cand = _profile(xr.DataArray(after, coords={"s": cand_x}, dims=("s",)))
    plan = plan_chart(base, cand)
    assert isinstance(plan, OverlapTable)
    md = overlap_table("cost", None, plan) + "\n\n" + data_block("cost", plan)
    rows = re.findall(r"^\| ([\d.e+]+) \|", md, re.MULTILINE)
    assert 0 < len(rows) <= 30
    assert f"s is binned to {len(rows)} groups of consecutive values." in md
    assert len(_csv(md, "cost")) == len(rows) + 1
    left = "s=3 (no sample after)" if nan_after else "s=4999 (before only)"
    assert left in md


def test_a_heatmap_over_a_partial_overlap_keeps_the_shared_columns_and_names_the_rest():
    dims = ("c", "b")
    base = _profile(xr.DataArray(np.ones((2, 2)), coords={"c": [1, 2], "b": [10, 20]}, dims=dims))
    cand = _profile(
        xr.DataArray(np.full((2, 2), 2.0), coords={"c": [1, 2], "b": [20, 30]}, dims=dims)
    )
    plan = plan_chart(base, cand)
    assert isinstance(plan, Heatmap)
    assert plan.col_labels == ("20",)
    assert plan.row_labels == ("1", "2")
    assert "Left out: b=10 (before only)." in plan.notes
    assert "Left out: b=30 (after only)." in plan.notes


def _hand_profile(x, mean, std):
    return _Profile(
        swept=("speed",),
        x=tuple(x),
        mean=np.asarray(mean, dtype=float),
        std=np.asarray(std, dtype=float),
        samples=len(x),
        points=tuple(np.array([m]) for m in mean),
    )


def test_a_long_noisy_sweep_is_binned_to_a_band_chart_of_30_points():
    x = [float(i) for i in range(60)]
    base = _hand_profile(x, np.linspace(1.0, 2.0, 60), np.full(60, 0.5))
    cand = _hand_profile(x, np.linspace(1.0, 2.0, 60) + 0.1, np.full(60, 0.5))
    plan = plan_chart(base, cand)
    assert isinstance(plan, BandChart)
    assert len(plan.labels) == len(set(plan.labels)) == 30
    assert plan.labels[0] == "0.5"
    chart = mermaid_chart("m", None, plan, None)
    (axis,) = re.findall(r'x-axis "speed" \[(.*)\]', chart)
    assert axis.count('"') == 60


def test_band_lines_sit_one_std_either_side_of_each_mean():
    x = [1.0, 2.0, 3.0]
    base = _hand_profile(x, [1.0, 2.0, 3.0], [0.5, 0.5, 0.5])
    cand = _hand_profile(x, [1.1, 2.1, 3.1], [0.5, 0.5, 0.5])
    plan = plan_chart(base, cand)
    assert isinstance(plan, BandChart)
    chart = mermaid_chart("m", None, plan, None)
    assert '    line "before -1 std" [0.5, 1.5, 2.5]' in chart
    assert '    line "before +1 std" [1.5, 2.5, 3.5]' in chart
    assert '    line "after -1 std" [0.6, 1.6, 2.6]' in chart
    assert '    line "after +1 std" [1.6, 2.6, 3.6]' in chart
    rows = _csv(data_block("m", plan), "m")
    assert rows[0] == ["speed", "before", "before_std", "after", "after_std"]
    assert rows[1] == ["1", "1", "0.5", "1.1", "0.5"]


def test_diff_bars_with_a_spread_print_the_std_and_a_std_csv():
    x = (1.0, 1.0 + 1e-15)  # labels that collide
    base = _hand_profile(x, [1.0, 2.0], [5.0, 5.0])
    cand = _hand_profile(x, [1.5, 2.5], [5.0, 5.0])
    plan = plan_chart(base, cand)
    assert isinstance(plan, DiffBars)
    assert all(r.before_std == r.after_std == 5.0 for r in plan.rows)
    fence = diff_bars("m", None, plan)
    assert fence.count(" ± 5 ") == 4
    rows = _csv(data_block("m", plan), "m")
    assert rows[0] == ["speed", "before", "before_std", "after", "after_std"]
    assert rows[1][1:] == ["1", "5", "1.5", "5"]


def _bar_lines(plan: DiffBars) -> tuple[str, str]:
    fence = diff_bars("m", None, plan)
    before, after = (line for line in fence.splitlines() if line[:2] in ("- ", "+ "))
    return before, after


def test_positive_text_bars_are_as_long_as_their_value_over_the_axis():
    before, after = _bar_lines(DiffBars(None, (DiffRow("", 1.0, 0.5),)))
    assert before.endswith("  " + "█" * 30)
    assert after.endswith("  " + "█" * 15)
    assert "│" not in before + after


def test_mixed_sign_text_bars_share_the_zero_column():
    before, after = _bar_lines(DiffBars(None, (DiffRow("", -0.2, 0.3),)))
    axis = before.index("│")
    assert after.index("│") == axis
    assert before[axis - 13 : axis] == " " + "█" * 12
    assert after[axis - 1] == " "
    assert after[axis + 1 :] == "█" * 18
    assert before[axis + 1 :] == ""


def test_a_label_with_a_fence_cannot_close_the_diff_or_csv_fence():
    plan = DiffBars("in```put", (DiffRow("a```b", 1.0, 2.0), DiffRow("c", 3.0, 4.0)))
    fence = diff_bars("m", None, plan)
    assert "a'''b" in fence
    body = fence[fence.index("```diff") :]
    assert body.count("```") == 2  # the opening and closing fence only
    block = data_block("m", plan)
    assert "a'''b" in block
    assert "in'''put" in block
    assert block.count("```") == 2


# --- every form ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("base_kw", "cand_kw"),
    [
        ({}, {}),  # two lines
        ({"inputs": ()}, {"inputs": ()}),  # bars
        ({"inputs": ("mode",)}, {"inputs": ("mode",)}),  # category table
    ],
)
def test_every_metric_has_a_data_block(base_kw, cand_kw):
    md = bn.evidence_markdown(_rig(0.3, **base_kw), _rig(0.2, **cand_kw))
    assert len(_csv(md, "cost")) >= 2


def test_markdown_never_writes_or_links_a_png(tmp_path):
    files = bn.write_evidence(
        _rig(0.3, ("speed", "load")),
        _rig(0.2, ("speed", "load")),
        markdown_path=tmp_path / "e.md",
    )
    _no_image((tmp_path / "e.md").read_text(encoding="utf-8"))
    assert files.pngs == {}
    assert list(tmp_path.rglob("*.png")) == []


def test_png_url_base_is_deprecated_and_adds_no_link(tmp_path):
    with pytest.warns(DeprecationWarning, match="text only"):
        md = bn.evidence_markdown(
            _rig(0.3, ("speed", "load")),
            _rig(0.2, ("speed", "load")),
            png_url_base="https://raw.example/x",
        )
    _no_image(md)


def test_compare_png_url_base_warns_on_stderr_and_still_succeeds(tmp_path, capsys):
    a = save_result(_rig(0.3, ("speed", "load")), tmp_path / "a.pkl")
    b = save_result(_rig(0.2, ("speed", "load")), tmp_path / "b.pkl")
    md = tmp_path / "e.md"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        args = ["compare", str(a), str(b), "--markdown", str(md), "--png-url-base", "https://x"]
        assert main(args) == 0
    assert "text only" in capsys.readouterr().err
    _no_image(md.read_text(encoding="utf-8"))
    assert list(tmp_path.rglob("*.png")) == []


def test_compare_png_dir_is_an_alias_of_png(tmp_path):
    a = save_result(_rig(0.3), tmp_path / "a.pkl")
    b = save_result(_rig(0.2), tmp_path / "b.pkl")
    assert main(["compare", str(a), str(b), "--png-dir", str(tmp_path / "png")]) == 0
    assert (tmp_path / "png" / "cost.png").exists()


def test_image_only_still_imports_and_warns_when_built():
    from bencher.evidence import ImageOnly

    with pytest.warns(DeprecationWarning, match="ImageOnly"):
        plan = ImageOnly("two swept inputs")
    assert plan.reason == "two swept inputs"
    with pytest.warns(DeprecationWarning, match="ImageOnly"):
        assert ImageOnly(reason="x").reason == "x"
