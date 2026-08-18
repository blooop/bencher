"""Tests for the enriched plot-selection signature fields on PltCntCfg (A2 Phase S1).

Each new field (has_time, time_steps, result_kinds, cat_levels, samples_per_point)
is asserted on small synthetic sweeps; the existing counts must be unchanged.
"""

import unittest
from datetime import datetime

import numpy as np
import xarray as xr

import bencher as bn
from bencher.bench_cfg import BenchCfg, TimeCfg
from bencher.plotting.plt_cnt_cfg import PltCntCfg, _samples_per_point, result_kind
from bencher.variables.time import TimeEvent, TimeSnapshot
from test.helpers import run_cfg_with


class CatFloat(bn.ParametrizedSweep):
    kind = bn.StringSweep(["a", "b", "c"])
    x = bn.FloatSweep(default=0, bounds=[0, 2], samples=3)
    value = bn.ResultFloat(units="m")
    ok = bn.ResultBool()

    def benchmark(self):
        self.value = self.x * (2.0 if self.kind == "a" else 3.0)
        self.ok = self.value > 1.0


def run_sweep(repeats: int = 1, over_time: bool = False):
    bench = bn.Bench("test_plt_cnt_cfg_signature", CatFloat())
    # clear_history keeps over_time runs hermetic: exactly one snapshot per test run
    return bench.plot_sweep(
        "sweep",
        input_vars=[CatFloat.param.kind, CatFloat.param.x],
        result_vars=[CatFloat.param.value, CatFloat.param.ok],
        run_cfg=run_cfg_with(repeats, over_time=over_time, clear_history=over_time),
    )


class TestSignatureFields(unittest.TestCase):
    def test_counts_unchanged(self):
        cfg = run_sweep().plt_cnt_cfg
        self.assertEqual(cfg.float_cnt, 1)
        self.assertEqual(cfg.cat_cnt, 1)
        self.assertEqual(cfg.panel_cnt, 0)
        self.assertEqual(cfg.inputs_cnt, 2)

    def test_result_kinds(self):
        cfg = run_sweep().plt_cnt_cfg
        self.assertEqual(cfg.result_kinds, {"value": "float", "ok": "bool"})

    def test_cat_levels(self):
        cfg = run_sweep().plt_cnt_cfg
        self.assertEqual(cfg.cat_levels, {"kind": 3})

    def test_no_time(self):
        cfg = run_sweep().plt_cnt_cfg
        self.assertFalse(cfg.has_time)
        self.assertEqual(cfg.time_steps, 0)

    def test_over_time(self):
        res = run_sweep(over_time=True)
        cfg = res.plt_cnt_cfg
        self.assertTrue(cfg.has_time)
        # clear_history=True makes this the first snapshot: exactly one time step
        self.assertEqual(cfg.time_steps, 1)
        self.assertEqual(cfg.time_steps, res.ds.sizes["over_time"])

    def test_samples_per_point_full(self):
        cfg = run_sweep(repeats=2).plt_cnt_cfg
        self.assertEqual(cfg.samples_per_point, 2)
        self.assertEqual(cfg.repeats, 2)

    def test_no_dataset_defaults(self):
        res = run_sweep()
        cfg = PltCntCfg.generate_plt_cnt_cfg(res.bench_cfg)
        self.assertFalse(cfg.has_time)
        self.assertEqual(cfg.time_steps, 0)
        self.assertEqual(cfg.samples_per_point, 0)
        # config-derived fields are still populated without a dataset
        self.assertEqual(cfg.cat_levels, {"kind": 3})
        self.assertEqual(cfg.result_kinds, {"value": "float", "ok": "bool"})

    def test_time_inputs_without_over_time(self):
        # TimeSnapshot/TimeEvent inputs are injected by the framework when over_time
        # is set, so build the config directly to isolate the input-var path:
        # has_time derives purely from the config, and time_steps stays 0 because
        # there is no over_time axis (no dataset at all here).
        for time_var in (TimeSnapshot(datetime(2026, 1, 1)), TimeEvent("v1.0")):
            time_var.name = "time"
            bench_cfg = BenchCfg(
                input_vars=[time_var],
                result_vars=[CatFloat.param.value],
                time=TimeCfg(over_time=False),
            )
            cfg = PltCntCfg.generate_plt_cnt_cfg(bench_cfg)
            self.assertTrue(cfg.has_time)
            self.assertEqual(cfg.time_steps, 0)
            self.assertEqual(cfg.result_kinds, {"value": "float"})


