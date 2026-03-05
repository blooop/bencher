/* Auto-crop gallery thumbnails to actual content height.
   Panel/Bokeh reports set html,body{height:100%} which makes scrollHeight
   return the iframe's CSS height, not the content height. We override that
   to auto, then poll until Bokeh renders (scrollHeight stabilises). */
(function () {
  var SCALE = 0.2;
  var MIN_CONTENT_HEIGHT = 100;
  var MAX_WAIT = 10000;
  var POLL_INTERVAL = 300;

  function resizeThumb(iframe) {
    try {
      var doc = iframe.contentDocument || iframe.contentWindow.document;
      if (!doc || !doc.body) return false;

      /* Override Panel's height:100% so scrollHeight reflects content */
      doc.documentElement.style.height = "auto";
      doc.body.style.height = "auto";

      var h = doc.body.scrollHeight;
      if (h > MIN_CONTENT_HEIGHT) {
        iframe.style.height = h + "px";
        iframe.parentElement.style.height = Math.ceil(h * SCALE) + "px";
        return true;
      }
    } catch (e) {
      /* cross-origin – leave default size */
    }
    return false;
  }

  function pollUntilRendered(iframe) {
    var elapsed = 0;
    var lastHeight = 0;
    var stableCount = 0;

    function check() {
      try {
        var doc = iframe.contentDocument || iframe.contentWindow.document;
        if (!doc || !doc.body) {
          if (elapsed < MAX_WAIT) {
            elapsed += POLL_INTERVAL;
            setTimeout(check, POLL_INTERVAL);
          }
          return;
        }

        doc.documentElement.style.height = "auto";
        doc.body.style.height = "auto";
        var h = doc.body.scrollHeight;

        if (h > MIN_CONTENT_HEIGHT && h === lastHeight) {
          stableCount++;
          if (stableCount >= 2) {
            /* Height stabilised — Bokeh has likely finished rendering */
            iframe.style.height = h + "px";
            iframe.parentElement.style.height = Math.ceil(h * SCALE) + "px";
            return;
          }
        } else {
          stableCount = 0;
        }
        lastHeight = h;
      } catch (e) {
        return; /* cross-origin */
      }

      elapsed += POLL_INTERVAL;
      if (elapsed < MAX_WAIT) {
        setTimeout(check, POLL_INTERVAL);
      }
    }

    check();
  }

  function onIframeLoad(iframe) {
    /* Start polling after the iframe fires load — Bokeh scripts will
       still be executing at this point. */
    pollUntilRendered(iframe);
  }

  function attachListeners() {
    var iframes = document.querySelectorAll(".gallery-thumb");
    for (var i = 0; i < iframes.length; i++) {
      (function (iframe) {
        iframe.addEventListener("load", function () {
          onIframeLoad(iframe);
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
