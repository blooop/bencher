"""Tests for bencher/results/holoview_results/band_result.py (BandResult)."""

import math
from types import SimpleNamespace

import holoviews as hv
import numpy as np
import pytest

import bencher as bn
from bencher.results.bench_result_base import ReduceType
from bencher.results.holoview_results.band_result import BandResult
from test.helpers import run_cfg_with, unwrap_hv


def plot_opts(overlay: hv.Overlay) -> dict:
    return overlay.opts.get("plot").kwargs


class BandBench(bn.ParametrizedSweep):
    """Minimal 1-float sweep; the repeat dimension supplies the percentile sample pool."""

    size = bn.FloatSweep(default=50, bounds=[10, 100], samples=3, doc="Size")
    throughput = bn.ResultFloat(units="MB/s", doc="Throughput")

    def benchmark(self):
        self.throughput = self.size * 0.5 + math.sin(self.size)


class BandCatBench(bn.ParametrizedSweep):
    """1 float + 1 categorical: the categorical dim is flattened into the sample pool."""

    size = bn.FloatSweep(default=50, bounds=[10, 100], samples=3, doc="Size")
    backend = bn.StringSweep(["redis", "local"], doc="Backend")
    throughput = bn.ResultFloat(units="MB/s", doc="Throughput")

    def benchmark(self):
        base = {"redis": 1.0, "local": 2.0}[self.backend]
        self.throughput = self.size * base


class BandNanBench(bn.ParametrizedSweep):
    """Sweep whose worker returns NaN for one input point."""

    size = bn.FloatSweep(default=50, bounds=[10, 100], samples=3, doc="Size")
    throughput = bn.ResultFloat(units="MB/s", doc="Throughput")

    def benchmark(self):
        self.throughput = float("nan") if self.size < 20 else self.size * 0.5


class BandVecBench(bn.ParametrizedSweep):
    """Vector (non-scalar) result — outside BandResult's SCALAR_RESULT_TYPES filter."""

    size = bn.FloatSweep(default=50, bounds=[10, 100], samples=3, doc="Size")
    vec = bn.ResultVec(size=2, units="m", doc="Vector result")

    def benchmark(self):
        self.vec = [self.size, self.size * 2]


class BandTimeBench(bn.ParametrizedSweep):
    """Sweep run over several time snapshots to exercise the over_time band path."""

    size = bn.FloatSweep(default=50, bounds=[10, 100], samples=3, doc="Size")
    throughput = bn.ResultFloat(units="MB/s", doc="Throughput")

    offset = 0.0

    def benchmark(self):
        self.throughput = self.size * 0.5 + self.offset


@pytest.fixture(scope="module", name="res_1d")
def fixture_res_1d():
    run_cfg = run_cfg_with(repeats=5)
    bench = BandBench().to_bench(run_cfg)
    return bench.plot_sweep(
        "band_1d", input_vars=["size"], result_vars=["throughput"], run_cfg=run_cfg
    )


@pytest.fixture(scope="module", name="res_cat")
def fixture_res_cat():
    run_cfg = run_cfg_with(repeats=2)
    bench = BandCatBench().to_bench(run_cfg)
    return bench.plot_sweep(
        "band_cat",
        input_vars=["size", "backend"],
        result_vars=["throughput"],
        run_cfg=run_cfg,
    )


@pytest.fixture(scope="module", name="res_time")
def fixture_res_time():
    benchable = BandTimeBench()
    run_cfg = bn.BenchRunCfg(
        over_time=True, repeats=2, cache_results=False, cache_samples=False, auto_plot=False
    )
    bench = benchable.to_bench(run_cfg)
    res = None
    for i in range(3):
        benchable.offset = i * 1.0
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "band_time",
            input_vars=["size"],
            result_vars=["throughput"],
            run_cfg=run_cfg,
            time_src=f"2026-06-{10 + i:02d} snap{i:04d}",
        )
    return res


