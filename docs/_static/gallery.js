/* Auto-crop gallery thumbnails to actual content height.
   Panel/Bokeh reports set html,body{height:100%} which makes scrollHeight
   return the iframe's CSS height, not the content height. We override that
   to auto, then use ResizeObserver to detect when Bokeh finishes rendering. */
(function () {
  var SCALE = 0.2;
  var MIN_CONTENT_HEIGHT = 100;
  var MAX_WRAPPER_HEIGHT = 600; /* never grow beyond the CSS default */

  function applyHeight(iframe, h) {
    if (h > MIN_CONTENT_HEIGHT) {
      var wrapH = Math.min(Math.ceil(h * SCALE), MAX_WRAPPER_HEIGHT);
      iframe.style.height = h + "px";
      iframe.parentElement.style.height = wrapH + "px";
    }
  }

  function fixBodyHeight(doc) {
    try {
      doc.documentElement.style.setProperty("height", "auto", "important");
      doc.body.style.setProperty("height", "auto", "important");
    } catch (e) { /* cross-origin */ }
  }

  function observeIframe(iframe) {
    try {
      var doc = iframe.contentDocument || iframe.contentWindow.document;
      if (!doc || !doc.body) return;

      fixBodyHeight(doc);

      /* Use ResizeObserver on the body to react to Bokeh rendering */
      if (typeof ResizeObserver !== "undefined") {
        var observer = new ResizeObserver(function () {
          fixBodyHeight(doc);
          var h = doc.body.scrollHeight;
          applyHeight(iframe, h);
        });
        observer.observe(doc.body);
        /* Also observe documentElement for layout changes */
        observer.observe(doc.documentElement);
      }

      /* Immediate attempt as well */
      var h = doc.body.scrollHeight;
      applyHeight(iframe, h);
    } catch (e) {
      console.log("gallery.js: cannot access iframe", e.message);
    }
  }

  function attachListeners() {
    var iframes = document.querySelectorAll(".gallery-thumb");
    for (var i = 0; i < iframes.length; i++) {
      (function (iframe) {
        iframe.addEventListener("load", function () {
          observeIframe(iframe);
        });
      })(iframes[i]);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", attachListeners);
  } else {
    attachListeners();
  }
})();
