"""Tests for bencher.sparkline."""

from bencher.sparkline import sparkline_svg


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
        # Per-run nodes are round dots: zero-length <line>s with a round cap (a
        # <circle> would deform into an ellipse when stretched).
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

    def test_line_has_one_node_per_run(self):
        # One small node marks each event on the line; the right-margin
        # distribution column adds its own dots after, so count only the nodes
        # before that column.
        svg = sparkline_svg([1.0, 2.0], [0.1, 0.1])
        assert "<polyline" in svg
        on_line = svg.split('<g class="dist"')[0]
        assert on_line.count("<line") == 2

    def test_more_means_than_stds_keeps_all_points(self):
        # A short stds list must not silently truncate trailing means: all three
        # means are plotted (missing std -> zero-width band), so three nodes sit
        # on the line before the distribution column.
        svg = sparkline_svg([1.0, 2.0, 3.0], [0.1])
        assert "<polyline" in svg
        on_line = svg.split('<g class="dist"')[0]
        assert on_line.count("<line") == 3

    def test_more_stds_than_means_ignores_surplus(self):
        # A surplus std with no matching mean is dropped rather than raising; only
        # the two real points are plotted.
        svg = sparkline_svg([1.0, 2.0], [0.1, 0.1, 0.1, 0.1])
        assert "<polyline" in svg
        on_line = svg.split('<g class="dist"')[0]
        assert on_line.count("<line") == 2

    def test_multi_point_has_distribution_column(self):
        # >1 point -> a right-margin column with one faint alpha dot per run and
        # nothing else (no mean tick, no specially-drawn latest dot).
        svg = sparkline_svg([1.0, 2.0, 1.5, 1.8], [0.1, 0.1, 0.1, 0.1])
        assert 'class="dist"' in svg
        assert 'stroke-opacity="0.32"' in svg  # faint density dots
        col = svg.split('class="dist"', 1)[1]
        assert col.count("<line") == 4

    def test_single_point_has_no_distribution_column(self):
        # One run has no spread to show; keep just the single node marker.
        svg = sparkline_svg([1.0], [0.1])
        assert 'class="dist"' not in svg

    def test_sparkline_is_uncolored(self):
        # Nodes and distribution dots are uniform; the cell background carries
        # the regression verdict, so the SVG emits no verdict color and no
        # oversized latest-dot stroke.
        svg = sparkline_svg([1.0, 2.0, 1.5], [0.1, 0.2, 0.1])
        assert "#dc2626" not in svg  # regressed red
        assert "#16a34a" not in svg  # improved green
        assert 'stroke-width="5"' not in svg and 'stroke-width="6"' not in svg
