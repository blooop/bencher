"""Publication commits the entry last and resolves retries from frozen bytes."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from bencher.execution import Execution
from bencher.object_store import CreateOnly, LocalStore, Present, ReadFailed, WriteFailed
from bencher.publishing import Published, Publisher, PublishFailed


@pytest.fixture(name="report")
def frozen_report(tmp_path):
    root = tmp_path / "report"
    root.mkdir()
    execution = Execution.start()
    files = {"index.html": b"entry", "nested/data.rrd": b"recording", "summary.json": b"{}"}
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    manifest = {
        "schema_version": 1,
        "execution": execution.to_dict(),
        "entry_page": "index.html",
        "results": [
            {
                "benchmark": "metric-free",
                "tag": "tag",
                "series": "test",
                "configuration_key": "key",
                "history_namespace": "legacy",
                "summary": "summary.json",
                "page": "index.html",
            }
        ],
        "files": [
            {"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in files.items()
        ],
    }
    (root / "report.json").write_text(json.dumps(manifest))
    return root


class RecordingStore(LocalStore):
    def __init__(self, path):
        super().__init__(path)
        self.writes = []
        self.fail_key = None
        self.lose_ack = False

    def write(self, key, data, condition, *, metadata=None):
        self.writes.append(key)
        if self.fail_key and key.endswith(self.fail_key):
            return WriteFailed("interrupted", outcome_unknown=False)
        result = super().write(key, data, condition, metadata=metadata)
        return WriteFailed("lost acknowledgment", outcome_unknown=True) if self.lose_ack else result


def test_entry_commits_last_and_retry_never_writes(report, tmp_path):
    store = RecordingStore(tmp_path / "store")
    publisher = Publisher(store, "reports/test", "https://reports.example.test/bench")
    first = publisher.publish(report)
    assert isinstance(first, Published)
    assert store.writes[-2:] == [
        f"{first.receipt.prefix}/report.json",
        f"{first.receipt.prefix}/index.html",
    ]
    assert first.url.endswith(f"/{first.receipt.execution['uuid']}/index.html")
    assert first.url.startswith("https://reports.example.test/bench/")
    assert first.receipt.results[0]["benchmark"] == "metric-free"
    store.writes.clear()
    second = publisher.publish(report)
    assert second == first
    assert store.writes == []


def test_interruption_before_entry_has_no_success_url_and_can_resume(report, tmp_path):
    store = RecordingStore(tmp_path / "store")
    publisher = Publisher(store, "reports", "https://example.test")
    store.fail_key = "index.html"
    assert isinstance(publisher.publish(report), PublishFailed)
    store.fail_key = None
    assert isinstance(publisher.publish(report), Published)


def test_lost_ack_is_resolved_by_verifying_bytes(report, tmp_path):
    store = RecordingStore(tmp_path / "store")
    store.lose_ack = True
    assert isinstance(
        Publisher(store, "reports", "https://example.test").publish(report), Published
    )


def test_conflicting_bytes_never_overwrite(report, tmp_path):
    store = RecordingStore(tmp_path / "store")
    execution = json.loads((report / "report.json").read_text())["execution"]
    key = f"reports/{execution['uuid']}/nested/data.rrd"
    store.write(key, b"different", CreateOnly())
    outcome = Publisher(store, "reports", "https://example.test").publish(report)
    assert isinstance(outcome, PublishFailed) and "conflict" in outcome.reason
    current = store.read(key)
    assert isinstance(current, Present) and current.data == b"different"
    assert not any(item.endswith("index.html") for item in store.writes)


def test_denied_read_is_not_absent(report, tmp_path, monkeypatch):
    store = RecordingStore(tmp_path / "store")
    monkeypatch.setattr(store, "read", lambda key: ReadFailed("denied"))
    outcome = Publisher(store, "reports", "https://example.test").publish(report)
    assert isinstance(outcome, PublishFailed) and "denied" in outcome.reason
    assert not store.writes


def test_programming_errors_are_not_suppressed(report, tmp_path, monkeypatch):
    store = LocalStore(tmp_path / "store")

    def broken(_key):
        raise TypeError("programming error")

    monkeypatch.setattr(store, "read", broken)
    with pytest.raises(TypeError, match="programming error"):
        Publisher(store, "reports", "https://example.test").publish(report)


def test_simultaneous_retries_converge_on_one_receipt(report, tmp_path):
    store = LocalStore(tmp_path / "store")
    publisher = Publisher(store, "reports", "https://example.test")
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda _: publisher.publish(report), range(4)))
    assert all(isinstance(result, Published) and result == results[0] for result in results)
    assert len(store.list().items) == 4


def test_committed_report_with_missing_asset_is_not_silently_repaired(
    report, tmp_path, monkeypatch
):
    from bencher.object_store import Absent

    store = RecordingStore(tmp_path / "store")
    publisher = Publisher(store, "reports", "https://example.test")
    assert isinstance(publisher.publish(report), Published)
    read = store.read
    monkeypatch.setattr(
        store, "read", lambda key: Absent() if key.endswith("data.rrd") else read(key)
    )
    store.writes.clear()
    assert isinstance(publisher.publish(report), PublishFailed)
    assert store.writes == []


def test_new_reference_requires_verified_dependency_lifetime(report, tmp_path):
    from bencher.publication_pointers import PointerFailed, PointerUpdated

    now = [0.0]
    store = LocalStore(tmp_path / "store", expiry_seconds=90, clock=lambda: now[0])
    publisher = Publisher(
        store, "reports", "https://example.test", minimum_remaining_seconds=30, clock=lambda: now[0]
    )
    first = publisher.publish(report)
    assert isinstance(first, Published)
    now[0] = 70
    assert isinstance(publisher.point(first.receipt, "latest"), PointerFailed)
    for item in store.list().items:
        store.renew(item.key, item.version)
    assert isinstance(publisher.point(first.receipt, "latest"), PointerUpdated)


def test_receipt_target_cannot_diverge_from_its_manifest(report, tmp_path):
    publisher = Publisher(LocalStore(tmp_path / "store"), "reports", "https://example.test")
    first = publisher.publish(report)
    assert isinstance(first, Published)
    wrong_url = replace(first.receipt, url="https://another.example.test/index.html")
    assert isinstance(publisher.verify(wrong_url), PublishFailed)


def test_receipt_round_trip_is_verified_by_a_fresh_publisher(report, tmp_path):
    from bencher.publishing import PublicationReceipt

    store = LocalStore(tmp_path / "store")
    first = Publisher(store, "reports", "https://example.test").publish(report)
    assert isinstance(first, Published)
    decoded = PublicationReceipt.from_dict(json.loads(json.dumps(first.receipt.to_dict())))
    assert decoded == first.receipt
    fresh = Publisher(LocalStore(tmp_path / "store"), "reports", "https://example.test")
    assert not isinstance(fresh.verify(decoded), PublishFailed)
