"""Export, merge and restore native history records between trusted machines.

Snapshots contain the same records collection reads for regression baselines.
They retain configuration keys, column metadata and execution provenance. File
references remain references: callers must transfer the associated cache assets.
Only deserialize snapshots from trusted writers, as with bencher's other pickles.
"""

from __future__ import annotations

import copy
import pickle
from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import xarray as xr
from diskcache import Cache

from bencher.cache_management import CACHE_VERSION
from bencher.history import HISTORY_FORMAT, incompatible_reason
from bencher.variables.results import RESULT_SPECS


class NamespacedHistory(MutableMapping[str, Any]):
    """Partition native cache keys without changing benchmark/configuration identities."""

    def __init__(self, cache: Cache, namespace: str = "") -> None:
        self.cache = cache
        self.namespace = namespace

    def _key(self, key: str) -> str | tuple[str, str]:
        return (self.namespace, key) if self.namespace else key

    def __getitem__(self, key: str) -> Any:
        return self.cache[self._key(key)]

    def __setitem__(self, key: str, value: Any) -> None:
        self.cache[self._key(key)] = value

    def __delitem__(self, key: str) -> None:
        del self.cache[self._key(key)]

    def __iter__(self) -> Iterator[str]:
        for key in self.cache:
            if self.namespace:
                if isinstance(key, tuple) and len(key) == 2 and key[0] == self.namespace:
                    yield key[1]
            elif isinstance(key, str):
                yield key

    def __len__(self) -> int:
        return sum(1 for _ in self)


def _event_order(record: dict, event: Any) -> tuple[str, str]:
    metadata = record.get("event_metadata", {}).get(str(event), {})
    timestamp = metadata.get("executed_at")
    if timestamp is not None:
        parsed = datetime.fromisoformat(timestamp)
        if parsed.tzinfo is None:
            raise ValueError("executed_at must include a timezone")
        return parsed.astimezone(UTC).isoformat(), str(event)
    return str(event), str(event)


def _latest(record: dict) -> tuple[str, str]:
    return max(
        (_event_order(record, e) for e in record["dataset"].over_time.values), default=("", "")
    )


def _missing_as_nan(record: dict) -> xr.Dataset:
    dataset = record["dataset"].copy(deep=True)
    specs = {cls.__name__: spec for cls, spec in RESULT_SPECS.items()}
    for name, meta in record.get("columns", {}).items():
        spec = specs.get(meta.get("class"))
        if name in dataset and spec and spec.fill_dtype in {object, int}:
            dataset[name] = dataset[name].where(dataset[name] != spec.missing_fill)
    return dataset


def _merge_record(left: dict, right: dict, max_time_events: int | None) -> dict:
    reason = incompatible_reason(left["dataset"], right["dataset"])
    if reason:
        raise ValueError(f"history configuration conflict: {reason}")
    for name, coordinate in left["dataset"].coords.items():
        if (
            "over_time" not in coordinate.dims
            and name in right["dataset"].coords
            and not coordinate.equals(right["dataset"].coords[name])
        ):
            raise ValueError(f"history coordinate conflict: {name}")
    older, newer = sorted((left, right), key=_latest)
    result = copy.deepcopy(newer)
    for field_name in ("columns", "retired", "event_metadata"):
        result[field_name] = {
            **copy.deepcopy(older.get(field_name, {})),
            **result.get(field_name, {}),
        }
    for name, meta in left.get("columns", {}).items():
        other = right.get("columns", {}).get(name)
        if other and meta.get("identity") != other.get("identity"):
            raise ValueError(f"history column identity conflict: {name}")
    for event, meta in left.get("event_metadata", {}).items():
        other = right.get("event_metadata", {}).get(event)
        if other is not None and other != meta:
            raise ValueError(f"history execution metadata conflict: {event}")
    try:
        dataset = xr.merge(
            [_missing_as_nan(older), _missing_as_nan(newer)],
            compat="no_conflicts",
            join="outer",
            combine_attrs="override",
        )
    except xr.MergeError as exc:
        raise ValueError(f"history execution content conflict: {exc}") from exc
    order = sorted(dataset.over_time.values, key=lambda e: _event_order(result, e))
    if max_time_events is None:
        max_time_events = result.get("max_time_events")
    if max_time_events is not None:
        order = order[-max_time_events:]
    result["dataset"] = dataset.sel(over_time=order)
    result["event_metadata"] = {
        key: value
        for key, value in result.get("event_metadata", {}).items()
        if key in {str(event) for event in order}
    }
    for name, meta in result.get("columns", {}).items():
        births = [
            r["columns"][name].get("birth") for r in (left, right) if name in r.get("columns", {})
        ]
        meta["birth"] = (
            min(births, key=lambda e: _event_order(result, e))
            if all(b is not None for b in births)
            else None
        )
        if name not in result["dataset"]:
            continue
        specs = {cls.__name__: spec for cls, spec in RESULT_SPECS.items()}
        spec = specs.get(meta.get("class"))
        if spec and spec.fill_dtype in {object, int}:
            result["dataset"][name] = (
                result["dataset"][name].fillna(spec.missing_fill).astype(spec.fill_dtype)
            )
        limit = meta.get("max_time_events")
        if limit is not None and spec and len(order) > limit:
            result["dataset"][name].loc[{"over_time": order[:-limit]}] = spec.missing_fill
    return result


