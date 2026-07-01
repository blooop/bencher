/* Sizes embedded bencher report iframes from size messages posted by the
 * reports themselves (see _EMBED_HEIGHT_SCRIPT in bencher/bench_report.py).
 * Each saved report measures its own content with a ResizeObserver and posts
 * {type: "bencher:height", height, width} to its parent, so the docs page
 * needs no polling and never touches the report's DOM.
 *
 * Reports keep their natural scale: when one is wider than the content area,
 * the iframe grows to the report's full width inside its .bencher-report-wrap
 * container, which scrolls horizontally. Vertical scrolling stays on the
 * page's single scrollbar. */
(function () {
  "use strict";
  window.addEventListener("message", function (e) {
    if (!e.data || e.data.type !== "bencher:height") return;
    var height = Number(e.data.height);
    var width = Number(e.data.width) || 0;
    if (!isFinite(height) || height <= 0) return;
    document.querySelectorAll("iframe.bencher-report").forEach(function (f) {
      if (f.contentWindow !== e.source) return;
      f.style.height = height + "px";
      var wrap = f.parentElement;
      var avail = wrap ? wrap.clientWidth : 0;
      f.style.width = width > avail && avail > 0 ? width + "px" : "";
    });
  });
})();
