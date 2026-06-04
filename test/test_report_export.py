"""Tests for machine-readable result export (bencher.report_export)."""

import json
import tempfile
import unittest
from pathlib import Path

from bencher import (
    Bench,
    BenchRunCfg,
    compare_results,
    comparison_to_json,
    result_to_dict,
    result_to_json,
)
from bencher.regression import RegressionReport, RegressionResult
from bencher.example.benchmark_data import ExampleBenchCfg


def _make_bench() -> Bench:
    return Bench("test_export", ExampleBenchCfg())


def _collect(offset: float = 0.0, result_vars=None):
    """Collect a deterministic theta sweep of out_sin at a constant offset."""
    if result_vars is None:
        result_vars = [ExampleBenchCfg.param.out_sin]
    return _make_bench().collect(
        input_vars=[ExampleBenchCfg.param.theta],
        result_vars=result_vars,
        const_vars=[(ExampleBenchCfg.param.offset, offset)],
        run_cfg=BenchRunCfg(repeats=1),
        title=f"export_offset_{offset}",
    )


def _is_jsonable(obj) -> bool:
    """True if the object round-trips through strict JSON (no NaN/inf/numpy)."""
    try:
        json.loads(json.dumps(obj, allow_nan=False))
        return True
    except (ValueError, TypeError):
        return False


class TestResultToDict(unittest.TestCase):
    def test_schema_and_metrics(self):
        res = _collect()
        data = result_to_dict(res)
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["bench_name"], "test_export")
        self.assertFalse(data["over_time"])
        names = {m["variable"] for m in data["metrics"]}
        self.assertIn("out_sin", names)
        out_sin = next(m for m in data["metrics"] if m["variable"] == "out_sin")
        self.assertEqual(out_sin["units"], "v")
        self.assertEqual(out_sin["direction"], "minimize")

    def test_no_regressions_without_over_time(self):
        data = result_to_dict(_collect())
        self.assertFalse(data["regressions"]["has_regressions"])
        self.assertEqual(data["regressions"]["results"], [])

    def test_output_is_strict_json(self):
        # The whole contract (including any zero-baseline percent -> None) must
        # be strict JSON: no NaN/inf tokens, no numpy scalars.
        self.assertTrue(_is_jsonable(result_to_dict(_collect())))

    def test_result_to_json_writes_file(self):
        res = _collect()
        with tempfile.TemporaryDirectory() as tmp:
            path = result_to_json(res, Path(tmp) / "sub" / "result.json")
            self.assertTrue(path.exists())
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["bench_name"], "test_export")


class TestRegressionDataclassToDict(unittest.TestCase):
    def test_regression_result_to_dict_fields(self):
        r = RegressionResult(
            variable="latency",
            method="percentage",
            regressed=True,
            current_value=12.0,
            baseline_value=10.0,
            change_percent=20.0,
            threshold=10.0,
            direction="minimize",
            details="…",
            band_lower=9.0,
            band_upper=11.0,
        )
        d = r.to_dict()
        self.assertEqual(d["variable"], "latency")
        self.assertTrue(d["regressed"])
        self.assertEqual(d["change_percent"], 20.0)
        self.assertEqual(d["band_lower"], 9.0)
        # Numpy replay arrays must never leak into the dict.
        self.assertNotIn("historical", d)
        self.assertNotIn("current_samples", d)

    def test_non_finite_becomes_none(self):
        r = RegressionResult(
            variable="x",
            method="percentage",
            regressed=False,
            current_value=1.0,
            baseline_value=0.0,
            change_percent=float("inf"),  # zero-baseline division
            threshold=10.0,
            direction="minimize",
            details="",
        )
        self.assertIsNone(r.to_dict()["change_percent"])

    def test_report_to_dict_parity_with_markdown(self):
        regressed = RegressionResult(
            "a", "percentage", True, 12.0, 10.0, 20.0, 10.0, "minimize", ""
        )
        passed = RegressionResult("b", "percentage", False, 10.0, 10.0, 0.0, 10.0, "minimize", "")
        report = RegressionReport(results=[regressed, passed])
        d = report.to_dict()
        self.assertTrue(d["has_regressions"])
        self.assertEqual(len(d["results"]), 2)
        # Every variable named in the markdown table appears in the dict.
        md = report.to_markdown()
        for r in report.results:
            self.assertIn(r.variable, md)
            self.assertIn(r.variable, {x["variable"] for x in d["results"]})


class TestCompareResults(unittest.TestCase):
    def test_regression_detected(self):
        # offset shifts out_sin upward; direction=minimize => increase regresses.
        cmp = compare_results(_collect(offset=0.0), _collect(offset=0.2))
        out_sin = next(m for m in cmp["metrics"] if m["variable"] == "out_sin")
        self.assertEqual(out_sin["verdict"], "regressed")
        self.assertTrue(out_sin["regressed"])
        self.assertGreater(out_sin["change_percent"], 0)
        self.assertEqual(cmp["summary"]["regressed"], 1)

    def test_improvement_detected(self):
        cmp = compare_results(_collect(offset=0.2), _collect(offset=0.0))
        out_sin = next(m for m in cmp["metrics"] if m["variable"] == "out_sin")
        self.assertEqual(out_sin["verdict"], "improved")
        self.assertFalse(out_sin["regressed"])
        self.assertEqual(cmp["summary"]["improved"], 1)

    def test_unchanged(self):
        cmp = compare_results(_collect(offset=0.1), _collect(offset=0.1))
        out_sin = next(m for m in cmp["metrics"] if m["variable"] == "out_sin")
        self.assertEqual(out_sin["verdict"], "unchanged")
        self.assertEqual(cmp["summary"]["unchanged"], 1)

    def test_no_shared_metric_raises(self):
        base = _collect(result_vars=[ExampleBenchCfg.param.out_sin])
        cand = _collect(result_vars=[ExampleBenchCfg.param.out_cos])
        with self.assertRaises(ValueError):
            compare_results(base, cand)

    def test_comparison_is_strict_json(self):
        cmp = compare_results(_collect(offset=0.0), _collect(offset=0.2))
        self.assertTrue(_is_jsonable(cmp))

    def test_comparison_to_json_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = comparison_to_json(
                _collect(offset=0.0), _collect(offset=0.2), Path(tmp) / "cmp.json"
            )
            self.assertTrue(path.exists())
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema_version"], 1)
            self.assertIn("summary", loaded)


if __name__ == "__main__":
    unittest.main()
