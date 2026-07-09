"""Tests for bencher.ci module."""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from bencher.ci import (
    generate_regression_comment,
    parse_performance_summary,
    render_regression_plots,
    warn_on_regressions,
    write_performance_summary,
)
from bencher.regression import (
    RegressionReport,
    RegressionResult,
    detect_percentage,
)
from bencher.variables.results import OptDir


def _result(
    variable: str = "latency",
    regressed: bool = True,
    change_percent: float = 20.0,
    baseline: float = 100.0,
    current: float = 120.0,
    threshold: float = 15.0,
    direction: str = "minimize",
    method: str = "percentage",
) -> RegressionResult:
    return RegressionResult(
        variable=variable,
        method=method,
        regressed=regressed,
        current_value=current,
        baseline_value=baseline,
        change_percent=change_percent,
        threshold=threshold,
        direction=direction,
        details="test",
    )


def _report_with_regressions() -> RegressionReport:
    return RegressionReport(
        results=[
            _result("planning_time", regressed=True, change_percent=25.0),
            _result("planning_success", regressed=False, change_percent=2.0, direction="maximize"),
        ]
    )


# ── write_performance_summary ─────────────────────────────────────────────


class TestWritePerformanceSummary:
    def test_writes_all_results_without_filter(self, tmp_path):
        report = _report_with_regressions()
        path = tmp_path / "summary.txt"
        lines = write_performance_summary(report, path)
        assert len(lines) == 2
        assert path.exists()
        content = path.read_text()
        assert "planning_time" in content
        assert "planning_success" in content

    def test_filters_metrics(self, tmp_path):
        report = _report_with_regressions()
        path = tmp_path / "summary.txt"
        metrics_filter = {"bench/planning_time": 20.0}
        lines = write_performance_summary(
            report, path, metrics_filter=metrics_filter, bench_name="bench"
        )
        assert len(lines) == 1
        assert "bench/planning_time" in lines[0]

    def test_applies_custom_threshold(self, tmp_path):
        report = RegressionReport(
            results=[_result("x", regressed=False, change_percent=12.0)]
        )
        path = tmp_path / "summary.txt"

        lines_strict = write_performance_summary(
            report, path, metrics_filter={"x": 10.0}, append=False
        )
        assert "True" in lines_strict[0]

        lines_loose = write_performance_summary(
            report, path, metrics_filter={"x": 20.0}, append=False
        )
        assert "False" in lines_loose[0]

    def test_appends_by_default(self, tmp_path):
        report = _report_with_regressions()
        path = tmp_path / "summary.txt"
        write_performance_summary(report, path)
        write_performance_summary(report, path)
        content = path.read_text()
        assert content.count("planning_time") == 2

    def test_overwrite_mode(self, tmp_path):
        report = _report_with_regressions()
        path = tmp_path / "summary.txt"
        write_performance_summary(report, path)
        write_performance_summary(report, path, append=False)
        content = path.read_text()
        assert content.count("planning_time") == 1

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "summary.txt"
        report = _report_with_regressions()
        write_performance_summary(report, path)
        assert path.exists()

    def test_empty_report_writes_nothing(self, tmp_path):
        path = tmp_path / "summary.txt"
        lines = write_performance_summary(RegressionReport(), path)
        assert lines == []
        assert not path.exists()

    def test_bench_name_prefix(self, tmp_path):
        report = RegressionReport(results=[_result("x")])
        path = tmp_path / "summary.txt"
        lines = write_performance_summary(report, path, bench_name="my_bench")
        assert lines[0].startswith("my_bench/x|")

    def test_absolute_method_threshold(self, tmp_path):
        r = _result(method="absolute", change_percent=float("nan"))
        r.regressed = True
        report = RegressionReport(results=[r])
        path = tmp_path / "summary.txt"
        lines = write_performance_summary(report, path, metrics_filter={"latency": 50.0})
        assert "True" in lines[0]


# ── render_regression_plots ───────────────────────────────────────────────


class TestRenderRegressionPlots:
    def test_renders_regressed_metrics(self, tmp_path):
        hist = np.array([100.0, 102.0, 98.0, 101.0, 100.5])
        curr = np.array([130.0])
        r = detect_percentage("planning_time", hist, curr, threshold_percent=5.0)
        r.historical = hist
        r.current_samples = curr
        report = RegressionReport(results=[r])
        rendered = render_regression_plots(report, tmp_path)
        assert "planning_time" in rendered
        assert rendered["planning_time"].exists()
        assert rendered["planning_time"].stat().st_size > 500

    def test_skips_non_regressed(self, tmp_path):
        r = _result(regressed=False)
        report = RegressionReport(results=[r])
        rendered = render_regression_plots(report, tmp_path)
        assert rendered == {}

    def test_filter_limits_rendering(self, tmp_path):
        hist = np.array([100.0, 102.0, 98.0, 101.0, 100.5])
        curr = np.array([130.0])
        r1 = detect_percentage("planning_time", hist, curr, threshold_percent=5.0)
        r1.historical = hist
        r1.current_samples = curr
        r2 = detect_percentage("other", hist, curr, threshold_percent=5.0)
        r2.historical = hist
        r2.current_samples = curr
        report = RegressionReport(results=[r1, r2])
        rendered = render_regression_plots(
            report, tmp_path, metrics_filter={"bench/planning_time": 5.0}, bench_name="bench"
        )
        assert "bench/planning_time" in rendered
        assert "bench/other" not in rendered


# ── warn_on_regressions ──────────────────────────────────────────────────


