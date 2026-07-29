"""Tests for gallery thumbnail cropping and resizing.

Thumbnails must frame each report's results rather than the top of the page, which is
title and description text. The region hunt runs against a live browser during doc
generation; these tests exercise the geometry decisions against a stub page so the rules
are pinned without needing playwright or Chromium.
"""

import io
from pathlib import Path

import pytest
from PIL import Image

from bencher.example.meta.generate_examples import (
    MAX_CROP_ASPECT,
    RESULT_SELECTOR_TIERS,
    RESULT_WAIT_ATTEMPTS,
    RESULTS_HEADING_SELECTOR,
    SECTION_SELECTOR,
    THUMB_MAX_H,
    THUMB_MAX_W,
    TOOLBAR_SELECTOR,
    _hide_toolbars,
    _resize_and_save_png,
    _results_clip,
    _wait_for_results,
)


class FakeHandle:
    """Stand-in for a playwright element handle."""

    def __init__(self, box=None, text=""):
        self._box = box
        self._text = text
        self.evaluated = []

    def bounding_box(self):
        return self._box

    def text_content(self):
        return self._text

    def evaluate(self, script):
        self.evaluated.append(script)


class FakeFrame:
    """Stand-in for a playwright frame, dispatching on the real module selectors."""

    def __init__(self, headings=(), tier1=(), tier2=(), section=(), toolbars=()):
        self._by_selector = {
            RESULTS_HEADING_SELECTOR: list(headings),
            RESULT_SELECTOR_TIERS[0]: list(tier1),
            RESULT_SELECTOR_TIERS[1]: list(tier2),
            SECTION_SELECTOR: list(section),
            TOOLBAR_SELECTOR: list(toolbars),
        }

    def query_selector_all(self, selector):
        return self._by_selector[selector]


class FakePage:
    """Stand-in for a playwright page exposing only what the crop helpers touch."""

    def __init__(self, frames=None, page_w=1200, page_h=2000, **frame_kwargs):
        self.frames = list(frames) if frames is not None else [FakeFrame(**frame_kwargs)]
        self._page_w = page_w
        self._page_h = page_h
        self.waits = []

    def evaluate(self, script):
        assert "scrollWidth" in script and "scrollHeight" in script, (
            "page size should be fetched in a single round-trip"
        )
        return [self._page_w, self._page_h]

    def wait_for_timeout(self, ms):
        self.waits.append(ms)


class SlowRenderPage(FakePage):
    """A page whose results only become measurable after `renders_after` polls.

    Models Bokeh painting late on a cold browser, which used to yield a blank thumbnail.
    """

    def __init__(self, renders_after, **kwargs):
        self._renders_after = renders_after
        self._polls = 0
        self._late = FakeFrame(
            headings=[_heading("Results: ¶", 700)],
            tier1=[FakeHandle(box=_box(10, 740, 600, 600))],
        )
        super().__init__(**kwargs)

    @property
    def frames(self):
        self._polls += 1
        return [self._late] if self._polls > self._renders_after else [FakeFrame()]

    @frames.setter
    def frames(self, value):
        pass  # the property above decides what is visible


def _box(x, y, w, h):
    return {"x": x, "y": y, "width": w, "height": h}


def _heading(text, bottom, h=26):
    """A heading whose bottom edge is at `bottom` — that edge is what the crop keys off."""
    return FakeHandle(box=_box(10, bottom - h, 100, h), text=text)


