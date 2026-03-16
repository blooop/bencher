"""Tests for bencher/results/video_controls.py"""

import unittest

import panel as pn

from bencher.results.video_controls import VideoControls


class TestVideoControls(unittest.TestCase):
    def test_init(self):
        vc = VideoControls()
        self.assertEqual(vc.vid_p, [])

    def test_video_container_nonexistent(self):
        vc = VideoControls()
        result = vc.video_container("/nonexistent/path/video.mp4")
        self.assertIsInstance(result, pn.pane.Markdown)
        self.assertIn("does not exist", result.object)

    def test_video_container_none_path(self):
        vc = VideoControls()
        result = vc.video_container(None)
        self.assertIsInstance(result, pn.pane.Markdown)

    def test_video_controls(self):
        vc = VideoControls()
        result = vc.video_controls()
        self.assertIsInstance(result, pn.Column)
        # Should have a Row of buttons
        self.assertTrue(len(result) > 0)
