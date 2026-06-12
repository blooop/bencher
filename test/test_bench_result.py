"""Tests for BenchResult container behavior (bencher/results/bench_result.py)."""

import unittest

import numpy as np
import panel as pn

import bencher as bn
from bencher.results.bench_result import BenchResult
from bencher.results.holoview_results.line_result import LineResult


class Linear(bn.ParametrizedSweep):
    """Minimal 1-float-input sweep with a deterministic worker (value = 2 * x)."""

    x = bn.FloatSweep(default=0, bounds=[0, 2], samples=3)
    value = bn.ResultFloat(units="m")

    def benchmark(self):
        self.value = self.x * 2.0


class LinearWithNan(bn.ParametrizedSweep):
    """Same as Linear but returns NaN for the midpoint (x == 1)."""

    x = bn.FloatSweep(default=0, bounds=[0, 2], samples=3)
    value = bn.ResultFloat(units="m")

    def benchmark(self):
        self.value = float("nan") if self.x == 1.0 else self.x * 2.0


def run_sweep(sweep_cls=Linear) -> BenchResult:
    """Run the smallest possible sweep (1 input var, 3 samples, repeats=1, no plots)."""
    bench = bn.Bench("test_bench_result", sweep_cls())
    return bench.plot_sweep(
        "sweep",
        input_vars=["x"],
        result_vars=["value"],
        run_cfg=bn.BenchRunCfg(repeats=1, cache_results=False, cache_samples=False),
        auto_plot=False,
    )


def collect_hv_elements(panel_obj) -> list:
    """Recursively collect holoviews elements from a Panel layout."""
    elements = []
    if hasattr(panel_obj, "opts") and hasattr(panel_obj, "kdims"):
        elements.append(panel_obj)
    elif hasattr(panel_obj, "object") and hasattr(panel_obj.object, "opts"):
        elements.append(panel_obj.object)
    elif hasattr(panel_obj, "__iter__"):
        for child in panel_obj:
            elements.extend(collect_hv_elements(child))
    return elements


def _failing_cb(self, **kwargs):  # pylint: disable=unused-argument
    raise RuntimeError("intentional test failure")


def _marker_cb_a(self, **kwargs):  # pylint: disable=unused-argument
    return pn.pane.Markdown("marker_a")


def _marker_cb_b(self, **kwargs):  # pylint: disable=unused-argument
    return pn.pane.Markdown("marker_b")


class TestBenchResultTo(unittest.TestCase):
    """Tests for the BenchResult.to(result_type) conversion path."""

    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep()

    def test_to_line_result_returns_viewable(self):
        plot = self.res.to(LineResult)
        self.assertIsNotNone(plot)
        self.assertIsInstance(plot, pn.viewable.Viewable)

    def test_to_line_result_plots_worker_values(self):
        plot = self.res.to(LineResult)
        elements = collect_hv_elements(plot)
        self.assertGreater(len(elements), 0, "Expected at least one holoviews element")
        df = elements[0].dframe()
        self.assertIn("x", df.columns)
        self.assertIn("value", df.columns)
        df = df.sort_values("x")
        np.testing.assert_allclose(df["x"].to_numpy(), [0.0, 1.0, 2.0])
        np.testing.assert_allclose(df["value"].to_numpy(), [0.0, 2.0, 4.0])

    def test_to_does_not_mutate_source(self):
        ds_before = self.res.ds
        self.res.to(LineResult)
        self.assertIs(self.res.ds, ds_before)


