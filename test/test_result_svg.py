"""ResultSVG: an SVG file path that the report draws inline, not as a base64 <img>."""

from __future__ import annotations

import panel as pn
import pytest

import bencher as bn
from bencher.results.video_summary import VideoSummaryResult
from bencher.variables.results import ResultImage, result_kind, result_spec


class SvgSweep(bn.ParametrizedSweep):
    n = bn.IntSweep(default=1, bounds=(1, 3))

    drawing = bn.ResultSVG()

    def benchmark(self):
        path = bn.gen_image_path(f"svg_{self.n}", filetype=".svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                f'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20">'
                f'<rect id="r{self.n}" width="{self.n * 5}" height="5"/></svg>'
            )
        self.drawing = path


def _sweep(**run_cfg_kwargs) -> bn.Bench:
    run_cfg = bn.BenchRunCfg(cache_results=False, cache_samples=False, **run_cfg_kwargs)
    bench = SvgSweep().to_bench(run_cfg)
    bench.plot_sweep("svg", input_vars=["n"], result_vars=["drawing"])
    return bench


def _sample_panes(bench: bn.Bench) -> list[pn.pane.SVG]:
    """The SVG panes showing benchmark samples (not the sweep summary's animation)."""
    return [
        p
        for p in bench.report.pane.select(pn.pane.SVG)
        if "/svg_" in str(p.object) and str(p.object).endswith(".svg")
    ]


class TestResultSvgType:
    def test_is_not_an_image(self):
        """A sibling, so the raster-only ResultImage branches never see it."""
        assert not isinstance(bn.ResultSVG(), ResultImage)

    def test_classified_as_svg_media(self):
        spec = result_spec(bn.ResultSVG())
        assert spec is not None
        assert result_kind(bn.ResultSVG()) == "svg"
        assert spec.is_panel
        assert spec.is_media

    def test_container_inlines_the_markup(self, tmp_path):
        path = tmp_path / "a.svg"
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>')
        pane = bn.ResultSVG().to_container()(str(path))
        assert isinstance(pane, pn.pane.SVG)
        assert pane.encode is False


class TestResultSvgInReport:
    def test_each_sample_is_an_inline_svg_pane(self):
        panes = _sample_panes(_sweep())
        drawn = {p.object for p in panes}
        assert len(drawn) == 3
        assert all(p.encode is False for p in panes)

    def test_over_time_uses_the_generic_pane_layout(self):
        """Not ResultImage's slider, which labels every frame image/png."""
        bench = SvgSweep().to_bench(
            bn.BenchRunCfg(cache_results=False, cache_samples=False, over_time=True)
        )
        for t in range(2):
            bench.run_cfg.clear_cache = False
            bench.plot_sweep(
                "svg",
                input_vars=["n"],
                result_vars=["drawing"],
                time_src=f"2026-01-0{t + 1}",
            )
        panes = _sample_panes(bench)
        assert panes
        assert all(p.encode is False for p in panes)

    def test_video_summary_skips_it(self):
        """The video summary feeds images to moviepy, which cannot read SVG."""
        bench = _sweep()
        res = bench.results[-1]
        assert isinstance(res, VideoSummaryResult)
        summary = res.to_video_summary()
        assert summary is None or len(summary) == 0


def test_describe_sweep_inlines_the_cartesian_animation():
    """The sweep summary embeds the animation as markup, so it gzips with the page."""
    bench = _sweep()
    desc = bench.results[-1].bench_cfg.describe_sweep()
    panes = list(desc.select(pn.pane.SVG))
    assert len(panes) == 1
    assert panes[0].encode is False
    assert str(panes[0].object).endswith(".svg")


@pytest.fixture(autouse=True)
def _no_show(monkeypatch):
    monkeypatch.setenv("BENCHER_NO_SHOW", "1")
