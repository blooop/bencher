"""Tests for gallery thumbnail cropping and resizing.

Thumbnails must frame each report's result plots rather than the top of the page, which
is title and description text. The region hunt runs against a live browser during doc
generation; these tests exercise the geometry decisions against a stub page so the rules
are pinned without needing playwright or Chromium.
"""

import io

import pytest
from PIL import Image

from bencher.example.meta.generate_examples import (
    MAX_CROP_ASPECT,
    THUMB_MAX_H,
    THUMB_MAX_W,
    _resize_and_save_png,
    _results_clip,
)


class FakeHandle:
    """Stand-in for a playwright element handle."""

    def __init__(self, box=None, text=""):
        self._box = box
        self._text = text

    def bounding_box(self):
        return self._box

    def text_content(self):
        return self._text

    def evaluate(self, _script):
        return None


class FakePage:
    """Stand-in for a playwright page exposing only what _results_clip touches."""

    def __init__(self, results=(), headings=(), page_w=1200, page_h=2000):
        self._results = list(results)
        self._headings = list(headings)
        self._page_w = page_w
        self._page_h = page_h

    def query_selector_all(self, selector):
        # _results_clip asks for headings and result elements with distinct selectors.
        if selector.startswith("h1"):
            return self._headings
        return self._results

    def evaluate(self, script):
        return self._page_w if "scrollWidth" in script else self._page_h


def _box(x, y, w, h):
    return {"x": x, "y": y, "width": w, "height": h}


def _heading(text, y, h=26):
    return FakeHandle(box=_box(10, y, 100, h), text=text)


class TestResultsClip:
    def test_returns_none_when_no_results(self):
        assert _results_clip(FakePage()) is None

    def test_ignores_content_above_results_heading(self):
        """The sweep-shape diagram above "Results:" must not be mistaken for a plot."""
        diagram = FakeHandle(box=_box(10, 300, 350, 250))
        plot = FakeHandle(box=_box(10, 740, 600, 600))
        page = FakePage(
            results=[diagram, plot],
            headings=[_heading("Results: ¶", 700)],
        )
        clip = _results_clip(page)
        # Crop starts at the plot, not the diagram at y=300.
        assert clip["y"] > 700
        assert clip["height"] == pytest.approx(616, abs=2)

    def test_matches_heading_despite_panel_anchor_suffix(self):
        """Panel appends a "¶" anchor to headings; matching must tolerate it."""
        above = FakeHandle(box=_box(10, 100, 350, 250))
        plot = FakeHandle(box=_box(10, 740, 600, 600))
        for text in ("Results:", "Results: ¶", "  results ¶ "):
            page = FakePage(results=[above, plot], headings=[_heading(text, 700)])
            assert _results_clip(page)["y"] > 700, f"failed for {text!r}"

    def test_unrelated_heading_does_not_filter(self):
        plot = FakeHandle(box=_box(10, 740, 600, 600))
        page = FakePage(results=[plot], headings=[_heading("Results over time", 700)])
        clip = _results_clip(page)
        assert clip["y"] == pytest.approx(732, abs=2)

    def test_skips_toolbar_sized_elements(self):
        """Small chrome (toolbar icons, swatches) must not define the crop."""
        icon = FakeHandle(box=_box(570, 700, 20, 20))
        plot = FakeHandle(box=_box(10, 740, 600, 600))
        clip = _results_clip(FakePage(results=[icon, plot]))
        assert clip["x"] == pytest.approx(2, abs=1)
        assert clip["width"] == pytest.approx(616, abs=2)

    def test_stops_before_crop_becomes_a_tall_strip(self):
        """Stacked plots must not all be included, or each becomes unreadable."""
        plots = [FakeHandle(box=_box(10, 740 + i * 620, 600, 600)) for i in range(3)]
        clip = _results_clip(FakePage(results=plots, page_h=4000))
        assert clip["height"] / clip["width"] <= MAX_CROP_ASPECT
        # Only the first plot is framed.
        assert clip["height"] == pytest.approx(616, abs=2)

    def test_single_tall_result_is_still_captured(self):
        """A lone result taller than the aspect cap must not be dropped entirely."""
        tall = FakeHandle(box=_box(10, 200, 200, 900))
        clip = _results_clip(FakePage(results=[tall]))
        assert clip is not None
        assert clip["height"] == pytest.approx(916, abs=2)

    def test_clip_is_clamped_to_page_bounds(self):
        plot = FakeHandle(box=_box(0, 0, 600, 600))
        clip = _results_clip(FakePage(results=[plot], page_w=600, page_h=600))
        assert clip["x"] == 0
        assert clip["y"] == 0
        assert clip["x"] + clip["width"] <= 600
        assert clip["y"] + clip["height"] <= 600


def _png_bytes(width, height):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, format="PNG")
    return buf.getvalue()


class TestResizeAndSave:
    def test_large_image_is_fitted_inside_max_box(self, tmp_path):
        out = tmp_path / "thumb.png"
        _resize_and_save_png(_png_bytes(1232, 1232), out)
        w, h = Image.open(out).size
        assert w <= THUMB_MAX_W and h <= THUMB_MAX_H
        # Square input stays square — no distortion to fill the box.
        assert w == h == THUMB_MAX_H

    def test_aspect_ratio_is_preserved(self, tmp_path):
        out = tmp_path / "thumb.png"
        _resize_and_save_png(_png_bytes(2000, 1000), out)
        w, h = Image.open(out).size
        assert w / h == pytest.approx(2.0, abs=0.02)

    def test_small_image_is_not_upscaled(self, tmp_path):
        """Upscaling a small result (a 200px video, say) would only blur it."""
        out = tmp_path / "thumb.png"
        _resize_and_save_png(_png_bytes(220, 200), out)
        assert Image.open(out).size == (220, 200)

    def test_creates_missing_parent_directory(self, tmp_path):
        out = tmp_path / "nested" / "dir" / "thumb.png"
        _resize_and_save_png(_png_bytes(600, 600), out)
        assert out.is_file()
