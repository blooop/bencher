"""Regression tests for honest missing-value handling in the rerun renderer.

Plan 23 C12: never-sampled points must render as genuine gaps, never as
fabricated zeros; result types without a rerun mapping surface visibly instead
of being coerced through ``float()``; failures log at WARNING, not DEBUG.

The ``_log_*`` helpers take the ``rr`` module and the recording as parameters,
so these tests drive them with lightweight fakes — no rerun-sdk dependency and
no viewer round-trip.
"""

import math
import unittest
from types import SimpleNamespace

import numpy as np
import param
import xarray as xr

from bencher.results.rerun_result import (
    _log_bar_chart,
    _log_line_graph,
    _log_result_var,
    _log_tensor,
)
from bencher.variables.results import ResultFloat, ResultPath, ResultString

LOGGER = "bencher.results.rerun_result"


class _Vars(param.Parameterized):
    """Owner class so the result-var parameters carry their names."""

    metric = ResultFloat()
    label = ResultString()
    file_out = ResultPath()


def _fake_rr() -> SimpleNamespace:
    return SimpleNamespace(
        Scalars=lambda value: ("Scalars", value),
        BarChart=lambda values: ("BarChart", values),
        Tensor=lambda arr, dim_names=None, value_range=None: (
            "Tensor",
            arr,
            dim_names,
            value_range,
        ),
        TextDocument=lambda text: ("TextDocument", text),
    )


class _FakeRecording:
    def __init__(self):
        self.logged = []
        self.times = []

    def set_time(self, timeline, sequence=None, **_kwargs):
        self.times.append((timeline, sequence))

    def log(self, path, payload):
        self.logged.append((path, payload))


class TestLineGraphMissing(unittest.TestCase):
    def test_missing_point_is_a_gap_not_zero(self):
        """A never-sampled point is skipped (a gap), not logged as any value."""
        rec = _FakeRecording()
        ds = xr.Dataset({"metric": ("x", [1.0, np.nan, 3.0])}, coords={"x": [0, 1, 2]})
        _log_line_graph(_fake_rr(), rec, ds, "", _Vars.param.metric, "x")

        self.assertEqual(len(rec.logged), 2)
        values = [payload[1] for _path, payload in rec.logged]
        self.assertEqual(values, [1.0, 3.0])
        self.assertNotIn(0.0, values)
        # The tick sequence keeps its coordinate position, leaving a hole at 1
        self.assertEqual([seq for _tl, seq in rec.times], [0, 2])


class TestBarChartMissing(unittest.TestCase):
    def test_missing_category_is_nan_not_zero(self):
        """A never-sampled category stays NaN instead of a fabricated 0-height bar."""
        rec = _FakeRecording()
        ds = xr.Dataset({"metric": ("c", [2.0, np.nan])}, coords={"c": ["a", "b"]})
        _log_bar_chart(_fake_rr(), rec, ds, "", _Vars.param.metric, "c")

        self.assertEqual(len(rec.logged), 1)
        _path, (_kind, values) = rec.logged[0]
        self.assertEqual(values[0], 2.0)
        self.assertTrue(math.isnan(values[1]), f"expected NaN gap, got {values[1]!r}")


class TestTensorMissing(unittest.TestCase):
    def test_nan_preserved_and_range_from_recorded_values(self):
        """NaN cells are kept as gaps; value_range comes from the recorded values."""
        rec = _FakeRecording()
        ds = xr.Dataset(
            {"metric": (("x", "y"), [[1.0, np.nan], [3.0, 4.0]])},
            coords={"x": [0, 1], "y": [0, 1]},
        )
        _log_tensor(_fake_rr(), rec, ds, "", _Vars.param.metric, ["x", "y"])

        self.assertEqual(len(rec.logged), 1)
        _path, (_kind, arr, _dims, value_range) = rec.logged[0]
        self.assertTrue(np.isnan(arr[0, 1]), "missing cell must stay NaN, not become 0.0")
        self.assertEqual(value_range, [1.0, 4.0])

    def test_all_missing_tensor_skipped_with_warning(self):
        rec = _FakeRecording()
        ds = xr.Dataset(
            {"metric": (("x", "y"), [[np.nan, np.nan], [np.nan, np.nan]])},
            coords={"x": [0, 1], "y": [0, 1]},
        )
        with self.assertLogs(LOGGER, level="WARNING") as cm:
            _log_tensor(_fake_rr(), rec, ds, "", _Vars.param.metric, ["x", "y"])
        self.assertEqual(rec.logged, [])
        self.assertIn("no recorded values", "\n".join(cm.output))


class TestResultVarDispatch(unittest.TestCase):
    def test_missing_scalar_not_logged(self):
        rec = _FakeRecording()
        ds = xr.Dataset({"metric": xr.DataArray(np.nan)})
        _log_result_var(_fake_rr(), rec, ds, "", _Vars.param.metric)
        self.assertEqual(rec.logged, [])

    def test_present_scalar_logged(self):
        rec = _FakeRecording()
        ds = xr.Dataset({"metric": xr.DataArray(1.5)})
        _log_result_var(_fake_rr(), rec, ds, "", _Vars.param.metric)
        self.assertEqual(rec.logged, [("metric", ("Scalars", 1.5))])

    def test_missing_string_sentinel_not_logged(self):
        rec = _FakeRecording()
        ds = xr.Dataset({"label": xr.DataArray("NAN")})
        _log_result_var(_fake_rr(), rec, ds, "", _Vars.param.label)
        self.assertEqual(rec.logged, [])

    def test_present_string_logged(self):
        rec = _FakeRecording()
        ds = xr.Dataset({"label": xr.DataArray("hello")})
        _log_result_var(_fake_rr(), rec, ds, "", _Vars.param.label)
        self.assertEqual(rec.logged, [("label", ("TextDocument", "hello"))])

    def test_unmapped_type_warns_instead_of_float_coercion(self):
        """A ResultPath must not fall through to float("/path/..."); it surfaces
        visibly as a warning and is skipped."""
        rec = _FakeRecording()
        ds = xr.Dataset({"file_out": xr.DataArray("/tmp/result.csv")})
        with self.assertLogs(LOGGER, level="WARNING") as cm:
            _log_result_var(_fake_rr(), rec, ds, "", _Vars.param.file_out)
        self.assertEqual(rec.logged, [])
        out = "\n".join(cm.output)
        self.assertIn("ResultPath", out)
        self.assertIn("file_out", out)


if __name__ == "__main__":
    unittest.main()
