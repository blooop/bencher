"""PR-ready evidence from two results: the Markdown block and the PNG charts."""

from __future__ import annotations

import itertools
import json
import math
import re

import numpy as np
import pytest
from matplotlib.figure import Figure
from matplotlib.image import imread

import bencher as bn
from bencher.evidence import BeforeAfterBars, mermaid_chart
from bencher.render import main, save_result

_NOISE = itertools.cycle([0.5, -0.5])


class Braking(bn.ParametrizedSweep):
    speed = bn.FloatSweep(default=1.0, bounds=(1.0, 3.0), samples=3)
    load = bn.FloatSweep(default=1.0, bounds=(1.0, 2.0), samples=2)
    gain = bn.FloatSweep(default=0.2)
    noisy = bn.BoolSweep(default=False)

    stop_distance = bn.ResultFloat(units="m", claim="< 0.7")

    def benchmark(self):
        noise = next(_NOISE) if self.noisy else 0.0
        self.stop_distance = self.gain * self.speed * self.load + noise


def _collect(gain, input_vars=("speed",), repeats=1, noisy=False, samples=3):
    bench = bn.Bench(f"braking_{gain}", Braking())
    res = bench.collect(
        input_vars=[
            Braking.param.speed.with_samples(samples) if v == "speed" else v for v in input_vars
        ],
        result_vars=["stop_distance"],
        const_vars=[("gain", gain), ("noisy", noisy)],
        run_cfg=bn.BenchRunCfg(repeats=repeats),
    )
    bench.close()
    return res


def _chart(markdown: str) -> str:
    return re.search(r"```mermaid\n(.*?)```", markdown, re.DOTALL)[1]


def test_one_swept_input_draws_before_as_bars_and_after_as_a_line():
    md = bn.evidence_markdown(_collect(0.3), _collect(0.2))
    chart = _chart(md)
    assert chart.startswith("xychart-beta\n")
    assert 'title "stop_distance (m): bars = before, line = after"' in chart
    assert 'x-axis "speed" ["1", "2", "3"]' in chart
    assert "bar [0.3, 0.6, 0.9]" in chart
    assert "line [0.2, 0.4, 0.6]" in chart
    lo, hi = map(float, re.search(r"y-axis \"[^\"]*\" (\S+) --> (\S+)", chart).groups())
    assert lo == 0
    assert hi >= 0.9


def test_the_caption_gives_verdict_values_claim_and_provenance():
    md = bn.evidence_markdown(_collect(0.3), _collect(0.2))
    assert "**stop_distance** improved: mean 0.6 → 0.4 m (-33.3%)" in md
    assert (
        "claim `< 0.7`: baseline fails (worst 0.9 at speed=3, repeat=1)"
        " → candidate holds (worst 0.6 at speed=3, repeat=1)" in md
    )
    assert "3 samples" in md


def test_no_swept_input_compares_one_bar_per_side():
    chart = _chart(bn.evidence_markdown(_collect(0.3, input_vars=()), _collect(0.2, input_vars=())))
    assert 'x-axis ["before", "after"]' in chart
    assert "bar [0.3, 0.2]" in chart
    assert "line" not in chart


def test_the_y_range_holds_the_claim_threshold():
    # Values near 0.2 with a claim at 0.7: the range must reach the threshold.
    chart = _chart(
        bn.evidence_markdown(_collect(0.1, input_vars=()), _collect(0.09, input_vars=()))
    )
    lo, hi = map(float, re.search(r"y-axis \"[^\"]*\" (\S+) --> (\S+)", chart).groups())
    assert hi >= 0.7
    # A change of 0.01 on an axis from 0 would be under 5% of it: the axis starts above 0.
    assert 0 < lo <= 0.09


