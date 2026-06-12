"""Tests for bencher/results/holoview_results/distribution_result/violin_result.py"""

import math
import unittest

import holoviews as hv
import panel as pn

import bencher as bn
from bencher.results.bench_result_base import ReduceType
from bencher.results.holoview_results.distribution_result.violin_result import ViolinResult
from test.helpers import inner_element as _inner_element


class ViolinBench(bn.ParametrizedSweep):
    """Deterministic 1-categorical benchmark with per-repeat variation."""

    _call_count = 0

    category = bn.StringSweep(["alpha", "beta"])
    value = bn.ResultFloat(units="ms")

    def benchmark(self):
        ViolinBench._call_count += 1
        base = 1.0 if self.category == "alpha" else 2.0
        self.value = base + 0.01 * ViolinBench._call_count


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
        f"test_violin_{worker_cls.__name__}_{repeats}",
        input_vars=input_vars,
        result_vars=["value"],
        run_cfg=run_cfg,
        plot_callbacks=False,
    )


class TestViolinResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = _run_sweep(ViolinBench, ["category"], repeats=3)
        # store the list, not the Parameter itself: param Parameters are
        # descriptors, so a class-attribute Parameter would resolve to its
        # default value on attribute access.
        cls.result_vars = cls.res.bench_cfg.result_vars
        cls.ds = cls.res.to_dataset(ReduceType.NONE)

    def test_to_violin_ds_returns_violin_element(self):
        overlay = self.res.to_violin_ds(self.ds, self.result_vars[0])
        self.assertIsInstance(overlay, hv.Overlay)
        self.assertIsInstance(_inner_element(overlay), hv.Violin)

    def test_kdims_vdims_match_input_and_result_vars(self):
        el = _inner_element(self.res.to_violin_ds(self.ds, self.result_vars[0]))
        self.assertEqual([d.name for d in el.kdims], ["category"])
        self.assertEqual([d.name for d in el.vdims], ["value"])

    def test_title_and_ylabel_contain_result_var_and_units(self):
        el = _inner_element(self.res.to_violin_ds(self.ds, self.result_vars[0]))
        opts = hv.Store.lookup_options("bokeh", el, "plot").kwargs
        self.assertEqual(opts["ylabel"], "value [ms]")
        self.assertEqual(opts["title"], "value vs category vs repeat")

    def test_distribution_contains_all_repeat_samples(self):
        """With repeats=3 each x position must hold 3 individual samples."""
        el = _inner_element(self.res.to_violin_ds(self.ds, self.result_vars[0]))
        counts = el.dframe().groupby("category").size().to_dict()
        self.assertEqual(counts, {"alpha": 3, "beta": 3})

    def test_to_plot_returns_panel_row_with_holoviews_pane(self):
        plot = ViolinResult.to_plot(self.res)
        self.assertIsInstance(plot, pn.Row)
        self.assertGreater(len(plot), 0)

    def test_to_plot_rejected_for_single_repeat(self):
        """Distribution plots need repeats>=2; with override=False the filter rejects."""
        res_1rep = _run_sweep(ViolinBench, ["category"], repeats=1)
        plot = ViolinResult.to_plot(res_1rep, override=False)
        self.assertNotIsInstance(plot, pn.Row)
        self.assertTrue(plot is None or isinstance(plot, pn.pane.Markdown))

    def test_nan_results_do_not_crash(self):
        res_nan = _run_sweep(NanBench, ["category"], repeats=3)
        plot = ViolinResult.to_plot(res_nan)
        self.assertIsInstance(plot, pn.Row)
        ds_nan = res_nan.to_dataset(ReduceType.NONE)
        el = _inner_element(res_nan.to_violin_ds(ds_nan, res_nan.bench_cfg.result_vars[0]))
        df = el.dframe()
        broken = df[df["category"] == "broken"]["value"]
        self.assertEqual(len(broken), 3)
        self.assertTrue(all(math.isnan(v) for v in broken))


if __name__ == "__main__":
    unittest.main()
