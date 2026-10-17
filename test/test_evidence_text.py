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
    DiffBars,
    OverlapTable,
    _Profile,
    _profile,
    diff_bars,
    heatmap_table,
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


def test_the_heatmap_data_block_has_one_row_per_cell():
    md = bn.evidence_markdown(_rig(0.3, ("speed", "load")), _rig(0.2, ("speed", "load")))
    rows = _csv(md, "cost")
    assert rows[0] == ["speed", "load", "before", "after", "change_percent"]
    assert len(rows) == 1 + 3 * 2
    assert float(rows[1][4]) == pytest.approx(-100 / 3)


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
