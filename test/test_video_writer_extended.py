"""Tests for bencher/video_writer.py — extended coverage."""

import unittest
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from bencher.video_writer import VideoWriter


class TestVideoWriterCreateLabel(unittest.TestCase):
    def test_create_label_default_width(self):
        img = VideoWriter.create_label("hello")
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size[0], len("hello") * 10)
        self.assertEqual(img.size[1], 16)

    def test_create_label_custom_size(self):
        img = VideoWriter.create_label("test", width=200, height=32)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size, (200, 32))


class TestVideoWriterLabelImage(unittest.TestCase):
    def test_label_image(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a simple test image
            img = Image.new("RGB", (100, 80), color=(0, 255, 0))
            path = Path(tmpdir) / "test_img.png"
            img.save(path)

            result = VideoWriter.label_image(path, "Test Label")
            self.assertIsInstance(result, Image.Image)
            # Height should be original height + padding (default=20)
            self.assertEqual(result.size[0], 100)
            self.assertEqual(result.size[1], 80 + 20)


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
            self.assertTrue(Path(video_path).exists())

            # Extract a frame
            output = VideoWriter.extract_frame(video_path, time=0.0)
            self.assertTrue(Path(output).exists())
            self.assertTrue(output.endswith(".png"))

    def test_extract_frame_default_time(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = self._create_test_video(tmpdir)

            # Extract frame with default time (last frame)
            output = VideoWriter.extract_frame(video_path)
            self.assertTrue(Path(output).exists())

    def test_extract_frame_custom_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = self._create_test_video(tmpdir)
            output_path = Path(tmpdir) / "custom_frame.png"

            output = VideoWriter.extract_frame(video_path, time=0.0, output_path=str(output_path))
            self.assertEqual(output, output_path.as_posix())
            self.assertTrue(output_path.exists())

    def test_convert_to_compatible_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = self._create_test_video(tmpdir)
            new_path = VideoWriter.convert_to_compatible_format(video_path)
            self.assertTrue(Path(new_path).exists())
            self.assertIn("_fixed", new_path)
