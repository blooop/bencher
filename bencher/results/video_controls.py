from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import panel as pn


class VideoControls:
    def __init__(self) -> None:
        self.vid_p: list[pn.pane.Video] = []

    def video_container(self, path, **kwargs):
        if path is not None and Path(path).exists():
            vid = pn.pane.Video(path, autoplay=True, **kwargs)
            vid.loop = True
            self.vid_p.append(vid)
            return vid
        return pn.pane.Markdown(f"video does not exist {path}")

    def play_videos(self, _event=None) -> None:
        """Unpause every registered video."""
        for vid in self.vid_p:
            vid.paused = False

    def pause_videos(self, _event=None) -> None:
        """Pause every registered video."""
        for vid in self.vid_p:
            vid.paused = True

    def loop_videos(self, _event=None) -> None:
        """Toggle looping on every registered video."""
        for vid in self.vid_p:
            vid.loop = not vid.loop

    def reset_videos(self, _event=None) -> None:
        """Rewind every registered video to the start and play it."""
        for vid in self.vid_p:
            vid.time = 0
            vid.paused = False

    def video_controls(self) -> pn.Column:
        button_specs: list[tuple[str, Callable]] = [
            ("Play Videos", self.play_videos),
            ("Pause Videos", self.pause_videos),
            ("Loop Videos", self.loop_videos),
            ("Reset Videos", self.reset_videos),
        ]

        buttons = pn.Row()
        for name, cb in button_specs:
            button = pn.widgets.Button(label=name)
            button.on_click(cb)
            buttons.append(button)

        return pn.Column(buttons)