class TestWarnOnRegressions:
    def test_emits_warning_on_regression(self):
        report = _report_with_regressions()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warn_on_regressions(report)
            assert len(w) == 1
            assert "regression" in str(w[0].message).lower()

    def test_no_warning_when_clean(self):
        report = RegressionReport(results=[_result(regressed=False, change_percent=1.0)])
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warn_on_regressions(report)
            assert len(w) == 0

    def test_writes_summary_and_plots(self, tmp_path):
        hist = np.array([100.0, 102.0, 98.0, 101.0, 100.5])
        curr = np.array([130.0])
        r = detect_percentage("planning_time", hist, curr, threshold_percent=5.0)
        r.historical = hist
        r.current_samples = curr
        report = RegressionReport(results=[r])
        summary_path = tmp_path / "summary.txt"
        plot_dir = tmp_path / "plots"
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            warn_on_regressions(
                report, summary_path=summary_path, plot_dir=plot_dir
            )
        assert summary_path.exists()
        assert any(plot_dir.iterdir())


# ── parse_performance_summary ────────────────────────────────────────────


class TestParsePerformanceSummary:
    def test_parses_valid_lines(self, tmp_path):
        path = tmp_path / "summary.txt"
        path.write_text(
            "plan_time|True|+25.00|100|125|15.0|minimize|percentage\n"
            "success|False|+2.00|0.95|0.97|15.0|maximize|percentage\n"
        )
        rows = parse_performance_summary(path)
        assert len(rows) == 2
        assert rows[0]["variable"] == "plan_time"
        assert rows[0]["regressed"] == "True"
        assert rows[1]["variable"] == "success"

    def test_skips_blank_and_malformed_lines(self, tmp_path):
        path = tmp_path / "summary.txt"
        path.write_text(
            "\n"
            "plan_time|True|+25.00|100|125|15.0|minimize|percentage\n"
            "malformed line\n"
            "\n"
        )
        rows = parse_performance_summary(path)
        assert len(rows) == 1


# ── generate_regression_comment ──────────────────────────────────────────


class TestGenerateRegressionComment:
    def _summary_file(self, tmp_path, lines):
        path = tmp_path / "summary.txt"
        path.write_text("\n".join(lines) + "\n")
        return path

    def test_generates_table_with_regressions(self, tmp_path):
        path = self._summary_file(
            tmp_path,
            [
                "plan_time|True|+25.00|100|125|15.0|minimize|percentage",
                "success|False|+2.00|0.95|0.97|15.0|maximize|percentage",
            ],
        )
        md = generate_regression_comment(path, report_url="https://example.com/report")
        assert "<!-- benchmark-regression-comment -->" in md
        assert ":warning: Benchmark Regressions Detected" in md
        assert "| `plan_time`" in md
        assert "| `success`" in md
        assert ":x: **Regression**" in md
        assert "How to proceed" in md
        assert "https://example.com/report" in md

    def test_no_regressions_clean_summary(self, tmp_path):
        path = self._summary_file(
            tmp_path,
            ["latency|False|+3.00|100|103|15.0|minimize|percentage"],
        )
        md = generate_regression_comment(path)
        assert "## Benchmark Performance Summary" in md
        assert ":warning:" not in md
        assert "How to proceed" not in md

    def test_empty_file_returns_empty(self, tmp_path):
        path = self._summary_file(tmp_path, [])
        md = generate_regression_comment(path)
        assert md == ""

    def test_absolute_method_rendering(self, tmp_path):
        path = self._summary_file(
            tmp_path,
            ["throughput|True|nan|100|80|100|maximize|absolute"],
        )
        md = generate_regression_comment(path)
        assert "≥ 100" in md
        assert "below floor" in md

    def test_absolute_minimize_rendering(self, tmp_path):
        path = self._summary_file(
            tmp_path,
            ["latency|True|nan|50|60|50|minimize|absolute"],
        )
        md = generate_regression_comment(path)
        assert "≤ 50" in md
        assert "above ceiling" in md

    def test_plot_links_when_prefix_provided(self, tmp_path):
        path = self._summary_file(
            tmp_path,
            ["plan_time|True|+25.00|100|125|15.0|minimize|percentage"],
        )
        md = generate_regression_comment(
            path,
            plot_url_prefix="https://reports.example.com/regression_plots",
        )
        assert "### Regression Graphs" in md
        assert "https://reports.example.com/regression_plots/plan_time.png" in md

    def test_status_categories(self, tmp_path):
        path = self._summary_file(
            tmp_path,
            [
                "a|True|+25.00|100|125|15.0|minimize|percentage",
                "b|False|+5.00|100|105|15.0|minimize|percentage",
                "c|False|-12.00|100|88|15.0|minimize|percentage",
                "d|False|+12.00|100|112|15.0|maximize|percentage",
            ],
        )
        md = generate_regression_comment(path)
        assert ":x: **Regression**" in md
        assert "Within noise" in md
        assert "Improved" in md

    def test_improvement_detection(self, tmp_path):
        path = self._summary_file(
            tmp_path,
            ["latency|False|-12.00|100|88|15.0|minimize|percentage"],
        )
        md = generate_regression_comment(path)
        assert ":white_check_mark: Improved" in md

    def test_maximize_improvement(self, tmp_path):
        path = self._summary_file(
            tmp_path,
            ["throughput|False|+12.00|100|112|15.0|maximize|percentage"],
        )
        md = generate_regression_comment(path)
        assert ":white_check_mark: Improved" in md
