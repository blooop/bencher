"""The change estimate behind an A/B verdict, and how the evidence block shows it.

Each compared metric gets a ``change`` record in ``comparison.json``: the mean
difference (candidate - baseline), a bootstrap 95% CI and a ``stat_verdict``. The
evidence Markdown draws a numeric sweep as two lines, a categorical sweep as a table,
and three or more metrics on one radar chart.
"""

from __future__ import annotations

import itertools
import math
import re

import numpy as np
import pytest
import xarray as xr

import bencher as bn
from bencher.change_stats import (
    EQUIVALENT,
    NO_SIGNIFICANT_CHANGE,
    NOT_COMPARABLE,
    TOO_FEW_SAMPLES,
    change_between,
    paired_change,
    unpaired_change,
)
from bencher.evidence import (
    BeforeAfterBars,
    CategoryRow,
    CategoryTable,
    _Profile,
    category_table,
    change_line,
    mermaid_chart,
    radar_chart,
)

# --- the statistics on known data ------------------------------------------------


def test_a_constant_shift_gives_a_tight_ci_around_the_shift():
    before = np.array([0.10, 0.22, 0.36, 0.54, 0.76])
    change = paired_change(before, before - 0.09, direction="minimize", margin_percent=10.0)
    assert change["method"] == "paired_bootstrap"
    assert change["n"] == 5
    assert change["ci_level"] == 0.95
    assert change["mean_diff"] == pytest.approx(-0.09)
    assert change["ci_low"] == pytest.approx(-0.09)
    assert change["ci_high"] == pytest.approx(-0.09)
    assert change["stat_verdict"] == "improved"


def test_a_noisy_shift_has_a_ci_that_holds_the_true_shift():
    rng = np.random.default_rng(1)
    before = rng.uniform(1.0, 2.0, size=40)
    after = before + 0.3 + rng.normal(0.0, 0.05, size=40)
    change = paired_change(before, after, direction="minimize", margin_percent=10.0)
    assert change["ci_low"] < 0.3 < change["ci_high"]
    assert change["ci_high"] - change["ci_low"] < 0.1
    assert change["stat_verdict"] == "regressed"


def test_a_maximized_metric_that_rises_is_improved():
    before = np.array([1.0, 2.0, 3.0])
    change = paired_change(before, before + 1.0, direction="maximize", margin_percent=10.0)
    assert change["stat_verdict"] == "improved"


def test_a_metric_with_no_direction_says_which_way_it_moved():
    before = np.array([1.0, 2.0, 3.0])
    change = paired_change(before, before + 1.0, direction="none", margin_percent=10.0)
    assert change["stat_verdict"] == "increased"


def test_a_ci_that_holds_zero_is_no_significant_change():
    before = np.array([1.0, 1.0, 1.0, 1.0])
    after = np.array([1.3, 0.7, 1.4, 0.6])
    change = paired_change(before, after, direction="minimize", margin_percent=10.0)
    assert change["ci_low"] < 0 < change["ci_high"]
    assert change["stat_verdict"] == NO_SIGNIFICANT_CHANGE


def test_a_ci_inside_the_margin_is_equivalent():
    before = np.array([1.0, 2.0, 3.0, 4.0])
    after = before + np.array([0.01, -0.01, 0.02, -0.02])
    change = paired_change(before, after, direction="minimize", margin_percent=10.0)
    assert change["stat_verdict"] == f"{EQUIVALENT} ±10%"
    assert change["equivalence_percent"] == 10.0


def test_one_point_is_too_few_samples_and_has_no_ci():
    change = paired_change(np.array([1.0]), np.array([0.5]), "minimize", 10.0)
    assert change["stat_verdict"] == TOO_FEW_SAMPLES
    assert change["ci_low"] is None
    assert change["ci_high"] is None
    assert change["n"] == 1


