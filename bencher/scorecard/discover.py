"""Discover benchmark summaries and reports under a reports directory.

Walks ``<reports_dir>/<layout.root>/<tag>/`` collecting the machine-readable
``*.summary.json`` (:func:`~bencher.report_export.result_to_dict` with
``series``) for the scorecard table, and the HTML reports for the
"reports without metrics" link section. All project specifics — the tag registry
and the on-disk layout — come from the :class:`ScorecardConfig`.
"""

from __future__ import annotations

import json
from pathlib import Path

from bencher.scorecard.config import ScorecardConfig
from bencher.scorecard.model import unify_metric_names


def tag_to_name(tag: str) -> str:
    """Fallback display name for an unregistered tag (strip prefix, title-case)."""
    name = tag
    for prefix in ("test_bench_", "bench_"):
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break
    return name.replace("_", " ").title()


def _resolve(tag: str, config: ScorecardConfig) -> tuple[str, str]:
    """Return (category, display_name) for a tag from the registry or fallback."""
    registry = config.registry.get(tag)
    if registry is not None:
        category, name, _description = registry
        return category, name
    return config.other_category, tag_to_name(tag)


def discover_summaries(reports_dir: Path, config: ScorecardConfig) -> list[dict]:
    """Parse every ``*.summary.json`` under the reports root.

    Returns one record per summary file with registry metadata attached, in
    deterministic (category order, then display name) order. Benchmarks with no
    scalar metrics and malformed JSON are skipped.
    """
    root = reports_dir / config.layout.root
    if not root.is_dir():
        return []

    records: list[dict] = []
    for tag_dir in sorted(root.iterdir()):
        if not tag_dir.is_dir():
            continue
        tag = tag_dir.name
        category, name = _resolve(tag, config)
        for summary_file in sorted(tag_dir.glob("*.summary.json")):
            try:
                data = json.loads(summary_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            metrics = {m["variable"]: m for m in data.get("metrics", [])}
            if not metrics:
                # Nothing numeric to trend (e.g. image-only visual regression).
                continue
            regressions = {r["variable"]: r for r in data.get("regressions", {}).get("results", [])}
            metrics, regressions = unify_metric_names(metrics, regressions, dict(config.aliases))
            bench_name = data.get("bench_name") or summary_file.stem
            records.append(
                {
                    "tag": tag,
                    "name": name,
                    "category": category,
                    "bench_name": bench_name,
                    "link": config.layout.link(tag, bench_name),
                    "metrics": metrics,
                    "regressions": regressions,
                    "time_event": data.get("provenance", {}).get("time_event", ""),
                }
            )

    order = {cat: i for i, cat in enumerate(config.category_order())}
    records.sort(key=lambda r: (order.get(r["category"], len(order)), r["name"]))
    return records


def _discover_html_reports(reports_dir: Path, config: ScorecardConfig) -> list[dict]:
    """One ``{tag, name, category, link}`` per tag dir with an HTML report."""
    root = reports_dir / config.layout.root
    if not root.is_dir():
        return []
    results: list[dict] = []
    for tag_dir in sorted(root.iterdir()):
        if not tag_dir.is_dir():
            continue
        html_files = sorted(f for f in tag_dir.iterdir() if f.suffix == ".html" and f.is_file())
        if not html_files:
            continue
        category, name = _resolve(tag_dir.name, config)
        link = config.layout.link(tag_dir.name, html_files[0].stem)
        results.append({"tag": tag_dir.name, "name": name, "category": category, "link": link})
    return results


def discover_report_links(
    reports_dir: Path, config: ScorecardConfig, exclude_tags: set[str]
) -> list[dict]:
    """Benchmarks with an HTML report but no scalar metrics, grouped by category.

    The scorecard charts only benchmarks that emit scalar metrics; image-only
    reports and any report whose summary is missing would otherwise be
    unreachable. Drops any ``tag`` already shown as a metric row. Returns
    ``[{category, links: [{name, link}]}]`` in category display order.
    """
    sections: dict[str, list[dict]] = {}
    for bench in _discover_html_reports(reports_dir, config):
        if bench["tag"] in exclude_tags:
            continue
        sections.setdefault(bench["category"], []).append(
            {"name": bench["name"], "link": bench["link"]}
        )
    order = {cat: i for i, cat in enumerate(config.category_order())}
    return [
        {"category": cat, "links": sorted(sections[cat], key=lambda b: b["name"])}
        for cat in sorted(sections, key=lambda c: order.get(c, len(order)))
    ]
