"""Verify built docs example pages show exactly one vertical scrollbar.

These tests load representative example pages from a locally built docs site
(docs/builtdocs) in headless Chromium and assert that the page scrollbar is the
only vertical scroll container: report iframes must be sized to their content,
with no nested scrolling in the report or the multi-tab inner iframe.

Skipped automatically when playwright or a built docs site is unavailable, so
they do not run in normal CI. Typical usage:

    pixi run -e docs docs-subset   # regenerate the representative reports
    pixi run -e docs docs-quick    # sphinx build
    pixi run -e docs docs-check    # this file

Set BENCHER_DOCS_URL to check a deployed site (e.g. readthedocs) instead of a
local build.
"""

import functools
import http.server
import os
import threading
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import (  # pylint: disable=wrong-import-position,import-error
    sync_playwright,
)

BUILTDOCS = Path(__file__).resolve().parent.parent / "docs" / "builtdocs"

# Representative example pages covering the layouts that have historically
# produced nested scrollbars.
PAGE_SIMPLE = "reference/meta/1_float/no_repeats/example_sweep_1_float_0_cat_no_repeats.html"
PAGE_TALL = "reference/meta/statistics/example_stats_repeats_comparison.html"
PAGE_MULTITAB = "reference/meta/0_float/over_time/example_sweep_0_float_0_cat_over_time.html"
PAGE_WIDE = "reference/meta/plot_types/example_plot_heatmap.html"
# Wider than the viewport: must keep natural scale and scroll horizontally.
PAGE_XWIDE = "reference/meta/3_float/with_repeats/example_sweep_3_float_2_cat_with_repeats.html"
# A report opened directly (not embedded) must keep native page scrolling.
PAGE_STANDALONE = (
    "reference/meta/1_float/no_repeats/_reports/"
    "example_sweep_1_float_0_cat_no_repeats/SortBenchmark.html"
)

# Scroll containers that are legitimately independent of the main page scroll.
SCROLL_WHITELIST = [".wy-side-scroll"]

# JS: collect every element with an active vertical scrollbar (overflow-y
# auto/scroll and overflowing content), recursing into same-origin iframes.
# Also flags any iframe whose document is taller than the iframe viewport,
# since an iframe's root scrolls even with default overflow.
_FIND_SCROLLERS_JS = """
(whitelist) => {
  const out = [];
  const describe = (el) =>
    el.tagName.toLowerCase() +
    (el.id ? '#' + el.id : '') +
    (el.className && typeof el.className === 'string'
      ? '.' + el.className.trim().split(/\\s+/).join('.') : '');
  const sweep = (doc, prefix, isTop) => {
    const de = doc.documentElement;
    if (!isTop && de.scrollHeight > de.clientHeight + 4) {
      const oy = doc.defaultView.getComputedStyle(de).overflowY;
      const boy = doc.defaultView.getComputedStyle(doc.body).overflowY;
      if (oy !== 'hidden' && boy !== 'hidden') {
        out.push(prefix + 'document(' + de.scrollHeight + '>' + de.clientHeight + ')');
      }
    }
    for (const el of doc.querySelectorAll('*')) {
      // The top document's root/body scrolling IS the single allowed scrollbar.
      if (isTop && (el === de || el === doc.body)) continue;
      const cs = doc.defaultView.getComputedStyle(el);
      if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') &&
          el.scrollHeight > el.clientHeight + 2 &&
          !whitelist.some((w) => el.matches(w))) {
        out.push(prefix + describe(el) + '(' + el.scrollHeight + '>' + el.clientHeight + ')');
      }
      if (el.tagName === 'IFRAME') {
        try {
          if (el.contentDocument) {
            sweep(el.contentDocument, prefix + describe(el) + ' >> ', false);
          }
        } catch (e) { /* cross-origin */ }
      }
    }
  };
  sweep(document, '', true);
  return out;
}
"""

# Matches the current template (class) and the older fixed-height template so the
# harness can characterize pre-fix builds too.
REPORT_IFRAME_SELECTOR = "iframe.bencher-report, .rst-content iframe"

# JS: [iframe clientHeight, content scrollHeight] for the report iframe.
_IFRAME_FIT_JS = """
(selector) => {
  const f = document.querySelector(selector);
  if (!f || !f.contentDocument) return null;
  const doc = f.contentDocument.documentElement;
  return [f.clientHeight, Math.max(doc.scrollHeight, f.contentDocument.body.scrollHeight)];
}
"""