def test_two_swept_inputs_link_an_image_instead():
    md = bn.evidence_markdown(
        _collect(0.3, input_vars=("speed", "load")),
        _collect(0.2, input_vars=("speed", "load")),
        png_url_base="https://raw.example/pr/abc/",
    )
    assert "```mermaid" not in md
    assert "![stop_distance: before vs after](https://raw.example/pr/abc/stop_distance.png)" in md


def test_a_spread_as_large_as_the_change_links_an_image():
    md = bn.evidence_markdown(
        _collect(0.3, repeats=2, noisy=True), _collect(0.29, repeats=2, noisy=True)
    )
    assert "```mermaid" not in md
    assert "](stop_distance.png)" in md


def test_a_long_sweep_is_binned_to_at_most_thirty_points():
    chart = _chart(bn.evidence_markdown(_collect(0.3, samples=70), _collect(0.2, samples=70)))
    labels = re.search(r"x-axis \"speed\" \[(.*)\]", chart)[1].split(", ")
    # 70 points in bins of ceil(70 / 30) = 3 make 24 bars.
    assert len(labels) == 24
    assert len(re.search(r"line \[(.*)\]", chart)[1].split(", ")) == len(labels)
    first_bar = float(re.search(r"bar \[(.*?),", chart)[1])
    speeds = np.linspace(1.0, 3.0, 70)
    assert first_bar == pytest.approx(0.3 * speeds[:3].mean(), rel=1e-3)


def test_quotes_in_units_do_not_break_the_title():
    base, cand = _collect(0.3), _collect(0.2)
    for res in (base, cand):
        res.bench_cfg.result_vars[0].units = 'm "wet"'
    title = re.search(r"title (.*)", _chart(bn.evidence_markdown(base, cand)))[1]
    assert title.count('"') == 2


def test_a_metric_that_reads_zero_on_both_sides_still_charts(monkeypatch):
    base, cand = _collect(0.0, input_vars=()), _collect(0.0, input_vars=())
    for res in (base, cand):
        monkeypatch.setattr(res.bench_cfg.result_vars[0], "claim", None)
    assert "bar [0, 0]" in _chart(bn.evidence_markdown(base, cand))


_NUMBER = r"-?\d+(\.\d+)?"


@pytest.mark.parametrize(
    ("before", "after", "bars"),
    [
        (1e5, 2e5, "bar [100000, 200000, 300000]"),
        (2e-6, 1e-6, "bar [0.000002, 0.000004, 0.000006]"),
    ],
)
def test_large_and_small_values_are_written_without_an_exponent(before, after, bars):
    # Mermaid's xychart grammar has no exponent: "1e+05" is a parse error on GitHub.
    chart = _chart(bn.evidence_markdown(_collect(before), _collect(after)))
    assert bars in chart
    axis = re.search(r"y-axis \"[^\"]*\" (\S+) --> (\S+)", chart)
    assert all(re.fullmatch(_NUMBER, bound) for bound in axis.groups())
    for series in re.findall(r"(?:bar|line) \[(.*)\]", chart):
        assert all(re.fullmatch(_NUMBER, v) for v in series.split(", "))


def test_a_png_draws_a_side_that_swept_nothing_beside_one_that_swept(tmp_path):
    # The change added a swept input: the baseline is one value, the candidate a curve.
    pngs = bn.write_evidence_pngs(_collect(0.3, input_vars=()), _collect(0.2), tmp_path)
    assert imread(pngs["stop_distance"]).shape[0] > 0


@pytest.fixture(name="saved")
def saved_pair(tmp_path):
    a = save_result(_collect(0.3, input_vars=("speed", "load")), tmp_path / "a.pkl")
    b = save_result(_collect(0.2, input_vars=("speed", "load")), tmp_path / "b.pkl")
    return a, b


def test_compare_writes_markdown_and_one_png_per_metric(saved, tmp_path):
    a, b = saved
    md, png_dir = tmp_path / "out" / "evidence.md", tmp_path / "out" / "png"
    assert main(["compare", str(a), str(b), "--markdown", str(md), "--png", str(png_dir)]) == 0
    assert "](png/stop_distance.png)" in md.read_text(encoding="utf-8")
    image = imread(png_dir / "stop_distance.png")
    assert image.shape[:2] == (440, 880)


