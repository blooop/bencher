"""Tests for bencher/results/video_controls.py"""

import os
import tempfile
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

    def test_video_container_existing_file(self):
        vc = VideoControls()
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            result = vc.video_container(tmp_path)
            self.assertIsInstance(result, pn.pane.Video)
            self.assertIn(result, vc.vid_p)
        finally:
            os.remove(tmp_path)

    def test_video_container_none_path(self):
        vc = VideoControls()
        result = vc.video_container(None)
        self.assertIsInstance(result, pn.pane.Markdown)

    def test_video_controls(self):
        vc = VideoControls()
        result = vc.video_controls()
        self.assertIsInstance(result, pn.Column)
        # Should have a Row of buttons
        self.assertGreater(len(result), 0)

    def _make_video(self, vc: VideoControls) -> pn.pane.Video:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name
        self.addCleanup(os.remove, tmp_path)
        vid = vc.video_container(tmp_path)
        self.assertIsInstance(vid, pn.pane.Video)
        return vid

    def test_all_four_buttons_created_with_correct_labels(self):
        """Regression test: zip over a 2-element callback list used to truncate
        the button row to two buttons (and wired 'Pause Videos' to a callback
        that unpaused)."""
        vc = VideoControls()
        column = vc.video_controls()
        buttons = list(column[0])
        self.assertEqual(
            [b.label for b in buttons],
            ["Play Videos", "Pause Videos", "Loop Videos", "Reset Videos"],
        )
        for button in buttons:
            self.assertIsInstance(button, pn.widgets.Button)

    def test_play_callback_unpauses(self):
        vc = VideoControls()
        vid = self._make_video(vc)
        vid.paused = True
        vc.play_videos()
        self.assertFalse(vid.paused)

    def test_pause_callback_pauses(self):
        vc = VideoControls()
        vid = self._make_video(vc)
        vid.paused = False
        vc.pause_videos()
        self.assertTrue(vid.paused)

    def test_loop_callback_toggles(self):
        vc = VideoControls()
        vid = self._make_video(vc)
        self.assertTrue(vid.loop)  # video_container turns looping on
        vc.loop_videos()
        self.assertFalse(vid.loop)
        vc.loop_videos()
        self.assertTrue(vid.loop)

    def test_reset_callback_rewinds_and_plays(self):
        vc = VideoControls()
        vid = self._make_video(vc)
        vid.time = 12.5
        vid.paused = True
        vc.reset_videos()
        self.assertEqual(vid.time, 0)
        self.assertFalse(vid.paused)

    def test_buttons_clicks_drive_the_matching_callback(self):
        """End-to-end: clicking each button changes the recorded video state."""
        vc = VideoControls()
        vid = self._make_video(vc)
        column = vc.video_controls()
        play, pause, loop, reset = list(column[0])

        pause.param.trigger("clicks")
        self.assertTrue(vid.paused)
        play.param.trigger("clicks")
        self.assertFalse(vid.paused)
        loop.param.trigger("clicks")
        self.assertFalse(vid.loop)
        vid.time = 3.0
        vid.paused = True
        reset.param.trigger("clicks")
        self.assertEqual(vid.time, 0)
        self.assertFalse(vid.paused)
