"""Tests for bencher/results/video_controls.py"""

import os
import tempfile
import unittest
from pathlib import Path

import panel as pn

from bencher.results.video_controls import VideoControls


class TestVideoControls(unittest.TestCase):
    def test_init(self):
        vc = VideoControls()
        assert vc.vid_p == []

    def test_video_container_nonexistent(self):
        vc = VideoControls()
        result = vc.video_container("/nonexistent/path/video.mp4")
        assert isinstance(result, pn.pane.Markdown)
        assert "does not exist" in result.object

    def test_video_container_existing_file(self):
        vc = VideoControls()
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            result = vc.video_container(tmp_path)
            assert isinstance(result, pn.pane.Video)
            assert result in vc.vid_p
        finally:
            Path(tmp_path).unlink()

    def test_video_container_none_path(self):
        vc = VideoControls()
        result = vc.video_container(None)
        assert isinstance(result, pn.pane.Markdown)

    def test_video_controls(self):
        vc = VideoControls()
        result = vc.video_controls()
        assert isinstance(result, pn.Column)
        # Should have a Row of buttons
        assert len(result) > 0

    def _make_video(self, vc: VideoControls) -> pn.pane.Video:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name
        self.addCleanup(os.remove, tmp_path)
        vid = vc.video_container(tmp_path)
        assert isinstance(vid, pn.pane.Video)
        return vid

    def test_all_four_buttons_created_with_correct_labels(self):
        """Regression test: zip over a 2-element callback list used to truncate
        the button row to two buttons (and wired 'Pause Videos' to a callback
        that unpaused)."""
        vc = VideoControls()
        column = vc.video_controls()
        buttons = list(column[0])
        assert [b.label for b in buttons] == [
            "Play Videos",
            "Pause Videos",
            "Toggle Looping",
            "Reset Videos",
        ]
        for button in buttons:
            assert isinstance(button, pn.widgets.Button)

    def test_play_callback_unpauses(self):
        vc = VideoControls()
        vid = self._make_video(vc)
        vid.paused = True
        vc.play_videos()
        assert not vid.paused

    def test_pause_callback_pauses(self):
        vc = VideoControls()
        vid = self._make_video(vc)
        vid.paused = False
        vc.pause_videos()
        assert vid.paused

    def test_toggle_looping_flips_every_video_together(self):
        vc = VideoControls()
        vid = self._make_video(vc)
        assert vid.loop  # video_container starts videos looping
        vc.toggle_looping()
        assert not vid.loop
        vc.toggle_looping()
        assert vid.loop

    def test_toggle_looping_converges_on_mixed_state(self):
        """A per-pane toggle would invert each video independently and never
        converge; one shared flag drives them all to the same value."""
        vc = VideoControls()
        first = self._make_video(vc)
        second = self._make_video(vc)
        second.loop = False  # desynchronise, e.g. set by caller/kwargs
        vc.toggle_looping()
        assert first.loop == second.loop
        assert not first.loop
        vc.toggle_looping()
        assert first.loop == second.loop
        assert first.loop

    def test_reset_callback_sets_python_state_and_plays(self):
        """Asserts only the python-side state: the ``time`` write is a request
        panel's client-side ``set_time`` can swallow while playing (see
        ``VideoControls.reset_videos``), so this is not evidence of a browser
        rewind. Unpausing has no such guard and is reliable."""
        vc = VideoControls()
        vid = self._make_video(vc)
        vid.time = 12.5
        vid.paused = True
        vc.reset_videos()
        assert vid.time == 0
        assert not vid.paused

    def test_buttons_clicks_drive_the_matching_callback(self):
        """End-to-end: clicking each button changes the recorded video state."""
        vc = VideoControls()
        vid = self._make_video(vc)
        column = vc.video_controls()
        play, pause, loop, reset = list(column[0])

        pause.param.trigger("clicks")
        assert vid.paused
        play.param.trigger("clicks")
        assert not vid.paused
        loop.param.trigger("clicks")
        assert not vid.loop
        vid.time = 3.0
        vid.paused = True
        reset.param.trigger("clicks")
        assert vid.time == 0
        assert not vid.paused