def test_non_finite_points_are_dropped_before_the_count():
    before = np.array([1.0, math.nan, 3.0])
    after = np.array([0.5, 1.0, math.inf])
    change = paired_change(before, after, "minimize", 10.0)
    assert change["n"] == 1
    assert change["stat_verdict"] == TOO_FEW_SAMPLES


def test_repeats_without_a_sweep_bootstrap_the_difference_of_means():
    change = unpaired_change(
        np.array([1.0, 1.1, 0.9, 1.0]), np.array([0.5, 0.6, 0.4, 0.5]), "minimize", 10.0
    )
    assert change["method"] == "bootstrap"
    assert change["n_baseline"] == 4
    assert change["n_candidate"] == 4
    assert change["mean_diff"] == pytest.approx(-0.5)
    assert change["ci_low"] <= -0.5 <= change["ci_high"]
    assert change["stat_verdict"] == "improved"


def test_the_bootstrap_is_deterministic():
    rng = np.random.default_rng(7)
    before, after = rng.normal(1, 0.2, 30), rng.normal(1.1, 0.2, 30)
    assert unpaired_change(before, after, "minimize", 10.0) == unpaired_change(
        before, after, "minimize", 10.0
    )
    assert paired_change(before, after, "minimize", 10.0) == paired_change(
        before, after, "minimize", 10.0
    )


# --- through compare_results -----------------------------------------------------

_NOISE = itertools.cycle([0.02, -0.02, 0.01, -0.01])


class Shift(bn.ParametrizedSweep):
    speed = bn.FloatSweep(default=1.0, bounds=(0.5, 2.5), samples=5)
    mode = bn.StringSweep(["eco", "normal", "sport"])
    offset = bn.FloatSweep(default=0.0)
    noisy = bn.BoolSweep(default=False)

    stop_distance = bn.ResultFloat(units="m")
    peak_decel = bn.ResultFloat(units="m/s^2", direction=bn.OptDir.minimize)
    cpu_time = bn.ResultFloat(units="ms", direction=bn.OptDir.minimize)
    zero = bn.ResultFloat(units="count")

    def benchmark(self):
        noise = next(_NOISE) if self.noisy else 0.0
        scale = {"eco": 1.0, "normal": 1.5, "sport": 2.0}[self.mode]
        self.stop_distance = 0.3 * self.speed * scale + self.offset + noise
        self.peak_decel = 2.0 * self.speed + self.offset
        self.cpu_time = 5.0 + self.speed
        self.zero = 0.0


def _shift(offset, input_vars=("speed",), result_vars=("stop_distance",), repeats=1, noisy=False):
    bench = bn.Bench(f"shift_{offset}_{len(input_vars)}_{len(result_vars)}", Shift())
    res = bench.collect(
        input_vars=list(input_vars),
        result_vars=list(result_vars),
        const_vars=[("offset", offset), ("noisy", noisy)],
        run_cfg=bn.BenchRunCfg(repeats=repeats),
    )
    bench.close()
    return res


EXISTING_METRIC_KEYS = {
    "variable",
    "baseline_value",
    "current_value",
    "change_percent",
    "direction",
    "method",
    "regressed",
    "verdict",
}


def test_compare_adds_a_change_record_and_keeps_every_existing_key():
    cmp = bn.compare_results(_shift(0.0), _shift(-0.09))
    assert cmp["schema_version"] == 1
    (metric,) = cmp["metrics"]
    assert set(metric) == EXISTING_METRIC_KEYS | {"change"}
    assert metric["verdict"] == "improved"
    assert metric["regressed"] is False
    assert metric["method"] == "percentage"
    assert metric["baseline_value"] == pytest.approx(0.45)
    assert metric["current_value"] == pytest.approx(0.36)
    change = metric["change"]
    assert change["method"] == "paired_bootstrap"
    assert change["n"] == 5
    assert change["mean_diff"] == pytest.approx(-0.09)
    assert change["ci_low"] == pytest.approx(-0.09)
    assert change["ci_high"] == pytest.approx(-0.09)
    assert change["stat_verdict"] == "improved"
    assert set(cmp["summary"]) == {"improved", "regressed", "unchanged"}


