"""Tests for the collect/render split: Bench.collect, save/load, render_report, CLI."""

import gc
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bencher import Bench, BenchRunCfg, render_report, save_result, load_result
from bencher.render import main as render_main, _prog
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

    def test_run_cfg_auto_plot_false_is_honored(self):
        """auto_plot=None (default) must defer to run_cfg.auto_plot, so a caller
        can disable plotting once on the run_cfg and have nested plot_sweep
        calls honour it (without passing auto_plot to each one)."""
        bench = _make_bench()
        run_cfg = BenchRunCfg(repeats=1)
        run_cfg.auto_plot = False
        bench.plot_sweep(
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=run_cfg,
            title="run_cfg_auto_plot_false",
        )
        self.assertEqual(len(bench.report.pane), 0)

    def test_collect_rejects_explicit_auto_plot(self):
        bench = _make_bench()
        with self.assertRaises(TypeError):
            bench.collect(
                input_vars=[ExampleBenchCfg.param.theta],
                result_vars=[ExampleBenchCfg.param.out_sin],
                auto_plot=True,
            )


class TestCollectParity(unittest.TestCase):
    """Layer A: collect() must compute the same artifacts as plot_sweep().

    The split is only safe to rely on if disabling auto_plot changes *nothing*
    about the computed result. ExampleBenchCfg is deterministic (``noisy``
    defaults to False), so the two paths must produce byte-identical datasets.
    """

    PARITY_KWARGS = dict(
        input_vars=[ExampleBenchCfg.param.theta],
        result_vars=[ExampleBenchCfg.param.out_sin, ExampleBenchCfg.param.out_cos],
        title="collect_parity",
    )

    def test_collect_dataset_matches_plot_sweep(self):
        import xarray as xr

        bench_plot, bench_collect = _make_bench(), _make_bench()
        res_plot = bench_plot.plot_sweep(run_cfg=BenchRunCfg(repeats=2), **self.PARITY_KWARGS)
        res_collect = bench_collect.collect(run_cfg=BenchRunCfg(repeats=2), **self.PARITY_KWARGS)

        # plot_sweep built a report tab; collect built none. The *data* is equal.
        self.assertGreater(len(bench_plot.report.pane), 0)
        self.assertEqual(len(bench_collect.report.pane), 0)
        xr.testing.assert_equal(res_collect.ds, res_plot.ds)
        self.assertEqual(set(res_collect.ds.data_vars), set(res_plot.ds.data_vars))

    def test_collect_regression_report_matches_plot_sweep(self):
        res_plot = _make_bench().plot_sweep(run_cfg=BenchRunCfg(repeats=2), **self.PARITY_KWARGS)
        res_collect = _make_bench().collect(run_cfg=BenchRunCfg(repeats=2), **self.PARITY_KWARGS)
        # Regression detection runs during collection too; without over_time both
        # paths leave it at the default (None).
        self.assertEqual(
            getattr(res_collect, "regression_report", None),
            getattr(res_plot, "regression_report", None),
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

    def test_save_result_preserves_object_index(self):
        """save_result must strip object_index for pickling but leave the live
        object unchanged (it can hold non-pickleable ResultReference objects)."""
        bench = _make_bench()
        res = self._collect(bench)
        # Inject a sentinel (object) so the invariant is tested deterministically
        # regardless of whether the benchmark produced reference results.
        sentinel = [object(), object()]
        res.object_index = sentinel
        with tempfile.TemporaryDirectory() as tmp:
            save_result(res, Path(tmp) / "result.pkl")
        # Same list identity and contents after saving.
        self.assertIs(res.object_index, sentinel)
        self.assertEqual(len(res.object_index), 2)

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

    def test_cli_render_failure_returns_1(self):
        """A render failure must be caught by the CLI guard and reported as exit
        code 1 (not propagated), with the error logged."""
        bench = _make_bench()
        res = self._collect(bench)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.pkl"
            save_result(res, path)
            out_dir = Path(tmp) / "report"
            with (
                mock.patch("bencher.render.render_report", side_effect=RuntimeError("boom")),
                self.assertLogs("bencher.render", level="ERROR") as cm,
            ):
                rc = render_main([str(path), str(out_dir)])
            self.assertEqual(rc, 1)
            self.assertTrue(any("boom" in line for line in cm.output))

    def test_cli_bad_args(self):
        self.assertEqual(render_main([]), 2)

    def test_cli_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = render_main([str(Path(tmp) / "nope.pkl"), tmp])
            self.assertEqual(rc, 2)

    def test_cli_render_with_json(self):
        import json

        bench = _make_bench()
        res = self._collect(bench)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.pkl"
            save_result(res, path)
            out_dir = Path(tmp) / "report"
            json_path = Path(tmp) / "result.json"
            rc = render_main([str(path), str(out_dir), "--json", str(json_path)])
            self.assertEqual(rc, 0)
            self.assertTrue(any(out_dir.rglob("*.html")))
            self.assertTrue(json_path.exists())
            self.assertEqual(json.loads(json_path.read_text())["schema_version"], 1)

    def test_cli_compare(self):
        import json

        bench_a, bench_b = _make_bench(), _make_bench()
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.pkl"
            b = Path(tmp) / "b.pkl"
            save_result(self._collect(bench_a), a)
            save_result(self._collect(bench_b), b)
            cmp_path = Path(tmp) / "cmp.json"
            rc = render_main(["compare", str(a), str(b), "--json", str(cmp_path)])
            self.assertEqual(rc, 0)
            self.assertTrue(cmp_path.exists())
            self.assertIn("summary", json.loads(cmp_path.read_text()))

    def test_cli_compare_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = render_main(
                [
                    "compare",
                    str(Path(tmp) / "nope.pkl"),
                    str(Path(tmp) / "x.pkl"),
                    "--json",
                    str(Path(tmp) / "out.json"),
                ]
            )
            self.assertEqual(rc, 2)

    def test_cli_compare_value_error_surfaced(self):
        """A ValueError from compare (e.g. no shared metrics) must be printed to
        stderr so the user sees why, not only logged generically."""
        import io
        import contextlib

        bench_a, bench_b = _make_bench(), _make_bench()
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.pkl"
            b = Path(tmp) / "b.pkl"
            save_result(self._collect(bench_a), a)
            save_result(self._collect(bench_b), b)
            stderr = io.StringIO()
            with (
                mock.patch(
                    "bencher.report_export.comparison_to_json",
                    side_effect=ValueError("no comparable scalar result variables"),
                ),
                contextlib.redirect_stderr(stderr),
            ):
                rc = render_main(["compare", str(a), str(b), "--json", str(Path(tmp) / "c.json")])
            self.assertEqual(rc, 1)
            self.assertIn("no comparable scalar result variables", stderr.getvalue())

    def test_prog_name_is_invocation_aware(self):
        """Usage/help shows ``bencher`` under the console script and the
        explicit module form otherwise, so the displayed command is runnable."""
        with mock.patch("bencher.render.sys.argv", ["/usr/local/bin/bencher", "--help"]):
            self.assertEqual(_prog(), "bencher")
        with mock.patch("bencher.render.sys.argv", ["/path/to/render.py"]):
            self.assertEqual(_prog(), "python -m bencher.render")

    def test_save_emit_json_opt_in(self):
        """BenchReport.save(emit_json=...) writes result.json next to the HTML."""
        import json

        bench = _make_bench()
        res = self._collect(bench)
        bench.report.append_result(res)
        with tempfile.TemporaryDirectory() as tmp:
            bench.report.save(directory=tmp, emit_json=True)
            matches = list(Path(tmp).rglob("result.json"))
            self.assertTrue(matches)
            self.assertEqual(json.loads(matches[0].read_text())["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
