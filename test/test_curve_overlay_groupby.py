"""Unit tests for _build_curve_overlay groupby path correctness.

Validates that the overlay produced when categorical groupby dimensions exist
contains the expected Curve elements with correct labels and optional Spread bands.
"""

# pylint: disable=protected-access

import holoviews as hv
import numpy as np
import xarray as xr
from unittest.mock import MagicMock
from param import Parameter

from bencher.results.holoview_results.holoview_result import HoloviewResult


def _make_dataset(backends, sizes, has_std=True):
    """Build a synthetic xarray Dataset mimicking reduced benchmark output.

    Dimensions: size (float) x backend (categorical).
    Data vars: time, time_std (optional).
    """
    data = np.random.default_rng(42).random((len(sizes), len(backends)))
    ds = xr.Dataset(
        {"time": (["size", "backend"], data)},
        coords={"size": sizes, "backend": backends},
    )
    if has_std:
        std_data = np.abs(np.random.default_rng(7).random((len(sizes), len(backends)))) * 0.1
        ds["time_std"] = (["size", "backend"], std_data)
    return ds


def _make_result_stub(float_var_names):
    """Create a minimal HoloviewResult-like object with plt_cnt_cfg.float_vars stub."""
    result = MagicMock(spec=HoloviewResult)
    float_vars = []
    for name in float_var_names:
        fv = MagicMock()
        fv.name = name
        float_vars.append(fv)
    result.plt_cnt_cfg = MagicMock()
    result.plt_cnt_cfg.float_vars = float_vars
    result.title_from_ds = MagicMock(return_value="Test Title")
    return result


def _make_result_var(name):
    """Create a Parameter-like result var with a .name attribute."""
    rv = MagicMock(spec=Parameter)
    rv.name = name
    return rv


class TestBuildCurveOverlayGroupby:
    """Tests for the groupby path in _build_curve_overlay."""

    def test_produces_curve_per_category(self):
        """Each categorical value should produce one Curve in the overlay."""
        backends = ["redis", "local"]
        ds = _make_dataset(backends, [10.0, 50.0, 100.0], has_std=False)
        stub = _make_result_stub(["size"])
        rv = _make_result_var("time")

        overlay = HoloviewResult._build_curve_overlay(stub, ds, rv)

        curves = [el for el in overlay if isinstance(el, hv.Curve)]
        assert len(curves) == len(backends), f"Expected {len(backends)} curves, got {len(curves)}"

    def test_curve_labels_match_categories(self):
        """Curve labels should correspond to the categorical dimension values."""
        backends = ["redis", "local"]
        ds = _make_dataset(backends, [10.0, 50.0, 100.0], has_std=False)
        stub = _make_result_stub(["size"])
        rv = _make_result_var("time")

        overlay = HoloviewResult._build_curve_overlay(stub, ds, rv)

        labels = sorted(el.label for el in overlay if isinstance(el, hv.Curve))
        assert labels == sorted(backends)

    def test_spread_present_when_std_exists(self):
        """When _std var exists, Spread elements should accompany Curves."""
        backends = ["redis", "local"]
        ds = _make_dataset(backends, [10.0, 50.0, 100.0], has_std=True)
        stub = _make_result_stub(["size"])
        rv = _make_result_var("time")

        overlay = HoloviewResult._build_curve_overlay(stub, ds, rv)

        spreads = [el for el in overlay if isinstance(el, hv.Spread)]
        assert len(spreads) == len(backends), (
            f"Expected {len(backends)} spreads, got {len(spreads)}"
        )

    def test_no_spread_without_std(self):
        """Without _std var, no Spread elements should be in overlay."""
        backends = ["redis", "local"]
        ds = _make_dataset(backends, [10.0, 50.0, 100.0], has_std=False)
        stub = _make_result_stub(["size"])
        rv = _make_result_var("time")

        overlay = HoloviewResult._build_curve_overlay(stub, ds, rv)

        spreads = [el for el in overlay if isinstance(el, hv.Spread)]
        assert len(spreads) == 0

    def test_multi_category_labels(self):
        """With two categorical dimensions, labels should be comma-joined."""
        sizes = [10.0, 50.0, 100.0]
        data = np.random.default_rng(42).random((len(sizes), 2, 3))
        ds = xr.Dataset(
            {"time": (["size", "backend", "algo"], data)},
            coords={
                "size": sizes,
                "backend": ["redis", "local"],
                "algo": ["quick", "merge", "heap"],
            },
        )
        stub = _make_result_stub(["size"])
        rv = _make_result_var("time")

        overlay = HoloviewResult._build_curve_overlay(stub, ds, rv)

        curves = [el for el in overlay if isinstance(el, hv.Curve)]
        # 2 backends × 3 algos = 6 curves
        assert len(curves) == 6, f"Expected 6 curves, got {len(curves)}"
        # Labels should contain comma-separated values
        labels = [el.label for el in overlay if isinstance(el, hv.Curve)]
        for label in labels:
            assert ", " in label, f"Expected comma-separated label, got '{label}'"

    def test_curve_data_not_empty(self):
        """Each Curve should contain actual data points."""
        backends = ["redis", "local"]
        ds = _make_dataset(backends, [10.0, 50.0, 100.0], has_std=False)
        stub = _make_result_stub(["size"])
        rv = _make_result_var("time")

        overlay = HoloviewResult._build_curve_overlay(stub, ds, rv)

        for el in overlay:
            if isinstance(el, hv.Curve):
                assert len(el) == 3, f"Expected 3 data points, got {len(el)}"