def test_compare_markdown_alone_writes_the_pngs_it_links_beside_it(saved, tmp_path):
    a, b = saved
    md = tmp_path / "evidence.md"
    assert main(["compare", str(a), str(b), "--markdown", str(md)]) == 0
    assert "](stop_distance.png)" in md.read_text(encoding="utf-8")
    assert (tmp_path / "stop_distance.png").exists()


def test_compare_png_url_base_pins_the_image_links(saved, tmp_path):
    a, b = saved
    md = tmp_path / "evidence.md"
    base = "https://raw.githubusercontent.com/o/r/sha/evidence"
    args = ["compare", str(a), str(b), "--markdown", str(md), "--png-url-base", base]
    assert main(args) == 0
    assert f"]({base}/stop_distance.png)" in md.read_text(encoding="utf-8")


def test_compare_json_still_works_and_carries_the_claim(saved, tmp_path):
    a, b = saved
    out = tmp_path / "cmp.json"
    assert main(["compare", str(a), str(b), "--json", str(out)]) == 0
    metric = json.loads(out.read_text(encoding="utf-8"))["metrics"][0]
    assert metric["claim"]["candidate"]["holds"] is False  # 0.2 * 3 * 2 = 1.2


def test_compare_needs_at_least_one_output(saved):
    a, b = saved
    with pytest.raises(SystemExit) as exc:
        main(["compare", str(a), str(b)])
    assert exc.value.code == 2


@pytest.mark.parametrize(("before", "after"), [(123456.7, 123500.0), (12345678.0, 12345679.0)])
def test_a_small_change_on_a_large_value_stays_visible_in_the_chart_text(before, after):
    chart = mermaid_chart("m", None, BeforeAfterBars(before, after), None)
    bars = re.search(r"bar \[(.*)\]", chart)[1].split(", ")
    lo, hi = re.search(r"y-axis \"[^\"]*\" (\S+) --> (\S+)", chart).groups()
    assert all(re.fullmatch(_NUMBER, v) for v in [*bars, lo, hi])
    assert bars[0] != bars[1]
    assert float(lo) < float(hi)
    assert float(lo) <= min(before, after)
    assert float(hi) >= max(before, after)


class Tuning(bn.ParametrizedSweep):
    fine = bn.FloatSweep(default=1000.0, bounds=(1000.0, 1001.0), samples=10)
    count = bn.IntSweep(default=10000, bounds=(10000, 10039))
    gain = bn.FloatSweep(default=0.2)

    cost = bn.ResultFloat(units="s")

    def benchmark(self):
        self.cost = self.gain * (1.0 + self.fine + self.count)


def _collect_tuning(gain, input_var):
    bench = bn.Bench(f"tuning_{gain}_{input_var}", Tuning())
    res = bench.collect(input_vars=[input_var], result_vars=["cost"], const_vars=[("gain", gain)])
    bench.close()
    return res


@pytest.mark.parametrize("input_var", ["fine", "count"])
def test_sweep_labels_are_unique_and_written_without_an_exponent(input_var):
    md = bn.evidence_markdown(_collect_tuning(0.3, input_var), _collect_tuning(0.2, input_var))
    labels = re.search(rf"x-axis \"{input_var}\" \[(.*)\]", _chart(md))[1].split(", ")
    assert len(set(labels)) == len(labels)
    assert all(re.fullmatch(rf'"{_NUMBER}"', label) for label in labels)