# JS: width/scale measurements for the report iframe and its scroll wrapper.
_IFRAME_WIDTH_JS = """
(selector) => {
  const f = document.querySelector(selector);
  if (!f || !f.contentDocument) return null;
  const doc = f.contentDocument;
  const wrap = f.parentElement;
  return {
    iframeW: f.clientWidth,
    contentW: Math.max(doc.documentElement.scrollWidth, doc.body.scrollWidth),
    wrapW: wrap.clientWidth,
    wrapScrollW: wrap.scrollWidth,
    zoom: doc.body.style.zoom || '',
  };
}
"""


@pytest.fixture(scope="module", name="base_url")
def fixture_base_url():
    """Serve docs/builtdocs locally, or use BENCHER_DOCS_URL if set."""
    env_url = os.environ.get("BENCHER_DOCS_URL")
    if env_url:
        yield env_url.rstrip("/")
        return
    if not (BUILTDOCS / "index.html").exists():
        pytest.skip("docs/builtdocs not built (run: pixi run -e docs docs-quick)")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(BUILTDOCS))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(scope="module", name="page")
def fixture_page():
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as e:  # pylint: disable=broad-except
            pytest.skip(f"could not launch chromium: {e}")
        pg = browser.new_page(viewport={"width": 1280, "height": 900})
        yield pg
        browser.close()


def _wait_stable(page, timeout_s: float = 20.0, quiet_s: float = 1.5):
    """Wait until the report iframe height stops changing (async Bokeh render)."""

    def height():
        return page.evaluate(
            "(selector) => { const f = document.querySelector(selector);"
            " return f ? f.clientHeight : document.body.scrollHeight; }",
            REPORT_IFRAME_SELECTOR,
        )

    last, quiet_ms, waited_ms, step_ms = height(), 0, 0, 250
    while waited_ms < timeout_s * 1000:
        page.wait_for_timeout(step_ms)
        waited_ms += step_ms
        cur = height()
        if cur == last:
            quiet_ms += step_ms
            if quiet_ms >= quiet_s * 1000:
                return
        else:
            quiet_ms = 0
        last = cur


def _goto(page, base_url: str, rel: str):
    page.goto(f"{base_url}/{rel}", wait_until="networkidle", timeout=60000)
    _wait_stable(page)


def _assert_single_scrollbar(page, label: str):
    scrollers = page.evaluate(_FIND_SCROLLERS_JS, SCROLL_WHITELIST)
    assert scrollers == [], f"{label}: unexpected nested scroll containers: {scrollers}"


def _assert_iframe_fits(page, label: str, min_height: int = 0):
    fit = page.evaluate(_IFRAME_FIT_JS, REPORT_IFRAME_SELECTOR)
    assert fit is not None, f"{label}: report iframe or its document not found"
    client_h, content_h = fit
    assert content_h > 50, f"{label}: report content did not render (height {content_h})"
    assert content_h <= client_h + 4, (
        f"{label}: report iframe scrolls internally (content {content_h}px > iframe {client_h}px)"
    )
    if min_height:
        assert client_h > min_height, (
            f"{label}: iframe height {client_h}px suggests auto-resize did not run "
            f"(expected > {min_height}px)"
        )


def _assert_no_horizontal_overflow(page, label: str):
    scroll_w, client_w = page.evaluate(
        "() => [document.scrollingElement.scrollWidth, document.scrollingElement.clientWidth]"
    )
    assert scroll_w <= client_w + 2, (
        f"{label}: page overflows horizontally ({scroll_w}px > {client_w}px)"
    )


def _assert_natural_scale(page, label: str):
    """The report must never be zoomed/scaled down to fit."""
    m = page.evaluate(_IFRAME_WIDTH_JS, REPORT_IFRAME_SELECTOR)
    assert m is not None, f"{label}: report iframe or its document not found"
    assert m["zoom"] in ("", "1"), f"{label}: report content is scaled (zoom={m['zoom']})"


def _assert_page_ok(page, label: str, min_height: int = 0):
    _assert_single_scrollbar(page, label)
    _assert_iframe_fits(page, label, min_height=min_height)
    _assert_natural_scale(page, label)
    _assert_no_horizontal_overflow(page, label)


def test_simple_page_single_scrollbar(page, base_url):
    _goto(page, base_url, PAGE_SIMPLE)
    _assert_page_ok(page, "simple")


def test_tall_page_single_scrollbar(page, base_url):
    _goto(page, base_url, PAGE_TALL)
    # Tall content must grow the iframe past the old fixed 800px height.
    _assert_page_ok(page, "tall", min_height=800)


