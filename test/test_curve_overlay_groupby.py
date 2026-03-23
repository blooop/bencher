"""Unit tests for _build_curve_overlay groupby path correctness.

Validates that the Plotly figure produced when categorical groupby
dimensions exist contains the expected traces with correct names.
"""

# pylint: disable=protected-access

import numpy as np
import xarray as xr
import plotly.graph_objects as go
from unittest.mock import MagicMock
from param import Parameter

from bencher.results.holoview_results.holoview_result import HoloviewResult


def _make_dataset(backends, sizes, has_std=True):
    """Build a synthetic xarray Dataset mimicking reduced benchmark output."""
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
    """Create a minimal HoloviewResult-like object."""
    result = MagicMock(spec=HoloviewResult)
    float_vars = []
    for name in float_var_names:
        fv = MagicMock()
        fv.name = name
        float_vars.append(fv)
    result.plt_cnt_cfg = MagicMock()
    result.plt_cnt_cfg.float_vars = float_vars
    result.title_from_ds = MagicMock(return_value="Test Title")
    result._default_layout = HoloviewResult._default_layout
    return result


def _make_result_var(name):
    rv = MagicMock(spec=Parameter)
    rv.name = name
    rv.units = "s"
    return rv


class TestBuildCurveOverlayGroupby:
    """Tests for the groupby path in _build_curve_overlay."""

    def test_produces_trace_per_category(self):
        """Each categorical value should produce at least one trace."""
        backends = ["redis", "local"]
        ds = _make_dataset(backends, [10.0, 50.0, 100.0], has_std=False)
        stub = _make_result_stub(["size"])
        rv = _make_result_var("time")

        fig = HoloviewResult._build_curve_overlay(stub, ds, rv)
        assert isinstance(fig, go.Figure)

        # Should have one Scatter trace per backend
        scatter_traces = [t for t in fig.data if isinstance(t, go.Scatter) and t.mode == "lines"]
        assert len(scatter_traces) == len(backends)

    def test_trace_names_match_categories(self):
        """Trace names should correspond to the categorical dimension values."""
        backends = ["redis", "local"]
        ds = _make_dataset(backends, [10.0, 50.0, 100.0], has_std=False)
        stub = _make_result_stub(["size"])
        rv = _make_result_var("time")

        fig = HoloviewResult._build_curve_overlay(stub, ds, rv)
        names = sorted(t.name for t in fig.data if isinstance(t, go.Scatter) and t.mode == "lines")
        assert names == sorted(backends)

    def test_fill_traces_present_when_std_exists(self):
        """When _std var exists, fill traces should accompany line traces."""
        backends = ["redis", "local"]
        ds = _make_dataset(backends, [10.0, 50.0, 100.0], has_std=True)
        stub = _make_result_stub(["size"])
        rv = _make_result_var("time")

        fig = HoloviewResult._build_curve_overlay(stub, ds, rv)

        fill_traces = [t for t in fig.data if hasattr(t, "fill") and t.fill == "toself"]
        assert len(fill_traces) == len(backends)

    def test_no_fill_without_std(self):
        """Without _std var, no fill traces should be in figure."""
        backends = ["redis", "local"]
        ds = _make_dataset(backends, [10.0, 50.0, 100.0], has_std=False)
        stub = _make_result_stub(["size"])
        rv = _make_result_var("time")

        fig = HoloviewResult._build_curve_overlay(stub, ds, rv)

        fill_traces = [t for t in fig.data if hasattr(t, "fill") and t.fill == "toself"]
        assert len(fill_traces) == 0

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

        fig = HoloviewResult._build_curve_overlay(stub, ds, rv)

        line_traces = [t for t in fig.data if isinstance(t, go.Scatter) and t.mode == "lines"]
        # 2 backends × 3 algos = 6 traces
        assert len(line_traces) == 6
        for t in line_traces:
            assert ", " in t.name

    def test_trace_data_not_empty(self):
        """Each trace should contain actual data points."""
        backends = ["redis", "local"]
        ds = _make_dataset(backends, [10.0, 50.0, 100.0], has_std=False)
        stub = _make_result_stub(["size"])
        rv = _make_result_var("time")

        fig = HoloviewResult._build_curve_overlay(stub, ds, rv)

        for t in fig.data:
            if isinstance(t, go.Scatter) and t.mode == "lines":
                assert len(t.x) == 3