@dataclass
class HistorySnapshot:
    """A transferable view of native records from one history namespace.

    Unmentioned configurations are retained indefinitely. Merge uses each record's
    collection depth limit unless ``max_time_events`` explicitly overrides it.
    Execution order uses ``event_metadata[event]['executed_at']`` when present,
    otherwise the string form of the original coordinate (legacy timestamp labels).
    """

    namespace: str = ""
    records: dict[str, dict] = field(default_factory=dict)
    series: dict[str, dict] = field(default_factory=dict)
    cache_version: str = CACHE_VERSION

    @classmethod
    def export(
        cls, cachedir: str | Path = "cachedir", *, namespace: str = "", keys: set[str] | None = None
    ) -> HistorySnapshot:
        """Export selected native records and the series pointers that reference them."""
        with Cache(str(Path(cachedir) / "history"), eviction_policy="none") as raw, raw.transact():
            return cls._read(NamespacedHistory(raw, namespace), keys)

    @classmethod
    def _read(cls, cache: NamespacedHistory, keys: set[str] | None = None) -> HistorySnapshot:
        snapshot = cls(namespace=cache.namespace)
        for key in cache:
            value = cache[key]
            if key.startswith("__history_last_seen__:"):
                if keys is None or value["key"] in keys:
                    snapshot.series[key] = value
            elif keys is None or key in keys:
                if isinstance(value, xr.Dataset):
                    value = {
                        "format": HISTORY_FORMAT,
                        "dataset": value,
                        "columns": {},
                        "retired": {},
                    }
                if not isinstance(value, dict) or not isinstance(value.get("dataset"), xr.Dataset):
                    raise ValueError(f"unrecognized history record: {key}")
                snapshot.records[key] = value
        return snapshot

    def merge(
        self, other: HistorySnapshot, *, max_time_events: int | None = None
    ) -> HistorySnapshot:
        """Merge distinct executions, rejecting namespace or content conflicts."""
        if self.namespace != other.namespace:
            raise ValueError("cannot merge different history namespaces")
        if self.cache_version != CACHE_VERSION or other.cache_version != CACHE_VERSION:
            raise ValueError("history cache version does not match this bencher release")
        if max_time_events is not None and max_time_events < 1:
            raise ValueError("max_time_events must be positive")
        result = copy.deepcopy(self)
        for key, incoming in other.records.items():
            if key in result.records:
                result.records[key] = _merge_record(result.records[key], incoming, max_time_events)
            else:
                result.records[key] = _merge_record(incoming, incoming, max_time_events)
        for key, incoming in other.series.items():
            previous = result.series.get(key)
            if previous is None or _latest(result.records[incoming["key"]]) > _latest(
                result.records[previous["key"]]
            ):
                result.series[key] = copy.deepcopy(incoming)
        return result

    def restore(
        self, cachedir: str | Path = "cachedir", *, max_time_events: int | None = None
    ) -> None:
        """Merge into a native cache in one transaction, preserving other namespaces."""
        if self.cache_version != CACHE_VERSION:
            raise ValueError("history cache version does not match this bencher release")
        version_file = Path(cachedir) / "CACHE_VERSION"
        if version_file.exists() and version_file.read_text().strip() != CACHE_VERSION:
            raise ValueError("destination cache version does not match this bencher release")
        version_file.parent.mkdir(parents=True, exist_ok=True)
        version_file.write_text(CACHE_VERSION)
        with Cache(str(Path(cachedir) / "history"), eviction_policy="none") as raw, raw.transact():
            cache = NamespacedHistory(raw, self.namespace)
            merged = self._read(cache).merge(self, max_time_events=max_time_events)
            for key, value in {**merged.records, **merged.series}.items():
                cache[key] = value

    def to_bytes(self) -> bytes:
        """Serialize a snapshot for transfer between trusted writers."""
        return pickle.dumps(self, protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def from_bytes(cls, data: bytes) -> HistorySnapshot:
        """Read a trusted snapshot, rejecting an unrelated or unsupported payload."""
        snapshot = pickle.loads(data)
        if not isinstance(snapshot, cls):
            raise TypeError("not a bencher history snapshot")
        if snapshot.cache_version != CACHE_VERSION:
            raise ValueError("history cache version does not match this bencher release")
        return snapshot