def test_wide_page_single_scrollbar(page, base_url):
    _goto(page, base_url, PAGE_WIDE)
    _assert_page_ok(page, "wide")


def test_xwide_page_natural_scale_with_horizontal_scroll(page, base_url):
    _goto(page, base_url, PAGE_XWIDE)
    _assert_single_scrollbar(page, "xwide")
    _assert_iframe_fits(page, "xwide")
    _assert_natural_scale(page, "xwide")
    _assert_no_horizontal_overflow(page, "xwide")
    m = page.evaluate(_IFRAME_WIDTH_JS, REPORT_IFRAME_SELECTOR)
    # The report must be fully reachable at natural scale: the iframe grows to
    # the content width and the wrapper provides the horizontal scrollbar.
    assert m["iframeW"] >= m["contentW"] - 4, (
        f"xwide: content clipped ({m['contentW']}px in {m['iframeW']}px iframe)"
    )
    assert m["contentW"] > m["wrapW"], (
        f"xwide: expected a report wider than the content area, got {m}"
    )
    assert m["wrapScrollW"] > m["wrapW"], f"xwide: wrapper is not horizontally scrollable ({m})"


def test_xwide_page_sticky_proxy_scrollbar(page, base_url):
    """The horizontal scrollbar stays pinned to the viewport bottom while a
    tall wide report is on screen, and scrolling it moves the report."""
    _goto(page, base_url, PAGE_XWIDE)
    # Scroll partway into the (taller than viewport) report region.
    page.evaluate(
        "() => document.querySelector('.bencher-report-region').scrollIntoView({block: 'start'})"
    )
    page.evaluate("() => window.scrollBy(0, 300)")
    page.wait_for_timeout(200)
    state = page.evaluate(
        """() => {
          const proxy = document.querySelector('.bencher-hscroll');
          const wrap = document.querySelector('.bencher-report-wrap');
          const r = proxy.getBoundingClientRect();
          return {
            display: getComputedStyle(proxy).display,
            innerW: proxy.querySelector('.bencher-hscroll-inner').clientWidth,
            bottom: r.bottom,
            viewportH: window.innerHeight,
            wrapBottom: wrap.getBoundingClientRect().bottom,
          };
        }"""
    )
    assert state["display"] != "none", "xwide: sticky proxy scrollbar is hidden"
    assert state["innerW"] > 1280, f"xwide: proxy not sized to content ({state})"
    # The report extends past the viewport, yet the proxy is pinned inside it.
    assert state["wrapBottom"] > state["viewportH"], f"xwide: report not taller than view ({state})"
    assert state["bottom"] <= state["viewportH"] + 1, f"xwide: proxy not sticky ({state})"
    # Dragging the proxy scrolls the report.
    wrap_left = page.evaluate(
        """() => {
          document.querySelector('.bencher-hscroll').scrollLeft = 500;
          return new Promise((res) => requestAnimationFrame(() =>
            requestAnimationFrame(() =>
              res(document.querySelector('.bencher-report-wrap').scrollLeft))));
        }"""
    )
    assert wrap_left > 400, f"xwide: proxy scroll did not move the report (got {wrap_left})"


def test_simple_page_proxy_scrollbar_hidden(page, base_url):
    """Reports that fit the page must not show the horizontal proxy."""
    _goto(page, base_url, PAGE_SIMPLE)
    display = page.evaluate(
        "() => getComputedStyle(document.querySelector('.bencher-hscroll')).display"
    )
    assert display == "none", f"simple: proxy scrollbar should be hidden (display={display})"


def test_multitab_page_single_scrollbar_across_tabs(page, base_url):
    _goto(page, base_url, PAGE_MULTITAB)
    _assert_page_ok(page, "multitab")
    # Switching tabs changes content height (HoloMap sliders); layout must re-fit.
    tabs = page.frame_locator(REPORT_IFRAME_SELECTOR).locator(".tab-btn")
    if tabs.count() > 1:
        tabs.nth(1).click()
        _wait_stable(page)
        _assert_page_ok(page, "multitab/tab2")


def test_standalone_report_keeps_native_scrolling(page, base_url):
    page.goto(f"{base_url}/{PAGE_STANDALONE}", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(1000)
    body_overflow, body_zoom = page.evaluate(
        "() => [document.body.style.overflowY, document.body.style.zoom]"
    )
    assert body_overflow in ("", "visible"), (
        f"standalone: embed script must not hide overflow (got '{body_overflow}')"
    )
    assert body_zoom in ("", "1"), f"standalone: embed script must not zoom (got '{body_zoom}')"
