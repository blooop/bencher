"""Render the benchmark health scorecard to a single HTML page.

Discovers every ``*.summary.json`` under the reports directory, groups them by
category, and builds one metric cell per (benchmark, metric) pair per category,
rendered by a bundled Jinja template. Each cell shows a verdict-colored value, a
Δ, and a noise sparkline. The template lays those cells out two ways — one column
per metric (compare a metric across benchmarks) or one column per benchmark
(stack a benchmark's metrics on a shared time axis) — and a client-side control
toggles between them. Benchmarks with only image reports are listed as plain
links so they stay reachable from this page.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from bencher.scorecard.config import Chrome, ScorecardConfig
from bencher.scorecard.discover import discover_report_links, discover_summaries
from bencher.scorecard.model import build_cell, column_units, metric_columns

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
# A well-formed http(s) URL: scheme, then at least one non-whitespace char to the
# end. The `\S+$` anchor rejects any embedded whitespace outright.
_SAFE_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)
# ASCII control chars (incl. NUL, tab, newline) that must never reach an href.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize_url(url: str) -> str:
    """Return *url* only if it is a clean http(s) link, else an empty string.

    Chrome links may originate from CI environment variables, so treat them as
    untrusted: strip surrounding whitespace, reject any embedded control
    characters (which could smuggle a second scheme or break out of the href),
    and require an ``http(s)://`` scheme with no internal whitespace.
    """
    if not url:
        return ""
    url = url.strip()
    if _CONTROL_CHARS_RE.search(url):
        return ""
    if not _SAFE_URL_RE.match(url):
        return ""
    return url


def _group(records: list[dict], columns: list[str], config: ScorecardConfig) -> dict:
    """One table group: both label axes, plus a cell per (benchmark, column).

    Every benchmark's ``cells`` are in column order, and that one list feeds both
    orientations — read across for one column per metric, or indexed down a
    metric row for one column per benchmark — since the view is toggled
    client-side from a single render.
    """
    units = column_units(records, columns, config)
    return {
        "metrics": [{"name": var, "units": units[var]} for var in columns],
        "benchmarks": [
            {
                "name": rec["name"],
                "tag": rec["tag"],
                "link": rec["link"],
                "time_event": rec["time_event"],
                "cells": [
                    build_cell(rec, var, config, units_in_header=bool(units[var]))
                    for var in columns
                ],
            }
            for rec in records
        ],
    }


def generate_scorecard(
    reports_dir: Path | str,
    config: ScorecardConfig | None = None,
    *,
    chrome: Chrome | None = None,
    output_name: str = "index.html",
) -> Path:
    """Render the scorecard for all summaries under *reports_dir*.

    Args:
        reports_dir: Directory containing ``<layout.root>/<tag>/*.summary.json``.
        config: Project specifics (registry, aliases, layout, ...). Defaults to a
            zero-config :class:`ScorecardConfig` (auto-named benchmarks).
        chrome: Optional page header / CI nav content.
        output_name: File written under *reports_dir* (the scorecard is usually
            published as ``index.html`` so it is the landing page).

    Returns:
        The path to the written HTML file.
    """
    reports_dir = Path(reports_dir)
    config = config or ScorecardConfig()
    chrome = chrome or Chrome()

    records = discover_summaries(reports_dir, config)

    # One section per category, in the registry's display order (records are
    # already sorted that way), holding only the metrics that category reports.
    # Its columns split into the section's own subject and the config's secondary
    # (harness) metrics, each rendered as its own group.
    sections: list[dict] = []
    for category in dict.fromkeys(r["category"] for r in records):
        cat_records = [r for r in records if r["category"] == category]
        columns = metric_columns(cat_records)
        primary = [var for var in columns if var not in config.secondary_metrics]
        secondary = [var for var in columns if var in config.secondary_metrics]
        # A section reporting nothing else has them as its subject.
        if not primary:
            primary, secondary = secondary, []
        sections.append(
            {
                "category": category,
                "main": _group(cat_records, primary, config),
                "secondary": _group(cat_records, secondary, config) if secondary else None,
            }
        )

    link_sections = discover_report_links(reports_dir, config, {r["tag"] for r in records})

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    template = env.get_template("scorecard.html")
    html = template.render(
        sections=sections,
        secondary_label=config.secondary_label,
        link_sections=link_sections,
        bench_count=len(records),
        title=chrome.title,
        commit_sha=chrome.commit_sha,
        branch=chrome.branch,
        pr_number=chrome.pr_number if chrome.pr_number.isdigit() else "",
        run_url=_sanitize_url(chrome.run_url),
        repo_url=_sanitize_url(chrome.repo_url),
        nightly_url=_sanitize_url(chrome.nightly_url),
        main_url=_sanitize_url(chrome.main_url),
        stable_url=_sanitize_url(chrome.stable_url),
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
    )

    output_path = reports_dir / output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
