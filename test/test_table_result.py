"""Tests for bencher/results/holoview_results/table_result.py (TableResult)."""

import holoviews as hv
import numpy as np
import pytest

import bencher as bn
from bencher.results.holoview_results.table_result import TableResult
from test.helpers import run_cfg_with


class TableBench(bn.ParametrizedSweep):
    """Minimal 1-float sweep for table output."""

    size = bn.FloatSweep(default=50, bounds=[10, 100], samples=3, doc="Size")
    throughput = bn.ResultFloat(units="MB/s", doc="Throughput")

    def benchmark(self):
        self.throughput = self.size * 0.5


class TableNanBench(bn.ParametrizedSweep):
    """Sweep whose worker returns NaN for one input point."""

    size = bn.FloatSweep(default=50, bounds=[10, 100], samples=3, doc="Size")
    throughput = bn.ResultFloat(units="MB/s", doc="Throughput")

    def benchmark(self):
        self.throughput = float("nan") if self.size < 20 else self.size * 0.5


@pytest.fixture(scope="module", name="res_repeats")
def fixture_res_repeats():
    run_cfg = run_cfg_with(repeats=3)
    bench = TableBench().to_bench(run_cfg)
    return bench.plot_sweep(
        "table_repeats", input_vars=["size"], result_vars=["throughput"], run_cfg=run_cfg
    )


@pytest.fixture(scope="module", name="res_single")
def fixture_res_single():
    run_cfg = run_cfg_with(repeats=1)
    bench = TableBench().to_bench(run_cfg)
    return bench.plot_sweep(
        "table_single", input_vars=["size"], result_vars=["throughput"], run_cfg=run_cfg
    )


class TestTableResult:
    def test_to_plot_returns_table(self, res_repeats):
        table = TableResult.to_plot(res_repeats)
        assert isinstance(table, hv.Table)

    def test_table_dims(self, res_repeats):
        """Input vars (plus repeat) are kdims; the result var is a vdim."""
        table = TableResult.to_plot(res_repeats)
        assert [d.name for d in table.kdims] == ["size", "repeat"]
        assert [d.name for d in table.vdims] == ["throughput"]

    def test_table_row_count(self, res_repeats):
        """One row per sweep sample: 3 sizes x 3 repeats."""
        table = TableResult.to_plot(res_repeats)
        assert len(table) == 9

    def test_table_values_match_worker_output(self, res_repeats):
        """Table rows hold the values computed by benchmark()."""
        table = TableResult.to_plot(res_repeats)
        sizes = table.dimension_values("size")
        throughputs = table.dimension_values("throughput")
        np.testing.assert_allclose(throughputs, sizes * 0.5)

    def test_table_squeezes_single_repeat(self, res_single):
        """With repeats=1 the repeat dim is squeezed out of the kdims."""
        table = TableResult.to_plot(res_single)
        assert isinstance(table, hv.Table)
        assert [d.name for d in table.kdims] == ["size"]
        assert len(table) == 3

    def test_table_nan_input_does_not_crash(self):
        """A NaN result value still appears as a row in the table."""
        run_cfg = run_cfg_with(repeats=1)
        bench = TableNanBench().to_bench(run_cfg)
        res = bench.plot_sweep(
            "table_nan", input_vars=["size"], result_vars=["throughput"], run_cfg=run_cfg
        )
        table = TableResult.to_plot(res)
        assert isinstance(table, hv.Table)
        assert len(table) == 3
        values = table.dimension_values("throughput")
        assert np.isnan(values).sum() == 1