class TestBandResult:
    def test_to_band_overlay_composition(self, res_1d):
        """to_band yields two percentile Areas, a median Curve and a samples Scatter."""
        plot = res_1d.to_band()
        assert plot is not None
        overlay = unwrap_hv(plot)
        assert isinstance(overlay, hv.Overlay)
        # exact types: hv.Area is a subclass of hv.Curve, so isinstance would double count
        assert len([el for el in overlay if type(el) is hv.Area]) == 2
        assert len([el for el in overlay if type(el) is hv.Curve]) == 1
        assert len([el for el in overlay if type(el) is hv.Scatter]) == 1

    def test_band_labels_and_dims(self, res_1d):
        """Element labels and kdims/vdims reflect the input and result variables."""
        overlay = unwrap_hv(res_1d.to_band())
        labels = sorted(el.label for el in overlay)
        assert labels == sorted(["10th–90th pctl", "25th–75th pctl", "median", "samples"])
        for el in overlay:
            assert [d.name for d in el.kdims] == ["size"]
        outer = next(el for el in overlay if el.label == "10th–90th pctl")
        assert [d.name for d in outer.vdims] == ["throughput_p10", "throughput_p90"]
        median = next(el for el in overlay if el.label == "median")
        assert [d.name for d in median.vdims] == ["throughput"]

    def test_band_title_and_ylabel(self, res_1d):
        """Default title names var vs x-axis; ylabel includes the units."""
        overlay = unwrap_hv(res_1d.to_band())
        opts = plot_opts(overlay)
        assert opts["title"] == "throughput vs size (aggregated over repeat)"
        assert opts["ylabel"] == "throughput [MB/s]"

    def test_band_explicit_title_preserved(self, res_1d):
        ds = res_1d.to_dataset(reduce=ReduceType.NONE)
        rv = res_1d.bench_cfg.result_vars[0]
        overlay = res_1d.to_band_ds(ds, rv, title="my custom title")
        assert plot_opts(overlay)["title"] == "my custom title"

    def test_band_enable_scatter_false(self, res_1d):
        """enable_scatter=False drops the samples Scatter layer."""
        ds = res_1d.to_dataset(reduce=ReduceType.NONE)
        rv = res_1d.bench_cfg.result_vars[0]
        overlay = res_1d.to_band_ds(ds, rv, enable_scatter=False)
        assert not any(isinstance(el, hv.Scatter) for el in overlay)
        assert any(isinstance(el, hv.Curve) for el in overlay)

    def test_band_categorical_flattened_into_samples(self, res_cat):
        """A categorical dim becomes part of the sample pool; the float stays on x."""
        overlay = unwrap_hv(res_cat.to_band())
        assert isinstance(overlay, hv.Overlay)
        for el in overlay:
            assert [d.name for d in el.kdims] == ["size"]
        assert plot_opts(overlay)["title"] == "throughput vs size (aggregated over backend)"

    def test_band_over_time_uses_time_axis(self, res_time):
        """With over_time history, the band x-axis is the over_time dimension."""
        ds = res_time.to_dataset(reduce=ReduceType.NONE)
        rv = res_time.bench_cfg.result_vars[0]
        overlay = res_time.to_band_ds(ds, rv)
        assert isinstance(overlay, hv.Overlay)
        for el in overlay:
            assert [d.name for d in el.kdims] == ["over_time"]
        assert plot_opts(overlay)["title"] == "throughput vs over_time (aggregated over size)"

    def test_band_suppressed_when_regression_overlay_exists(self, res_1d):
        """to_band_ds returns None when the regression overlay already shows the history."""
        ds = res_1d.to_dataset(reduce=ReduceType.NONE)
        rv = res_1d.bench_cfg.result_vars[0]
        original = res_1d.regression_report
        res_1d.regression_report = SimpleNamespace(
            results=[SimpleNamespace(variable="throughput", historical=[1.0, 2.0])]
        )
        try:
            assert res_1d.to_band_ds(ds, rv) is None
        finally:
            res_1d.regression_report = original

    def test_to_band_rejects_non_scalar_result(self):
        """A non-scalar (vector) result is outside SCALAR_RESULT_TYPES, so no band is drawn.

        BandResult's filter accepts any float/cat/repeat shape (repeats>=1 included),
        so the meaningful rejection path is the result type — a vector sweep must not
        silently produce a misleading band overlay.
        """
        run_cfg = run_cfg_with(repeats=3)
        bench = BandVecBench().to_bench(run_cfg)
        res = bench.plot_sweep(
            "band_vec", input_vars=["size"], result_vars=["vec"], run_cfg=run_cfg
        )
        result = res.to(BandResult, override=False)
        assert not isinstance(unwrap_hv(result), hv.Overlay)

    def test_band_nan_input_does_not_crash(self):
        """NaN results survive percentile computation and are masked out of the scatter."""
        run_cfg = run_cfg_with(repeats=3)
        bench = BandNanBench().to_bench(run_cfg)
        res = bench.plot_sweep(
            "band_nan", input_vars=["size"], result_vars=["throughput"], run_cfg=run_cfg
        )
        overlay = unwrap_hv(res.to_band())
        assert isinstance(overlay, hv.Overlay)
        scatter = next(el for el in overlay if isinstance(el, hv.Scatter))
        assert not np.isnan(scatter.dimension_values("throughput")).any()
