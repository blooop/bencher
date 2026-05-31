"""Tests for the collect/render split: Bench.collect, save/load, render_report, CLI."""

import gc
import tempfile
import unittest
from pathlib import Path

from bencher import Bench, BenchRunCfg, render_report, save_result, load_result
from bencher.render import main as render_main
from bencher.example.benchmark_data import ExampleBenchCfg


def _count_plot_objects() -> int:
    """Count live holoviews/bokeh *instances* (not modules)."""
    n = 0
    for o in gc.get_objects():
        mod = getattr(type(o), "__module__", "")
        if isinstance(mod, str) and mod.startswith(("holoviews.", "bokeh.")):
            n += 1
    return n


def _make_bench() -> Bench:
    return Bench("test_render", ExampleBenchCfg())


class TestCollect(unittest.TestCase):
    def test_collect_builds_no_report_tabs(self):
        bench = _make_bench()
        res = bench.collect(
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=BenchRunCfg(repeats=1),
            title="collect_no_tabs",
        )
        self.assertIsNotNone(res)
        self.assertIsNotNone(res.ds)
        # The defining property: collection appends nothing to the report.
        self.assertEqual(len(bench.report.pane), 0)

    def test_collect_constructs_far_fewer_objects_than_render(self):
        """collect() must build dramatically fewer holoviews/bokeh objects than a render.

        A full plot build creates dozens-to-hundreds of element objects per
        result; collect() should create ~none. Measured in one process so the
        comparison is apples-to-apples (object counts accumulate across tests).
        """
        gc.collect()
        b_collect = _make_bench()
        base = _count_plot_objects()
        b_collect.collect(
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=BenchRunCfg(repeats=1),
            title="collect_objs",
        )
        collect_delta = _count_plot_objects() - base

        gc.collect()
        b_render = _make_bench()
        base2 = _count_plot_objects()
        b_render.plot_sweep(
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=BenchRunCfg(repeats=1),
            title="render_objs",
        )
        render_delta = _count_plot_objects() - base2

        self.assertLess(
            collect_delta,
            max(10, render_delta // 4),
            f"collect built {collect_delta} plot objects vs render {render_delta}",
        )

    def test_plot_sweep_auto_plot_false_matches_collect(self):
        bench = _make_bench()
        res = bench.plot_sweep(
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=BenchRunCfg(repeats=1),
            title="auto_plot_false",
            auto_plot=False,
        )
        self.assertIsNotNone(res)
        self.assertEqual(len(bench.report.pane), 0)

    def test_plot_sweep_auto_plot_true_builds_report(self):
        bench = _make_bench()
        bench.plot_sweep(
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=BenchRunCfg(repeats=1),
            title="auto_plot_true",
        )
        self.assertGreater(len(bench.report.pane), 0)

    def test_collect_rejects_explicit_auto_plot(self):
        bench = _make_bench()
        with self.assertRaises(TypeError):
            bench.collect(
                input_vars=[ExampleBenchCfg.param.theta],
                result_vars=[ExampleBenchCfg.param.out_sin],
                auto_plot=True,
            )


class TestSaveLoadRender(unittest.TestCase):
    def _collect(self, bench: Bench):
        return bench.collect(
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=BenchRunCfg(repeats=1),
            title="roundtrip",
        )

    def test_save_load_roundtrip(self):
        bench = _make_bench()
        res = self._collect(bench)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.pkl"
            save_result(res, path)
            self.assertTrue(path.exists())
            loaded = load_result(path)
            self.assertIsNotNone(loaded.ds)
            # Dataset round-trips with identical variables.
            self.assertEqual(set(loaded.ds.data_vars), set(res.ds.data_vars))

    def test_render_report_from_object(self):
        bench = _make_bench()
        res = self._collect(bench)
        with tempfile.TemporaryDirectory() as tmp:
            out = render_report(res, tmp)
            self.assertTrue(Path(out).exists())
            self.assertGreater(Path(out).stat().st_size, 0)

    def test_render_report_from_path(self):
        bench = _make_bench()
        res = self._collect(bench)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.pkl"
            save_result(res, path)
            out_dir = Path(tmp) / "report"
            out = render_report(path, out_dir)
            self.assertTrue(Path(out).exists())
            self.assertTrue(any(out_dir.rglob("*.html")))

    def test_cli_main(self):
        bench = _make_bench()
        res = self._collect(bench)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.pkl"
            save_result(res, path)
            out_dir = Path(tmp) / "report"
            rc = render_main([str(path), str(out_dir)])
            self.assertEqual(rc, 0)
            self.assertTrue(any(out_dir.rglob("*.html")))

    def test_cli_bad_args(self):
        self.assertEqual(render_main([]), 2)

    def test_cli_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = render_main([str(Path(tmp) / "nope.pkl"), tmp])
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
