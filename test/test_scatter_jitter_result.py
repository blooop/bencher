"""Tests for bencher/results/holoview_results/distribution_result/scatter_jitter_result.py"""

import math
import unittest

import holoviews as hv
import panel as pn

import bencher as bn
from bencher.results.bench_result_base import ReduceType
from bencher.results.holoview_results.distribution_result.scatter_jitter_result import (
    ScatterJitterResult,
)
from test.helpers import inner_element as _inner_element


class JitterBench(bn.ParametrizedSweep):
    """Deterministic 1-categorical benchmark with per-repeat variation."""

    _call_count = 0

    category = bn.StringSweep(["alpha", "beta"])
    value = bn.ResultFloat(units="ms")

    def benchmark(self):
        JitterBench._call_count += 1
        base = 1.0 if self.category == "alpha" else 2.0
        self.value = base + 0.01 * JitterBench._call_count


class TwoCatBench(bn.ParametrizedSweep):
    category = bn.StringSweep(["alpha", "beta"])
    backend = bn.StringSweep(["cpu", "gpu"])
    value = bn.ResultFloat(units="ms")

    def benchmark(self):
        self.value = 1.0 if self.category == "alpha" else 2.0


class NanBench(bn.ParametrizedSweep):
    """One category always returns NaN (the missing-value default)."""

    category = bn.StringSweep(["ok", "broken"])
    value = bn.ResultFloat(units="ms")

    def benchmark(self):
        self.value = float("nan") if self.category == "broken" else 1.0


def _run_sweep(worker_cls, input_vars, repeats):
    run_cfg = bn.BenchRunCfg(repeats=repeats, cache_results=False, cache_samples=False)
    bench = worker_cls().to_bench(run_cfg)
    return bench.plot_sweep(
        f"test_scatter_jitter_{worker_cls.__name__}_{repeats}",
        input_vars=input_vars,
        result_vars=["value"],
        run_cfg=run_cfg,
        plot_callbacks=False,
    )


class TestScatterJitterResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = _run_sweep(JitterBench, ["category"], repeats=3)
        # store the list, not the Parameter itself: param Parameters are
        # descriptors, so a class-attribute Parameter would resolve to its
        # default value on attribute access.
        cls.result_vars = cls.res.bench_cfg.result_vars
        cls.ds = cls.res.to_dataset(ReduceType.NONE)

    def test_to_scatter_jitter_ds_returns_scatter_element(self):
        overlay = self.res.to_scatter_jitter_ds(self.ds, self.result_vars[0])
        self.assertIsInstance(overlay, hv.Overlay)
        self.assertIsInstance(_inner_element(overlay), hv.Scatter)

    def test_kdims_vdims_match_input_and_result_vars(self):
        el = _inner_element(self.res.to_scatter_jitter_ds(self.ds, self.result_vars[0]))
        self.assertEqual([d.name for d in el.kdims], ["category"])
        self.assertEqual([d.name for d in el.vdims], ["value"])

    def test_title_and_ylabel_contain_result_var_and_units(self):
        el = _inner_element(self.res.to_scatter_jitter_ds(self.ds, self.result_vars[0]))
        opts = hv.Store.lookup_options("bokeh", el, "plot").kwargs
        self.assertEqual(opts["ylabel"], "value [ms]")
        self.assertEqual(opts["title"], "value vs category vs repeat")

    def test_default_jitter_opt_applied(self):
        el = _inner_element(self.res.to_scatter_jitter_ds(self.ds, self.result_vars[0]))
        opts = hv.Store.lookup_options("bokeh", el, "plot").kwargs
        self.assertEqual(opts["jitter"], 0.1)

    def test_custom_jitter_opt_propagated(self):
        el = _inner_element(
            self.res.to_scatter_jitter_ds(self.ds, self.result_vars[0], jitter=0.25)
        )
        opts = hv.Store.lookup_options("bokeh", el, "plot").kwargs
        self.assertEqual(opts["jitter"], 0.25)

    def test_scatter_shows_every_individual_sample(self):
        """Scatter jitter plots raw points: repeats x categories rows, values intact."""
        el = _inner_element(self.res.to_scatter_jitter_ds(self.ds, self.result_vars[0]))
        df = el.dframe()
        counts = df.groupby("category").size().to_dict()
        self.assertEqual(counts, {"alpha": 3, "beta": 3})
        # all alpha samples stay near 1, all beta samples near 2 (no aggregation)
        self.assertTrue((df[df["category"] == "alpha"]["value"] < 1.5).all())
        self.assertTrue((df[df["category"] == "beta"]["value"] > 1.5).all())

    def test_to_plot_returns_panel_row_with_holoviews_pane(self):
        plot = ScatterJitterResult.to_plot(self.res)
        self.assertIsInstance(plot, pn.Row)
        self.assertGreater(len(plot), 0)

    def test_to_plot_rejected_for_single_repeat(self):
        """Scatter jitter needs repeats>=2; with override=False the filter rejects."""
        res_1rep = _run_sweep(JitterBench, ["category"], repeats=1)
        plot = ScatterJitterResult.to_plot(res_1rep, override=False)
        self.assertNotIsInstance(plot, pn.Row)
        self.assertTrue(plot is None or isinstance(plot, pn.pane.Markdown))

    def test_to_plot_rejected_for_two_categorical_inputs(self):
        """Unlike box/violin, scatter jitter accepts at most 1 categorical input."""
        res_2cat = _run_sweep(TwoCatBench, ["category", "backend"], repeats=3)
        plot = ScatterJitterResult.to_plot(res_2cat, override=False)
        self.assertNotIsInstance(plot, pn.Row)
        self.assertTrue(plot is None or isinstance(plot, pn.pane.Markdown))

    def test_nan_results_do_not_crash(self):
        res_nan = _run_sweep(NanBench, ["category"], repeats=3)
        plot = ScatterJitterResult.to_plot(res_nan)
        self.assertIsInstance(plot, pn.Row)
        ds_nan = res_nan.to_dataset(ReduceType.NONE)
        el = _inner_element(res_nan.to_scatter_jitter_ds(ds_nan, res_nan.bench_cfg.result_vars[0]))
        df = el.dframe()
        broken = df[df["category"] == "broken"]["value"]
        self.assertEqual(len(broken), 3)
        self.assertTrue(all(math.isnan(v) for v in broken))


if __name__ == "__main__":
    unittest.main()
