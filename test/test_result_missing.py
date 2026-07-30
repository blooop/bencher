"""Direct tests for the centralised missing-value representation helpers.

``result_missing_fill`` and ``result_is_missing`` (bencher.variables.results)
are the single source of truth for how a missing/unrecorded result entry is
stored and detected.  These tests pin the (fill, dtype) mapping per result
type so a future result type that silently falls through to the NaN default
fails loudly here instead of corrupting datasets.
"""

import math
import unittest

import numpy as np

from bencher.result_collector import _sentinel_for_result_var
from bencher.variables.results import (
    ALL_RESULT_TYPES,
    DATA_VAR_RESULT_TYPES,
    XARRAY_MULTIDIM_RESULT_TYPES,
    ResultBool,
    ResultContainer,
    ResultDataSet,
    ResultFloat,
    ResultHmap,
    ResultImage,
    ResultPath,
    ResultReference,
    ResultRerun,
    ResultString,
    ResultVec,
    ResultVideo,
    result_is_missing,
    result_kind,
    result_missing_fill,
)


def _instantiate(cls):
    """A default instance of *cls*; ResultVec needs an explicit size."""
    return cls(size=2) if cls is ResultVec else cls()


def _nan_backed_vars():
    return [ResultFloat(), ResultBool(), ResultVec(size=2)]


def _reference_backed_vars():
    return [ResultReference(), ResultDataSet()]


def _object_backed_vars():
    return [
        ResultPath(),
        ResultVideo(),
        ResultImage(),
        ResultString(),
        ResultContainer(),
        ResultRerun(),
    ]


class TestResultMissingFill(unittest.TestCase):
    def test_numeric_types_fill_nan_float(self):
        for rv in _nan_backed_vars():
            fill, dtype = result_missing_fill(rv)
            with self.subTest(rv=type(rv).__name__):
                self.assertTrue(math.isnan(fill))
                self.assertIs(dtype, float)

    def test_reference_types_fill_minus_one_int(self):
        for rv in _reference_backed_vars():
            with self.subTest(rv=type(rv).__name__):
                self.assertEqual(result_missing_fill(rv), (-1, int))

    def test_object_types_fill_nan_string_object(self):
        for rv in _object_backed_vars():
            with self.subTest(rv=type(rv).__name__):
                self.assertEqual(result_missing_fill(rv), ("NAN", object))

    def test_sentinel_wrapper_matches_fill(self):
        # The over_time aging path goes through result_collector's thin
        # wrapper; it must stay in lockstep with the fill helper.
        for rv in _nan_backed_vars() + _reference_backed_vars() + _object_backed_vars():
            fill, _ = result_missing_fill(rv)
            sentinel = _sentinel_for_result_var(rv)
            with self.subTest(rv=type(rv).__name__):
                if isinstance(fill, float) and math.isnan(fill):
                    self.assertTrue(math.isnan(sentinel))
                else:
                    self.assertEqual(sentinel, fill)


class TestDataVarResultTypes(unittest.TestCase):
    def test_single_column_types_included(self):
        for rv in _reference_backed_vars() + _object_backed_vars():
            with self.subTest(rv=type(rv).__name__):
                self.assertIsInstance(rv, DATA_VAR_RESULT_TYPES)
        self.assertIsInstance(ResultFloat(), DATA_VAR_RESULT_TYPES)
        self.assertIsInstance(ResultBool(), DATA_VAR_RESULT_TYPES)

    def test_out_of_band_and_multi_column_types_excluded(self):
        # ResultVec expands to one column per element; ResultHmap is stored
        # out-of-band — neither gets a single data var.
        self.assertNotIsInstance(ResultVec(size=2), DATA_VAR_RESULT_TYPES)
        self.assertNotIsInstance(ResultHmap(), DATA_VAR_RESULT_TYPES)


