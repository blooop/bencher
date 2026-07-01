/* Sizes embedded bencher report iframes from height messages posted by the
 * reports themselves (see _EMBED_HEIGHT_SCRIPT in bencher/bench_report.py).
 * Each saved report measures its own content with a ResizeObserver and posts
 * {type: "bencher:height", height} to its parent, so the docs page needs no
 * polling and never touches the report's DOM. */
(function () {
  "use strict";
  window.addEventListener("message", function (e) {
    if (!e.data || e.data.type !== "bencher:height") return;
    var height = Number(e.data.height);
    if (!isFinite(height) || height <= 0) return;
    document.querySelectorAll("iframe.bencher-report").forEach(function (f) {
      if (f.contentWindow === e.source) {
        f.style.height = height + "px";
      }
    });
  });
})();