def test_the_margin_is_the_regression_percentage():
    cmp = bn.compare_results(
        _shift(0.0), _shift(0.0), run_cfg=bn.BenchRunCfg(regression_percentage=5.0)
    )
    change = cmp["metrics"][0]["change"]
    assert change["equivalence_percent"] == 5.0
    assert change["stat_verdict"] == f"{EQUIVALENT} ±5%"


def test_repeats_are_averaged_per_point_before_pairing():
    cmp = bn.compare_results(_shift(0.0, repeats=4, noisy=True), _shift(0.2, repeats=4, noisy=True))
    change = cmp["metrics"][0]["change"]
    assert change["method"] == "paired_bootstrap"
    assert change["n"] == 5
    assert change["mean_diff"] == pytest.approx(0.2, abs=0.02)


def test_no_sweep_with_one_repeat_is_too_few_samples():
    cmp = bn.compare_results(_shift(0.0, input_vars=()), _shift(-0.09, input_vars=()))
    change = cmp["metrics"][0]["change"]
    assert change["method"] == "bootstrap"
    assert change["stat_verdict"] == TOO_FEW_SAMPLES
    assert change["ci_low"] is None


def test_sides_that_swept_different_inputs_are_not_comparable():
    cmp = bn.compare_results(_shift(0.0, input_vars=("speed",)), _shift(0.0, input_vars=("mode",)))
    change = cmp["metrics"][0]["change"]
    assert change["stat_verdict"] == NOT_COMPARABLE
    assert change["ci_low"] is None
    assert change["reason"] == "the sides swept different inputs"


# --- the evidence Markdown -------------------------------------------------------


def _charts(markdown: str) -> list[str]:
    return re.findall(r"```mermaid\n(.*?)```", markdown, re.DOTALL)


def test_a_numeric_sweep_draws_two_named_lines_with_a_fixed_palette():
    (chart,) = _charts(bn.evidence_markdown(_shift(0.0), _shift(-0.09)))
    assert chart.startswith("---\nconfig:\n")
    assert 'plotColorPalette: "#8c8c8c, #2f81f7"' in chart
    # Named series make GitHub draw a legend, so the title does not name the colors.
    assert 'title "stop_distance (m): before vs after"' in chart
    assert "grey" not in chart and "blue" not in chart
    assert len(re.findall(r'^    line "before" \[', chart, re.MULTILINE)) == 1
    assert len(re.findall(r'^    line "after" \[', chart, re.MULTILINE)) == 1
    assert "bar [" not in chart


def test_the_caption_gives_the_change_and_its_ci():
    md = bn.evidence_markdown(_shift(0.0), _shift(-0.09))
    assert "**stop_distance** improved: mean 0.45 → 0.36 m (-20.0%)" in md
    assert "change -0.09 m, 95% CI [-0.09, -0.09] (paired bootstrap, n=5) → improved" in md


def test_a_categorical_sweep_is_a_table_not_a_chart():
    md = bn.evidence_markdown(
        _shift(0.0, input_vars=("mode",), repeats=3, noisy=True),
        _shift(-0.3, input_vars=("mode",), repeats=3, noisy=True),
    )
    assert "```mermaid" not in md
    assert "| mode | before | after | change | 95% CI |" in md
    rows = re.findall(r"^\| (eco|normal|sport) \|.*\|$", md, re.MULTILINE)
    assert rows == ["eco", "normal", "sport"]
    eco = re.search(r"^\| eco \|.*$", md, re.MULTILINE)[0]
    assert re.search(r"\| -0\.\d+ \| \[-0\.\d+, -0\.\d+\] → improved \|$", eco)


