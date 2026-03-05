/* Auto-crop gallery thumbnails to actual content height.
   Same-origin iframes let us read contentDocument.body.scrollHeight,
   then shrink the wrapper to scrollHeight * scale so short reports
   don't leave huge whitespace. */
(function () {
  var SCALE = 0.2;

  function resizeThumb(iframe) {
    try {
      var doc = iframe.contentDocument || iframe.contentWindow.document;
      var h = doc.body.scrollHeight;
      if (h > 0) {
        iframe.style.height = h + "px";
        iframe.parentElement.style.height = Math.ceil(h * SCALE) + "px";
      }
    } catch (e) {
      /* cross-origin – leave default size */
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var iframes = document.querySelectorAll(".gallery-thumb");
    for (var i = 0; i < iframes.length; i++) {
      iframes[i].addEventListener("load", function () {
        resizeThumb(this);
      });
      /* If already loaded (cached) */
      if (iframes[i].contentDocument && iframes[i].contentDocument.readyState === "complete") {
        resizeThumb(iframes[i]);
      }
    }
  });
})();