class TestResultsClip:
    def test_returns_none_when_page_is_empty(self):
        assert _results_clip(FakePage()) is None

    def test_ignores_content_above_results_heading(self):
        """The sweep-shape diagram above "Results:" must not be mistaken for a plot."""
        diagram = FakeHandle(box=_box(10, 300, 350, 250))
        plot = FakeHandle(box=_box(10, 740, 600, 600))
        page = FakePage(tier1=[diagram, plot], headings=[_heading("Results: ¶", 700)])
        clip = _results_clip(page)
        # Crop starts at the plot, not the diagram at y=300.
        assert clip["y"] > 700
        assert clip["height"] == pytest.approx(616, abs=2)

    def test_matches_heading_despite_panel_anchor_suffix(self):
        """Panel appends a "¶" anchor to headings; matching must tolerate it."""
        above = FakeHandle(box=_box(10, 100, 350, 250))
        plot = FakeHandle(box=_box(10, 740, 600, 600))
        for text in ("Results:", "Results: ¶", "  results ¶ "):
            page = FakePage(tier1=[above, plot], headings=[_heading(text, 700)])
            assert _results_clip(page)["y"] > 700, f"failed for {text!r}"

    def test_unrelated_heading_does_not_filter(self):
        plot = FakeHandle(box=_box(10, 740, 600, 600))
        page = FakePage(tier1=[plot], headings=[_heading("Results over time", 700)])
        assert _results_clip(page)["y"] == pytest.approx(732, abs=2)

    def test_excludes_wrappers_that_only_end_below_the_marker(self):
        """A page-spanning wrapper div would otherwise stretch the crop to full width."""
        wrapper = FakeHandle(box=_box(0, 100, 1013, 850))
        text = FakeHandle(box=_box(10, 620, 280, 45))
        page = FakePage(section=[wrapper, text], headings=[_heading("Results:", 600)])
        clip = _results_clip(page)
        assert clip["width"] < 400, "wrapper div leaked into the crop"

    def test_skips_toolbar_sized_elements(self):
        """Small chrome (toolbar icons, swatches) must not define the crop."""
        icon = FakeHandle(box=_box(570, 700, 20, 20))
        plot = FakeHandle(box=_box(10, 740, 600, 600))
        clip = _results_clip(FakePage(tier1=[icon, plot]))
        assert clip["x"] == pytest.approx(2, abs=1)
        assert clip["width"] == pytest.approx(616, abs=2)

    def test_stops_before_crop_becomes_a_tall_strip(self):
        """Stacked plots must not all be included, or each becomes unreadable."""
        plots = [FakeHandle(box=_box(10, 740 + i * 620, 600, 600)) for i in range(3)]
        clip = _results_clip(FakePage(tier1=plots, page_h=4000))
        assert clip["height"] / clip["width"] <= MAX_CROP_ASPECT
        # Only the first plot is framed.
        assert clip["height"] == pytest.approx(616, abs=2)

    def test_single_tall_result_is_topped_not_squeezed(self):
        """A 200x1200 stacked video composition must not become a 7:1 sliver."""
        tall = FakeHandle(box=_box(128, 557, 200, 1200))
        clip = _results_clip(FakePage(tier1=[tall]))
        assert clip is not None
        assert clip["height"] / clip["width"] <= MAX_CROP_ASPECT

    def test_clip_is_clamped_to_page_bounds(self):
        plot = FakeHandle(box=_box(0, 0, 600, 600))
        clip = _results_clip(FakePage(tier1=[plot], page_w=600, page_h=600))
        assert clip["x"] == 0
        assert clip["y"] == 0
        assert clip["x"] + clip["width"] <= 600
        assert clip["y"] + clip["height"] <= 600


class TestSelectorTiers:
    def test_plot_is_preferred_over_a_preceding_table(self):
        """xy_scatter leads with a 226x1587 DataFrame table; the figure makes a better thumb."""
        table = FakeHandle(box=_box(128, 578, 226, 1587))
        figure = FakeHandle(box=_box(128, 5382, 600, 600))
        page = FakePage(
            tier1=[figure],
            tier2=[table],
            headings=[_heading("Results:", 560)],
            page_h=7259,
        )
        clip = _results_clip(page)
        assert clip["y"] == pytest.approx(5374, abs=4), "table won over the figure"
        assert clip["height"] == pytest.approx(616, abs=2)

    def test_table_is_used_when_no_plot_exists(self):
        table = FakeHandle(box=_box(128, 578, 400, 300))
        page = FakePage(tier2=[table], headings=[_heading("Results:", 560)])
        clip = _results_clip(page)
        assert clip["y"] == pytest.approx(570, abs=4)

    def test_text_results_fall_back_to_the_results_section(self):
        """ResultString/ResultVec render as markup panes with no plot to frame."""
        pane = FakeHandle(box=_box(10, 629, 277, 41))
        column = FakeHandle(box=_box(10, 624, 297, 51))
        page = FakePage(section=[column, pane], headings=[_heading("Results: ¶", 612)])
        clip = _results_clip(page)
        assert clip is not None
        assert clip["y"] == pytest.approx(604, abs=4)
        # Framed to the text column, not stretched to the report's full content width.
        assert clip["width"] == pytest.approx(313, abs=4)

    def test_section_fallback_needs_a_results_marker(self):
        """Without a marker there is no way to tell results from page furniture."""
        pane = FakeHandle(box=_box(10, 629, 277, 41))
        assert _results_clip(FakePage(section=[pane])) is None