def test_a_png_draws_sides_that_swept_different_inputs_each_against_its_own(tmp_path, monkeypatch):
    figures = []
    save = Figure.savefig

    def record(fig, *args, **kwargs):
        figures.append(fig)
        return save(fig, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", record)
    bn.write_evidence_pngs(
        _collect(0.3, input_vars=("speed",)), _collect(0.2, input_vars=("load",)), tmp_path
    )
    (fig,) = figures
    assert {ax.get_xlabel() for ax in fig.axes} == {"speed", "load"}


class Margin(bn.ParametrizedSweep):
    speed = bn.FloatSweep(default=1.0, bounds=(1.0, 3.0), samples=3)
    floor = bn.FloatSweep(default=0.0)

    margin = bn.ResultFloat(units="m", claim="> 0")

    def benchmark(self):
        self.margin = self.floor if self.speed == 3.0 else self.speed


def _collect_margin(floor):
    bench = bn.Bench(f"margin_{floor}", Margin())
    res = bench.collect(input_vars=["speed"], result_vars=["margin"], const_vars=[("floor", floor)])
    bench.close()
    return res


def test_a_minus_inf_worst_sample_is_not_captioned_as_inf():
    md = bn.evidence_markdown(_collect_margin(1.0), _collect_margin(-math.inf))
    claim = re.search(r"claim `> 0`: .*", md)[0]
    assert "candidate fails" in claim
    assert "worst inf" not in claim


def test_an_empty_png_url_base_links_relative_to_the_markdown(tmp_path):
    md, png_dir = tmp_path / "out" / "e.md", tmp_path / "out" / "png"
    bn.write_evidence(
        _collect(0.3, input_vars=("speed", "load")),
        _collect(0.2, input_vars=("speed", "load")),
        markdown_path=md,
        png_dir=png_dir,
        png_url_base="",
    )
    assert "](png/stop_distance.png)" in md.read_text(encoding="utf-8")
    assert (png_dir / "stop_distance.png").exists()


def test_an_image_link_through_a_path_with_spaces_stays_a_link(tmp_path):
    md = tmp_path / "md dir" / "evidence.md"
    bn.write_evidence(
        _collect(0.3, input_vars=("speed", "load")),
        _collect(0.2, input_vars=("speed", "load")),
        markdown_path=md,
        png_dir=tmp_path / "my pngs",
    )
    destination = re.search(r"!\[[^\]]*\]\(([^)]*)\)", md.read_text(encoding="utf-8"))[1]
    assert " " not in destination
    assert destination.endswith("/stop_distance.png")


def test_a_baseline_that_swept_nothing_against_a_swept_candidate_links_an_image():
    md = bn.evidence_markdown(_collect(0.3, input_vars=()), _collect(0.2))
    assert "```mermaid" not in md
    assert "](stop_distance.png)" in md


def test_a_point_with_no_recorded_sample_links_an_image():
    md = bn.evidence_markdown(_collect_margin(1.0), _collect_margin(math.nan))
    assert "```mermaid" not in md
    assert "](margin.png)" in md


class Fleet(bn.ParametrizedSweep):
    robot = bn.StringSweep([f"r{i:02d}" for i in range(31)])
    gain = bn.FloatSweep(default=0.2)

    load = bn.ResultFloat(units="kg")

    def benchmark(self):
        self.load = self.gain * int(self.robot[1:])


def _collect_fleet(gain):
    bench = bn.Bench(f"fleet_{gain}", Fleet())
    res = bench.collect(input_vars=["robot"], result_vars=["load"], const_vars=[("gain", gain)])
    bench.close()
    return res


def test_more_than_thirty_categories_link_an_image():
    md = bn.evidence_markdown(_collect_fleet(0.3), _collect_fleet(0.2))
    assert "```mermaid" not in md
    assert "](load.png)" in md


def test_markdown_alone_with_only_charted_metrics_writes_no_png(tmp_path):
    files = bn.write_evidence(_collect(0.3), _collect(0.2), markdown_path=tmp_path / "e.md")
    assert "```mermaid" in (tmp_path / "e.md").read_text(encoding="utf-8")
    assert files.pngs == {}
    assert list(tmp_path.rglob("*.png")) == []
