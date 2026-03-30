(function () {
  "use strict";

  function resizeToContent(iframe) {
    try {
      var doc = iframe.contentDocument || iframe.contentWindow.document;
      if (!doc || !doc.body) return;
      doc.documentElement.style.overflow = "hidden";
      doc.body.style.overflow = "hidden";

      var h = Math.max(doc.documentElement.scrollHeight, doc.body.scrollHeight);
      if (h > 0) iframe.style.height = h + "px";

      var w = Math.max(doc.documentElement.scrollWidth, doc.body.scrollWidth);
      if (w > iframe.clientWidth) iframe.style.width = w + "px";
    } catch (e) {
      // Cross-origin: fall back to min-height set via CSS
    }
  }

  function observeContent(iframe) {
    try {
      var doc = iframe.contentDocument || iframe.contentWindow.document;
      if (!doc || !doc.body) return;
      new ResizeObserver(function () {
        resizeToContent(iframe);
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

  // Listen for resize messages posted by inner report iframes
  window.addEventListener("message", function (e) {
    if (e.data && e.data.type === "bencher-resize") {
      var iframes = document.querySelectorAll("iframe.bencher-report");
      iframes.forEach(function (iframe) {
        resizeToContent(iframe);
      });
    }
  });

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
