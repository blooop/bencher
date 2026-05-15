"""Tests for the rerun-viewer wrapper and saved-report URL rewriting."""

import html
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bencher.utils_rrd import (
    _RRD_URL_RE,
    _wrap_viewer_controls,
    inline_rrd_iframes,
)


class TestWrapViewerControls(unittest.TestCase):
    """``_wrap_viewer_controls`` builds the iframe + control overlay HTML."""

    def test_contains_both_controls(self):
        iframe = (
            '<iframe src="A" width="400" height="400" frameborder="0" allowfullscreen></iframe>'
        )
        out = _wrap_viewer_controls(iframe, "A", 400, 400)
        self.assertIn("requestFullscreen()", out)
        self.assertIn('target="_blank"', out)

    def test_anchor_href_is_set_at_construction(self):
        """Middle-click / Cmd-click rely on a real ``href`` attribute, not onclick."""
        iframe = '<iframe src="/some/url" width="100" height="100" frameborder="0" allowfullscreen></iframe>'
        out = _wrap_viewer_controls(iframe, "/some/url", 100, 100)
        # Anchor must carry the URL directly, not a placeholder filled in by JS.
        self.assertIn('href="/some/url"', out)
        self.assertNotIn("about:blank", out)
        # The new-tab anchor must not depend on onclick — only the fullscreen
        # button should have an onclick handler.
        self.assertEqual(out.count("onclick="), 1)

    def test_preserves_iframe_html_verbatim(self):
        iframe = '<iframe src="X" width="1" height="2" frameborder="0" allowfullscreen></iframe>'
        out = _wrap_viewer_controls(iframe, "X", 1, 2)
        self.assertIn(iframe, out)


class TestRrdUrlRegex(unittest.TestCase):
    """``_RRD_URL_RE`` finds the URL in Bokeh's double-escaped saved HTML."""

    def test_matches_both_iframe_and_anchor_occurrences(self):
        iframe = '<iframe src="/rrd_static/viewer_0.32.0.html?url=/rrd_static/job/foo.rrd" width="400" height="400" frameborder="0" allowfullscreen></iframe>'
        wrapped = _wrap_viewer_controls(
            iframe, "/rrd_static/viewer_0.32.0.html?url=/rrd_static/job/foo.rrd", 400, 400
        )
        # Bokeh serialises HTML inside JSON, producing a double-entity encoding.
        bokeh_encoded = html.escape(html.escape(wrapped))
        matches = _RRD_URL_RE.findall(bokeh_encoded)
        self.assertEqual(matches, [("0.32.0", "job/foo.rrd"), ("0.32.0", "job/foo.rrd")])

    def test_does_not_match_outside_quotes(self):
        # A bare /rrd_static/... reference (not wrapped in &amp;quot;) should
        # not match — otherwise debug log lines could be mangled.
        bare = "see /rrd_static/viewer_0.32.0.html?url=/rrd_static/job/foo.rrd in logs"
        self.assertIsNone(_RRD_URL_RE.search(bare))


