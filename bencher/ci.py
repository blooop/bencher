"""CI integration utilities for benchmark regression gating.

Provides functions to:
- Write structured performance summaries parseable by CI workflows
- Generate GitHub-flavored Markdown for PR comments
- Render regression plot PNGs for regressed metrics
- Emit pytest warnings on detected regressions

All functions operate on :class:`~bencher.regression.RegressionReport` and
:class:`~bencher.regression.RegressionResult` — no framework-specific
dependencies beyond bencher itself.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path

from bencher.regression import RegressionReport, RegressionResult, method_cells

logger = logging.getLogger(__name__)

_SUMMARY_HEADER = "variable|regressed|change_percent|baseline|current|threshold|direction|method"


def write_performance_summary(
    report: RegressionReport,
    path: Path | str,
    *,
    metrics_filter: dict[str, float] | None = None,
    bench_name: str = "",
    append: bool = True,
) -> list[str]:
    """Write regression results to a pipe-delimited text file for CI parsing.

    Each line encodes one variable comparison::

        variable|regressed|change_percent|baseline|current|threshold|direction|method

    Args:
        report: Regression report from a benchmark run.
        path: Output file path. Created (with parents) if it does not exist.
        metrics_filter: Optional allowlist mapping ``"bench_name/variable"``
            (or just ``"variable"`` when *bench_name* is empty) to a
            per-metric regression threshold (percentage).  When provided,
            only matching metrics are written and the per-metric threshold
            overrides the report-level one for the regressed/not-regressed
            decision.  When ``None``, every result in the report is written
            using the thresholds already stored on each
            :class:`~bencher.regression.RegressionResult`.
        bench_name: Optional prefix for variable names in the output
            (e.g. ``"bench_robot_state_planning"``).  When set, each
            variable is written as ``"{bench_name}/{variable}"``.
        append: Append to the file (default) rather than overwriting.

    Returns:
        The lines that were written (without trailing newlines).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for r in report.results:
        qualified = f"{bench_name}/{r.variable}" if bench_name else r.variable

        if metrics_filter is not None:
            if qualified not in metrics_filter:
                continue
            threshold = metrics_filter[qualified]
            regressed = _apply_threshold(r, threshold)
        else:
            threshold = r.threshold
            regressed = r.regressed

        lines.append(
            f"{qualified}|{regressed}|{r.change_percent:+.2f}|"
            f"{r.baseline_value:.4g}|{r.current_value:.4g}|"
            f"{threshold}|{r.direction}|{r.method}"
        )

    if lines:
        mode = "a" if append else "w"
        with open(path, mode) as f:
            f.write("\n".join(lines) + "\n")

    return lines


def _apply_threshold(r: RegressionResult, threshold: float) -> bool:
    """Re-evaluate whether *r* is regressed using a custom *threshold* (%)."""
    if r.method == "absolute":
        return r.regressed
    if r.direction == "minimize":
        return r.change_percent >= threshold
    if r.direction == "maximize":
        return r.change_percent <= -threshold
    return abs(r.change_percent) >= threshold