class TestSamplesPerPoint(unittest.TestCase):
    def test_nan_holes_reduce_count(self):
        data = np.ones((2, 3))
        data[0, 1] = np.nan  # one missing repeat at one sweep point
        ds = xr.Dataset({"value": (("x", "repeat"), data)})
        self.assertEqual(_samples_per_point(ds), 2)
        data[1, 1] = np.nan
        data[1, 2] = np.nan
        ds = xr.Dataset({"value": (("x", "repeat"), data)})
        self.assertEqual(_samples_per_point(ds), 1)

    def test_no_repeat_dim(self):
        ds = xr.Dataset({"value": (("x",), np.ones(3))})
        self.assertEqual(_samples_per_point(ds), 1)

    def test_repeat_dim_without_repeat_vars(self):
        # a structural repeat axis whose data vars don't carry it behaves the same
        # as no repeat axis at all: one sample per point, not "no samples"
        ds = xr.Dataset({"value": (("x",), np.ones(3))}, coords={"repeat": [1, 2]})
        self.assertIn("repeat", ds.dims)
        self.assertEqual(_samples_per_point(ds), 1)

    def test_zero_size_dim(self):
        # a zero-size sweep dim leaves no points to count: 0, not a ValueError
        # from reducing an empty array
        ds = xr.Dataset({"value": (("x", "repeat"), np.ones((0, 3)))})
        self.assertEqual(_samples_per_point(ds), 0)

    def test_sentinel_missing_counted(self):
        # object-backed result types store misses as the "NAN" sentinel, which
        # notnull() would count as present; the per-variable sentinel must not
        img = bn.ResultImage()
        img.name = "img"
        data = np.array([["a.png", "b.png", "NAN"]], dtype=object)
        ds = xr.Dataset({"img": (("x", "repeat"), data)})
        self.assertEqual(_samples_per_point(ds, [img]), 2)
        # without the result var to identify the sentinel, NaN is all we can test
        self.assertEqual(_samples_per_point(ds), 3)

    def test_over_time_history_padding_ignored(self):
        # when repeats grow between over_time runs, historical steps are NaN-padded;
        # only the latest step reflects the current run's samples
        data = np.full((2, 2, 3), np.nan)
        data[1] = 1.0  # latest step: full repeat coverage
        data[0, :, 0] = 1.0  # historical step recorded with repeats=1
        ds = xr.Dataset({"value": (("over_time", "x", "repeat"), data)})
        self.assertEqual(_samples_per_point(ds), 3)

    def test_empty_dataset(self):
        self.assertEqual(_samples_per_point(xr.Dataset()), 0)


class TestResultKind(unittest.TestCase):
    def test_kind_order(self):
        self.assertEqual(result_kind(bn.ResultBool()), "bool")
        self.assertEqual(result_kind(bn.ResultFloat()), "float")
        self.assertEqual(result_kind(bn.ResultImage()), "image")
        self.assertEqual(result_kind(bn.ResultVideo()), "video")
        self.assertEqual(result_kind(bn.ResultString()), "string")
        self.assertEqual(result_kind(bn.ResultContainer()), "container")
        self.assertEqual(result_kind(object()), "unknown")

    def test_rerun_kind_before_container(self):
        from bencher.variables.results import ResultRerun

        self.assertEqual(result_kind(ResultRerun()), "rerun")


if __name__ == "__main__":
    unittest.main()