class TestEveryResultTypeIsStorable(unittest.TestCase):
    """No result type may be declarable but unstorable.

    ``ResultVolume`` used to be exactly that: exported and listed in
    ``ALL_RESULT_TYPES``/``RESULT_KIND_ORDER``, but absent from every registry
    that decides how a sample is *stored*. Putting one in ``result_vars`` died in
    ``precompute_result_arrays`` with ``KeyError: No variable named ...`` — the
    type had no data variable, yet the collector indexed one anyway. It was
    deleted rather than wired up.

    This pins the invariant that made it a trap: membership in
    ``ALL_RESULT_TYPES`` implies the collector's store loop has a branch for the
    type. That loop dispatches on ``XARRAY_MULTIDIM_RESULT_TYPES``,
    ``ResultDataSet``, ``ResultReference`` and ``ResultVec``, and raises
    ``TypeError`` otherwise; ``ResultHmap`` is the one legitimate exception,
    collected separately via ``bench_res.result_hmaps``.
    """

    STORABLE = XARRAY_MULTIDIM_RESULT_TYPES + (ResultDataSet, ResultReference, ResultVec)

    def test_all_result_types_have_a_collector_branch(self):
        for cls in ALL_RESULT_TYPES:
            if cls is ResultHmap:
                continue
            with self.subTest(cls=cls.__name__):
                self.assertTrue(
                    issubclass(cls, self.STORABLE),
                    f"{cls.__name__} is in ALL_RESULT_TYPES but the collector has no "
                    f"branch to store it, so declaring one raises at sweep time. "
                    f"Either wire it into a storage registry or drop it from "
                    f"ALL_RESULT_TYPES.",
                )

    def test_result_kind_covers_all_result_types(self):
        # A type absent from RESULT_KIND_ORDER classifies as "unknown", which
        # silently degrades plot selection rather than failing.
        for cls in ALL_RESULT_TYPES:
            with self.subTest(cls=cls.__name__):
                self.assertNotEqual(result_kind(_instantiate(cls)), "unknown")


class TestResultIsMissing(unittest.TestCase):
    def test_numeric_nan_and_none_are_missing(self):
        rv = ResultFloat()
        self.assertTrue(result_is_missing(rv, float("nan")))
        self.assertTrue(result_is_missing(rv, np.nan))
        self.assertTrue(result_is_missing(rv, np.float32("nan")))
        self.assertTrue(result_is_missing(rv, None))

    def test_numeric_real_values_are_not_missing(self):
        rv = ResultFloat()
        self.assertFalse(result_is_missing(rv, 0.0))
        self.assertFalse(result_is_missing(rv, -1))
        self.assertFalse(result_is_missing(rv, np.float64(3.5)))
        self.assertFalse(result_is_missing(rv, True))

    def test_numeric_non_numbers_are_not_missing(self):
        # The *string* "nan" is real data, not the NaN sentinel — no float
        # coercion is attempted for non-numeric values.
        rv = ResultFloat()
        self.assertFalse(result_is_missing(rv, "nan"))
        self.assertFalse(result_is_missing(rv, "NAN"))
        self.assertFalse(result_is_missing(rv, "abc"))
        self.assertFalse(result_is_missing(rv, [float("nan")]))

    def test_reference_minus_one_is_missing(self):
        rv = ResultReference()
        self.assertTrue(result_is_missing(rv, -1))
        self.assertTrue(result_is_missing(rv, np.int64(-1)))
        self.assertFalse(result_is_missing(rv, 0))
        self.assertFalse(result_is_missing(rv, 7))
        self.assertFalse(result_is_missing(rv, None))

    def test_object_nan_string_is_missing(self):
        rv = ResultPath()
        self.assertTrue(result_is_missing(rv, "NAN"))
        self.assertTrue(result_is_missing(rv, np.str_("NAN")))
        self.assertFalse(result_is_missing(rv, "img/frame_001.png"))
        self.assertFalse(result_is_missing(rv, ""))
        self.assertFalse(result_is_missing(rv, None))

    def test_fill_round_trips_through_typed_array(self):
        # An array initialised with (fill, dtype) — exactly what
        # ResultCollector.setup_dataset builds — must read back as missing.
        for rv in _nan_backed_vars() + _reference_backed_vars() + _object_backed_vars():
            fill, dtype = result_missing_fill(rv)
            arr = np.full(3, fill, dtype=dtype)
            with self.subTest(rv=type(rv).__name__):
                self.assertTrue(result_is_missing(rv, arr[0]))


if __name__ == "__main__":
    unittest.main()
