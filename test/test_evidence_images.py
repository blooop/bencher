"""Evidence images: the PNG and CSV per metric, and the Markdown that links them."""

from __future__ import annotations

import csv
import itertools
from enum import Enum, auto

import pytest
from matplotlib.colors import to_hex
from matplotlib.image import imread

import bencher as bn
from bencher.evidence import (
    _IMAGE_BETTER,
    _IMAGE_DOWN,
    _IMAGE_UP,
    _IMAGE_WORSE,
    Heatmap,
    HeatmapGrid,
    _render_heatmap_image,
)

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
        images=bn.ImageOutput(tmp_path / "images", publish=_fake_publish(calls)),
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
    bn.write_evidence(_collect(0.3), _collect(0.2), images=bn.ImageOutput(tmp_path))

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
        images=bn.ImageOutput(tmp_path / "images", publish=lambda _files: {}),
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
        images=bn.ImageOutput(tmp_path / "images", publish=_fake_publish(calls)),
    )

    assert files.images == {}
    assert calls == []
    assert "![" not in files.markdown_path.read_text(encoding="utf-8")


def test_two_swept_inputs_get_a_heatmap_image_even_with_one_sample(tmp_path):
    files = bn.write_evidence(
        _collect(0.3, input_vars=("speed", "load"), repeats=1),
        _collect(0.2, input_vars=("speed", "load"), repeats=1),
        images=bn.ImageOutput(tmp_path),
    )

    assert files.images == {"stop_distance": tmp_path / "stop_distance.png"}
    height, width, _ = imread(files.images["stop_distance"]).shape
    assert width > 200
    assert height > 200


def test_no_swept_input_with_repeats_gets_an_image(tmp_path):
    files = bn.write_evidence(
        _collect(0.3, input_vars=()), _collect(0.2, input_vars=()), images=bn.ImageOutput(tmp_path)
    )

    assert set(files.images) == {"stop_distance"}


@pytest.mark.parametrize("input_vars", [("speed",), (), ("speed", "load")])
def test_images_do_not_change_the_png_dir_pngs(tmp_path, input_vars):
    base, cand = _collect(0.3, input_vars=input_vars), _collect(0.2, input_vars=input_vars)
    alone = bn.write_evidence(base, cand, png_dir=tmp_path / "a")
    both = bn.write_evidence(
        base, cand, png_dir=tmp_path / "b", images=bn.ImageOutput(tmp_path / "img")
    )

    assert (tmp_path / "a" / "stop_distance.png").read_bytes() == (
        tmp_path / "b" / "stop_distance.png"
    ).read_bytes()
    assert set(alone.pngs) == set(both.pngs)


def test_the_same_dir_for_pngs_and_images_is_an_error(tmp_path):
    with pytest.raises(ValueError, match=r"png_dir and images.dir"):
        bn.write_evidence(
            _collect(0.3),
            _collect(0.2),
            png_dir=tmp_path / "x",
            images=bn.ImageOutput(tmp_path / "y" / ".." / "x"),
        )

    assert not (tmp_path / "x").exists()


def test_a_png_link_without_a_csv_link_draws_the_image_and_no_csv_link(tmp_path):
    url = "https://example.test/stop_distance.png?raw=true"
    files = bn.write_evidence(
        _collect(0.3),
        _collect(0.2),
        markdown_path=tmp_path / "evidence.md",
        images=bn.ImageOutput(
            tmp_path / "images", publish=lambda _files: {"stop_distance.png": url}
        ),
    )
    md = files.markdown_path.read_text(encoding="utf-8")

    assert f"![stop_distance: before vs after]({url})" in md
    assert "samples (CSV)" not in md
    assert files.image_urls == {"stop_distance": url}


class Surface(Enum):
    DRY = auto()
    WET = auto()
    ICE = auto()


class Layouts(bn.ParametrizedSweep):
    fine = bn.FloatSweep(default=1.0, bounds=(1.0, 3.0), samples=31)
    rows = bn.FloatSweep(default=1.0, bounds=(1.0, 2.0), samples=12)
    cols = bn.FloatSweep(default=1.0, bounds=(1.0, 2.0), samples=11)
    surface = bn.EnumSweep(Surface)
    load = bn.FloatSweep(default=1.0, bounds=(1.0, 2.0), samples=2)
    gain = bn.FloatSweep(default=0.2)

    stop_distance = bn.ResultFloat(units="m", direction=bn.OptDir.minimize)

    def benchmark(self):
        grip = {Surface.DRY: 1.0, Surface.WET: 1.5, Surface.ICE: 3.0}[self.surface]
        self.stop_distance = (
            self.gain * self.fine * self.rows * self.cols * self.load * grip + next(_NOISE)
        )


def _collect_layout(gain, input_vars, repeats):
    bench = bn.Bench(f"layouts_img_{gain}_{'_'.join(input_vars)}_{repeats}", Layouts())
    res = bench.collect(
        input_vars=list(input_vars),
        result_vars=["stop_distance"],
        const_vars=[("gain", gain)],
        run_cfg=bn.BenchRunCfg(repeats=repeats),
    )
    bench.close()
    return res


