"""Direct tests for the centralised missing-value representation helpers.

``result_missing_fill`` and ``result_is_missing`` (bencher.variables.results)
are the single source of truth for how a missing/unrecorded result entry is
stored and detected.  These tests pin the (fill, dtype) mapping per result
type so a future result type that silently falls through to the NaN default
fails loudly here instead of corrupting datasets.
"""

import math
import unittest
import warnings

import numpy as np
import param

from bencher.result_collector import _sentinel_for_result_var
from bencher.variables.parametrised_sweep import ParametrizedSweep
from bencher.variables.results import (
    _MEDIA_RESULT_TYPES,
    _OBJECT_MISSING_TYPES,
    _REFERENCE_MISSING_TYPES,
    ALL_RESULT_TYPES,
    DATA_VAR_RESULT_TYPES,
    PANEL_TYPES,
    RESULT_KIND_ORDER,
    RESULT_SPEC_EXEMPT,
    RESULT_SPECS,
    SCALAR_RESULT_TYPES,
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
    result_spec,
)


def _instantiate(cls):
    """A default instance of *cls*; ResultVec needs an explicit size."""
    with warnings.catch_warnings():
        # ResultHmap warns on instantiation (deprecated); its storage semantics
        # are still pinned here until phase 3 removes it.
        warnings.simplefilter("ignore", DeprecationWarning)
        return cls(size=2) if cls is ResultVec else cls()


def _nan_backed_vars():
    return [ResultFloat(), ResultBool(), ResultVec(size=2)]


def _reference_backed_vars():
    return [ResultReference()]


