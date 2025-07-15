import numpy as np
import moviepy.video.io.ImageSequenceClip
import moviepy.video.io.VideoFileClip
from pathlib import Path
from .utils import gen_video_path, gen_image_path
from PIL import Image, ImageDraw


class VideoWriter:
    def __init__(self, filename: str = "vid") -> None:
        self.images = []
        self.image_files = []
        self.video_files = []
        self.filename = gen_video_path(filename)

    def append(self, img):
        self.images.append(img)

    def write(self) -> str:
        if len(self.images) > 0:
            clip = moviepy.video.io.ImageSequenceClip.ImageSequenceClip(
                self.images, fps=30, with_mask=False, load_images=True
            )
            self.write_video_raw(clip)
        return self.filename

    @staticmethod
    def create_label(label, width=None, height=16, color=(255, 255, 255)):
        if width is None:
            width = len(label) * 10
        new_img = Image.new("RGB", (width, height), color=color)
        # ImageDraw.Draw(new_img).text((width/2, 0), label, (0, 0, 0),align="center",anchor="ms")
        ImageDraw.Draw(new_img).text(
            (width / 2.0, 0), label, (0, 0, 0), anchor="mt", font_size=height
        )

        return new_img

    @staticmethod
    def label_image(path: Path, label, padding=20, color=(255, 255, 255)) -> Path:
        image = Image.open(path)
        new_img = VideoWriter.create_label(
            label, image.size[0], image.size[1] + padding, color=color
        )
        new_img.paste(image, (0, padding))
        return new_img

    @staticmethod
    def convert_to_compatible_format(video_path: str) -> str:
        new_path = Path(video_path)
        new_path = new_path.with_name(f"{new_path.stem}_fixed{new_path.suffix}").as_posix()
        vw = VideoWriter()
        vw.filename = new_path
        with moviepy.video.io.VideoFileClip.VideoFileClip(video_path) as vid:
            vw.write_video_raw(vid)
        return new_path

    def write_video_raw(self, video_clip: moviepy.video.VideoClip, fps: int = 30) -> str:
        video_clip.write_videofile(
            self.filename,
            codec="libx264",
            audio=False,
            bitrate="0",
            fps=fps,
            ffmpeg_params=["-crf", "23"],
            threads=8,
        )
        video_clip.close()
        return self.filename

    @staticmethod
    def extract_frame(video_path: str, time: float = None, output_path: str = None) -> str:
        """Extract a frame from a video at a specific time.

        Args:
            video_path: Path to the video file
            time: Time in seconds to extract frame. If None, uses last frame
            output_path: Optional path where to save the image. If None, uses video name with _frame.png

        Returns:
            str: Path to the saved PNG image
        """
        if output_path is None:
            output_path = (
                Path(video_path).with_stem(f"{Path(video_path).stem}_frame").with_suffix(".png")
            )
        else:
            output_path = Path(output_path)

        with moviepy.video.io.VideoFileClip.VideoFileClip(video_path) as video:
            frame_time = time if time is not None else video.duration - 2.0 / video.fps
            frame_time = max(frame_time, 0)
            frame = video.get_frame(frame_time)
            Image.fromarray(frame).save(output_path)

        return output_path.as_posix()


def add_image(np_array: np.ndarray, name: str = "img") -> str:
    """Creates a file on disk from a numpy array and returns the created image path"""
    filename = gen_image_path(name)
    Image.fromarray(np_array).save(filename)
    return filename
