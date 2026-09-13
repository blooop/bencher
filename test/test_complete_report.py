"""Execution identity and portable, frozen execution reports."""

import json
import shutil
import subprocess
import sys
from uuid import UUID

import panel as pn
import pytest

import bencher as bn
from bencher.example.benchmark_data import ExampleBenchCfg
from bencher.history_transfer import HistorySnapshot
from bencher.utils_rrd import rrd_file_to_pane


def collect(run_cfg=None):
    bench = bn.Bench("complete", ExampleBenchCfg())
    try:
        return bench.collect(
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=run_cfg or bn.BenchRunCfg(),
        )
    finally:
        bench.close()


def test_reused_configuration_gets_new_execution_without_rekeying(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = bn.BenchRunCfg(over_time=True, uuid_events=True)
    first, second = collect(cfg), collect(cfg)
    a, b = first.bench_cfg.execution, second.bench_cfg.execution
    assert UUID(a.uuid) != UUID(b.uuid)
    assert first.bench_cfg.hash_value == second.bench_cfg.hash_value
    assert cfg.time_event is None
    assert cfg.time_event_metadata is None
    assert second.ds.over_time.values.tolist() == [a.uuid, b.uuid]
    snapshot = HistorySnapshot.export()
    record = next(iter(snapshot.records.values()))
    assert record["event_metadata"][a.uuid]["executed_at"] == a.executed_at


def test_explicit_time_events_remain_compatible(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = collect(bn.BenchRunCfg(over_time=True, uuid_events=True, time_event="legacy"))
    assert result.ds.over_time.values.tolist() == ["legacy"]


def test_bundle_render_preserves_execution_and_each_configuration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with bn.execution_context(source_revision="old-sha", workflow="example", lane="cpu", attempt=2):
        results = [collect(), collect(bn.BenchRunCfg(repeats=2))]
    bundle = bn.save_results(results, tmp_path / "results.pkl")
    entry = bn.render_report(bundle, tmp_path / "reports", complete=True)
    manifest = json.loads(entry.with_name("report.json").read_text())
    assert manifest["execution"]["source_revision"] == "old-sha"
    assert manifest["execution"]["attempt"] == 2
    assert len(manifest["results"]) == 2
    assert len({r["configuration_key"] for r in manifest["results"]}) == 2
    assert len({r["summary"] for r in manifest["results"]}) == 2
    assert {r["history_namespace"] for r in manifest["results"]} == {""}
    for result in manifest["results"]:
        assert (entry.parent / result["summary"]).is_file()
        assert (entry.parent / result["page"]).is_file()
    assert entry.parent.name == results[0].bench_cfg.execution.uuid
    assert bn.verify_report(entry.parent) == manifest
    before = {p: p.read_bytes() for p in entry.parent.rglob("*") if p.is_file()}
    assert bn.render_report(bundle, tmp_path / "reports", complete=True) == entry
    assert all(p.read_bytes() == data for p, data in before.items())


def test_complete_bundle_cli_and_legacy_compare(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with bn.execution_context():
        results = [collect(), collect()]
    bundle = bn.save_results(results, tmp_path / "bundle.pkl")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "bencher.render",
            str(bundle),
            str(tmp_path / "out"),
            "--report",
            "--cachedir",
            str(tmp_path / "cachedir"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    entry = tmp_path / "out" / results[0].bench_cfg.execution.uuid / "index.html"
    assert len(bn.verify_report(entry.parent)["results"]) == 2


def test_asset_closure_after_moving_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name, data in [
        ("a/image.png", b"first"),
        ("b/image.png", b"second"),
        ("nested/movie.mp4", b"movie"),
        ("nested/data.rrd", b"rrd"),
    ]:
        path = tmp_path / "source" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    nested = tmp_path / "source" / "nested" / "tab.html"
    nested.write_text('<video src="movie.mp4"></video><a href="data.rrd">Recording</a>')
    report = bn.BenchReport("assets")
    report.append_result(collect())
    report.append_tab(
        pn.pane.HTML(
            f'<img src="{tmp_path}/source/a/image.png">'
            f'<img src="{tmp_path}/source/b/image.png">'
            f'<iframe src="{nested}"></iframe>'
        ),
        "media",
    )
    root = tmp_path / "reports"
    root.mkdir()
    (root / "stale.html").write_text("stale")
    entry = report.save_report(root)
    moved = tmp_path / "moved"
    shutil.move(entry.parent, moved)
    shutil.rmtree(tmp_path / "source")
    manifest = bn.verify_report(moved)
    contents = {(moved / f["path"]).read_bytes() for f in manifest["files"]}
    assert {b"first", b"second", b"movie", b"rrd"} <= contents
    assert b"stale" not in contents
    for path in moved.rglob("*.html"):
        assert str(tmp_path / "source") not in path.read_text()


def test_missing_asset_does_not_finalize(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    report = bn.BenchReport("missing")
    result = collect()
    report.append_result(result)
    report.append_tab(pn.pane.HTML('<img src="missing.png">'), "missing")
    with pytest.raises(FileNotFoundError, match="missing.png"):
        report.save_report(tmp_path / "reports")
    assert not (tmp_path / "reports" / result.bench_cfg.execution.uuid).exists()


def test_inventory_rejects_modified_bytes_and_unsafe_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    entry = bn.render_report(collect(), tmp_path / "reports", complete=True)
    entry.write_text("changed")
    with pytest.raises(ValueError, match="digest|inventory"):
        bn.verify_report(entry.parent)


def test_bundle_rejects_unrelated_executions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="execution"):
        bn.save_results([collect(), collect()], tmp_path / "bundle.pkl")


def test_runner_complete_mode_covers_each_requested_sweep_and_keeps_keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def benchmark(run_cfg):
        bench = bn.Bench("runner", ExampleBenchCfg(), run_cfg=run_cfg)
        bench.collect(input_vars=["theta"], result_vars=["out_sin"])
        bench.collect(input_vars=["theta"], result_vars=["out_cos"])
        bench.close()
        return bench

    cfg = bn.BenchRunCfg(uuid_events=True, history_namespace="explicit-machine")
    with bn.execution_context(source_revision="launcher-sha") as execution:
        bn.run(
            benchmark,
            run_cfg=cfg,
            show=False,
            max_repeats=2,
            report_directory=str(tmp_path / "out"),
        )
    manifest = bn.verify_report(tmp_path / "out" / execution.uuid)
    assert manifest["execution"]["source_revision"] == "launcher-sha"
    assert len(manifest["results"]) == 4
    assert {r["benchmark"] for r in manifest["results"]} == {"runner"}
    assert {r["history_namespace"] for r in manifest["results"]} == {"explicit-machine"}
    assert len({r["configuration_key"] for r in manifest["results"]}) == 2


def test_recordings_with_duplicate_parent_names_and_nested_tabs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    report = bn.BenchReport("recordings")
    report.record_result(collect())
    for prefix in ("first", "second"):
        recording = tmp_path / "cachedir" / "rrd" / prefix / "shared" / "scene.rrd"
        recording.parent.mkdir(parents=True)
        recording.write_bytes(prefix.encode())
        report.append_tab(pn.Tabs((prefix, rrd_file_to_pane(recording))), prefix)
    entry = report.save_report(tmp_path / "reports")
    manifest = bn.verify_report(entry.parent)
    recordings = [entry.parent / f["path"] for f in manifest["files"] if f["path"].endswith(".rrd")]
    assert {p.read_bytes() for p in recordings} == {b"first", b"second"}
    assert all("/rrd_static/" not in p.read_text() for p in entry.parent.rglob("*.html"))


def test_css_srcset_and_overlapping_urls_are_rewritten_once(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "image.png").write_bytes(b"image")
    (tmp_path / "style.css").write_text('@import "nested.css";')
    (tmp_path / "nested.css").write_text('body { background: url("image.png"); }')
    report = bn.BenchReport("asset-urls")
    report.record_result(collect())
    report.append_tab(
        pn.pane.HTML(
            '<link rel="stylesheet" href="style.css">'
            f'<img src="{tmp_path}/image.png" srcset="image.png 1x, {tmp_path}/image.png 2x">'
            '<img src="https://example.com/image.png">'
        ),
        "assets",
    )
    entry = report.save_report(tmp_path / "out")
    manifest = bn.verify_report(entry.parent)
    assert len([f for f in manifest["files"] if f["path"].endswith("image.png")]) == 1
    media = next(p for p in entry.parent.rglob("*.html") if "example.com" in p.read_text())
    assert "https://example.com/image.png" in media.read_text()
    assert media.read_text().count("_assets/") == 4


@pytest.mark.parametrize("unsafe", ["../outside", "/absolute", "a/../b", "a//b", ".", "a\\b"])
def test_inventory_rejects_unsafe_paths_before_reading(tmp_path, monkeypatch, unsafe):
    monkeypatch.chdir(tmp_path)
    entry = bn.render_report(collect(), tmp_path / "reports", complete=True)
    manifest_path = entry.with_name("report.json")
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][0]["path"] = unsafe
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unsafe"):
        bn.verify_report(entry.parent)


def test_retry_never_renders_again_and_a_failed_render_keeps_results(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = collect()
    report = bn.BenchReport("retry")
    report.record_result(result)

    def fail(*_args, **_kwargs):
        raise RuntimeError("renderer failed")

    with monkeypatch.context() as patcher:
        patcher.setattr(bn.BenchReport, "append_result", fail)
        with pytest.raises(RuntimeError, match="renderer failed"):
            report.save_report(tmp_path / "out")
    assert report.bench_results == (result,)
    entry = report.save_report(tmp_path / "out")
    monkeypatch.setattr(bn.BenchReport, "save", fail)
    monkeypatch.setattr(bn.BenchReport, "append_result", fail)
    assert bn.render_report(result, tmp_path / "out", complete=True) == entry
