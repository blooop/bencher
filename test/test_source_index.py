"""The ``by-src/<hash>/index.html`` pages: links only, merged safely, dead links dropped."""

from __future__ import annotations

import json

import pytest

import bencher as bn
from bencher.example.benchmark_data import ExampleBenchCfg
from bencher.object_store import Absent, ListFailed, LocalStore, Present
from bencher.publication_target import PublicationTarget, publish_frozen_report
from bencher.publishing import Published
from bencher.render import main as bencher_main
from bencher.report_export import result_to_dict
from bencher.source_index import (
    IndexEntry,
    IndexFailed,
    IndexUpdated,
    SourceIndex,
    read_index,
    tree_entries,
)
from bencher.source_link import SourceIdentity, source_hash

DIGEST = "0123456789abcdef"
HTTP = "https://reports.example.org"


def entry(run: str, when: str, benchmark: str = "bench") -> IndexEntry:
    return IndexEntry(
        url=f"{HTTP}/{run}/index.html",
        run=run,
        key=f"{run}/index.html",
        benchmark=benchmark,
        executed_at=when,
        source_revision="abc123",
        source_path="pkg/bench.py",
    )


def put(store: LocalStore, key: str, data: bytes = b"x") -> None:
    from bencher.object_store import CreateOnly

    store.write(key, data, CreateOnly())


def page(store: LocalStore, digest: str = DIGEST, prefix: str = "") -> list[IndexEntry]:
    key = f"{prefix}/by-src/{digest}/index.html" if prefix else f"by-src/{digest}/index.html"
    current = store.read(key)
    assert isinstance(current, Present)
    return read_index(current.data)


def test_page_lists_runs_newest_first_and_holds_only_links(tmp_path):
    store = LocalStore(tmp_path / "store")
    put(store, "runs/a/index.html", b"REPORT-A")
    put(store, "runs/b/index.html", b"REPORT-B")
    index = SourceIndex(store, HTTP)
    index.add(DIGEST, [entry("runs/a", "2026-01-01T00:00:00+00:00")])
    outcome = index.add(DIGEST, [entry("runs/b", "2026-02-01T00:00:00+00:00")])
    assert isinstance(outcome, IndexUpdated)
    assert outcome.url == f"{HTTP}/by-src/{DIGEST}/index.html"
    assert [e.run for e in page(store)] == ["runs/b", "runs/a"]
    data = store.read(f"by-src/{DIGEST}/index.html").data
    assert b"REPORT-A" not in data
    assert f'href="{HTTP}/runs/b/index.html"'.encode() in data


def test_concurrent_writer_loses_no_entry(tmp_path):
    class Racing(LocalStore):
        """Lands a competing writer's page just before this writer's first write."""

        raced = False

        def write(self, key, data, condition, *, metadata=None):
            if key.startswith("by-src/") and not self.raced:
                self.raced = True
                rival = SourceIndex(LocalStore(tmp_path / "store"), HTTP)
                assert isinstance(
                    rival.add(DIGEST, [entry("runs/rival", "2026-03-01T00:00:00+00:00")]),
                    IndexUpdated,
                )
            return super().write(key, data, condition, metadata=metadata)

    store = Racing(tmp_path / "store")
    put(store, "runs/rival/index.html")
    put(store, "runs/mine/index.html")
    outcome = SourceIndex(store, HTTP).add(DIGEST, [entry("runs/mine", "2026-03-02T00:00:00")])
    assert isinstance(outcome, IndexUpdated)
    assert store.raced
    assert {e.run for e in page(store)} == {"runs/rival", "runs/mine"}


def test_dead_links_drop_on_rewrite(tmp_path):
    store = LocalStore(tmp_path / "store")
    put(store, "runs/kept/index.html")
    seed = SourceIndex(store, HTTP)
    seed.add(
        DIGEST,
        [entry("runs/kept", "2026-01-01T00:00:00"), entry("runs/gone", "2026-01-02T00:00:00")],
    )
    assert len(page(store)) == 2  # New entries are trusted, not checked.
    put(store, "runs/new/index.html")
    outcome = SourceIndex(store, HTTP).add(DIGEST, [entry("runs/new", "2026-01-03T00:00:00")])
    assert isinstance(outcome, IndexUpdated)
    assert outcome.dropped == 1
    assert [e.run for e in page(store)] == ["runs/new", "runs/kept"]


def test_failed_listing_keeps_the_link(tmp_path):
    class Blind(LocalStore):
        def list(self, prefix="", *, token=None, limit=1000):
            return ListFailed("denied")

    store = Blind(tmp_path / "store")
    SourceIndex(store, HTTP).add(DIGEST, [entry("runs/old", "2026-01-01T00:00:00")])
    SourceIndex(store, HTTP).add(DIGEST, [entry("runs/new", "2026-01-02T00:00:00")])
    assert [e.run for e in page(store)] == ["runs/new", "runs/old"]


def test_never_overwrites_a_foreign_object(tmp_path):
    store = LocalStore(tmp_path / "store")
    put(store, f"by-src/{DIGEST}/index.html", b"<html>not ours</html>")
    outcome = SourceIndex(store, HTTP).add(DIGEST, [entry("runs/a", "2026-01-01T00:00:00")])
    assert isinstance(outcome, IndexFailed)
    assert store.read(f"by-src/{DIGEST}/index.html").data == b"<html>not ours</html>"


