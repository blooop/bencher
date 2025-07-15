from __future__ import annotations
import numpy as np
from copy import deepcopy
from pathlib import Path
from dataclasses import dataclass
from moviepy import (
    ImageClip,
    CompositeVideoClip,
    clips_array,
    concatenate_videoclips,
    VideoClip,
    VideoFileClip,
)

from bencher.results.composable_container.composable_container_base import (
    ComposableContainerBase,
    ComposeType,
)
from bencher.video_writer import VideoWriter
from moviepy import vfx


@dataclass()
class RenderCfg:
    """Configuration class for video rendering options.

    This class controls how videos and images are composed and rendered together.
    It provides options for timing, layout, appearance, and labeling of the output.

    Attributes:
        compose_method (ComposeType): Method to compose multiple clips (sequence, right, down, overlay).
            Defaults to ComposeType.sequence.
        var_name (str, optional): Variable name for labeling. Defaults to None.
        var_value (str, optional): Variable value for labeling. Defaults to None.
        background_col (tuple[int, int, int]): RGB color for background. Defaults to white (255, 255, 255).
        duration (float): Target duration for the composed video in seconds. Defaults to 10.0.
        default_duration (float): Fallback duration when duration is None. Defaults to 10.0.
        duration_target (bool): If True, tries to match target duration while respecting frame
            duration constraints. If False, uses exact duration. Defaults to True.
        min_frame_duration (float): Minimum duration for each frame in seconds. Defaults to 1/30.
        max_frame_duration (float): Maximum duration for each frame in seconds. Defaults to 2.0.
        margin (int): Margin size in pixels to add around clips. Defaults to 0.
    """

    compose_method: ComposeType = ComposeType.sequence
    var_name: str = None
    var_value: str = None
    background_col: tuple[int, int, int] = (255, 255, 255)
    duration: float = 10.0
    default_duration: float = 10.0
    duration_target: bool = True
    min_frame_duration: float = 1.0 / 30
    max_frame_duration: float = 2.0
    margin: int = 0


@dataclass
class ComposableContainerVideo(ComposableContainerBase):
    def append(self, obj: VideoClip | ImageClip | str | np.ndarray) -> None:
        """Appends an image or video to the container

        Args:
            obj (VideoClip | ImageClip | str | np.ndarray): Any representation of an image or video

        Raises:
            RuntimeWarning: if file format is not recognised
        """

        # print(f"append obj: {type(obj)}, {obj}")
        if obj is not None:
            if isinstance(obj, VideoClip):
                self.container.append(obj)
            elif isinstance(obj, ComposableContainerVideo):
                self.container.append(obj.render())
            elif isinstance(obj, np.ndarray):
                self.container.append(ImageClip(obj))
            else:
                path = Path(obj)
                extension = str.lower(path.suffix)
                if extension in [".jpg", ".jepg", ".png"]:
                    self.container.append(ImageClip(obj))
                elif extension in [".mpeg", ".mpg", ".mp4", ".webm"]:
                    # print(obj)
                    self.container.append(VideoFileClip(obj))
                else:
                    raise RuntimeWarning(f"unsupported filetype {extension}")
        else:
            raise RuntimeWarning("No data passed to ComposableContainerVideo.append()")

    def calculate_duration(self, frames, render_cfg: RenderCfg):
        if render_cfg.duration_target:
            # calculate duration based on fps constraints
            duration = (
                render_cfg.default_duration if render_cfg.duration is None else render_cfg.duration
            )
            frame_duration = duration / frames
            if render_cfg.min_frame_duration is not None:
                frame_duration = max(frame_duration, render_cfg.min_frame_duration)
            if render_cfg.max_frame_duration is not None:
                frame_duration = min(frame_duration, render_cfg.max_frame_duration)
            duration = frame_duration * frames
        else:
            if render_cfg.duration is None:
                duration = render_cfg.default_duration
            else:
                duration = render_cfg.duration
            frame_duration = duration / float(frames)

        print("max_frame_duration", render_cfg.max_frame_duration)
        print("DURATION", duration)

        return duration, frame_duration

    def render(self, render_cfg: RenderCfg = None, **kwargs) -> CompositeVideoClip:
        """Composes the images/videos into a single image/video based on the type of compose method

        Args:
            compose_method (ComposeType, optional): optionally override the default compose type. Defaults to None.

        Returns:
            CompositeVideoClip: A composite video clip containing the images/videos added via append()
        """
        if render_cfg is None:
            render_cfg = RenderCfg(**kwargs)

        print("rc", render_cfg)
        _, frame_duration = self.calculate_duration(float(len(self.container)), render_cfg)
        out = None
        print(f"using compose type: {render_cfg.compose_method}")
        max_duration = 0.0

        for i in range(len(self.container)):
            if self.container[i].duration is None:
                self.container[i].duration = frame_duration
            max_duration = max(max_duration, self.container[i].duration)
        match render_cfg.compose_method:
            case ComposeType.right | ComposeType.down:
                for i in range(len(self.container)):
                    self.container[i] = self.extend_clip(self.container[i], max_duration)
                    self.container[i] = self.container[i].with_effects(
                        [vfx.Margin(top=render_cfg.margin, color=render_cfg.background_col)]
                    )

                if render_cfg.compose_method == ComposeType.right:
                    clips = [self.container]
                else:
                    clips = [[c] for c in self.container]
                out = clips_array(clips, bg_color=render_cfg.background_col)
                if out.duration is None:
                    out.duration = max_duration
            case ComposeType.sequence:
                out = concatenate_videoclips(
                    self.container, bg_color=render_cfg.background_col, method="compose"
                )
            case ComposeType.overlay:
                for i in range(len(self.container)):
                    self.container[i] = self.container[i].with_opacity(1.0 / len(self.container))
                out = CompositeVideoClip(self.container, bg_color=render_cfg.background_col)
            case _:
                raise RuntimeError(
                    f"This compose type is not supported: {render_cfg.compose_method}"
                )

        label = self.label_formatter(render_cfg.var_name, render_cfg.var_value)
        if label is not None:
            # print("adding label")
            label = ImageClip(
                np.array(VideoWriter.create_label(label, color=render_cfg.background_col))
            )
            label.duration = out.duration
            label_compose = ComposeType.down
            if render_cfg.compose_method == ComposeType.down:
                label_compose = ComposeType.right
            con2 = ComposableContainerVideo()
            con2.append(label)
            con2.append(out)
            return con2.render(
                RenderCfg(
                    background_col=render_cfg.background_col,
                    compose_method=label_compose,
                    duration=out.duration,
                    duration_target=False,  # want exact duration
                )
            )
        return out

    def to_video(
        self,
        render_args: RenderCfg = None,
    ) -> str:
        """Returns the composite video clip as a webm file path

        Returns:
            str: webm filepath
        """
        return VideoWriter().write_video_raw(self.render(render_args))

    def deep(self):
        return deepcopy(self)

    def extend_clip(self, clip: VideoClip, desired_duration: float):
        if clip.duration < desired_duration:
            return concatenate_videoclips(
                [
                    clip,
                    ImageClip(
                        clip.get_frame(clip.duration), duration=desired_duration - clip.duration
                    ),
                ]
            )
        return clip
