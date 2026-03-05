/* Deferred iframe loading with IntersectionObserver + concurrency limiter.
   Gallery iframes start with data-src instead of src. When an iframe enters
   the viewport (with 200px margin), its src is set and loading begins.
   At most MAX_CONCURRENT iframes load simultaneously to avoid browser thrash.
   Once loaded, ResizeObserver auto-crops each thumbnail to its content height. */
(function () {
  var SCALE = 0.2;
  var MIN_CONTENT_HEIGHT = 100;
  var MAX_WRAPPER_HEIGHT = 600;
  var MAX_CONCURRENT = 4;

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
    } catch (e) {}
  }

  function observeIframe(iframe) {
    try {
      var doc = iframe.contentDocument || iframe.contentWindow.document;
      if (!doc || !doc.body) return;
      fixBodyHeight(doc);
      if (typeof ResizeObserver !== "undefined") {
        var observer = new ResizeObserver(function () {
          fixBodyHeight(doc);
          applyHeight(iframe, doc.body.scrollHeight);
        });
        observer.observe(doc.body);
        observer.observe(doc.documentElement);
      }
      applyHeight(iframe, doc.body.scrollHeight);
    } catch (e) {}
  }

  function withConcurrencyLimit(max, worker) {
    var active = 0;
    var queue = [];

    function runNext() {
      if (active >= max || !queue.length) return;
      active++;
      var item = queue.shift();
      worker(item, function done() {
        active--;
        runNext();
      });
    }

    return function enqueue(item) {
      queue.push(item);
      runNext();
    };
  }

  var enqueueIframe = withConcurrencyLimit(MAX_CONCURRENT, function (iframe, done) {
    var src = iframe.getAttribute("data-src");
    if (!src) {
      done();
      return;
    }

    iframe.addEventListener("load", function () {
      observeIframe(iframe);
      done();
    }, { once: true });

    iframe.src = src;
    iframe.removeAttribute("data-src");
  });

  function setupDeferredLoading() {
    var iframes = document.querySelectorAll(".gallery-thumb[data-src]");
    if (!iframes.length) return;

    if (typeof IntersectionObserver === "undefined") {
      iframes.forEach(enqueueIframe);
      return;
    }

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          observer.unobserve(entry.target);
          enqueueIframe(entry.target);
        }
      });
    }, { rootMargin: "200px" });

    iframes.forEach(function (iframe) {
      observer.observe(iframe);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupDeferredLoading);
  } else {
    setupDeferredLoading();
  }
})();