class TestBenchResultToAuto(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep()

    def test_to_auto_explicit_plot_list(self):
        panes = self.res.to_auto(plot_list=[LineResult.to_plot])
        self.assertIsInstance(panes, pn.Column)
        self.assertEqual(len(panes), 1)
        self.assertGreater(len(collect_hv_elements(panes)), 0)

    def test_to_auto_remove_plots(self):
        both = self.res.to_auto(plot_list=[_marker_cb_a, _marker_cb_b])
        self.assertEqual([p.object for p in both], ["marker_a", "marker_b"])
        removed = self.res.to_auto(
            plot_list=[_marker_cb_a, _marker_cb_b],
            remove_plots=[_marker_cb_b],
        )
        self.assertEqual([p.object for p in removed], ["marker_a"])

    def test_to_auto_all_removed_returns_placeholder(self):
        panes = self.res.to_auto(plot_list=[LineResult.to_plot], remove_plots=[LineResult.to_plot])
        self.assertEqual(len(panes), 1)
        self.assertIsInstance(panes[0], pn.pane.Markdown)
        self.assertIn("No Plotters are able to represent these results", panes[0].object)

    def test_to_auto_failing_callback_logged_not_raised(self):
        with self.assertLogs(level="ERROR") as captured:
            panes = self.res.to_auto(plot_list=[_failing_cb, LineResult.to_plot])
        self.assertTrue(any("_failing_cb" in msg for msg in captured.output))
        # The failing callback is skipped but the working one still renders.
        self.assertEqual(len(panes), 1)
        self.assertGreater(len(collect_hv_elements(panes)), 0)


class TestBenchResultToAutoPlots(unittest.TestCase):
    def test_to_auto_plots_first_entry_is_sweep_summary(self):
        res = run_sweep()
        col = res.to_auto_plots()
        self.assertIsInstance(col, pn.Column)
        self.assertGreaterEqual(len(col), 2)
        self.assertEqual(col[0].name, "Plots View")


class TestBenchResultPlot(unittest.TestCase):
    def test_plot_none_callbacks_returns_none(self):
        res = run_sweep()
        res.bench_cfg.plot_callbacks = None
        self.assertIsNone(res.plot())

    def test_plot_empty_callbacks_returns_empty_column(self):
        res = run_sweep()
        res.bench_cfg.plot_callbacks = []
        out = res.plot()
        self.assertIsInstance(out, pn.Column)
        self.assertEqual(len(out), 0)

    def test_plot_list_callbacks_one_entry_each(self):
        res = run_sweep()
        res.bench_cfg.plot_callbacks = [
            lambda r: pn.pane.Markdown("first"),
            lambda r: pn.pane.Markdown("second"),
        ]
        out = res.plot()
        self.assertIsInstance(out, pn.Column)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0].object, "first")
        self.assertEqual(out[1].object, "second")

    def test_plot_callbacks_receive_result_instance(self):
        res = run_sweep()
        seen = []
        res.bench_cfg.plot_callbacks = [lambda r: seen.append(r) or pn.pane.Markdown("cb")]
        res.plot()
        self.assertEqual(seen, [res])


class TestDefaultPlotCallbacks(unittest.TestCase):
    def test_default_plot_callbacks_non_empty(self):
        callbacks = BenchResult.default_plot_callbacks()
        self.assertIsInstance(callbacks, list)
        self.assertGreater(len(callbacks), 0)
        self.assertTrue(all(callable(cb) for cb in callbacks))
        self.assertIn(LineResult.to_plot, callbacks)


class TestFromExisting(unittest.TestCase):
    def test_from_existing_copies_state(self):
        res = run_sweep()
        clone = BenchResult.from_existing(res)
        self.assertIsNot(clone, res)
        self.assertIsInstance(clone, BenchResult)
        self.assertIs(clone.ds, res.ds)
        self.assertIs(clone.bench_cfg, res.bench_cfg)
        self.assertIs(clone.plt_cnt_cfg, res.plt_cnt_cfg)
        self.assertIs(clone.regression_report, res.regression_report)

    def test_from_existing_produces_same_dataset(self):
        res = run_sweep()
        clone = BenchResult.from_existing(res)
        np.testing.assert_allclose(
            clone.to_dataset()["value"].values, res.to_dataset()["value"].values
        )


class TestNanRobustness(unittest.TestCase):
    """A worker returning NaN for one point must not crash plotting paths."""

    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep(LinearWithNan)

    def test_nan_present_in_dataset(self):
        vals = self.res.to_dataset()["value"].values.flatten()
        self.assertEqual(int(np.isnan(vals).sum()), 1)
        np.testing.assert_allclose(np.sort(vals[~np.isnan(vals)]), [0.0, 4.0])

    def test_to_line_with_nan_does_not_crash(self):
        plot = self.res.to(LineResult)
        self.assertIsNotNone(plot)

    def test_to_auto_plots_with_nan_does_not_crash(self):
        col = self.res.to_auto_plots()
        self.assertIsInstance(col, pn.Column)
        self.assertEqual(col[0].name, "Plots View")


if __name__ == "__main__":
    unittest.main()