class TestInlineRrdIframes(unittest.TestCase):
    """End-to-end: build a fake saved HTML, run the post-processor, check rewrites."""

    def setUp(self):
        # Run inside a fresh tempdir so we can drop a fake cachedir/rrd/<job>/foo.rrd
        # without disturbing the real one.
        self._cwd_patch = mock.patch("os.getcwd")
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "cachedir" / "rrd" / "jobA").mkdir(parents=True)
        self.rrd_path = self.tmp / "cachedir" / "rrd" / "jobA" / "foo.rrd"
        self.rrd_path.write_bytes(b"fake rrd contents")

        # _RRD_CACHE_DIR.resolve() in utils_rrd anchors to cwd, so chdir.
        self._orig_cwd = Path.cwd()
        import os

        os.chdir(self.tmp)

    def tearDown(self):
        import os

        os.chdir(self._orig_cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build_saved_html(self, viewer_url: str) -> str:
        iframe = (
            f'<iframe src="{viewer_url}" width="400" height="400"'
            f' frameborder="0" allowfullscreen></iframe>'
        )
        wrapped = _wrap_viewer_controls(iframe, viewer_url, 400, 400)
        # Mimic the double-entity encoding Bokeh applies on save.
        return f"<html><body>{html.escape(html.escape(wrapped))}</body></html>"

    def test_rewrites_iframe_and_anchor_in_one_pass(self):
        viewer_url = "/rrd_static/viewer_0.32.0.html?url=/rrd_static/jobA/foo.rrd"
        report_dir = self.tmp / "report"
        report_dir.mkdir()
        html_path = report_dir / "index.html"
        html_path.write_text(self._build_saved_html(viewer_url), encoding="utf-8")

        inline_rrd_iframes(html_path)

        rewritten = html_path.read_text(encoding="utf-8")
        # No /rrd_static/ URLs should remain — both iframe src and anchor href
        # must be rewritten to the relative ``_rrd/...`` path.
        self.assertNotIn("/rrd_static/", rewritten)
        # The sidecar viewer + rrd should now exist next to the report.
        self.assertTrue((report_dir / "_rrd" / "viewer_0.32.0.html").is_file())
        self.assertTrue((report_dir / "_rrd" / "jobA" / "foo.rrd").is_file())
        # The relative path should appear twice — once for the iframe, once for
        # the anchor href.
        relative = "_rrd/viewer_0.32.0.html?url=jobA/foo.rrd"
        self.assertEqual(rewritten.count(relative), 2)

    def test_idempotent_per_recording(self):
        """Memoization avoids writing the sidecar files twice per recording."""
        viewer_url = "/rrd_static/viewer_0.32.0.html?url=/rrd_static/jobA/foo.rrd"
        report_dir = self.tmp / "report2"
        report_dir.mkdir()
        html_path = report_dir / "index.html"
        html_path.write_text(self._build_saved_html(viewer_url), encoding="utf-8")

        # The iframe src and anchor href both contain the same URL.  Patch
        # _write_rrd_sidecar to count invocations.
        # pylint: disable=protected-access
        import bencher.utils_rrd as mod

        original = mod._write_rrd_sidecar
        call_count = 0

        def counting(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return original(*args, **kwargs)

        with mock.patch.object(mod, "_write_rrd_sidecar", counting):
            inline_rrd_iframes(html_path)

        self.assertEqual(
            call_count,
            1,
            "_write_rrd_sidecar should run once per recording, not once per URL match",
        )

    def test_logs_warning_when_url_present_but_regex_misses(self):
        """If Bokeh's encoding changes, we want a visible warning, not silent success."""
        report_dir = self.tmp / "report3"
        report_dir.mkdir()
        html_path = report_dir / "index.html"
        # Mangled encoding: /rrd_static/ is present but not wrapped in the
        # expected double-entity quoting, so the regex misses.
        html_path.write_text(
            "<html><body>see /rrd_static/viewer_0.32.0.html in logs</body></html>",
            encoding="utf-8",
        )

        with self.assertLogs("root", level="WARNING") as captured:
            inline_rrd_iframes(html_path)

        joined = "\n".join(captured.output)
        self.assertIn("/rrd_static/", joined)
        self.assertIn("URL regex matched nothing", joined)


# --- Extra guards on the wrapper output ---


class TestWrapperOutputShape(unittest.TestCase):
    def test_wrapper_class_used_consistently(self):
        """The JS selectors look for ``.bencher-rrd-wrap`` — the wrapper must use it."""
        iframe = '<iframe src="X" width="1" height="2" frameborder="0" allowfullscreen></iframe>'
        out = _wrap_viewer_controls(iframe, "X", 1, 2)
        self.assertIn('class="bencher-rrd-wrap"', out)
        # The fullscreen onclick references the class — check the literal that
        # appears in the rendered HTML.
        self.assertIn(".bencher-rrd-wrap", out)

    def test_dimensions_propagate_to_wrapper(self):
        iframe = (
            '<iframe src="X" width="321" height="123" frameborder="0" allowfullscreen></iframe>'
        )
        out = _wrap_viewer_controls(iframe, "X", 321, 123)
        self.assertRegex(out, re.compile(r"width:321px;height:123px"))


if __name__ == "__main__":
    unittest.main()
