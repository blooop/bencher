"""PR-ready evidence from two results: the Markdown block and the PNG charts."""

from __future__ import annotations

import itertools
import json
import re

import pytest
from matplotlib.image import imread

import bencher as bn
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
    hi = float(re.search(r"--> (\S+)", chart)[1])
    assert hi >= 0.7


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
    assert 2 <= len(labels) <= 30
    assert len(re.search(r"line \[(.*)\]", chart)[1].split(", ")) == len(labels)


def test_quotes_in_units_do_not_break_the_title():
    base, cand = _collect(0.3), _collect(0.2)
    for res in (base, cand):
        res.bench_cfg.result_vars[0].units = 'm "wet"'
    title = re.search(r"title (.*)", _chart(bn.evidence_markdown(base, cand)))[1]
    assert title.count('"') == 2


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
