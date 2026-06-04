"""Tests for the NaN default on scalar result variables.

``ResultFloat``/``ResultVec`` default to NaN so an *unrecorded* sample (e.g. a
run that aborted before measuring) is treated as missing and dropped by the
nan-aware reductions used for regression/aggregation, rather than being
indistinguishable from a real 0 measurement.  Callers can opt out with
``default=0`` to make unrecorded samples read as 0.  ``ResultBool`` keeps a 0
(``False``) default.
"""

import math
import os
import tempfile
import unittest
from enum import auto

import numpy as np
from strenum import StrEnum

import bencher as bn
from bencher.variables.results import ResultBool, ResultFloat, ResultVec


class _Cat(StrEnum):
    A = auto()
    B = auto()


class UnrecordedZeroBench(bn.ParametrizedSweep):
    """Result var that opts out to a 0 default; benchmark never records it."""

    cat = bn.EnumSweep(_Cat)
    out = bn.ResultFloat(doc="never recorded", default=0)

    def benchmark(self):
        return self.get_results_values_as_dict()


class UnrecordedNanBench(bn.ParametrizedSweep):
    """Result var that opts in to a NaN default; benchmark never records it."""

    cat = bn.EnumSweep(_Cat)
    out = bn.ResultFloat(doc="never recorded", default=float("nan"))

    def benchmark(self):
        return self.get_results_values_as_dict()


def _run_sweep(bench_cls):
    run_cfg = bn.BenchRunCfg(repeats=1)
    bench = bench_cls().to_bench(run_cfg)
    return bench.plot_sweep(
        input_vars=["cat"],
        result_vars=["out"],
        title="test",
        plot_callbacks=False,
    )


class TestNanDefaultConstruction(unittest.TestCase):
    def test_default_is_nan(self):
        self.assertTrue(math.isnan(ResultFloat().default))
        self.assertTrue(math.isnan(ResultVec(size=2).default))

    def test_default_can_be_nan(self):
        self.assertTrue(math.isnan(ResultFloat(default=float("nan")).default))
        self.assertTrue(math.isnan(ResultVec(size=2, default=float("nan")).default))

    def test_explicit_zero_default_opt_out(self):
        self.assertEqual(ResultFloat(default=0).default, 0)
        self.assertEqual(ResultVec(size=2, default=0).default, 0)

    def test_bool_default_stays_false_not_nan(self):
        # ResultBool intentionally keeps a 0 (=False) default rather than NaN:
        # False is a meaningful default for a binary outcome and the binomial-std
        # calc treats bool means as proportions over a fixed repeat count.
        self.assertEqual(ResultBool().default, 0)
        self.assertFalse(ResultBool().default)
        self.assertFalse(math.isnan(ResultBool().default))

    def test_explicit_numeric_default_still_honoured(self):
        self.assertEqual(ResultFloat(default=5).default, 5)

    def test_nan_default_does_not_change_hash(self):
        # ``default`` is not a hashed slot, so opting in to NaN must not wipe
        # over_time history for an otherwise-identical result var.
        self.assertEqual(
            ResultFloat(units="s").hash_persistent(),
            ResultFloat(units="s", default=float("nan")).hash_persistent(),
        )


class TestNanDefaultEndToEnd(unittest.TestCase):
    """An unrecorded metric should land as NaN (nan default) or 0 (default)."""

    def test_unrecorded_zero_default_stores_zero(self):
        ds = _run_sweep(UnrecordedZeroBench).to_dataset()
        for val in ds["out"].values.flat:
            self.assertEqual(float(val), 0.0)

    def test_unrecorded_nan_default_stores_nan(self):
        ds = _run_sweep(UnrecordedNanBench).to_dataset()
        for val in ds["out"].values.flat:
            self.assertTrue(np.isnan(val))


class TestNanDefaultSerialization(unittest.TestCase):
    """Opting into a NaN default must not break the serialization/render paths.

    The hardcoded ``0`` default was historically justified with the comment
    "json is terrible and does not support nan values".  The package no longer
    uses ``json`` directly: collected results are pickled
    (``save_result``/``load_result``) and plots are serialised to the browser by
    bokeh, which encodes NaN as ``null``.  A NaN default must therefore survive
    both the pickle cache path and the HoloViews -> bokeh render-to-HTML path
    without raising or silently corrupting the data.
    """

    @staticmethod
    def _collect_nan():
        bench = UnrecordedNanBench().to_bench(bn.BenchRunCfg(repeats=1))
        return bench.collect(
            input_vars=["cat"],
            result_vars=["out"],
            title="nan-serialise",
        )

    def test_save_load_pickle_roundtrip_preserves_nan(self):
        res = self._collect_nan()
        with tempfile.TemporaryDirectory() as tmp:
            path = bn.save_result(res, os.path.join(tmp, "res.pkl"))
            loaded = bn.load_result(path)
        for val in loaded.to_dataset()["out"].values.flat:
            self.assertTrue(np.isnan(val))

    def test_render_report_with_nan_default_succeeds(self):
        # render_report is the only step that builds holoviews/panel/bokeh
        # objects and serialises them to HTML (bokeh JSON-encodes the data).
        # A NaN default must not break that path.
        res = self._collect_nan()
        with tempfile.TemporaryDirectory() as tmp:
            out = bn.render_report(res, tmp)
            self.assertTrue(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