class TestFrames:
    def test_finds_results_inside_a_child_frame(self):
        """over_time reports are a tab bar plus an iframe holding the whole report."""
        main = FakeFrame()
        child = FakeFrame(
            headings=[_heading("Results: ¶", 769)],
            tier1=[FakeHandle(box=_box(10, 891, 600, 600))],
        )
        clip = _results_clip(FakePage(frames=[main, child], page_h=2233))
        assert clip is not None, "child frame content was not found"
        assert clip["y"] == pytest.approx(883, abs=4)
        assert clip["height"] == pytest.approx(616, abs=2)

    def test_hides_toolbars_in_every_frame(self):
        main_toolbar = FakeHandle(box=_box(570, 100, 30, 510))
        child_toolbar = FakeHandle(box=_box(570, 900, 30, 510))
        page = FakePage(
            frames=[FakeFrame(toolbars=[main_toolbar]), FakeFrame(toolbars=[child_toolbar])]
        )
        _hide_toolbars(page)
        assert main_toolbar.evaluated, "main frame toolbar not hidden"
        assert child_toolbar.evaluated, "child frame toolbar not hidden"


class TestWaitForResults:
    def test_returns_immediately_when_results_are_already_rendered(self):
        page = FakePage(
            headings=[_heading("Results: ¶", 700)],
            tier1=[FakeHandle(box=_box(10, 740, 600, 600))],
        )
        assert _wait_for_results(page) is not None
        assert page.waits == [], "slept despite results being ready"

    def test_waits_for_a_late_rendering_report(self):
        """A fixed sleep was a coin flip on a cold browser; polling must ride it out."""
        page = SlowRenderPage(renders_after=3)
        clip = _wait_for_results(page)
        assert clip is not None, "gave up before Bokeh painted"
        assert clip["height"] == pytest.approx(616, abs=2)

    def test_gives_up_on_a_report_that_renders_nothing(self):
        page = FakePage()
        assert _wait_for_results(page) is None
        # Bounded: does not sleep after the final attempt.
        assert len(page.waits) == RESULT_WAIT_ATTEMPTS - 1


def _png_bytes(width, height):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, format="PNG")
    return buf.getvalue()


class ScreenshotPage(FakePage):
    """A page that records how screenshot() was called."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.screenshot_calls = []

    def set_viewport_size(self, size):
        self.viewport = size

    def goto(self, _url, **_kwargs):
        return None

    def screenshot(self, **kwargs):
        self.screenshot_calls.append(kwargs)
        return _png_bytes(200, 200)


class TestScreenshotArgs:
    """Regression guard for the clip/full_page interaction.

    A report's first plot can sit thousands of pixels down the page (xy_scatter's is at
    y~5400 in a 900px viewport). Playwright's `clip` alone cannot reach past the viewport
    and raises "Clipped area is either empty or outside the resulting image", so
    `full_page=True` is required alongside it rather than redundant with it.
    """

    def _take(self, page, tmp_path):
        from bencher.example.meta.generate_examples import _take_thumbnail

        _take_thumbnail(Path("report.html"), tmp_path / "thumb.png", page=page)
        return page.screenshot_calls[-1]

    def test_clip_screenshot_also_passes_full_page(self, tmp_path):
        page = ScreenshotPage(
            headings=[_heading("Results: ¶", 560)],
            tier1=[FakeHandle(box=_box(128, 5382, 600, 600))],
            page_h=7259,
        )
        call = self._take(page, tmp_path)
        assert call.get("clip") is not None, "expected a cropped screenshot"
        assert call.get("full_page") is True, (
            "clip beyond the viewport needs full_page; see _screenshot_with"
        )
        assert call["clip"]["y"] > page.viewport["height"], "test no longer covers the case"

    def test_fallback_screenshot_passes_neither(self, tmp_path):
        """A report that renders nothing falls back to a plain viewport capture."""
        page = ScreenshotPage()
        call = self._take(page, tmp_path)
        assert call == {}


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
