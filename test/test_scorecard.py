"""Tests for bencher.scorecard."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bencher.scorecard import (
    ReportLayout,
    ScorecardConfig,
    build_cell,
    cell_verdict,
    discover_report_links,
    discover_summaries,
    generate_scorecard,
    metric_columns,
    unify_metric_names,
)

# A generic project config: two Performance benchmarks that share a metric core,
# a Startup benchmark using an aliased metric name, plus fallback/metric-less
# cases. No project-specific vocabulary — the scorecard machinery is generic.
CONFIG = ScorecardConfig(
    registry={
        "test_bench_latency": ("Performance", "Latency", "Request latency sweep."),
        "test_bench_throughput": ("Performance", "Throughput", "Throughput sweep."),
        "test_bench_startup": ("Startup", "Startup", "Process startup timing."),
        "test_bench_gallery": ("Rendering", "Gallery", "Image-only render sweep."),
    },
    aliases={"wall_time": "runtime"},
    percent_metrics=frozenset({"completion"}),
    layout=ReportLayout(root="benchmarks"),
)


def _metric(variable, direction, units, series, optimal_value=None):
    return {
        "variable": variable,
        "units": units,
        "direction": direction,
        "optimal_value": optimal_value,
        "optimal_inputs": {},
        "series": series,
    }


def _pt(time_event, mean, std, n=4):
    return {"time_event": time_event, "mean": mean, "std": std, "n": n}


def _reg(variable, direction, regressed, baseline, current, change, threshold=15.0):
    return {
        "variable": variable,
        "method": "percentage",
        "regressed": regressed,
        "current_value": current,
        "baseline_value": baseline,
        "change_percent": change,
        "threshold": threshold,
        "direction": direction,
    }


def _write_summary(reports_dir, tag, bench_name, metrics, regressions, time_event):
    tag_dir = reports_dir / "benchmarks" / tag
    tag_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": 1,
        "bench_name": bench_name,
        "provenance": {"time_event": time_event},
        "input_vars": [],
        "over_time": True,
        "metrics": metrics,
        "regressions": {
            "has_regressions": any(r["regressed"] for r in regressions),
            "results": regressions,
        },
    }
    (tag_dir / f"{bench_name}.summary.json").write_text(json.dumps(data))


@pytest.fixture()
def mock_reports(tmp_path: Path) -> Path:
    """Create mock summary.json files across categories and verdicts."""
    t0 = "2026-06-10 09:00 0000000"
    t1 = "2026-06-11 10:00 abc1234"

    # Performance/Latency: one of each verdict.
    _write_summary(
        tmp_path,
        "test_bench_latency",
        "Latency",
        metrics=[
            _metric("success", "maximize", "ratio", [_pt(t0, 1.0, 0.0), _pt(t1, 0.75, 0.43)]),
            _metric("runtime", "minimize", "s", [_pt(t0, 5.0, 0.2), _pt(t1, 4.0, 0.2)]),
            _metric("accuracy", "maximize", "", [_pt(t0, 0.9, 0.01), _pt(t1, 0.92, 0.01)]),
            # No regression entry -> uncolored "trend" verdict + self-computed delta.
            _metric("iterations", "maximize", "", [_pt(t0, 1.5, 0.1), _pt(t1, 2.0, 0.0)]),
        ],
        regressions=[
            _reg("success", "maximize", True, 1.0, 0.75, -25.0),
            _reg("runtime", "minimize", False, 5.0, 4.0, -20.0),
            _reg("accuracy", "maximize", False, 0.9, 0.92, 2.0),
        ],
        time_event=t1,
    )

    # Performance/Throughput: shares the success+runtime core so columns align.
    _write_summary(
        tmp_path,
        "test_bench_throughput",
        "Throughput",
        metrics=[
            _metric("success", "maximize", "ratio", [_pt(t0, 1.0, 0.0), _pt(t1, 1.0, 0.0)]),
            _metric("runtime", "minimize", "s", [_pt(t0, 8.0, 0.5), _pt(t1, 8.1, 0.4)]),
            _metric("queue_depth", "maximize", "", [_pt(t1, 2.0, 0.0)]),
        ],
        regressions=[
            _reg("success", "maximize", False, 1.0, 1.0, 0.0),
            _reg("runtime", "minimize", False, 8.0, 8.1, 1.25),
        ],
        time_event=t1,
    )

    # Startup: emits wall_time, aliased to the runtime column; completion is a
    # percent metric.
    _write_summary(
        tmp_path,
        "test_bench_startup",
        "Startup",
        metrics=[
            _metric("success", "maximize", "", [_pt(t0, 1.0, 0.0), _pt(t1, 1.0, 0.0)]),
            _metric("wall_time", "minimize", "s", [_pt(t0, 0.9, 0.05), _pt(t1, 0.8, 0.05)]),
            _metric("completion", "maximize", "ratio", [_pt(t1, 0.9, 0.0)]),
        ],
        regressions=[
            _reg("success", "maximize", False, 1.0, 1.0, 0.0),
            _reg("wall_time", "minimize", False, 0.9, 0.8, -11.0),
        ],
        time_event=t1,
    )

    # Unregistered tag -> falls back to the "Other" category with an auto name.
    _write_summary(
        tmp_path,
        "test_bench_mystery_thing",
        "MysteryThing",
        metrics=[_metric("widgets", "maximize", "", [_pt(t1, 7.0, 0.0)])],
        regressions=[],
        time_event=t1,
    )

    # Metric-less benchmark (image-only): no table row, but its HTML report is
    # listed as a link.
    _write_summary(tmp_path, "test_bench_gallery", "Gallery", [], [], t1)
    bench_root = tmp_path / "benchmarks"
    (bench_root / "test_bench_gallery" / "Gallery.html").write_text("<html>gallery</html>")
    # A charted bench that also has an HTML report: it is a row, so it must NOT be
    # duplicated as a link.
    (bench_root / "test_bench_startup" / "Startup.html").write_text("<html>startup</html>")

    return tmp_path


class TestCellVerdict:
    def test_none_is_trend(self):
        assert cell_verdict(None) == "trend"

    def test_regressed_overrides(self):
        assert cell_verdict(_reg("v", "maximize", True, 1.0, 0.75, -25.0)) == "regressed"

    def test_improved_when_beneficial_over_threshold(self):
        assert cell_verdict(_reg("v", "maximize", False, 1.0, 1.2, 20.0)) == "improved"
        assert cell_verdict(_reg("v", "minimize", False, 1.0, 0.8, -20.0)) == "improved"

    def test_passed_when_below_threshold(self):
        assert cell_verdict(_reg("v", "minimize", False, 1.0, 1.02, 2.0)) == "passed"

    def test_passed_when_adverse_but_not_flagged(self):
        assert cell_verdict(_reg("v", "minimize", False, 1.0, 1.05, 5.0)) == "passed"

    def test_passed_when_threshold_none(self):
        reg = _reg("v", "maximize", False, 1.0, 1.2, 20.0, threshold=None)
        assert cell_verdict(reg) == "passed"


class TestDiscover:
    def test_finds_benches_across_categories(self, mock_reports: Path):
        names = {r["bench_name"] for r in discover_summaries(mock_reports, CONFIG)}
        assert {"Latency", "Throughput", "Startup"} <= names

    def test_unregistered_tag_falls_back_to_other(self, mock_reports: Path):
        records = discover_summaries(mock_reports, CONFIG)
        mystery = next(r for r in records if r["tag"] == "test_bench_mystery_thing")
        assert mystery["category"] == "Other"
        assert mystery["name"] == "Mystery Thing"

    def test_metricless_bench_skipped(self, mock_reports: Path):
        records = discover_summaries(mock_reports, CONFIG)
        assert all(r["tag"] != "test_bench_gallery" for r in records)

    def test_attaches_category_and_name(self, mock_reports: Path):
        records = discover_summaries(mock_reports, CONFIG)
        rec = next(r for r in records if r["tag"] == "test_bench_latency")
        assert rec["category"] == "Performance"
        assert rec["name"] == "Latency"

    def test_link_uses_layout(self, mock_reports: Path):
        for r in discover_summaries(mock_reports, CONFIG):
            assert r["link"].startswith("benchmarks/")
            assert r["link"].endswith(".html")

    def test_empty_when_no_dir(self, tmp_path: Path):
        assert discover_summaries(tmp_path, CONFIG) == []


class TestDiscoverReportLinks:
    def _links(self, reports_dir: Path) -> list[dict]:
        excluded = {r["tag"] for r in discover_summaries(reports_dir, CONFIG)}
        sections = discover_report_links(reports_dir, CONFIG, excluded)
        return [link for section in sections for link in section["links"]]

    def test_metricless_bench_with_html_is_linked(self, mock_reports: Path):
        links = self._links(mock_reports)
        assert any(link["link"] == "benchmarks/test_bench_gallery/Gallery.html" for link in links)

    def test_charted_bench_is_excluded(self, mock_reports: Path):
        links = self._links(mock_reports)
        assert all("test_bench_startup" not in link["link"] for link in links)

    def test_grouped_by_category(self, mock_reports: Path):
        excluded = {r["tag"] for r in discover_summaries(mock_reports, CONFIG)}
        sections = discover_report_links(mock_reports, CONFIG, excluded)
        assert all({"category", "links"} <= section.keys() for section in sections)

    def test_empty_when_no_dir(self, tmp_path: Path):
        assert discover_report_links(tmp_path, CONFIG, set()) == []


class TestMetricColumns:
    def test_shared_vars_appear_once_and_lead(self, mock_reports: Path):
        records = [
            r for r in discover_summaries(mock_reports, CONFIG) if r["category"] == "Performance"
        ]
        cols = metric_columns(records)
        assert cols.count("success") == 1
        assert cols.count("runtime") == 1
        assert cols.index("runtime") < cols.index("queue_depth")
        assert cols.index("runtime") < cols.index("iterations")


class TestUnifyMetricNames:
    def test_aliases_rename_and_record_source(self):
        metrics = {"wall_time": _metric("wall_time", "minimize", "s", [])}
        regs = {"wall_time": _reg("wall_time", "minimize", False, 0.9, 0.8, -11.0)}
        unified, unified_regs = unify_metric_names(metrics, regs, {"wall_time": "runtime"})
        assert set(unified) == {"runtime"}
        assert unified["runtime"]["source_variable"] == "wall_time"
        assert set(unified_regs) == {"runtime"}

    def test_canonical_name_on_same_bench_wins(self):
        metrics = {
            "runtime": _metric("runtime", "minimize", "s", []),
            "wall_time": _metric("wall_time", "minimize", "s", []),
        }
        unified, _ = unify_metric_names(metrics, {}, {"wall_time": "runtime"})
        assert set(unified) == {"runtime", "wall_time"}
        assert "source_variable" not in unified["wall_time"]

    def test_unaliased_metrics_pass_through(self):
        metrics = {"startup_time": _metric("startup_time", "minimize", "s", [])}
        unified, _ = unify_metric_names(metrics, {}, {"wall_time": "runtime"})
        assert set(unified) == {"startup_time"}


class TestBuildCell:
    def test_missing_metric_returns_none(self, mock_reports: Path):
        rec = next(
            r for r in discover_summaries(mock_reports, CONFIG) if r["tag"] == "test_bench_startup"
        )
        assert build_cell(rec, "queue_depth", CONFIG) is None

    def test_regressed_cell(self, mock_reports: Path):
        rec = next(
            r for r in discover_summaries(mock_reports, CONFIG) if r["tag"] == "test_bench_latency"
        )
        cell = build_cell(rec, "success", CONFIG)
        assert cell["verdict"] == "regressed"
        assert cell["latest_str"] == "0.75"
        assert cell["change_str"] == "-25.0%"

    def test_improved_cell(self, mock_reports: Path):
        rec = next(
            r for r in discover_summaries(mock_reports, CONFIG) if r["tag"] == "test_bench_latency"
        )
        cell = build_cell(rec, "runtime", CONFIG)
        assert cell["verdict"] == "improved"

    def test_passed_cell_within_threshold(self, mock_reports: Path):
        rec = next(
            r for r in discover_summaries(mock_reports, CONFIG) if r["tag"] == "test_bench_latency"
        )
        assert build_cell(rec, "accuracy", CONFIG)["verdict"] == "passed"

    def test_trend_cell_without_regression(self, mock_reports: Path):
        # No regression gate -> "trend", with a delta from the series (1.5->2.0).
        rec = next(
            r for r in discover_summaries(mock_reports, CONFIG) if r["tag"] == "test_bench_latency"
        )
        cell = build_cell(rec, "iterations", CONFIG)
        assert cell["verdict"] == "trend"
        assert cell["latest_str"] == "2"
        assert cell["change_str"] == "+33.3%"

    def test_trend_cell_single_point_has_no_delta(self, mock_reports: Path):
        rec = next(
            r
            for r in discover_summaries(mock_reports, CONFIG)
            if r["tag"] == "test_bench_throughput"
        )
        cell = build_cell(rec, "queue_depth", CONFIG)
        assert cell["verdict"] == "trend"
        assert cell["change_str"] == ""

    def test_aliased_cell_carries_source_variable(self, mock_reports: Path):
        rec = next(
            r for r in discover_summaries(mock_reports, CONFIG) if r["tag"] == "test_bench_startup"
        )
        cell = build_cell(rec, "runtime", CONFIG)
        assert "variable: wall_time" in cell["tooltip"]

    def test_percent_metric_renders_as_percent(self, mock_reports: Path):
        rec = next(
            r for r in discover_summaries(mock_reports, CONFIG) if r["tag"] == "test_bench_startup"
        )
        assert build_cell(rec, "completion", CONFIG)["latest_str"] == "90%"

    def test_non_percent_ratio_stays_bare(self, mock_reports: Path):
        rec = next(
            r
            for r in discover_summaries(mock_reports, CONFIG)
            if r["tag"] == "test_bench_throughput"
        )
        assert build_cell(rec, "success", CONFIG)["latest_str"] == "1"


class TestGenerateScorecard:
    def test_creates_html(self, mock_reports: Path):
        out = generate_scorecard(mock_reports, CONFIG, output_name="summary.html")
        assert out == mock_reports / "summary.html"
        assert out.exists()

    def test_contains_rows_and_columns(self, mock_reports: Path):
        generate_scorecard(mock_reports, CONFIG)
        html = (mock_reports / "index.html").read_text()
        assert "Latency" in html
        assert "Throughput" in html
        assert "success" in html
        assert "runtime" in html
        # Aliased wall_time survives as a cell tooltip.
        assert "variable: wall_time" in html

    def test_renders_unescaped_svg(self, mock_reports: Path):
        generate_scorecard(mock_reports, CONFIG)
        html = (mock_reports / "index.html").read_text()
        assert "<svg" in html
        assert "&lt;svg" not in html

    def test_verdict_classes_present(self, mock_reports: Path):
        generate_scorecard(mock_reports, CONFIG)
        html = (mock_reports / "index.html").read_text()
        assert "v-regressed" in html
        assert "v-improved" in html
        assert "v-passed" in html
        assert "v-trend" in html

    def test_categories_and_other_rendered(self, mock_reports: Path):
        generate_scorecard(mock_reports, CONFIG)
        html = (mock_reports / "index.html").read_text()
        for category in ("Performance", "Startup", "Other"):
            assert category in html

    def test_category_order_other_last(self, mock_reports: Path):
        generate_scorecard(mock_reports, CONFIG)
        html = (mock_reports / "index.html").read_text()
        assert html.index("Performance") < html.index(">Other<")

    def test_title_and_chrome(self, mock_reports: Path):
        from bencher.scorecard import Chrome

        generate_scorecard(
            mock_reports,
            CONFIG,
            chrome=Chrome(title="My Health Page", pr_number="42"),
        )
        html = (mock_reports / "index.html").read_text()
        assert "My Health Page" in html
        assert "PR #42" in html

    def test_javascript_urls_stripped(self, mock_reports: Path):
        from bencher.scorecard import Chrome

        generate_scorecard(mock_reports, CONFIG, chrome=Chrome(run_url="javascript:alert(1)"))
        html = (mock_reports / "index.html").read_text()
        assert "javascript:" not in html

    def test_empty_reports_dir(self, tmp_path: Path):
        out = generate_scorecard(tmp_path, CONFIG)
        assert out.exists()
        assert "No benchmark summaries found." in out.read_text()

    def test_metricless_report_listed_as_link(self, mock_reports: Path):
        generate_scorecard(mock_reports, CONFIG)
        html = (mock_reports / "index.html").read_text()
        assert "Reports without metrics" in html
        assert "benchmarks/test_bench_gallery/Gallery.html" in html

    def test_charted_bench_not_duplicated_as_link(self, mock_reports: Path):
        generate_scorecard(mock_reports, CONFIG)
        html = (mock_reports / "index.html").read_text()
        assert html.count("benchmarks/test_bench_startup/Startup.html") == 1

    def test_zero_config_default_still_renders(self, mock_reports: Path):
        # No config: benchmarks auto-name and fall into "Other"; still a page.
        out = generate_scorecard(mock_reports, output_name="zero.html")
        # Default layout root is "" so the "benchmarks/" tree is not discovered.
        assert out.exists()
        assert "No benchmark summaries found." in out.read_text()
