(function () {
  "use strict";

  var _heights = new WeakMap();
  var _timer = null;

  function resizeToContent(iframe) {
    try {
      var doc = iframe.contentDocument || iframe.contentWindow.document;
      if (!doc || !doc.body) return;
      doc.documentElement.style.overflowY = "hidden";
      doc.body.style.overflowY = "hidden";

      // Scale content down to fit available width (avoids buried horizontal scrollbar)
      var availW = iframe.clientWidth;
      var contentW = Math.max(doc.documentElement.scrollWidth, doc.body.scrollWidth);
      if (availW > 0 && contentW > availW) {
        doc.body.style.zoom = (availW / contentW).toString();
      } else {
        doc.body.style.zoom = "1";
      }

      var h = Math.max(doc.documentElement.scrollHeight, doc.body.scrollHeight);
      if (h > 0 && h !== (_heights.get(iframe) || 0)) {
        _heights.set(iframe, h);
        iframe.style.height = h + "px";
      }
    } catch (e) {
      // Cross-origin: fall back to min-height set via CSS
    }
  }

  function debouncedResize(iframe) {
    if (_timer) return;
    _timer = setTimeout(function () {
      _timer = null;
      resizeToContent(iframe);
    }, 100);
  }

  function observeContent(iframe) {
    try {
      var doc = iframe.contentDocument || iframe.contentWindow.document;
      if (!doc || !doc.body) return;
      new ResizeObserver(function () {
        debouncedResize(iframe);
      }).observe(doc.body);

      // Multi-tab reports have an inner iframe#content — re-resize on tab switch
      var inner = doc.getElementById("content");
      if (inner) {
        inner.addEventListener("load", function () {
          setTimeout(function () { resizeToContent(iframe); }, 200);
          setTimeout(function () { resizeToContent(iframe); }, 1000);
          setTimeout(function () { resizeToContent(iframe); }, 3000);
        });
      }
    } catch (e) {
      // Cross-origin: silently skip
    }
  }

  function setupIframe(iframe) {
    resizeToContent(iframe);
    observeContent(iframe);
    setTimeout(function () { resizeToContent(iframe); }, 500);
    setTimeout(function () { resizeToContent(iframe); }, 1500);
    setTimeout(function () { resizeToContent(iframe); }, 3000);
  }

  function initAll() {
    var iframes = document.querySelectorAll("iframe.bencher-report");
    iframes.forEach(function (iframe) {
      if (iframe.contentDocument && iframe.contentDocument.readyState === "complete") {
        setupIframe(iframe);
      }
      iframe.addEventListener("load", function () {
        setupIframe(iframe);
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
  } else {
    initAll();
  }
})();
