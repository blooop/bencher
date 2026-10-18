"""Evidence images: the PNG and CSV per metric, and the Markdown that links them."""

from __future__ import annotations

import csv
import itertools

import pytest
from matplotlib.image import imread

import bencher as bn

_NOISE = itertools.cycle([0.05, -0.05, 0.0])


class Braking(bn.ParametrizedSweep):
    speed = bn.FloatSweep(default=1.0, bounds=(1.0, 3.0), samples=3)
    load = bn.FloatSweep(default=1.0, bounds=(1.0, 2.0), samples=2)
    gain = bn.FloatSweep(default=0.2)

    stop_distance = bn.ResultFloat(units="m", direction=bn.OptDir.minimize)

    def benchmark(self):
        self.stop_distance = self.gain * self.speed * self.load + next(_NOISE)


def _collect(gain, input_vars=("speed",), repeats=3):
    bench = bn.Bench(f"braking_img_{gain}", Braking())
    res = bench.collect(
        input_vars=list(input_vars),
        result_vars=["stop_distance"],
        const_vars=[("gain", gain)],
        run_cfg=bn.BenchRunCfg(repeats=repeats),
    )
    bench.close()
    return res


def _fake_publish(calls):
    def publish(files):
        calls.append(dict(files))
        return {name: f"https://example.test/{name}?raw=true" for name in files}

    return publish


def test_images_link_a_png_above_each_text_chart_and_keep_the_data(tmp_path):
    calls = []
    files = bn.write_evidence(
        _collect(0.3),
        _collect(0.2),
        markdown_path=tmp_path / "evidence.md",
        image_dir=tmp_path / "images",
        publish_images=_fake_publish(calls),
    )
    md = files.markdown_path.read_text(encoding="utf-8")

    png = tmp_path / "images" / "stop_distance.png"
    data = tmp_path / "images" / "stop_distance.csv"
    assert calls == [{"stop_distance.png": png, "stop_distance.csv": data}]
    image = "![stop_distance: before vs after](https://example.test/stop_distance.png?raw=true)"
    assert image in md
    assert "[samples (CSV)](https://example.test/stop_distance.csv?raw=true)" in md
    # The text chart, caption and CSV block stay under the image, in that order.
    assert md.index(image) < md.index("```mermaid") < md.index("<details>")
    assert files.images == {"stop_distance": png}
    assert files.image_urls == {"stop_distance": "https://example.test/stop_distance.png?raw=true"}


def test_an_image_is_a_real_png_and_its_csv_holds_every_repeat(tmp_path):
    bn.write_evidence(_collect(0.3), _collect(0.2), image_dir=tmp_path)

    height, width, _ = imread(tmp_path / "stop_distance.png").shape
    assert width > height > 200
    with (tmp_path / "stop_distance.csv").open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    # 3 speeds x 3 repeats per side.
    assert len(rows) == 18
    assert {r["side"] for r in rows} == {"before", "after"}
    assert {"speed", "repeat", "stop_distance"} <= set(rows[0])


def test_without_a_link_the_markdown_is_the_text_only_one(tmp_path):
    base, cand = _collect(0.3), _collect(0.2)
    files = bn.write_evidence(
        base,
        cand,
        markdown_path=tmp_path / "evidence.md",
        image_dir=tmp_path / "images",
        publish_images=lambda _files: {},
    )

    assert (tmp_path / "images" / "stop_distance.png").exists()
    assert files.markdown_path.read_text(encoding="utf-8") == bn.evidence_markdown(
        base, cand, comparison=files.comparison
    )
    assert files.image_urls == {}


def test_one_sample_per_point_draws_no_image_the_text_chart_already_shows(tmp_path):
    calls = []
    files = bn.write_evidence(
        _collect(0.3, repeats=1),
        _collect(0.2, repeats=1),
        markdown_path=tmp_path / "evidence.md",
        image_dir=tmp_path / "images",
        publish_images=_fake_publish(calls),
    )

    assert files.images == {}
    assert calls == []
    assert "![" not in files.markdown_path.read_text(encoding="utf-8")


def test_two_swept_inputs_get_a_heatmap_image_even_with_one_sample(tmp_path):
    files = bn.write_evidence(
        _collect(0.3, input_vars=("speed", "load"), repeats=1),
        _collect(0.2, input_vars=("speed", "load"), repeats=1),
        image_dir=tmp_path,
    )

    assert files.images == {"stop_distance": tmp_path / "stop_distance.png"}
    height, width, _ = imread(files.images["stop_distance"]).shape
    assert width > 200
    assert height > 200


def test_no_swept_input_with_repeats_gets_an_image(tmp_path):
    files = bn.write_evidence(
        _collect(0.3, input_vars=()), _collect(0.2, input_vars=()), image_dir=tmp_path
    )

    assert set(files.images) == {"stop_distance"}


@pytest.mark.parametrize("input_vars", [("speed",), (), ("speed", "load")])
def test_images_do_not_change_the_png_dir_pngs(tmp_path, input_vars):
    base, cand = _collect(0.3, input_vars=input_vars), _collect(0.2, input_vars=input_vars)
    alone = bn.write_evidence(base, cand, png_dir=tmp_path / "a")
    both = bn.write_evidence(base, cand, png_dir=tmp_path / "b", image_dir=tmp_path / "img")

    assert (tmp_path / "a" / "stop_distance.png").read_bytes() == (
        tmp_path / "b" / "stop_distance.png"
    ).read_bytes()
    assert set(alone.pngs) == set(both.pngs)
