"""Generate a BenchReport from pytest JUnit XML output.

CLI: python bencher/test_timing_report.py [junit.xml] [output_dir]
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import panel as pn
import plotly.graph_objs as go

from bencher.bench_report import BenchReport


def parse_junit_xml(path: str | Path) -> pd.DataFrame:
    """Parse a JUnit XML file into a DataFrame of test cases."""
    tree = ET.parse(path)
    root = tree.getroot()

    rows = []
    for suite in root.iter("testsuite"):
        for case in suite.iter("testcase"):
            name = case.get("name", "")
            classname = case.get("classname", "")
            time_s = float(case.get("time", 0))
            # Derive the file from classname (dotted module path)
            file = classname.rsplit(".", 1)[0] if "." in classname else classname
            rows.append({"file": file, "test": name, "classname": classname, "time": time_s})

    return pd.DataFrame(rows, columns=["file", "test", "classname", "time"])


def build_time_by_file_tab(df: pd.DataFrame) -> pn.pane.Plotly:
    """Horizontal bar chart of total time per test file."""
    by_file = df.groupby("file")["time"].sum().sort_values()
    fig = go.Figure(
        go.Bar(x=by_file.values, y=by_file.index, orientation="h", text=by_file.round(2))
    )
    fig.update_layout(
        title="Total Time by Test File (seconds)",
        xaxis_title="Time (s)",
        yaxis_title="",
        height=max(400, len(by_file) * 28),
        margin={"l": 300},
    )
    return pn.pane.Plotly(fig, name="Time by File", sizing_mode="stretch_width")


def build_slowest_tests_tab(df: pd.DataFrame, top_n: int = 50) -> pn.widgets.Tabulator:
    """Table of the slowest individual tests."""
    slowest = df.nlargest(top_n, "time")[["classname", "test", "time"]].reset_index(drop=True)
    slowest.columns = ["Module", "Test", "Time (s)"]
    slowest["Time (s)"] = slowest["Time (s)"].round(4)
    return pn.widgets.Tabulator(
        slowest,
        name="Slowest Tests",
        sizing_mode="stretch_width",
        show_index=False,
        page_size=50,
    )


def build_summary_tab(df: pd.DataFrame) -> pn.pane.Markdown:
    """Markdown summary of aggregate timing stats."""
    total = df["time"].sum()
    count = len(df)
    mean = df["time"].mean()
    median = df["time"].median()
    top5 = df.nlargest(5, "time")
    top5_lines = "\n".join(
        f"  - `{r['classname']}::{r['test']}` — {r['time']:.3f}s" for _, r in top5.iterrows()
    )
    md = f"""## Test Suite Timing Summary

| Metric | Value |
|--------|-------|
| Total tests | {count} |
| Total time | {total:.2f}s |
| Mean | {mean:.4f}s |
| Median | {median:.4f}s |

### Top 5 slowest tests
{top5_lines}
"""
    return pn.pane.Markdown(md, name="Summary", width=800)


def generate_report(junit_path: str | Path, output_dir: str | Path = "reports") -> Path:
    """Parse JUnit XML and generate an HTML timing report."""
    df = parse_junit_xml(junit_path)

    report = BenchReport("test_timing")
    report.append_tab(build_time_by_file_tab(df), "Time by File")
    report.append_tab(build_slowest_tests_tab(df), "Slowest Tests")
    report.append_tab(build_summary_tab(df), "Summary")

    return report.save_index(directory=str(output_dir))


if __name__ == "__main__":
    junit_xml = sys.argv[1] if len(sys.argv) > 1 else "test-results.xml"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "reports"
    result_path = generate_report(junit_xml, out_dir)
    print(f"Report saved to: {result_path}")