def render_regression_plots(
    report: RegressionReport,
    output_dir: Path | str,
    *,
    metrics_filter: dict[str, float] | None = None,
    bench_name: str = "",
) -> dict[str, Path]:
    """Render diagnostic PNGs for regressed metrics.

    Args:
        report: Regression report to scan for regressions.
        output_dir: Directory where PNGs are written.
        metrics_filter: When provided, only render plots for metrics that
            appear in the filter AND are regressed per the filter's threshold.
            When ``None``, renders for every regressed result in the report.
        bench_name: Optional prefix for variable names (same as
            :func:`write_performance_summary`).

    Returns:
        Mapping of qualified variable name to the saved PNG path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rendered: dict[str, Path] = {}
    for r in report.results:
        qualified = f"{bench_name}/{r.variable}" if bench_name else r.variable

        if metrics_filter is not None:
            if qualified not in metrics_filter:
                continue
            if not _apply_threshold(r, metrics_filter[qualified]):
                continue
        elif not r.regressed:
            continue

        safe_name = qualified.replace("/", "_")
        plot_path = output_dir / f"{safe_name}.png"
        try:
            r.render_png(path=plot_path)
            rendered[qualified] = plot_path
        except (OSError, ValueError, RuntimeError):
            logger.warning(
                "Failed to render regression PNG for %s at %s",
                qualified,
                plot_path,
                exc_info=True,
            )

    return rendered


def warn_on_regressions(
    report: RegressionReport,
    *,
    summary_path: Path | str | None = None,
    plot_dir: Path | str | None = None,
    metrics_filter: dict[str, float] | None = None,
    bench_name: str = "",
) -> None:
    """Emit pytest warnings for regressions and optionally write CI artifacts.

    Convenience wrapper that combines :func:`write_performance_summary`,
    :func:`render_regression_plots`, and pytest warning emission into a
    single call.

    Args:
        report: Regression report from a benchmark run.
        summary_path: If set, write the performance summary file here.
        plot_dir: If set, render regression PNGs into this directory.
        metrics_filter: Optional per-metric allowlist (see
            :func:`write_performance_summary`).
        bench_name: Optional prefix for qualified variable names.
    """
    if summary_path is not None:
        write_performance_summary(
            report,
            summary_path,
            metrics_filter=metrics_filter,
            bench_name=bench_name,
        )

    if plot_dir is not None:
        render_regression_plots(
            report,
            plot_dir,
            metrics_filter=metrics_filter,
            bench_name=bench_name,
        )

    if report.has_regressions:
        summary = report.summary()
        warnings.warn(
            f"Benchmark regression detected:\n{summary}",
            stacklevel=2,
        )


# ─── PR Comment Generation ──────────────────────────────────────────────────


def parse_performance_summary(path: Path | str) -> list[dict[str, str]]:
    """Parse a performance_summary.txt file into a list of row dicts.

    Each dict has keys: ``variable``, ``regressed``, ``change_percent``,
    ``baseline``, ``current``, ``threshold``, ``direction``, ``method``.

    Blank lines and lines that don't split into 8 fields are skipped.
    """
    rows: list[dict[str, str]] = []
    keys = _SUMMARY_HEADER.split("|")
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) != len(keys):
            continue
        rows.append(dict(zip(keys, parts)))
    return rows


def generate_regression_comment(
    summary_path: Path | str,
    *,
    report_url: str = "",
    plot_url_prefix: str = "",
) -> str:
    """Generate a GitHub-flavored Markdown comment from a performance summary.

    Produces a formatted table with status icons suitable for posting as a
    PR comment via the GitHub API.

    Args:
        summary_path: Path to the pipe-delimited performance_summary.txt.
        report_url: URL to the full benchmark report (linked at the bottom).
        plot_url_prefix: URL prefix for regression plot images. When set,
            regressed variables get a link to
            ``{plot_url_prefix}/{safe_variable_name}.png``.

    Returns:
        The Markdown comment body as a string.
    """
    rows = parse_performance_summary(summary_path)
    if not rows:
        return ""

    has_regressions = any(r["regressed"] == "True" for r in rows)

    lines: list[str] = []
    lines.append("<!-- benchmark-regression-comment -->")
    if has_regressions:
        lines.append("## :warning: Benchmark Regressions Detected")
    else:
        lines.append("## Benchmark Performance Summary")
    lines.append("")
    lines.append("Comparison against baseline:")
    lines.append("")
    lines.append("| Variable | Change | Baseline | Current | Status |")
    lines.append("|----------|--------|----------|---------|--------|")

    for row in rows:
        table_line = _format_comment_row(row)
        lines.append(table_line)

    if has_regressions and plot_url_prefix:
        lines.append("")
        lines.append("### Regression Graphs")
        lines.append("")
        for row in rows:
            if row["regressed"] == "True":
                safe_name = row["variable"].replace("/", "_")
                img_url = f"{plot_url_prefix}/{safe_name}.png"
                lines.append(f"- [`{row['variable']}`]({img_url})")
        lines.append("")

    if has_regressions:
        lines.append("")
        lines.append("### How to proceed")
        lines.append("")
        lines.append(
            "If regressions are expected (e.g. added safety checks, changed algorithm):"
        )
        lines.append(
            "1. Add the `benchmark-regression-expected` label to this PR"
        )
        lines.append(
            "2. Click **Re-run failed jobs** — only this gate re-runs (no full rebuild)"
        )

    if report_url:
        lines.append("")
        lines.append(f"<sub>[View benchmark reports]({report_url})</sub>")

    return "\n".join(lines)


def _format_comment_row(row: dict[str, str]) -> str:
    """Format a single performance summary row as a Markdown table row."""
    var = row["variable"]
    regressed = row["regressed"]
    change = row["change_percent"]
    baseline = row["baseline"]
    current = row["current"]
    direction = row["direction"]
    method = row["method"]

    if method == "absolute":
        if direction == "maximize":
            limit_label = f"≥ {baseline}"
            violation = "below floor"
        else:
            limit_label = f"≤ {baseline}"
            violation = "above ceiling"
        if regressed == "True":
            status = f":x: **Regression** ({violation})"
        else:
            status = ":white_check_mark: Within limit"
        return f"| `{var}` | — | {limit_label} | {current} | {status} |"

    try:
        abs_change = abs(float(change))
    except ValueError:
        abs_change = 0.0

    if regressed == "True":
        status = ":x: **Regression**"
    elif abs_change < 10.0:
        status = ":heavy_minus_sign: Within noise (<10%)"
    elif (change.startswith("-") and direction == "minimize") or (
        change.startswith("+") and direction == "maximize"
    ):
        status = ":white_check_mark: Improved"
    else:
        status = ":warning: Potential regression (10-15%)"

    return f"| `{var}` | {change}% | {baseline} | {current} | {status} |"
