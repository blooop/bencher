from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import panel as pn


class VideoControls:
    def __init__(self) -> None:
        self.vid_p: list[pn.pane.Video] = []
        # One shared flag rather than per-pane state: a per-pane toggle would
        # invert each video independently and never converge once they differ.
        self.loop_enabled: bool = True

    def video_container(self, path, **kwargs):
        if path is not None and Path(path).exists():
            vid = pn.pane.Video(path, autoplay=True, **kwargs)
            vid.loop = self.loop_enabled
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

    def toggle_looping(self, _event=None) -> None:
        """Flip looping on/off for every registered video, together.

        Videos start looping (:meth:`video_container`), so the first press turns
        looping *off* — hence the button reads "Toggle Looping" rather than
        "Loop Videos", which would have described the opposite of what a first
        click does.
        """
        self.loop_enabled = not self.loop_enabled
        for vid in self.vid_p:
            vid.loop = self.loop_enabled

    def reset_videos(self, _event=None) -> None:
        """Request a rewind to the start of every registered video, and play it.

        Unpausing is reliable. The rewind is a *request*: panel's client-side
        ``Video`` model (``panel/models/video.ts``) arms a ``_blocked`` flag on
        every throttled ``ontimeupdate`` and its ``set_time`` handler clears that
        flag and returns **without seeking**, so a ``time`` write that lands
        while the video is playing can be swallowed in the browser. Bokeh also
        only transmits *changed* properties, so writing ``0`` over an existing
        ``0`` sends nothing. The python-side state below is always updated.
        """
        for vid in self.vid_p:
            vid.time = 0
            vid.paused = False

    def video_controls(self) -> pn.Column:
        button_specs: list[tuple[str, Callable]] = [
            ("Play Videos", self.play_videos),
            ("Pause Videos", self.pause_videos),
            ("Toggle Looping", self.toggle_looping),
            ("Reset Videos", self.reset_videos),
        ]

        buttons = pn.Row()
        for name, cb in button_specs:
            button = pn.widgets.Button(label=name)
            button.on_click(cb)
            buttons.append(button)

        return pn.Column(buttons)