def test_a_categorical_point_with_one_sample_has_no_ci_in_the_table():
    md = bn.evidence_markdown(_shift(0.0, input_vars=("mode",)), _shift(-0.3, input_vars=("mode",)))
    eco = re.search(r"^\| eco \|.*$", md, re.MULTILINE)[0]
    assert "too few samples" in eco


def test_negative_values_are_never_drawn_as_bars():
    md = bn.evidence_markdown(_shift(-2.0, input_vars=()), _shift(-2.5, input_vars=()))
    assert "![stop_distance: before vs after]" in md
    for chart in _charts(md):
        for series in re.findall(r"bar \[(.*)\]", chart):
            assert all(float(v) >= 0 for v in series.split(", "))


def test_a_bar_chart_is_unchanged_for_positive_values():
    chart = mermaid_chart("m", None, BeforeAfterBars(0.3, 0.2), None)
    assert "bar [0.3, 0.2]" in chart


def test_the_evidence_is_byte_identical_across_runs():
    base, cand = _shift(0.0, repeats=3, noisy=True), _shift(0.1, repeats=3, noisy=True)
    first = bn.evidence_markdown(base, cand)
    assert "95% CI" in first
    assert first == bn.evidence_markdown(base, cand)


_THREE = ("stop_distance", "peak_decel", "cpu_time")


def test_three_metrics_get_a_radar_above_the_charts():
    md = bn.evidence_markdown(_shift(0.0, result_vars=_THREE), _shift(-0.2, result_vars=_THREE))
    charts = _charts(md)
    assert "radar-beta" in charts[0]
    assert md.index("radar-beta") < md.index("xychart-beta")
    radar = charts[0]
    assert 'axis m0["stop_distance"], m1["peak_decel"], m2["cpu_time"]' in radar
    assert 'curve before["before"]{1, 1, 1}' in radar
    assert re.search(r"^  min 0$", radar, re.MULTILINE)
    maximum = float(re.search(r"^  max (\S+)$", radar, re.MULTILINE)[1])
    assert maximum >= 1.0


def test_two_metrics_get_no_radar():
    two = _THREE[:2]
    md = bn.evidence_markdown(_shift(0.0, result_vars=two), _shift(-0.2, result_vars=two))
    assert "radar-beta" not in md


def test_a_metric_with_a_zero_baseline_is_left_off_the_radar_and_named():
    four = (*_THREE, "zero")
    md = bn.evidence_markdown(_shift(0.0, result_vars=four), _shift(-0.2, result_vars=four))
    radar = _charts(md)[0]
    assert "radar-beta" in radar
    assert '"zero"' not in radar
    assert "Not on the radar: `zero` (baseline mean is 0)" in md


def _radar_entry(variable, base, cand, direction="maximize"):
    return {
        "variable": variable,
        "baseline_value": base,
        "current_value": cand,
        "direction": direction,
    }


_POSITIVE = [_radar_entry(name, 1.0, 1.2) for name in ("a", "b", "c")]


@pytest.mark.parametrize(("base", "cand"), [(-10.0, -20.0), (-5.0, 0.0)])
def test_a_metric_with_a_negative_baseline_is_left_off_the_radar(base, cand):
    md = radar_chart([*_POSITIVE, _radar_entry("score", base, cand)])
    assert md is not None
    assert '"score"' not in md
    assert "-0" not in md
    assert "Not on the radar: `score` (baseline mean is negative)." in md


def _swept(name, values, offset=0.0, repeats=3):
    data = np.array([[v + offset + 0.01 * r for r in range(repeats)] for v in values])
    return xr.DataArray(
        data, dims=(name, "repeat"), coords={name: list(values), "repeat": range(repeats)}
    )


def test_one_point_at_different_values_is_not_comparable():
    change = change_between(_swept("x", [1.0]), _swept("x", [2.0]), "minimize", 10.0)
    assert change["stat_verdict"] == NOT_COMPARABLE
    assert change["reason"] == "the sides share no swept input point"


