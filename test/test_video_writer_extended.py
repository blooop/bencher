"""Tests for bencher/video_writer.py — extended coverage."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from bencher.video_writer import VideoWriter


class TestVideoWriterCreateLabel(unittest.TestCase):
    def test_create_label_default_width(self):
        img = VideoWriter.create_label("hello")
        assert isinstance(img, Image.Image)
        assert img.size[0] == len("hello") * 10
        assert img.size[1] == 16

    def test_create_label_custom_size(self):
        img = VideoWriter.create_label("test", width=200, height=32)
        assert isinstance(img, Image.Image)
        assert img.size == (200, 32)


class TestVideoWriterLabelImage(unittest.TestCase):
    def test_label_image(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a simple test image
            img = Image.new("RGB", (100, 80), color=(0, 255, 0))
            path = Path(tmpdir) / "test_img.png"
            img.save(path)

            result = VideoWriter.label_image(path, "Test Label")
            assert isinstance(result, Image.Image)
            # Height should be original height + padding (default=20)
            assert result.size[0] == 100
            assert result.size[1] == 80 + 20


class TestVideoWriterConvertAndExtract(unittest.TestCase):
    def _create_test_video(self, tmpdir):
        """Create a simple test video with solid frames."""
        vw = VideoWriter("test_vid")
        video_path = Path(tmpdir) / "test_video.mp4"
        vw.filename = str(video_path)
        # Create 10 frames of solid colors
        for i in range(10):
            frame = np.full((64, 64, 3), fill_value=i * 25, dtype=np.uint8)
            vw.append(frame)
        vw.write()
        return str(video_path)

    def test_write_and_extract_frame(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = self._create_test_video(tmpdir)
            assert Path(video_path).exists()

            # Extract a frame
            output = VideoWriter.extract_frame(video_path, time=0.0)
            assert Path(output).exists()
            assert output.endswith(".png")

    def test_extract_frame_default_time(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = self._create_test_video(tmpdir)

            # Extract frame with default time (last frame)
            output = VideoWriter.extract_frame(video_path)
            assert Path(output).exists()

    def test_extract_frame_custom_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = self._create_test_video(tmpdir)
            output_path = Path(tmpdir) / "custom_frame.png"

            output = VideoWriter.extract_frame(video_path, time=0.0, output_path=str(output_path))
            assert output == output_path.as_posix()
            assert output_path.exists()

    def test_extract_frame_nonexistent_source(self):
        with pytest.raises(OSError):
            VideoWriter.extract_frame("/nonexistent/path/video.mp4", time=0.0)

    def test_convert_to_compatible_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = self._create_test_video(tmpdir)
            new_path = VideoWriter.convert_to_compatible_format(video_path)
            assert Path(new_path).exists()
            assert "_fixed" in new_path
