"""The scorecard consumes verified manifests without a project-specific file adapter."""

import hashlib
import json
from dataclasses import replace

import pytest

from bencher.execution import Execution
from bencher.scorecard import (
    ReportLayout,
    ScorecardConfig,
    discover_complete_reports,
    discover_summaries,
    generate_scorecard,
)


def write_report(root, execution, configurations):
    directory = root / "reports" / "tag" / execution.uuid
    directory.mkdir(parents=True)
    files = {"index.html": b"report", "nested.html": b"nested report"}
    results = []
    for index, (configuration, mean) in enumerate(configurations):
        summary = f"summaries/{index}.json"
        files[summary] = json.dumps(
            {
                "bench_name": "same-benchmark",
                "metrics": []
                if mean is None
                else [
                    {
                        "variable": "duration",
                        "direction": "minimize",
                        "units": "s",
                        "series": [{"time_event": execution.uuid, "mean": mean, "std": 0, "n": 1}],
                    }
                ],
                "provenance": {"time_event": execution.uuid},
            }
        ).encode()
        results.append(
            {
                "benchmark": "same-benchmark",
                "tag": "tag",
                "series": "series",
                "configuration_key": configuration,
                "history_namespace": "legacy",
                "summary": summary,
                "page": "nested.html",
            }
        )
    for name, content in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (directory / "report.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "execution": execution.to_dict(),
                "results": results,
                "entry_page": "index.html",
                "files": [
                    {
                        "path": name,
                        "size": len(content),
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                    for name, content in files.items()
                ],
            }
        )
    )
    return directory


def test_scorecard_keeps_configurations_and_links_frozen_pages(tmp_path):
    old = replace(Execution.start(), executed_at="2026-01-01T00:00:00+00:00")
    new = replace(Execution.start(), executed_at="2026-01-02T00:00:00+00:00")
    write_report(tmp_path, old, [("a", 1.0), ("b", 2.0)])
    new_dir = write_report(tmp_path, new, [("a", 3.0), ("media", None)])
    config = ScorecardConfig(layout=ReportLayout(root="reports"))
    records = discover_summaries(tmp_path, config)
    assert len(records) == 2
    by_config = {record["configuration_key"]: record for record in records}
    assert by_config["a"]["time_event"] == new.uuid
    assert by_config["b"]["time_event"] == old.uuid
    assert by_config["a"]["link"] == new_dir.relative_to(tmp_path).as_posix() + "/nested.html"
    html = generate_scorecard(tmp_path, config).read_text()
    assert old.uuid in html and new.uuid in html
    assert "Reports without metrics" in html
    assert "report-time snapshot" in html.lower()


def test_uncommitted_manifest_is_not_a_discoverable_report(tmp_path):
    execution = Execution.start()
    directory = write_report(tmp_path, execution, [("a", 1.0)])
    (directory / "index.html").unlink()
    with pytest.warns(UserWarning, match="Skipping incomplete report"):
        assert (
            discover_summaries(tmp_path, ScorecardConfig(layout=ReportLayout(root="reports"))) == []
        )


def test_invalid_summary_cannot_partially_replace_good_execution(tmp_path):
    old = replace(Execution.start(), executed_at="2026-01-01T00:00:00+00:00")
    new = replace(Execution.start(), executed_at="2026-01-02T00:00:00+00:00")
    write_report(tmp_path, old, [("a", 1.0), ("b", 2.0)])
    directory = write_report(tmp_path, new, [("a", 3.0), ("b", 4.0)])
    summary = directory / "summaries/1.json"
    summary.write_bytes(b"[]")
    manifest_path = directory / "report.json"
    manifest = json.loads(manifest_path.read_text())
    item = next(item for item in manifest["files"] if item["path"] == "summaries/1.json")
    item.update(size=2, sha256=hashlib.sha256(b"[]").hexdigest())
    manifest_path.write_text(json.dumps(manifest))
    with pytest.warns(UserWarning, match="summary must be an object"):
        records = discover_complete_reports(tmp_path, "reports")
    assert len(records) == 2
    assert {record["execution"]["uuid"] for record in records} == {old.uuid}


def test_lanes_and_uuid_ties_select_independently(tmp_path):
    first = replace(Execution.start(lane="cpu"), executed_at="2026-01-01T00:00:00+00:00")
    second = replace(Execution.start(lane="cpu"), executed_at=first.executed_at)
    gpu = replace(Execution.start(lane="gpu"), executed_at=first.executed_at)
    for execution in [first, second, gpu]:
        write_report(tmp_path, execution, [("a", 1.0)])
    records = discover_complete_reports(tmp_path, "reports")
    assert len(records) == 2
    assert {record["execution"]["uuid"] for record in records} == {
        max(first.uuid, second.uuid),
        gpu.uuid,
    }


def test_keeps_every_result_of_the_selected_configuration(tmp_path):
    old = replace(Execution.start(), executed_at="2026-01-01T00:00:00+00:00")
    new = replace(Execution.start(), executed_at="2026-01-02T00:00:00+00:00")
    write_report(tmp_path, old, [("a", 1.0)])
    write_report(tmp_path, new, [("a", 2.0), ("a", 3.0)])
    records = discover_complete_reports(tmp_path, "reports")
    assert len(records) == 2
    assert {record["entry"]["summary"] for record in records} == {
        "summaries/0.json",
        "summaries/1.json",
    }
    assert {record["execution"]["uuid"] for record in records} == {new.uuid}
