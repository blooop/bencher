"""Tests for the opt-in NaN default on scalar result variables.

``ResultFloat``/``ResultVec`` default to 0 because NaN is not JSON-serialisable,
but a 0 default means an *unrecorded* sample (e.g. a run that aborted before
measuring) is indistinguishable from a real 0 measurement.  Callers can opt in
to ``default=float("nan")`` so unrecorded samples are treated as missing and
dropped by the nan-aware reductions used for regression/aggregation.
"""

import math
import unittest
from enum import auto

import numpy as np
from strenum import StrEnum

import bencher as bn
from bencher.variables.results import ResultFloat, ResultVec


class _Cat(StrEnum):
    A = auto()
    B = auto()


class UnrecordedZeroBench(bn.ParametrizedSweep):
    """Result var with the default 0 default; benchmark never records it."""

    cat = bn.EnumSweep(_Cat)
    out = bn.ResultFloat(doc="never recorded")

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
    def test_default_is_zero_for_backward_compat(self):
        self.assertEqual(ResultFloat().default, 0)
        self.assertEqual(ResultVec(size=2).default, 0)

    def test_default_can_be_nan(self):
        self.assertTrue(math.isnan(ResultFloat(default=float("nan")).default))
        self.assertTrue(math.isnan(ResultVec(size=2, default=float("nan")).default))

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


if __name__ == "__main__":
    unittest.main()