def test_bad_hash_and_entries_are_refused(tmp_path):
    index = SourceIndex(LocalStore(tmp_path / "store"), HTTP)
    with pytest.raises(ValueError, match="not a source hash"):
        index.page_key("../escape")
    with pytest.raises(ValueError, match="absolute http"):
        IndexEntry(url="javascript:x", run="r", key="r/index.html", benchmark="b")
    with pytest.raises(ValueError, match="not under its run"):
        IndexEntry(url=f"{HTTP}/x", run="r", key="other/index.html", benchmark="b")


def tree(tmp_path):
    """A report tree uploaded by other tooling: legacy pages beside summaries."""
    root = tmp_path / "tree"
    (root / "line_a").mkdir(parents=True)
    (root / "line_a" / "bench_one.html").write_text("page")
    (root / "line_a" / "bench_one.summary.json").write_text(
        json.dumps(
            {
                "bench_name": "bench_one",
                "provenance": {"executed_at": "2026-01-01T00:00:00+00:00"},
                "source": {"hash": DIGEST, "path": "pkg/bench.py"},
            }
        )
    )
    # A summary from an older bencher has no source and is skipped.
    (root / "line_a" / "old.html").write_text("page")
    (root / "line_a" / "old.summary.json").write_text(json.dumps({"bench_name": "old"}))
    return root


def test_tree_entries_link_the_page_beside_each_summary(tmp_path):
    pairs = tree_entries(tree(tmp_path), run="ci/run1", run_url=f"{HTTP}/ci/run1")
    assert len(pairs) == 1
    digest, found = pairs[0]
    assert digest == DIGEST
    assert found.url == f"{HTTP}/ci/run1/line_a/bench_one.html"
    assert found.key == "ci/run1/line_a/bench_one.html"
    assert found.benchmark == "bench_one"


def test_source_index_cli_indexes_an_uploaded_tree(tmp_path):
    store_dir = tmp_path / "store"
    root = tree(tmp_path)
    store = LocalStore(store_dir)
    put(store, "ci/run1/line_a/bench_one.html", b"page")
    code = bencher_main(
        [
            "source-index",
            str(root),
            "--store",
            str(store_dir),
            "--http-base",
            HTTP,
            "--uploaded-prefix",
            "ci/run1",
        ]
    )
    assert code == 0
    [found] = page(LocalStore(store_dir))
    assert found.url == f"{HTTP}/ci/run1/line_a/bench_one.html"


def run_benchmark(tmp_path, monkeypatch):
    monkeypatch.setenv("BENCHER_SOURCE_REVISION", "rev-1")
    bench = bn.Bench("indexed", ExampleBenchCfg())
    bench.collect(input_vars=["theta"], result_vars=["out_sin"])
    report = bench.report
    from bencher.complete_report import save_complete_report

    entry_page = save_complete_report(report, tmp_path / "frozen")
    bench.close()
    return bench, entry_page.parent


def test_a_run_records_its_source_and_publish_writes_the_index(tmp_path, monkeypatch):
    bench, directory = run_benchmark(tmp_path, monkeypatch)
    import bencher.example.benchmark_data as defining

    expected = SourceIdentity.of_file(defining.__file__)
    assert expected.path == "bencher/example/benchmark_data.py"
    assert expected.hash == source_hash(defining.__file__)

    manifest = json.loads((directory / "report.json").read_text())
    assert [r["source"] for r in manifest["results"]] == [expected.to_dict()]
    assert result_to_dict(bench.results[-1])["source"] == expected.to_dict()

    store_dir = tmp_path / "store"
    target = PublicationTarget(
        store=str(store_dir),
        prefix="team/bench",
        http_base=f"{HTTP}/team/bench",
        index_http_base=HTTP,
    )
    outcome = publish_frozen_report(directory, target)
    assert isinstance(outcome, Published)
    [found] = page(LocalStore(store_dir), expected.hash)
    assert found.url == outcome.url
    assert found.source_revision == "rev-1"
    assert found.run == outcome.receipt.prefix

    # Without an index root, by-src/ sits under the publish prefix.
    other = tmp_path / "other"
    target = PublicationTarget(store=str(other), prefix="p", http_base=f"{HTTP}/p")
    assert isinstance(publish_frozen_report(directory, target), Published)
    assert isinstance(LocalStore(other).read(f"by-src/{expected.hash}/index.html"), Absent)
    [found] = page(LocalStore(other), expected.hash, prefix="p")
    assert found.url.startswith(f"{HTTP}/p/")


def test_index_failure_never_fails_the_publish(tmp_path, monkeypatch):
    _, directory = run_benchmark(tmp_path, monkeypatch)

    class NoIndex(LocalStore):
        def write(self, key, data, condition, *, metadata=None):
            if "/by-src/" in f"/{key}":
                from bencher.object_store import WriteFailed

                return WriteFailed("denied", outcome_unknown=False)
            return super().write(key, data, condition, metadata=metadata)

    target = PublicationTarget(store=str(tmp_path / "s"), prefix="p", http_base=HTTP)
    publisher = target.publisher()
    publisher.store = NoIndex(tmp_path / "s")
    assert isinstance(publish_frozen_report(directory, target, publisher), Published)