def test_one_shared_point_compares_the_repeats_at_that_point():
    change = change_between(_swept("x", [1]), _swept("x", [1, 2], offset=-0.5), "minimize", 10.0)
    assert change["method"] == "bootstrap"
    assert change["n_baseline"] == 3
    assert change["n_candidate"] == 3
    assert change["mean_diff"] == pytest.approx(-0.5)
    assert change["stat_verdict"] == "improved"


def test_a_partial_overlap_pairs_the_shared_points():
    change = change_between(
        _swept("speed", [1, 2, 3]), _swept("speed", [2, 3, 4], offset=0.5), "minimize", 10.0
    )
    assert change["method"] == "paired_bootstrap"
    assert change["n"] == 2
    assert change["mean_diff"] == pytest.approx(0.5)


def test_a_zero_percentage_override_is_a_zero_margin():
    cfg = bn.BenchRunCfg(regression_overrides={"stop_distance": {"percentage": 0.0}})
    cmp = bn.compare_results(_shift(0.0), _shift(0.0), run_cfg=cfg)
    assert cmp["metrics"][0]["change"]["equivalence_percent"] == 0.0


def test_a_zero_regression_percentage_is_a_zero_margin():
    cmp = bn.compare_results(
        _shift(0.0), _shift(0.0), run_cfg=bn.BenchRunCfg(regression_percentage=0.0)
    )
    assert cmp["metrics"][0]["change"]["equivalence_percent"] == 0.0


def test_a_percentage_override_sets_the_margin():
    cfg = bn.BenchRunCfg(regression_overrides={"stop_distance": {"percentage": 15.0}})
    cmp = bn.compare_results(_shift(0.0), _shift(0.0), run_cfg=cfg)
    change = cmp["metrics"][0]["change"]
    assert change["equivalence_percent"] == 15.0
    assert change["stat_verdict"] == f"{EQUIVALENT} ±15%"


def _with_change(threshold_verdict, change):
    return {"variable": "m", "verdict": threshold_verdict, "change": change}


def test_the_caption_notes_a_threshold_verdict_the_ci_does_not_support():
    change = paired_change(
        np.array([1.0, 1.0, 1.0, 1.0]), np.array([1.3, 0.7, 1.4, 0.6]), "minimize", 10.0
    )
    assert change["stat_verdict"] == NO_SIGNIFICANT_CHANGE
    line = change_line(_with_change("improved", change), None)
    assert line is not None
    assert line.endswith("→ no significant change; the threshold verdict says improved")


def test_the_caption_has_no_note_when_the_verdicts_agree():
    before = np.array([1.0, 2.0, 3.0])
    change = paired_change(before, before - 0.5, "minimize", 10.0)
    line = change_line(_with_change("improved", change), None)
    assert line is not None
    assert line.endswith("→ improved")
    assert "threshold verdict" not in line


def test_two_scalable_metrics_of_four_get_no_radar():
    entries = [*_POSITIVE[:2], _radar_entry("z1", 0.0, 1.0), _radar_entry("z2", 0.0, 1.0)]
    md = radar_chart(entries)
    assert md is not None
    assert "radar-beta" not in md
    assert md.startswith("No radar: only 2 metrics can be scaled to their baseline.")


def test_one_scalable_metric_is_named_in_the_singular():
    zeros = [_radar_entry(f"z{i}", 0.0, 1.0) for i in range(3)]
    md = radar_chart([_POSITIVE[0], *zeros])
    assert md is not None
    assert md.startswith("No radar: only 1 metric can be scaled to its baseline.")


def test_a_profile_must_carry_its_points():
    fields = {"swept": ("x",), "x": (1, 2), "mean": np.zeros(2), "std": np.zeros(2), "samples": 2}
    with pytest.raises(TypeError):
        _Profile(**fields)


