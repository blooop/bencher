"""Tests for bencher.sparkline."""

import pytest

from bencher.sparkline import DEFAULT_ACCENT, sparkline_svg


class TestSparkline:
    def test_responsive_svg_scales_to_container(self):
        # No fixed width/height attr + preserveAspectRatio="none" so CSS stretches
        # it to the full container width; non-scaling-stroke keeps the line crisp.
        svg = sparkline_svg([1.0, 2.0, 1.5], [0.1, 0.2, 0.1])
        assert 'preserveAspectRatio="none"' in svg
        assert "width=" not in svg.split(">", 1)[0]
        assert 'vector-effect="non-scaling-stroke"' in svg

    def test_multi_point_has_band_and_line(self):
        svg = sparkline_svg([1.0, 2.0, 1.5], [0.1, 0.2, 0.1])
        assert svg.startswith("<svg")
        assert "<polygon" in svg
        assert "<polyline" in svg
        # Latest-point marker is a round dot: a zero-length <line> with a round
        # cap (a <circle> would deform into an ellipse when stretched).
        assert "<line" in svg
        assert 'stroke-linecap="round"' in svg

    def test_single_point_has_marker_no_trend_line(self):
        svg = sparkline_svg([1.0], [0.0])
        assert "<line" in svg
        assert "<polyline" not in svg

    def test_all_missing_is_empty_svg(self):
        svg = sparkline_svg([None, None], [None, None])
        assert svg.startswith("<svg")
        assert "<line" not in svg

    def test_handles_none_std(self):
        # A finite mean with missing std must not raise and still plots a line.
        svg = sparkline_svg([1.0, 2.0, 1.5], [None, None, None])
        assert "<polyline" in svg

    def test_two_points_has_both_ticks(self):
        # Two finite points -> previous dot + latest dot on the polyline.
        svg = sparkline_svg([1.0, 2.0], [0.1, 0.1])
        assert "<polyline" in svg
        assert svg.count("<line") == 2

    def test_more_means_than_stds_keeps_all_points(self):
        # A short stds list must not silently truncate trailing means: all three
        # means are plotted, with the missing std treated as a zero-width band.
        svg = sparkline_svg([1.0, 2.0, 3.0], [0.1])
        assert "<polyline" in svg
        # prev + latest dots -> both markers present, so the last point survived.
        assert svg.count("<line") == 2

    def test_more_stds_than_means_ignores_surplus(self):
        # A surplus std with no matching mean is dropped rather than raising.
        svg = sparkline_svg([1.0, 2.0], [0.1, 0.1, 0.1, 0.1])
        assert "<polyline" in svg
        assert svg.count("<line") == 2

    @pytest.mark.parametrize("accent", ["#dc2626", "#16a34a", "#475569"])
    def test_latest_tick_uses_accent(self, accent):
        # The latest dot (rightmost <line>) is drawn in the caller's accent.
        svg = sparkline_svg([1.0, 2.0, 1.5], [0.1, 0.2, 0.1], accent=accent)
        assert f'stroke="{accent}"' in svg

    def test_previous_tick_is_slate_regardless_of_accent(self):
        # Previous dot stays slate; only the latest event carries the accent.
        svg = sparkline_svg([1.0, 2.0, 1.5], [0.1, 0.2, 0.1], accent="#dc2626")
        assert 'stroke="#475569"' in svg  # prev dot
        assert 'stroke="#dc2626"' in svg  # latest dot

    def test_default_accent_when_none(self):
        # No accent -> neutral near-black latest dot.
        svg = sparkline_svg([1.0, 2.0, 1.5], [0.1, 0.2, 0.1])
        assert f'stroke="{DEFAULT_ACCENT}"' in svg
