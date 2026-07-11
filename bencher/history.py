"""Schema-evolving over_time history: column identity, reconciliation, projection.

The over_time history cache is keyed by the benchmark identity *excluding*
result variables (``BenchCfg.hash_persistent(True, include_result_vars=False)``),
so changing the set of measured metrics does not orphan the whole history.
Result-variable differences are instead reconciled per column at load time
under a retain + projection model:

- The stored record keeps a **superset** dataset holding every column ever
  measured. Columns are never deleted: a column whose variable left the config
  goes *dormant* (retained, excluded from what consumers see) and resumes if
  the variable returns with the same identity; a column whose identity changed
  (units, class, or ``meaning_version``) is *retired* under a mangled name and
  a fresh column starts.
- Consumers are served a **projection** onto exactly the current config's
  columns, so every downstream reader (plots, regression detection, export)
  sees a dataset congruent with the current benchmark definition — the same
  invariant a destructive prune would give, without the ability to lose data
  to a typo'd variable name or a partial run.
- A column's identity is ``(name, class, units, meaning_version)``. The
  explicit ``meaning_version`` field on result variables is the sanctioned way
  to declare "same name, new semantics"; bumping it restarts just that
  column's history instead of silently splicing two different quantities into
  one trend line.
- Newly added columns are NaN-backfilled by the merge; each live column
  carries its birth ``over_time`` coordinate (the ``history_birth`` DataArray
  attr on the served dataset) so consumers can tell "did not exist yet" from
  "sample failed" and regression gating can hold fire while a baseline is
  young.

Input variables and constants stay in the history key: changing the input
space is a different experiment and yields a clean, *reported* full reset
(never a cross-dimension merge). The ``on_history_reset`` policy on
``BenchRunCfg`` controls how loss-y events (full reset, dormant, retired,
discarded) surface: warn (default), error, or ignore.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import xarray as xr

from bencher.utils import hash_sha1
from bencher.variables.results import (
    DATA_VAR_RESULT_TYPES,
    ResultVec,
    result_missing_fill,
)

logger = logging.getLogger(__name__)

# Version of the on-disk history record layout (independent of CACHE_VERSION,
# which invalidates keys; this describes the value stored under a key).
HISTORY_FORMAT = 1

# DataArray attr on served datasets: the over_time coordinate value at which
# this column first appeared (or was last restarted by an identity change).
# Absent for columns as old as the history itself.
BIRTH_ATTR = "history_birth"

_LOSSY_KINDS = frozenset({"full_reset", "column_dormant", "column_retired", "history_discarded"})


class HistoryResetError(Exception):
    """Raised when history is reset or loses a column and on_history_reset='error'."""


@dataclass
class HistoryEvent:
    """One schema-affecting event detected while loading over_time history."""

    kind: str  # full_reset | column_born | column_dormant | column_retired |
    #            column_resumed | history_discarded
    detail: str
    column: str | None = None

    @property
    def lossy(self) -> bool:
        """True when the event removes data from what consumers will see."""
        return self.kind in _LOSSY_KINDS


def data_var_columns(result_vars: list | None) -> dict[str, Any]:
    """Map history column name -> owning result variable.

    Mirrors ``ResultCollector.setup_dataset``: ``ResultVec`` expands to one
    column per element; only ``DATA_VAR_RESULT_TYPES`` get a data variable.
    Result types stored out-of-band (hmaps, volumes) have no history column.
    """
    cols: dict[str, Any] = {}
    for rv in result_vars or []:
        if type(rv) is ResultVec:
            for i in range(rv.size):
                cols[rv.index_name(i)] = rv
        elif isinstance(rv, DATA_VAR_RESULT_TYPES):
            cols[rv.name] = rv
    return cols


def column_identity(rv: Any, col_name: str) -> str:
    """Persistent identity of one history column.

    ``(name, class, units, meaning_version)`` — a change to any of these means
    the column is a different measurement and must not continue the old trend.
    ``meaning_version`` is read with getattr so result types that do not carry
    the field participate with None.
    """
    return hash_sha1(
        (
            col_name,
            type(rv).__name__,
            getattr(rv, "units", None),
            getattr(rv, "meaning_version", None),
        )
    )


def column_meta(rv: Any, col_name: str, birth: Any) -> dict:
    """Metadata stored per live column in the history record."""
    return {
        "identity": column_identity(rv, col_name),
        "class": type(rv).__name__,
        "units": getattr(rv, "units", None),
        "meaning_version": getattr(rv, "meaning_version", None),
        "birth": birth,
        "dormant": False,
    }


def config_summary(bench_cfg: Any) -> dict:
    """Compact identity summary of a BenchCfg, stored in the last-seen index.

    Diffed against the current config when the history key moves, so the reset
    warning can name what changed instead of just reporting a missing key.
    """

    def row(v: Any) -> tuple:
        return (str(v.name), type(v).__name__, str(getattr(v, "units", None)))

    return {
        "inputs": [row(v) for v in bench_cfg.input_vars or []],
        "consts": sorted((*row(v), str(hash_sha1(val))) for v, val in bench_cfg.const_vars or []),
        "results": sorted(
            (*row(v), str(getattr(v, "meaning_version", None))) for v in bench_cfg.result_vars or []
        ),
        "repeats": int(bench_cfg.repeats),
    }


def diff_summaries(old: dict | None, new: dict | None) -> list[str]:
    """Human-readable lines describing how *new* differs from *old*."""
    if not old or not new:
        return []
    lines = []
    for kind in ("inputs", "consts", "results"):
        o = [tuple(t) for t in old.get(kind, [])]
        n = [tuple(t) for t in new.get(kind, [])]
        if o == n:
            continue
        added = [t[0] for t in n if t not in o]
        removed = [t[0] for t in o if t not in n]
        parts = []
        if added:
            parts.append(f"added {added}")
        if removed:
            parts.append(f"removed {removed}")
        if not parts:
            parts.append("reordered")
        lines.append(f"{kind} changed: " + ", ".join(parts))
    if old.get("repeats") != new.get("repeats"):
        lines.append(f"repeats changed: {old.get('repeats')} -> {new.get('repeats')}")
    return lines


def last_seen_key(bench_name: str, tag: str | None) -> str:
    """History-cache key of the last-seen index entry for one benchmark."""
    return f"__history_last_seen__:{bench_name}:{tag}"


def current_time_value(dataset: xr.Dataset) -> Any:
    """The over_time coordinate value of the (single) current run, or None.

    Only real coordinate values are usable as birth markers — a bare over_time
    dimension exposes an implicit positional index that shifts when history is
    trimmed, so no birth is recorded for coordinate-less datasets.
    """
    if "over_time" in dataset.coords and dataset.sizes.get("over_time"):
        return dataset["over_time"].values[-1]
    return None


def incompatible_reason(ds_old: xr.Dataset, fresh: xr.Dataset) -> str | None:
    """Why stored history cannot be merged with the fresh dataset, or None.

    Mismatched non-over_time dimension layouts must never reach ``xr.concat``:
    an outer join across different dims broadcasts both, fabricating points at
    coordinate combinations that were never measured (with no NaNs to betray
    it). The history key makes this unreachable in normal operation; this is
    the defense in depth for hand-seeded or corrupted records.
    """
    if "over_time" in ds_old.dims and "over_time" in fresh.dims:
        try:
            if ds_old["over_time"].dtype != fresh["over_time"].dtype:
                return (
                    "over_time dtype changed: "
                    f"{ds_old['over_time'].dtype} -> {fresh['over_time'].dtype}"
                )
        except KeyError:
            pass
    old_dims = {d: s for d, s in ds_old.sizes.items() if d != "over_time"}
    new_dims = {d: s for d, s in fresh.sizes.items() if d != "over_time"}
    if old_dims != new_dims:
        return f"dimension layout changed: {old_dims} -> {new_dims}"
    return None


def _mangled_name(name: str, meta: dict, taken: set[str]) -> str:
    """Stable, collision-free storage name for a retired column."""
    base = f"{name}__retired_{str(meta.get('identity'))[:8]}"
    candidate = base
    suffix = 1
    while candidate in taken:
        suffix += 1
        candidate = f"{base}_{suffix}"
    return candidate


def reconcile(
    record: dict, fresh: xr.Dataset, current_cols: dict[str, Any]
) -> tuple[xr.Dataset, dict, dict, list[HistoryEvent]]:
    """Merge stored history with the fresh run, classifying column mutations.

    Returns ``(merged_superset, columns_meta, retired, events)``. Never raises
    on schema differences — the caller applies the on_history_reset policy to
    the returned events *before* persisting anything.
    """
    ds_old = record["dataset"]
    columns: dict = {k: dict(v) for k, v in (record.get("columns") or {}).items()}
    retired: dict = dict(record.get("retired") or {})
    events: list[HistoryEvent] = []
    birth_val = current_time_value(fresh)
    n_history = int(ds_old.sizes.get("over_time", 0))

    renames: dict[str, str] = {}
    for name, rv in current_cols.items():
        ident = column_identity(rv, name)
        meta = columns.get(name)
        if meta is None:
            columns[name] = column_meta(rv, name, birth_val)
            if name in ds_old.data_vars:
                # Data exists under this name but carries no metadata (record
                # predates column tracking): adopt it as the same column
                # rather than fabricating a birth mid-history.
                columns[name]["birth"] = None
            else:
                events.append(
                    HistoryEvent(
                        "column_born",
                        f"result column '{name}' added; earlier history is backfilled "
                        f"as missing and its regression baseline starts now",
                        column=name,
                    )
                )
        elif meta.get("identity") is None:
            # Stub meta for a column from a record predating column tracking:
            # its identity was never recorded, so adopt it in place rather than
            # retiring (a retire would mangle real continuous history under a
            # dormant stub identity). Birth stays None: data as old as tracking.
            was_dormant = meta.get("dormant")
            columns[name] = column_meta(rv, name, birth=None)
            if was_dormant:
                events.append(
                    HistoryEvent(
                        "column_resumed",
                        f"result column '{name}' returned with the same identity; "
                        f"its earlier history resumes",
                        column=name,
                    )
                )
        elif meta.get("identity") != ident:
            taken = set(ds_old.data_vars) | set(retired)
            mangled = _mangled_name(name, meta, taken)
            if name in ds_old.data_vars:
                renames[name] = mangled
            retired[mangled] = {**meta, "retired_from": name}
            columns[name] = column_meta(rv, name, birth_val)
            events.append(
                HistoryEvent(
                    "column_retired",
                    f"result column '{name}' changed identity "
                    f"(class/units/meaning_version); {n_history} historical events "
                    f"retired to '{mangled}' and the column restarts",
                    column=name,
                )
            )
        elif meta.get("dormant"):
            meta["dormant"] = False
            events.append(
                HistoryEvent(
                    "column_resumed",
                    f"result column '{name}' returned with the same identity; "
                    f"its earlier history resumes",
                    column=name,
                )
            )

    # Data variables from a record predating column tracking carry no metadata.
    # Any such column absent from the current config must still go dormant, so
    # on_history_reset='error' fires and a later return resumes (via the
    # identity-None branch above) instead of silently re-adopting. Retired
    # mangled names are data_vars too and are skipped.
    for name in ds_old.data_vars:
        if name in columns or name in current_cols or name in retired:
            continue
        columns[name] = {
            "identity": None,
            "class": None,
            "units": None,
            "meaning_version": None,
            "birth": None,
            "dormant": True,
        }
        events.append(
            HistoryEvent(
                "column_dormant",
                f"result column '{name}' from a record predating column tracking is "
                f"absent from the config; {n_history} historical events retained "
                f"(dormant) and will resume if it returns",
                column=name,
            )
        )

    for name, meta in columns.items():
        if name not in current_cols and not meta.get("dormant"):
            meta["dormant"] = True
            events.append(
                HistoryEvent(
                    "column_dormant",
                    f"result column '{name}' removed from the config; {n_history} "
                    f"historical events retained (dormant) and will resume if it "
                    f"returns with the same identity",
                    column=name,
                )
            )

    if renames:
        ds_old = ds_old.rename(renames)

    merged = xr.concat([ds_old, fresh], "over_time")
    _restore_sentinel_fill(merged, current_cols)
    return merged, columns, retired, events


def _restore_sentinel_fill(merged: xr.Dataset, current_cols: dict[str, Any]) -> None:
    """Repair concat's NaN fill for columns whose missing sentinel is not NaN.

    ``xr.concat`` fills variables absent from one side with float NaN. For
    NaN-sentinel (numeric) columns that IS the missing marker; for object
    columns ("NAN" sentinel) and index-backed reference columns (-1 sentinel,
    int dtype promoted to float by the fill) the gap cells must be rewritten
    so ``result_is_missing`` still recognises them.
    """
    for name, rv in current_cols.items():
        if name not in merged.data_vars:
            continue
        fill, dtype = result_missing_fill(rv)
        if isinstance(fill, float) and math.isnan(fill):
            continue
        da = merged[name]
        if da.dtype == object:
            arr = da.values
            mask = np.array(
                [val is None or (isinstance(val, float) and math.isnan(val)) for val in arr.flat],
                dtype=bool,
            ).reshape(arr.shape)
            if mask.any():
                arr[mask] = fill
        elif np.issubdtype(da.dtype, np.floating):
            merged[name] = da.fillna(fill).astype(dtype)


def project(merged: xr.Dataset, current_cols: dict[str, Any], columns_meta: dict) -> xr.Dataset:
    """Serve exactly the current config's columns, with birth annotations.

    The returned dataset shares variables with *merged*; only the set of data
    variables narrows. Dormant and retired columns stay in the stored record
    but are invisible to every consumer.
    """
    keep = [n for n in current_cols if n in merged.data_vars]
    served = merged if len(keep) == len(merged.data_vars) else merged[keep]
    for name in keep:
        birth = (columns_meta.get(name) or {}).get("birth")
        if birth is not None:
            served[name].attrs[BIRTH_ATTR] = birth
        else:
            served[name].attrs.pop(BIRTH_ATTR, None)
    return served


def apply_policy(events: list[HistoryEvent], policy: str) -> None:
    """Surface history events according to on_history_reset.

    Informational events (born, resumed) always log at INFO. Lossy events
    (full reset, dormant, retired, discarded) warn by default; with
    policy='error' they raise HistoryResetError — callers must apply the
    policy *before* persisting the merged record so an erroring CI run does
    not advance history state; policy='ignore' logs at DEBUG.
    """
    for event in events:
        if not event.lossy:
            logger.info("history: %s", event.detail)
    lossy = [e for e in events if e.lossy]
    if not lossy:
        return
    if policy == "error":
        raise HistoryResetError("; ".join(e.detail for e in lossy))
    log = logger.warning if policy == "warn" else logger.debug
    for event in lossy:
        log("history: %s", event.detail)
