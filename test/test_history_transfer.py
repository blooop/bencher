"""Native history survives transfer and concurrent branches without re-keying."""

import copy

import numpy as np
import pytest
import xarray as xr
from diskcache import Cache

from bencher.history_transfer import HistorySnapshot, NamespacedHistory


def snapshot(events, namespace="machine-a", key="existing-config-key"):
    return HistorySnapshot(
        namespace=namespace,
        records={
            key: {
                "format": 1,
                "dataset": xr.Dataset(
                    {"duration": ("over_time", list(events.values()))},
                    coords={"over_time": np.array(list(events), dtype=object)},
                ),
                "columns": {},
                "retired": {},
            }
        },
    )


def test_concurrent_executions_are_merged_once_in_time_order():
    left = snapshot({"2026-01-01": 1, "2026-01-03": 3})
    right = snapshot({"2026-01-01": 1, "2026-01-02": 2})
    merged = left.merge(right)
    ds = merged.records["existing-config-key"]["dataset"]
    assert ds.duration.values.tolist() == [1, 2, 3]
    xr.testing.assert_identical(ds, merged.merge(right).records["existing-config-key"]["dataset"])


def test_uuid_events_sort_by_execution_time_not_upload_order():
    left = snapshot({"z-uuid": 1})
    right = snapshot({"a-uuid": 2})
    left.records["existing-config-key"]["event_metadata"] = {
        "z-uuid": {"executed_at": "2026-01-01T00:00:00+00:00"}
    }
    right.records["existing-config-key"]["event_metadata"] = {
        "a-uuid": {"executed_at": "2026-01-02T00:00:00+00:00"}
    }
    assert left.merge(right).records["existing-config-key"]["dataset"].duration.values.tolist() == [
        1,
        2,
    ]


def test_conflicting_same_event_raises_and_leaves_inputs_unchanged():
    left, right = snapshot({"event": 1}), snapshot({"event": 2})
    before = copy.deepcopy((left, right))
    with pytest.raises(ValueError, match="conflict"):
        left.merge(right)
    for actual, original in zip((left, right), before, strict=True):
        xr.testing.assert_identical(
            actual.records["existing-config-key"]["dataset"],
            original.records["existing-config-key"]["dataset"],
        )


def test_machine_namespaces_cannot_be_merged():
    with pytest.raises(ValueError, match="namespace"):
        snapshot({"event": 1}).merge(snapshot({"event": 2}, namespace="other"))


def test_depth_is_explicit_and_retired_configurations_are_retained():
    old = snapshot({"a": 1, "b": 2})
    new = snapshot({"c": 3})
    merged = old.merge(new, max_time_events=2)
    assert merged.records["existing-config-key"]["dataset"].duration.values.tolist() == [2, 3]
    assert len(merged.merge(snapshot({"d": 4}, key="new-config")).records) == 2


def test_restore_round_trip_uses_native_record_and_preserves_other_machines(tmp_path):
    first = snapshot({"a": 1})
    first.restore(tmp_path)
    second = snapshot({"a": 2}, namespace="other")
    second.restore(tmp_path)
    loaded = HistorySnapshot.export(tmp_path, namespace="machine-a")
    assert loaded.records.keys() == first.records.keys()
    xr.testing.assert_identical(
        loaded.records["existing-config-key"]["dataset"],
        first.records["existing-config-key"]["dataset"],
    )
    round_trip = HistorySnapshot.from_bytes(loaded.to_bytes())
    assert round_trip.namespace == "machine-a"
    with Cache(str(tmp_path / "history")) as cache:
        assert (
            NamespacedHistory(cache, "other")["existing-config-key"]["dataset"].duration.item() == 2
        )


def test_failed_restore_is_transactional(tmp_path):
    initial = snapshot({"a": 1})
    initial.restore(tmp_path)
    conflicting = snapshot({"a": 2})
    conflicting.records["another-config"] = snapshot({"b": 3}).records["existing-config-key"]
    with pytest.raises(ValueError):
        conflicting.restore(tmp_path)
    restored = HistorySnapshot.export(tmp_path, namespace="machine-a")
    assert list(restored.records) == ["existing-config-key"]


def test_legacy_empty_namespace_keeps_existing_cache_keys(tmp_path):
    initial = snapshot({"a": 1}, namespace="")
    initial.restore(tmp_path)
    with Cache(str(tmp_path / "history")) as cache:
        assert "existing-config-key" in cache


def test_normal_benchmark_initialization_does_not_clear_restored_history(tmp_path):
    from bencher.cache_management import ensure_cache_version

    snapshot({"a": 1}).restore(tmp_path)
    ensure_cache_version(str(tmp_path))
    assert "existing-config-key" in HistorySnapshot.export(tmp_path, namespace="machine-a").records


def test_collection_and_restore_use_the_same_namespaced_records(tmp_path, monkeypatch):
    from bencher.result_collector import ResultCollector

    monkeypatch.chdir(tmp_path)
    with ResultCollector() as collector:
        for machine, value in (("sim", 10), ("hardware", 100)):
            collector.load_history_cache(
                snapshot({"first": value}).records["existing-config-key"]["dataset"],
                "existing-config-key",
                False,
                namespace=machine,
                event_metadata={"executed_at": "2026-01-01T00:00:00+00:00"},
            )
    transferred = HistorySnapshot.export("cachedir", namespace="sim")
    assert (
        transferred.records["existing-config-key"]["event_metadata"]["first"]["executed_at"]
        == "2026-01-01T00:00:00+00:00"
    )
    transferred.restore("restored")
    monkeypatch.chdir(tmp_path / "restored")
    # Collection uses cachedir/history relative to its working directory.
    transferred.restore("cachedir")
    with ResultCollector() as collector:
        data = collector.load_history_cache(
            snapshot({"second": 20}).records["existing-config-key"]["dataset"],
            "existing-config-key",
            False,
            namespace="sim",
        )
    assert data.duration.values.tolist() == [10, 20]


def test_media_retention_does_not_conflict_with_an_older_snapshot():
    old, new = snapshot({"a": 1}), snapshot({"a": 1, "b": 2, "c": 3})
    old_record, new_record = (s.records["existing-config-key"] for s in (old, new))
    old_record["dataset"]["recording"] = ("over_time", np.array(["old.rrd"], dtype=object))
    new_record["dataset"]["recording"] = (
        "over_time",
        np.array(["NAN", "b.rrd", "c.rrd"], dtype=object),
    )
    for rec in (old_record, new_record):
        rec["columns"]["recording"] = {
            "class": "ResultRerun",
            "identity": "recording",
            "max_time_events": 2,
        }
    merged = old.merge(new).records["existing-config-key"]
    assert merged["dataset"].recording.values.tolist() == ["NAN", "b.rrd", "c.rrd"]


def test_different_input_coordinates_never_broadcast_into_fake_measurements():
    left, right = snapshot({"a": 1}), snapshot({"b": 2})
    left.records["existing-config-key"]["dataset"] = left.records["existing-config-key"][
        "dataset"
    ].expand_dims(position=[1])
    right.records["existing-config-key"]["dataset"] = right.records["existing-config-key"][
        "dataset"
    ].expand_dims(position=[2])
    with pytest.raises(ValueError, match="coordinate"):
        left.merge(right)