@pytest.mark.parametrize(
    ("input_vars", "repeats"),
    [
        pytest.param(("fine",), 2, id="more-than-30-points"),
        pytest.param(("surface",), 2, id="categorical-with-repeats"),
        pytest.param(("load", "cols", "surface"), 1, id="three-inputs-layered-heatmap"),
        pytest.param(("rows", "cols"), 1, id="heatmap-over-120-cells"),
    ],
)
def test_each_image_layout_writes_a_png_that_decodes(tmp_path, input_vars, repeats):
    files = bn.write_evidence(
        _collect_layout(0.3, input_vars, repeats),
        _collect_layout(0.2, input_vars, repeats),
        images=bn.ImageOutput(tmp_path),
    )

    png = tmp_path / "stop_distance.png"
    assert files.images == {"stop_distance": png}
    height, width, _ = imread(png).shape
    assert width > 200
    assert height > 200


def test_sides_that_sweep_different_inputs_get_no_image(tmp_path):
    files = bn.write_evidence(
        _collect(0.3, input_vars=("speed",)),
        _collect(0.2, input_vars=("load",)),
        images=bn.ImageOutput(tmp_path),
    )

    assert files.images == {}
    assert not (tmp_path / "stop_distance.png").exists()


class Coasting(bn.ParametrizedSweep):
    speed = bn.FloatSweep(default=1.0, bounds=(1.0, 3.0), samples=3)
    load = bn.FloatSweep(default=1.0, bounds=(1.0, 2.0), samples=2)
    gain = bn.FloatSweep(default=0.2)

    stop_distance = bn.ResultFloat(units="m", direction=bn.OptDir.minimize)

    def benchmark(self):
        self.stop_distance = self.gain * self.speed * self.load


def _collect_coasting(gain):
    bench = bn.Bench(f"coasting_img_{gain}", Coasting())
    res = bench.collect(
        input_vars=["speed", "load"],
        result_vars=["stop_distance"],
        const_vars=[("gain", gain)],
        run_cfg=bn.BenchRunCfg(repeats=1),
    )
    bench.close()
    return res


def test_a_heatmap_with_no_finite_change_gets_no_image(tmp_path):
    # A baseline of 0 at every point makes every percent change n/a.
    calls = []
    files = bn.write_evidence(
        _collect_coasting(0.0),
        _collect_coasting(0.2),
        markdown_path=tmp_path / "evidence.md",
        images=bn.ImageOutput(tmp_path / "images", publish=_fake_publish(calls)),
    )
    md = files.markdown_path.read_text(encoding="utf-8")

    assert "n/a" in md
    assert files.images == {}
    assert calls == []
    assert "![" not in md


@pytest.mark.parametrize(
    ("direction", "fell", "rose", "meaning"),
    [
        pytest.param(
            "minimize", _IMAGE_BETTER, _IMAGE_WORSE, "blue = better (lower)", id="minimize"
        ),
        pytest.param(
            "maximize", _IMAGE_WORSE, _IMAGE_BETTER, "blue = better (higher)", id="maximize"
        ),
        pytest.param("none", _IMAGE_DOWN, _IMAGE_UP, "violet = down, yellow = up", id="none"),
    ],
)
def test_a_heatmap_cell_is_colored_by_whether_its_change_is_better(direction, fell, rose, meaning):
    plan = Heatmap(
        row_input="speed",
        col_input="load",
        row_labels=("1",),
        col_labels=("1", "2"),
        grids=(HeatmapGrid(layer=None, before=((10.0, 10.0),), after=((5.0, 15.0),)),),
        layer_input=None,
        direction=direction,
        margin_percent=5.0,
        notes=(),
    )
    fig = _render_heatmap_image(plan, "stop_distance")

    image = fig.axes[0].images[0]
    fell_rgba, rose_rgba = image.to_rgba(image.get_array())[0]
    assert to_hex(fell_rgba) == fell
    assert to_hex(rose_rgba) == rose
    assert meaning in fig.axes[-1].get_ylabel()


class Faulty(Braking):
    """Braking whose fifth call gives ``bad`` instead of a distance."""

    def __init__(self, bad, **params):
        super().__init__(**params)
        self._bad = bad
        self._calls = 0

    def benchmark(self):
        super().benchmark()
        self._calls += 1
        if self._calls == 5:
            self.stop_distance = self._bad


def _collect_faulty(gain, bad):
    bench = bn.Bench(f"braking_faulty_{gain}", Faulty(bad))
    res = bench.collect(
        input_vars=["speed"],
        result_vars=["stop_distance"],
        const_vars=[("gain", gain)],
        run_cfg=bn.BenchRunCfg(repeats=3),
    )
    bench.close()
    return res


def test_a_csv_leaves_out_a_repeat_that_is_not_finite(tmp_path):
    bn.write_evidence(
        _collect(0.3),
        _collect_faulty(0.2, float("nan")),
        images=bn.ImageOutput(tmp_path),
    )

    text = (tmp_path / "stop_distance.csv").read_text(encoding="utf-8")
    assert "nan" not in text.lower()
    rows = list(csv.DictReader(text.splitlines()))
    # 3 speeds x 3 repeats per side, less the one nan repeat after.
    assert sum(r["side"] == "before" for r in rows) == 9
    assert sum(r["side"] == "after" for r in rows) == 8