def test_a_category_table_renders_one_line_per_row():
    change = unpaired_change(np.array([1.0, 1.1]), np.array([0.5, 0.6]), "minimize", 10.0)
    plan = CategoryTable("mode", (CategoryRow("eco", 1.05, 0.55, change),))
    table = category_table("m", None, plan)
    assert table.splitlines()[-1].startswith("| eco | 1.05 | 0.55 | -0.5 | [")


def test_a_metric_with_no_direction_that_falls_decreased():
    before = np.array([1.0, 2.0, 3.0])
    change = paired_change(before, before - 1.0, direction="none", margin_percent=10.0)
    assert change["stat_verdict"] == "decreased"


def test_a_maximized_metric_that_falls_is_regressed():
    before = np.array([1.0, 2.0, 3.0])
    change = paired_change(before, before - 1.0, direction="maximize", margin_percent=10.0)
    assert change["stat_verdict"] == "regressed"


def test_the_caption_says_too_few_samples_for_one_repeat_without_a_sweep():
    md = bn.evidence_markdown(_shift(0.0, input_vars=()), _shift(-0.09, input_vars=()))
    assert "change: too few samples for a CI (n=1 vs 1)" in md


def test_the_caption_says_why_the_sides_are_not_comparable():
    md = bn.evidence_markdown(_shift(0.0, input_vars=("speed",)), _shift(0.0, input_vars=("mode",)))
    assert "change: not comparable (the sides swept different inputs)" in md


class Piped(bn.ParametrizedSweep):
    label = bn.StringSweep(["a|b", "c"])
    offset = bn.FloatSweep(default=0.0)

    value = bn.ResultFloat(units="m")

    def benchmark(self):
        self.value = 1.0 + self.offset


def _piped(offset):
    bench = bn.Bench(f"piped_{offset}", Piped())
    res = bench.collect(
        input_vars=["label"], result_vars=["value"], const_vars=[("offset", offset)]
    )
    bench.close()
    return res


def test_a_category_with_a_pipe_stays_in_one_table_cell():
    md = bn.evidence_markdown(_piped(0.0), _piped(-0.1))
    rows = re.findall(r"^\| (\S+) \| 1 \| 0\.9 \|", md, re.MULTILINE)
    assert rows == ["a\\|b", "c"]


def test_a_bool_sweep_is_a_table_not_a_chart():
    md = bn.evidence_markdown(
        _shift(0.0, input_vars=("noisy",)), _shift(-0.1, input_vars=("noisy",))
    )
    assert "xychart-beta" not in md
    rows = re.findall(r"^\| (False|True) \|", md, re.MULTILINE)
    assert rows == ["False", "True"]


@pytest.mark.parametrize(
    ("base", "cand", "reason"),
    [
        (math.nan, 1.0, "baseline mean is not finite"),
        (1.0, -1.0, "the mean changed sign"),
        (-1.0, 0.0, "baseline mean is negative"),
    ],
)
def test_a_metric_that_cannot_be_scaled_is_left_off_the_radar(base, cand, reason):
    md = radar_chart([*_POSITIVE, _radar_entry("score", base, cand)])
    assert md is not None
    assert '"score"' not in md
    assert f"Not on the radar: `score` ({reason})." in md


def test_the_radar_max_leaves_room_above_the_largest_ratio():
    entries = [_radar_entry("a", 1.0, 1.5), *_POSITIVE[1:], _radar_entry("d", 2.0, 2.0)]
    md = radar_chart(entries)
    assert md is not None
    assert re.search(r"^  max 1\.7$", md, re.MULTILINE)


def test_the_radar_says_which_way_is_better():
    entries = [*_POSITIVE[:2], _radar_entry("cost", 2.0, 1.0, direction="minimize")]
    md = radar_chart(entries)
    assert md is not None
    assert "Lower is better for `cost`." in md
    assert "Higher is better for `a`, `b`." in md
