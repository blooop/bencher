"""Tests for bencher/results/histogram_result.py"""

import unittest

import holoviews as hv
import numpy as np

import bencher as bn
from bencher.results.histogram_result import HistogramResult

N_REPEATS = 10


class DeterministicWorker(bn.ParametrizedSweep):
    """No-input worker producing values 0..N-1 across repeats (one value per call)."""

    value = bn.ResultFloat(units="m")
    _counter = [0]

    def benchmark(self):
        self.value = float(self._counter[0])
        self._counter[0] += 1


class NanWorker(bn.ParametrizedSweep):
    """No-input worker that returns NaN for exactly one repeat."""

    value = bn.ResultFloat(units="m")
    _counter = [0]

    def benchmark(self):
        i = self._counter[0]
        self._counter[0] += 1
        self.value = float("nan") if i == 3 else float(i)


class FloatInputWorker(bn.ParametrizedSweep):
    """Worker with a float input — outside the histogram filter's native signature."""

    x = bn.FloatSweep(bounds=[0, 1], samples=3)
    value = bn.ResultFloat(units="m")

    def benchmark(self):
        self.value = self.x * 2.0


def _repeats_run_cfg() -> bn.BenchRunCfg:
    return bn.BenchRunCfg(repeats=N_REPEATS, cache_results=False, cache_samples=False)


def _collect_histograms(panel_obj) -> list[hv.Histogram]:
    """Recursively collect hv.Histogram elements from a panel/holoviews tree."""
    found = []
    if panel_obj is None:
        return found
    inner = getattr(panel_obj, "object", None)
    if hasattr(inner, "traverse"):
        found.extend(inner.traverse(lambda x: x, [hv.Histogram]))
    for child in getattr(panel_obj, "objects", []):
        found.extend(_collect_histograms(child))
    return found


class TestHistogramResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        DeterministicWorker._counter[0] = 0  # pylint: disable=protected-access
        bench = DeterministicWorker().to_bench(_repeats_run_cfg())
        cls.res = bench.plot_sweep(
            "test_hist",
            input_vars=[],
            result_vars=["value"],
            run_cfg=_repeats_run_cfg(),
            plot_callbacks=False,
        )
        cls.raw_ds = cls.res.to_dataset(reduce=bn.ReduceType.NONE)

        rc_float = bn.BenchRunCfg(repeats=1, cache_results=False, cache_samples=False)
        bench_float = FloatInputWorker().to_bench(rc_float)
        cls.res_float = bench_float.plot_sweep(
            "test_hist_float_input",
            input_vars=["x"],
            result_vars=["value"],
            run_cfg=rc_float,
            plot_callbacks=False,
        )

    def _single_histogram(self, plot) -> hv.Histogram:
        hists = plot.traverse(lambda x: x, [hv.Histogram])
        self.assertEqual(len(hists), 1)
        return hists[0]

    def test_to_histogram_ds_dimension_names(self):
        """The histogram x-dimension is the result var name; counts go on y."""
        rv = self.res.bench_cfg.result_vars[0]
        plot = self.res.to_histogram_ds(self.raw_ds, rv)
        hist = self._single_histogram(plot)
        self.assertEqual(hist.kdims[0].name, "value")
        self.assertEqual(hist.vdims[0].name, "value_count")

    def test_binning_counts_and_edges(self):
        """All N samples are binned and the bin edges span the data range [0, N-1]."""
        rv = self.res.bench_cfg.result_vars[0]
        plot = self.res.to_histogram_ds(self.raw_ds, rv)
        hist = self._single_histogram(plot)
        frequencies = hist.dimension_values(1)
        self.assertEqual(frequencies.sum(), N_REPEATS)
        self.assertEqual(hist.edges[0], 0.0)
        self.assertEqual(hist.edges[-1], float(N_REPEATS - 1))

    def test_binning_respects_bins_kwarg(self):
        """A bins= kwarg is forwarded to hvplot and controls the bin count."""
        rv = self.res.bench_cfg.result_vars[0]
        plot = self.res.to_histogram_ds(self.raw_ds, rv, bins=5)
        hist = self._single_histogram(plot)
        frequencies = hist.dimension_values(1)
        self.assertEqual(len(frequencies), 5)
        self.assertEqual(frequencies.sum(), N_REPEATS)

    def test_axis_labels_and_title(self):
        """Title contains the result var name; y axis is labelled 'count'."""
        rv = self.res.bench_cfg.result_vars[0]
        plot = self.res.to_histogram_ds(self.raw_ds, rv)
        opts = plot.opts.get().kwargs
        self.assertEqual(opts["title"], "value vs Count")
        self.assertEqual(opts["ylabel"], "count")
        self.assertEqual(opts["xrotation"], 30)

    def test_to_plot_repeats_only_sweep(self):
        """to_plot natively matches a 0-input repeats sweep (no override needed)."""
        pane = self.res.to(HistogramResult, override=False)
        hists = _collect_histograms(pane)
        self.assertEqual(len(hists), 1)
        self.assertEqual(hists[0].kdims[0].name, "value")
        self.assertEqual(hists[0].dimension_values(1).sum(), N_REPEATS)

    def test_to_plot_rejects_float_input_sweep(self):
        """The filter (0 floats, 0 inputs) rejects a float-input sweep without override."""
        pane = self.res_float.to(HistogramResult, override=False)
        self.assertEqual(_collect_histograms(pane), [])

    def test_to_plot_override_float_input_sweep(self):
        """With override the histogram renders, binning one sample per input point."""
        pane = self.res_float.to(HistogramResult)
        hists = _collect_histograms(pane)
        self.assertEqual(len(hists), 1)
        self.assertEqual(hists[0].kdims[0].name, "value")
        self.assertEqual(hists[0].dimension_values(1).sum(), 3)

    def test_nan_values_are_dropped_not_fatal(self):
        """A NaN sample must not crash rendering; it is excluded from the bin counts."""
        NanWorker._counter[0] = 0  # pylint: disable=protected-access
        bench = NanWorker().to_bench(_repeats_run_cfg())
        res = bench.plot_sweep(
            "test_hist_nan",
            input_vars=[],
            result_vars=["value"],
            run_cfg=_repeats_run_cfg(),
            plot_callbacks=False,
        )
        raw_ds = res.to_dataset(reduce=bn.ReduceType.NONE)
        rv = res.bench_cfg.result_vars[0]

        plot = res.to_histogram_ds(raw_ds, rv)
        hist = self._single_histogram(plot)
        frequencies = hist.dimension_values(1)
        self.assertTrue(np.isfinite(frequencies).all())
        self.assertEqual(frequencies.sum(), N_REPEATS - 1)

        pane = res.to(HistogramResult, override=False)
        self.assertEqual(len(_collect_histograms(pane)), 1)


if __name__ == "__main__":
    unittest.main()
