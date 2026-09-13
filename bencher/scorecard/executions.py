"""Verified local execution reports used by the report-time scorecard."""

from __future__ import annotations

import json
import warnings
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from bencher.complete_report import verify_report


def discover_complete_reports(reports_dir: Path, root: str = "") -> list[dict]:
    """Select the newest complete result for each tag, machine and configuration.

    This reads local exports, not the remote retained-report index. Native history
    remains authoritative for baselines; these summaries are report-time snapshots.
    Invalid or incomplete exports warn and cannot displace a verified report.
    """
    reports_dir = Path(reports_dir)
    selected: dict[tuple, tuple[tuple, list[dict]]] = {}
    for path in sorted((reports_dir / root).glob("*/*/report.json")):
        try:
            manifest = verify_report(path.parent)
            execution = manifest["execution"]
            rank = (datetime.fromisoformat(execution["executed_at"]), execution["uuid"])
            tag = path.parent.parent.name
            candidates = []
            for entry in manifest["results"]:
                key = (
                    tag,
                    entry["benchmark"],
                    entry["configuration_key"],
                    entry["history_namespace"],
                    entry["series"],
                    execution.get("lane"),
                )
                hash(key)
                summary = json.loads((path.parent / entry["summary"]).read_text(encoding="utf-8"))
                if not isinstance(summary, dict):
                    raise TypeError("Result summary must be an object")
                record = {
                    "tag": tag,
                    "entry": entry,
                    "execution": execution,
                    "summary": summary,
                    "link": quote(
                        (path.parent / entry["page"]).relative_to(reports_dir).as_posix(), safe="/"
                    ),
                    "entry_link": quote(
                        (path.parent / manifest["entry_page"]).relative_to(reports_dir).as_posix(),
                        safe="/",
                    ),
                }
                candidates.append((key, record))
            for key, record in candidates:
                if key not in selected or rank > selected[key][0]:
                    selected[key] = rank, [record]
                elif rank == selected[key][0]:
                    selected[key][1].append(record)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            warnings.warn(f"Skipping incomplete report {path}: {exc}", stacklevel=2)
    return [record for _rank, records in selected.values() for record in records]
