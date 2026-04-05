import unittest

import panel as pn

import bencher as bn
from bencher.example.meta.example_meta import BenchableObject


class TestExtraPanels(unittest.TestCase):
    """Tests for the extra_panels parameter in to_auto_plots."""

    def _make_result(self):
        bench = BenchableObject().to_bench()
        return bench.plot_sweep(
            "extra_panels_test",
            input_vars=[BenchableObject.param.float1],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=1, auto_plot=False),
            plot_callbacks=False,
        )

    def test_extra_panels_callable(self):
        """Callable extra panels are called with the BenchResult."""
        res = self._make_result()
        marker = pn.pane.Markdown("### Custom Panel")

        def my_panel(_bench_res):
            return marker

        plots = res.to_auto_plots(extra_panels=[my_panel])
        self.assertIn(marker, list(plots))

    def test_extra_panels_static(self):
        """Static panel objects are inserted directly."""
        res = self._make_result()
        marker = pn.pane.Markdown("### Static Panel")
        plots = res.to_auto_plots(extra_panels=[marker])
        self.assertIn(marker, list(plots))

    def test_extra_panels_none_is_default(self):
        """No extra panels by default — output matches original to_auto_plots."""
        res = self._make_result()
        default_plots = res.to_auto_plots()
        explicit_none = res.to_auto_plots(extra_panels=None)
        self.assertEqual(len(default_plots), len(explicit_none))

    def test_extra_panels_before_auto(self):
        """Extra panels appear after sweep summary but before auto plots."""
        res = self._make_result()
        marker = pn.pane.Markdown("### Injected")
        plots = list(res.to_auto_plots(extra_panels=[marker]))
        idx = plots.index(marker)
        # Should be after the sweep summary (index 0)
        self.assertGreater(idx, 0)
        # Should be before the last element (post_description)
        self.assertLess(idx, len(plots) - 1)

    def test_extra_panels_callable_error_is_caught(self):
        """A failing callable logs the error and does not crash to_auto_plots."""
        res = self._make_result()

        def bad_panel(_bench_res):
            raise RuntimeError("boom")

        # Should not raise; the error is logged and skipped.
        with self.assertLogs(level="ERROR") as cm:
            plots = res.to_auto_plots(extra_panels=[bad_panel])

        # The broken panel is omitted, but the rest of the output is still produced.
        self.assertGreater(len(plots), 0)
        # Verify the error was actually logged.
        self.assertTrue(any("bad_panel" in msg for msg in cm.output))

    def test_extra_panels_in_plot_callback(self):
        """extra_panels works when used inside a named plot_callbacks function."""
        res = self._make_result()
        marker = pn.pane.Markdown("### Callback Panel")

        rendered = res.to_auto_plots(extra_panels=[lambda r: marker])
        all_panes = list(rendered)
        found = any(_find_marker(p, marker) for p in all_panes)
        self.assertTrue(found, "Marker panel not found in rendered output")


def _find_marker(pane, marker):
    """Recursively check if marker is in a pane (which may be a Column)."""
    if pane is marker:
        return True
    if isinstance(pane, pn.Column):
        return any(_find_marker(child, marker) for child in pane)
    return False