def _object_backed_vars():
    # ResultDataSet joined the blob family with plan 22: its cells are paths
    # into the blob store and its fill is the object-family "NAN" sentinel.
    return [
        ResultPath(),
        ResultVideo(),
        ResultImage(),
        ResultString(),
        ResultContainer(),
        ResultRerun(),
        ResultDataSet(),
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
        self.assertNotIsInstance(_instantiate(ResultHmap), DATA_VAR_RESULT_TYPES)


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

    def test_dataset_accepts_both_sentinel_generations(self):
        """A mixed-generation over_time history holds "NAN" path sentinels next to
        legacy -1 index sentinels (possibly float-promoted by concat), permanently."""
        rv = ResultDataSet()
        self.assertTrue(result_is_missing(rv, "NAN"))
        self.assertTrue(result_is_missing(rv, -1))
        self.assertTrue(result_is_missing(rv, np.int64(-1)))
        self.assertTrue(result_is_missing(rv, np.float64(-1.0)))
        self.assertTrue(result_is_missing(rv, float("nan")))
        self.assertTrue(result_is_missing(rv, None))
        self.assertFalse(result_is_missing(rv, "cachedir/blobs/abc123.parquet"))
        self.assertFalse(result_is_missing(rv, 0))
        self.assertFalse(result_is_missing(rv, 3))

    def test_fill_round_trips_through_typed_array(self):
        # An array initialised with (fill, dtype) — exactly what
        # ResultCollector.setup_dataset builds — must read back as missing.
        for rv in _nan_backed_vars() + _reference_backed_vars() + _object_backed_vars():
            fill, dtype = result_missing_fill(rv)
            arr = np.full(3, fill, dtype=dtype)
            with self.subTest(rv=type(rv).__name__):
                self.assertTrue(result_is_missing(rv, arr[0]))


class TestResultSpecRegistry(unittest.TestCase):
    """Plan 23 P4: RESULT_SPECS is the single source of truth for result-type
    classification and storage; the nine legacy tuples are derived from it.
    These tests make "add a Result* class without a spec" a CI failure with
    one clear message instead of nine scattered silent failure modes."""

    def test_every_result_class_is_registered_or_exempt(self):
        from test.test_hash_persistent import _discover_all_result_classes

        for cls in _discover_all_result_classes():
            with self.subTest(cls=cls.__name__):
                self.assertTrue(
                    cls in RESULT_SPECS or cls in RESULT_SPEC_EXEMPT,
                    f"{cls.__name__} has no entry in RESULT_SPECS and is not in "
                    f"RESULT_SPEC_EXEMPT. Every Result* class must declare a "
                    f"ResultSpec (bencher/variables/results.py) so all nine "
                    f"derived registries stay complete.",
                )

    def test_exempt_classes_resolve_to_a_registered_spec(self):
        # An exempt class must still be classifiable: isinstance resolution
        # falls through to a registered base (ResultVar -> ResultFloat).
        for cls in RESULT_SPEC_EXEMPT:
            with self.subTest(cls=cls.__name__):
                self.assertIsNotNone(result_spec(_instantiate(cls)))
                self.assertNotIn(cls, ALL_RESULT_TYPES)

    def test_no_key_precedes_its_own_subclass(self):
        # Registry insertion order is the isinstance-resolution order, so a
        # base class listed before its subclass would shadow the subclass.
        keys = list(RESULT_SPECS)
        for i, earlier in enumerate(keys):
            for later in keys[i + 1 :]:
                self.assertFalse(
                    issubclass(later, earlier),
                    f"{later.__name__} subclasses {earlier.__name__} but is listed "
                    f"after it in RESULT_SPECS; isinstance dispatch would never "
                    f"reach it. Most-derived classes must come first.",
                )

    def test_missing_sentinels_agree_with_result_is_missing(self):
        # The spec's declared fill and sentinels must be judged missing by the
        # read-side oracle, so the two cannot drift apart.
        for cls, spec in RESULT_SPECS.items():
            inst = _instantiate(cls)
            with self.subTest(cls=cls.__name__):
                self.assertTrue(result_is_missing(inst, spec.missing_fill))
                for sentinel in spec.missing_sentinels:
                    self.assertTrue(result_is_missing(inst, sentinel))

    def test_result_spec_is_none_for_non_result_params(self):
        self.assertIsNone(result_spec(param.Number()))
        self.assertIsNone(result_spec(param.String()))


class TestDerivedTuplesMatchPreRegistryLiterals(unittest.TestCase):
    """TRANSITIONAL — delete after one release (added in plan 23 P4).

    Pins that the registry-derived tuples are membership-identical to the
    hand-maintained literals they replaced (copied here verbatim from the
    pre-P4 module). Every consumer is an ``isinstance()`` check, so membership
    is the behavioral contract; a single registry order cannot reproduce all
    nine historic tuple orders (PANEL_TYPES had Image before Video,
    XARRAY_MULTIDIM_RESULT_TYPES the reverse). RESULT_KIND_ORDER is the one
    order-sensitive name (most-derived-first isinstance dispatch) and is
    compared exactly, order included."""

    def test_membership_identical_to_pre_registry_literals(self):
        literals = {
            "PANEL_TYPES": (
                PANEL_TYPES,
                {
                    ResultPath,
                    ResultImage,
                    ResultVideo,
                    ResultContainer,
                    ResultRerun,
                    ResultString,
                    ResultReference,
                    ResultDataSet,
                },
            ),
            "SCALAR_RESULT_TYPES": (SCALAR_RESULT_TYPES, {ResultFloat, ResultBool}),
            "XARRAY_MULTIDIM_RESULT_TYPES": (
                XARRAY_MULTIDIM_RESULT_TYPES,
                {
                    ResultFloat,
                    ResultBool,
                    ResultVideo,
                    ResultImage,
                    ResultString,
                    ResultContainer,
                    ResultRerun,
                    ResultPath,
                },
            ),
            "ALL_RESULT_TYPES": (
                ALL_RESULT_TYPES,
                {
                    ResultFloat,
                    ResultBool,
                    ResultVec,
                    ResultHmap,
                    ResultPath,
                    ResultVideo,
                    ResultImage,
                    ResultString,
                    ResultContainer,
                    ResultRerun,
                    ResultDataSet,
                    ResultReference,
                },
            ),
            "_REFERENCE_MISSING_TYPES": (_REFERENCE_MISSING_TYPES, {ResultReference}),
            "_OBJECT_MISSING_TYPES": (
                _OBJECT_MISSING_TYPES,
                {
                    ResultPath,
                    ResultVideo,
                    ResultImage,
                    ResultString,
                    ResultContainer,
                    ResultRerun,
                    ResultDataSet,
                },
            ),
            "DATA_VAR_RESULT_TYPES": (
                DATA_VAR_RESULT_TYPES,
                {
                    ResultFloat,
                    ResultBool,
                    ResultReference,
                    ResultPath,
                    ResultVideo,
                    ResultImage,
                    ResultString,
                    ResultContainer,
                    ResultRerun,
                    ResultDataSet,
                },
            ),
            "_MEDIA_RESULT_TYPES": (
                _MEDIA_RESULT_TYPES,
                {ResultPath, ResultVideo, ResultImage, ResultContainer, ResultRerun},
            ),
        }
        for name, (derived, literal) in literals.items():
            with self.subTest(registry=name):
                self.assertEqual(set(derived), literal)
                self.assertEqual(len(derived), len(literal), f"{name} has duplicates")

    def test_result_kind_order_identical_including_order(self):
        self.assertEqual(
            RESULT_KIND_ORDER,
            (
                (ResultBool, "bool"),
                (ResultFloat, "float"),
                (ResultVec, "vec"),
                (ResultImage, "image"),
                (ResultVideo, "video"),
                (ResultPath, "path"),
                (ResultString, "string"),
                (ResultDataSet, "dataset"),
                (ResultRerun, "rerun"),
                (ResultContainer, "container"),
                (ResultHmap, "hmap"),
                (ResultReference, "reference"),
            ),
        )


class TestUnregisteredResultClassGuard(unittest.TestCase):
    """A parameter class defined in the results module but missing from
    RESULT_SPECS must be refused at sweep-declaration time, not silently
    classified as an input variable (the old ResultVolume trap)."""

    def test_unregistered_results_module_class_raises(self):
        class ResultBogus(param.Parameter):
            pass

        # Simulate a class defined in the results module but never registered.
        ResultBogus.__module__ = "bencher.variables.results"

        class BogusSweep(ParametrizedSweep):
            out = ResultBogus()

        with self.assertRaises(TypeError) as ctx:
            BogusSweep.get_input_and_results()
        self.assertIn("RESULT_SPECS", str(ctx.exception))

    def test_ordinary_inputs_still_classify_as_inputs(self):
        class PlainSweep(ParametrizedSweep):
            x = param.Number(1.0)
            out = ResultFloat()

        io = PlainSweep.get_input_and_results()
        self.assertIn("x", io.inputs)
        self.assertIn("out", io.results)


if __name__ == "__main__":
    unittest.main()
