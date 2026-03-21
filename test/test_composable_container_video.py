import unittest
import bencher as bn
import numpy as np
from hypothesis import given, strategies as st


class TestComposableContainerVideo(unittest.TestCase):
    def small_img(self, size=None):
        if size is None:
            size = (2, 1)
        return np.ones((size[0], size[1], 3))
        # return np.array(
        #     [[[1, 1, 1]], [[0, 0, 0]]]
        # )  # represents an image of 1x2 (keep it small for speed)

    def small_video(self, num_frames: int = 2, render_cfg=None, size=None):
        img = self.small_img(size=size)
        vid = bn.ComposableContainerVideo()
        for _ in range(num_frames):
            vid.append(img)
        return vid.render(render_cfg)

    # @given(frames=st.sampled_from([1, 2, 10, 100]))
    # def test_duration_default(self, frames):
    #     ccv = bn.ComposableContainerVideo()
    #     duration, frame_duration = ccv.calculate_duration(frames, bn.RenderCfg())
    #     self.assertEqual(duration, 10)
    #     self.assertEqual(frame_duration, 10 / frames)

    @given(frames=st.sampled_from([1, 2, 10, 100]), duration=st.sampled_from([0.1, 1, 10, 100]))
    def test_set_duration(self, frames, duration):
        ccv = bn.ComposableContainerVideo()
        duration, frame_duration = ccv.calculate_duration(frames, bn.RenderCfg(duration=duration))
        self.assertEqual(duration, duration)
        self.assertEqual(frame_duration, duration / frames)

    @given(frames=st.sampled_from([1, 2, 10, 100]), duration=st.sampled_from([0.1, 1, 10, 100]))
    def test_set_duration1(self, frames, duration):
        ccv = bn.ComposableContainerVideo()
        min_frame_duration = 1 / 30
        max_frame_duration = 2.0
        duration, frame_duration = ccv.calculate_duration(
            frames,
            bn.RenderCfg(
                duration=duration,
                min_frame_duration=1 / 30,
                max_frame_duration=2,
                duration_target=True,
            ),
        )
        self.assertEqual(duration, duration)
        self.assertEqual(frame_duration, duration / frames)
        self.assertLessEqual(frame_duration, max_frame_duration)
        self.assertGreaterEqual(frame_duration, min_frame_duration)

    def test_img_right(self):
        res = self.small_video(1, bn.RenderCfg(duration=0.1, compose_method=bn.ComposeType.right))
        self.assertEqual(res.size, (1, 2))
        self.assertEqual(res.duration, 0.1)

    def test_img_down(self):
        res = self.small_video(1, bn.RenderCfg(duration=0.1, compose_method=bn.ComposeType.down))
        self.assertEqual(res.size, (1, 2))
        self.assertEqual(res.duration, 0.1)

    def test_img_sequence(self):
        res = self.small_video(
            1, bn.RenderCfg(duration=0.1, compose_method=bn.ComposeType.sequence)
        )
        self.assertEqual(res.size, (1, 2))
        self.assertEqual(res.duration, 0.1)

    def test_img_overlay(self):
        res = self.small_video(1, bn.RenderCfg(duration=0.1, compose_method=bn.ComposeType.overlay))
        self.assertEqual(res.size, (1, 2))
        self.assertEqual(res.duration, 0.1)

    def test_img_right_x2(self):
        res = self.small_video(2, bn.RenderCfg(compose_method=bn.ComposeType.right))
        self.assertEqual(res.size, (2, 2))
        self.assertEqual(res.duration, 2)

    def test_img_down_x2(self):
        res = self.small_video(2, bn.RenderCfg(compose_method=bn.ComposeType.down))
        self.assertEqual(res.size, (1, 4))
        self.assertEqual(res.duration, 2)

    def test_img_seq_x2(self):
        res = self.small_video(2, bn.RenderCfg(compose_method=bn.ComposeType.sequence))
        self.assertEqual(res.size, (1, 2))
        self.assertEqual(res.duration, 4)

    def test_img_overlay_x2(self):
        res = self.small_video(2, bn.RenderCfg(compose_method=bn.ComposeType.overlay))
        self.assertEqual(res.size, (1, 2))
        self.assertEqual(res.duration, 2)

    def test_1px_all_compose_types(self):
        """Test all compose types with a minimal 1x1 pixel image."""
        img = np.ones((1, 1, 3))
        for compose_type in bn.ComposeType:
            vid = bn.ComposableContainerVideo()
            vid.append(img)
            vid.append(img)
            res = vid.render(bn.RenderCfg(compose_method=compose_type, duration=0.1))
            self.assertIsNotNone(res)
            self.assertGreater(res.duration, 0)

    def test_1px_overlay_pixel_values(self):
        """Overlay of two 1x1 images should blend pixel values via opacity."""
        white = np.ones((1, 1, 3)) * 255
        black = np.zeros((1, 1, 3))
        vid = bn.ComposableContainerVideo()
        vid.append(white)
        vid.append(black)
        res = vid.render(bn.RenderCfg(compose_method=bn.ComposeType.overlay, duration=0.1))
        frame = res.get_frame(0)
        self.assertEqual(frame.shape[0], 1)
        self.assertEqual(frame.shape[1], 1)

    def test_1px_to_video(self):
        """to_video() should produce a file path from 1x1 pixel images."""
        import os

        img = np.ones((1, 1, 3))
        vid = bn.ComposableContainerVideo()
        vid.append(img)
        vid.append(img)
        for compose_type in bn.ComposeType:
            vid2 = bn.ComposableContainerVideo()
            vid2.append(img)
            vid2.append(img)
            path = vid2.to_video(bn.RenderCfg(compose_method=compose_type, duration=0.1))
            self.assertTrue(os.path.exists(path), f"Video file not created for {compose_type}")

    def test_video_seq(self):
        img = self.small_img()
        vid1 = bn.ComposableContainerVideo()
        vid1.append(img)
        vid1.append(img)

        res = vid1.deep().render(bn.RenderCfg(duration=0.1, compose_method=bn.ComposeType.sequence))

        self.assertEqual(res.size, (1, 2))
        self.assertEqual(res.duration, 0.1)  # two frames

        render_cfg = bn.RenderCfg(
            duration=10.0,
            duration_target=True,
            min_frame_duration=1.0 / 30,
            max_frame_duration=1.0,
        )

        res = vid1.deep().render(render_cfg)

        self.assertEqual(res.size, (1, 2))
        self.assertEqual(res.duration, 2.0)  # 2 frames of minimum frame time 1.0

        vid1.append(img)

        res = vid1.render(render_cfg)
        self.assertEqual(res.size, (1, 2))
        self.assertEqual(res.duration, 3.0)  # 3 frames of minimum frame time 1.0

    def test_concat_equal_video_len(self):
        render_cfg = bn.RenderCfg(duration_target=True)
        res1 = self.small_video(num_frames=2, render_cfg=render_cfg)
        res2 = self.small_video(num_frames=2, render_cfg=render_cfg)

        self.assertEqual(res1.size, (1, 2))
        self.assertEqual(res1.duration, 4.0)  # 2 frames of minimum frame time 2.0

        self.assertEqual(res2.size, (1, 2))
        self.assertEqual(res2.duration, 4.0)  # 1 frames of minimum frame time 2.0

        vid = bn.ComposableContainerVideo()

        vid.append(res1)
        vid.append(res2)

        res = vid.deep().render(bn.RenderCfg(bn.ComposeType.right))
        self.assertEqual(res.size, (2, 2))
        self.assertEqual(res.duration, 4.0)  # the duration of the longer clip

        res = vid.deep().render(bn.RenderCfg(bn.ComposeType.down))
        self.assertEqual(res.size, (1, 4))
        self.assertEqual(res.duration, 4.0)  # the duration of the longer clip

        res = vid.deep().render(bn.RenderCfg(bn.ComposeType.sequence))
        self.assertEqual(res.size, (1, 2))
        self.assertEqual(res.duration, 8.0)  # the duration of both clips

    def test_concat_unequal_video_len(self):
        render_cfg = bn.RenderCfg(duration_target=True)
        res1 = self.small_video(num_frames=2, render_cfg=render_cfg)
        self.assertEqual(res1.size, (1, 2))
        self.assertEqual(res1.duration, 4.0)  # 3 frames of minimum frame time 1.0

        res2 = self.small_video(num_frames=3, render_cfg=render_cfg)
        self.assertEqual(res2.size, (1, 2))
        self.assertEqual(res2.duration, 6.0)  # 3 frames of minimum frame time 1.0

        vid = bn.ComposableContainerVideo()

        vid.append(res1)
        vid.append(res2)

        res = vid.deep().render(bn.RenderCfg(bn.ComposeType.right))
        self.assertEqual(res.size, (2, 2))
        self.assertEqual(res.duration, 6.0)  # the duration of the longer clip

        res = vid.deep().render(bn.RenderCfg(bn.ComposeType.down))
        self.assertEqual(res.size, (1, 4))
        self.assertEqual(res.duration, 6.0)  # the duration of the longer clip

        res = vid.deep().render(bn.RenderCfg(bn.ComposeType.sequence))
        self.assertEqual(res.size, (1, 2))
        self.assertEqual(res.duration, 10.0)  # the duration of both clips

        res_label = vid.deep().render(bn.RenderCfg(bn.ComposeType.sequence))
        self.assertEqual(res.duration, res_label.duration)  # the duration of both clips

    def test_bad_filetype(self):
        vid = bn.ComposableContainerVideo()
        with self.assertRaises(RuntimeWarning):
            vid.append("bad.badextension")

    def test_simple_image_length(self):
        ccv = bn.ComposableContainerVideo()
        ccv.append(self.small_img())
        ccv.append(self.small_img())

        res = ccv.render()
        self.assertEqual(res.duration, 4.0)  # limited by maximum frame time

        ccv = bn.ComposableContainerVideo()
        for _ in range(20):
            ccv.append(self.small_img())

        self.assertEqual(ccv.render().duration, 10.0)  # limited by target video duration

        ccv = bn.ComposableContainerVideo()
        for _ in range(200):
            ccv.append(self.small_img())

        # still limited by target video duration
        self.assertAlmostEqual(ccv.render().duration, 10.0)

    def test_composite_image_length(self):
        ccv = bn.ComposableContainerVideo()

        for _ in range(2):
            sub_img = bn.ComposableContainerVideo()
            sub_img.append(self.small_img())
            sub_img.append(self.small_img())
            sub_img.append(self.small_img())
            ccv.append(sub_img.render(compose_method=bn.ComposeType.right))

        # should be 4 because there are two sequential frames
        self.assertEqual(ccv.render().duration, 4.0)

        ccv = bn.ComposableContainerVideo()

        for _ in range(5):
            sub_img = bn.ComposableContainerVideo()
            sub_img.append(self.small_img())
            sub_img.append(self.small_img())
            sub_img.append(self.small_img())
            ccv.append(sub_img.render(compose_method=bn.ComposeType.right))

        # should be 10 because of the default target length
        self.assertEqual(ccv.render().duration, 10.0)

    def test_video_lengths(self):
        ccv = bn.ComposableContainerVideo()
        ccv.append(self.small_video())
        ccv.append(self.small_video())

        res = ccv.render()
        self.assertEqual(res.duration, 8.0)  # no frame limits, just concat videos

        ccv = bn.ComposableContainerVideo()
        for _ in range(20):
            ccv.append(self.small_video())

        self.assertEqual(ccv.render().duration, 80.0)  # concatted vid time

        ccv = bn.ComposableContainerVideo()
        for _ in range(200):
            ccv.append(self.small_video())

        # still concatted vid time
        self.assertAlmostEqual(ccv.render().duration, 800.0)

    def test_render_no_stdout(self):
        """render() should not print debug output to stdout."""
        import io
        import contextlib

        img = self.small_img()
        vid = bn.ComposableContainerVideo()
        vid.append(img)
        vid.append(img)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            vid.render(bn.RenderCfg(duration=0.1, compose_method=bn.ComposeType.sequence))

        assert buf.getvalue() == "", f"Unexpected stdout: {buf.getvalue()!r}"


if __name__ == "__main__":
    tst = TestComposableContainerVideo()

    tst.test_img_right()

    unittest.main()
