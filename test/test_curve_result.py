"""Tests for bencher/results/holoview_results/curve_result.py (CurveResult)."""

import math

import holoviews as hv
import panel as pn
import pytest

import bencher as bn
from bencher.results.bench_result_base import ReduceType
from bencher.results.holoview_results.curve_result import CurveResult


def run_cfg_with(repeats: int) -> bn.BenchRunCfg:
    return bn.BenchRunCfg(
        repeats=repeats, cache_results=False, cache_samples=False, auto_plot=False
    )


def unwrap_hv(obj):
    """Unwrap a panel Row/HoloViews pane returned by filter() to the hv object inside."""
    while True:
        if hasattr(obj, "object"):
            obj = obj.object
        elif hasattr(obj, "objects"):
            assert len(obj.objects) > 0
            obj = obj.objects[0]
        else:
            return obj


class CurveBench(bn.ParametrizedSweep):
    """Minimal 1-float sweep for curve plots (repeats provide the spread)."""

    size = bn.FloatSweep(default=50, bounds=[10, 100], samples=3, doc="Size")
    throughput = bn.ResultFloat(units="MB/s", doc="Throughput")

    def benchmark(self):
        self.throughput = self.size * 0.5 + math.sin(self.size)


class CurveCatBench(bn.ParametrizedSweep):
    """1 float + 1 categorical sweep to exercise the groupby overlay path."""

    size = bn.FloatSweep(default=50, bounds=[10, 100], samples=3, doc="Size")
    backend = bn.StringSweep(["redis", "local"], doc="Backend")
    throughput = bn.ResultFloat(units="MB/s", doc="Throughput")

    def benchmark(self):
        base = {"redis": 1.0, "local": 2.0}[self.backend]
        self.throughput = self.size * base


class CurveNanBench(bn.ParametrizedSweep):
    """Sweep whose worker returns NaN for one input point."""

    size = bn.FloatSweep(default=50, bounds=[10, 100], samples=3, doc="Size")
    throughput = bn.ResultFloat(units="MB/s", doc="Throughput")

    def benchmark(self):
        self.throughput = float("nan") if self.size < 20 else self.size * 0.5


@pytest.fixture(scope="module", name="res_1d")
def fixture_res_1d():
    run_cfg = run_cfg_with(repeats=3)
    bench = CurveBench().to_bench(run_cfg)
    return bench.plot_sweep(
        "curve_1d", input_vars=["size"], result_vars=["throughput"], run_cfg=run_cfg
    )


@pytest.fixture(scope="module", name="res_cat")
def fixture_res_cat():
    run_cfg = run_cfg_with(repeats=2)
    bench = CurveCatBench().to_bench(run_cfg)
    return bench.plot_sweep(
        "curve_cat",
        input_vars=["size", "backend"],
        result_vars=["throughput"],
        run_cfg=run_cfg,
    )


class TestCurveResult:
    def test_to_curve_returns_curve_and_spread(self, res_1d):
        """With repeats>1, to_curve yields an Overlay holding a Curve plus a Spread band."""
        plot = res_1d.to_curve()
        assert plot is not None
        overlay = unwrap_hv(plot)
        assert isinstance(overlay, hv.Overlay)
        curves = [el for el in overlay if isinstance(el, hv.Curve)]
        spreads = [el for el in overlay if isinstance(el, hv.Spread)]
        assert len(curves) == 1
        assert len(spreads) == 1

    def test_curve_dims_and_label(self, res_1d):
        """The Curve uses the input var as kdim, the result var as vdim and label."""
        overlay = unwrap_hv(res_1d.to_curve())
        curve = next(el for el in overlay if isinstance(el, hv.Curve))
        assert [d.name for d in curve.kdims] == ["size"]
        assert [d.name for d in curve.vdims] == ["throughput"]
        assert curve.label == "throughput"
        spread = next(el for el in overlay if isinstance(el, hv.Spread))
        assert [d.name for d in spread.vdims] == ["throughput", "throughput_std"]

    def test_to_plot_delegates_to_curve(self, res_1d):
        result = CurveResult.to_plot(res_1d)
        assert result is not None
        assert isinstance(unwrap_hv(result), hv.Overlay)

    def test_to_curve_ds_with_categorical_groupby(self, res_cat):
        """One Curve per category, labelled with the categorical value."""
        ds = res_cat.to_dataset(reduce=ReduceType.REDUCE)
        rv = res_cat.bench_cfg.result_vars[0]
        overlay = res_cat.to_curve_ds(ds, rv)
        assert isinstance(overlay, hv.Overlay)
        labels = sorted(el.label for el in overlay if isinstance(el, hv.Curve))
        assert labels == ["local", "redis"]
        # each category curve keeps the float input on the x-axis
        for el in overlay:
            if isinstance(el, hv.Curve):
                assert [d.name for d in el.kdims] == ["size"]

    def test_to_curve_rejected_without_repeats(self):
        """repeats=1 fails the repeats_range(2, None) filter when override=False."""
        run_cfg = run_cfg_with(repeats=1)
        bench = CurveBench().to_bench(run_cfg)
        res = bench.plot_sweep(
            "curve_r1", input_vars=["size"], result_vars=["throughput"], run_cfg=run_cfg
        )
        result = res.to_curve(override=False)
        assert isinstance(result, pn.pane.Markdown)

    def test_to_curve_nan_input_does_not_crash(self):
        """A NaN result for one sweep point still produces a Curve overlay."""
        run_cfg = run_cfg_with(repeats=2)
        bench = CurveNanBench().to_bench(run_cfg)
        res = bench.plot_sweep(
            "curve_nan", input_vars=["size"], result_vars=["throughput"], run_cfg=run_cfg
        )
        plot = res.to_curve()
        assert plot is not None
        overlay = unwrap_hv(plot)
        assert isinstance(overlay, hv.Overlay)
        assert any(isinstance(el, hv.Curve) for el in overlay)
