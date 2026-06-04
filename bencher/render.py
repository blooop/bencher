"""Out-of-process rendering for benchmark results.

This module is the *render* half of bencher's collect/render split. The
collect half (:meth:`bencher.Bench.collect`, i.e. ``plot_sweep(auto_plot=False)``)
runs a sweep and computes regression detection **without** building any
holoviews/panel/bokeh objects, returning a fully-populated :class:`BenchResult`.

Why split: holoviews/panel/bokeh build large object graphs backed by
C-extension wrappers (param, pandas, bokeh). When CPython's cyclic garbage
collector traverses those wrappers while *foreign* live C-extension state
exists in the same interpreter (e.g. ROS 2 ``rclpy``/DDS), the process can
segfault. Rendering from a persisted result in a separate, clean process
(one that never imported the foreign extension) makes that class of crash
impossible by construction.

Typical usage::

    # Process 1 — holds rclpy/DDS; never builds plots:
    res = bench.collect(...)            # auto_plot=False under the hood
    bencher.save_result(res, "result.pkl")

    # Process 2 — clean (only imports bencher), e.g. spawned via:
    #   python -m bencher.render result.pkl output_dir
    bencher.render_report("result.pkl", "output_dir")

``render_report`` is also importable for in-process use when isolation is not
required.
"""

from __future__ import annotations

import argparse
import logging
import pickle
import sys
from pathlib import Path

from bencher.results.bench_result import BenchResult
from bencher.bench_report import BenchReport

logger = logging.getLogger(__name__)


def save_result(bench_res: BenchResult, path: str | Path) -> Path:
    """Persist a collected :class:`BenchResult` to *path* via pickle.

    Mirrors how bencher already caches results internally: the (potentially
    non-pickleable) ``object_index`` is stripped before writing and restored
    afterwards, so the live object is unchanged.

    Args:
        bench_res: A result from :meth:`Bench.collect` / ``plot_sweep``.
        path: Destination file path.

    Returns:
        The path written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    obj_index_tmp = getattr(bench_res, "object_index", None)
    if obj_index_tmp is not None:
        bench_res.object_index = []
    try:
        with path.open("wb") as fh:
            pickle.dump(bench_res, fh, protocol=pickle.HIGHEST_PROTOCOL)
    finally:
        if obj_index_tmp is not None:
            bench_res.object_index = obj_index_tmp
    return path


def load_result(path: str | Path) -> BenchResult:
    """Load a :class:`BenchResult` previously written by :func:`save_result`."""
    with Path(path).open("rb") as fh:
        return pickle.load(fh)


def render_report(
    result_or_path: BenchResult | str | Path,
    output_dir: str | Path,
    *,
    report: BenchReport | None = None,
    filename: str | None = None,
    in_html_folder: bool = False,
    portable: bool = False,
    emit_json: bool | str = False,
) -> Path:
    """Render a collected result to an HTML report.

    Reconstructs the holoviews/panel report from a result produced by
    :meth:`Bench.collect` (or a path to one saved with :func:`save_result`)
    and writes it under *output_dir*. This is the only step that constructs
    plotting objects, and it is designed to run in a process free of foreign
    C-extension state.

    The result already carries its ``regression_report`` (computed during
    collection), so no sweep re-execution happens here.

    Args:
        result_or_path: A :class:`BenchResult`, or a path to a saved one.
        output_dir: Directory to write the report into.
        report: An existing :class:`BenchReport` to append to. A new one is
            created (named after the benchmark) when omitted.
        filename: Output HTML filename. Defaults to ``<bench_name>.html``.
        in_html_folder: Forwarded to :meth:`BenchReport.save`.
        portable: Forwarded to :meth:`BenchReport.save` (base64-inline assets).
        emit_json: Forwarded to :meth:`BenchReport.save`; when truthy also writes
            a machine-readable ``result.json`` next to the HTML.

    Returns:
        The path to the saved report.
    """
    bench_res = (
        result_or_path if isinstance(result_or_path, BenchResult) else load_result(result_or_path)
    )

    # post_setup is normally run by run_sweep before the auto_plot gate; it only
    # touches the dataset/metadata. Re-run defensively in case the result was
    # loaded from disk without it (idempotent).
    bench_res.post_setup()

    if report is None:
        report = BenchReport(bench_res.bench_cfg.bench_name)
    report.append_result(bench_res)

    return report.save(
        directory=output_dir,
        filename=filename,
        in_html_folder=in_html_folder,
        portable=portable,
        emit_json=emit_json,
    )


def _render_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m bencher.render",
        description="Render a saved benchmark result to HTML (and optionally JSON).",
    )
    parser.add_argument("result_path", nargs="?", help="Path to a saved .pkl result")
    parser.add_argument("output_dir", nargs="?", help="Directory to write the report into")
    parser.add_argument(
        "--json",
        dest="json_path",
        metavar="PATH",
        help="Also write a machine-readable result.json to PATH",
    )
    return parser


def _compare_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m bencher.render compare",
        description="Diff two saved results into a machine-readable comparison JSON.",
    )
    parser.add_argument("baseline", help="Path to the baseline .pkl result")
    parser.add_argument("candidate", help="Path to the candidate .pkl result")
    parser.add_argument(
        "--json", dest="json_path", metavar="PATH", required=True, help="Write comparison JSON here"
    )
    return parser


def _run_compare(argv: list[str]) -> int:
    from bencher.report_export import comparison_to_json

    args = _compare_parser().parse_args(argv)
    for label, path in (("baseline", args.baseline), ("candidate", args.candidate)):
        if not Path(path).exists():
            print(f"{label} result file not found: {path}", file=sys.stderr)
            return 2
    try:
        out = comparison_to_json(
            load_result(args.baseline), load_result(args.candidate), args.json_path
        )
    except Exception:  # noqa: BLE001  pylint: disable=broad-exception-caught
        logger.exception("Failed to compare %s vs %s", args.baseline, args.candidate)
        return 1
    print(out)
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint.

    Render: ``python -m bencher.render <result.pkl> <output_dir> [--json PATH]``
    Compare: ``python -m bencher.render compare <a.pkl> <b.pkl> --json PATH``
    """
    argv = sys.argv[1:] if argv is None else argv

    if argv and argv[0] == "compare":
        return _run_compare(argv[1:])

    args = _render_parser().parse_args(argv)

    if not args.result_path or not args.output_dir:
        print(
            "Usage: python -m bencher.render <result_path> <output_dir> [--json PATH]",
            file=sys.stderr,
        )
        return 2
    if not Path(args.result_path).exists():
        print(f"Result file not found: {args.result_path}", file=sys.stderr)
        return 2
    try:
        bench_res = load_result(args.result_path)
        out = render_report(bench_res, args.output_dir)
        if args.json_path:
            from bencher.report_export import result_to_json

            result_to_json(bench_res, args.json_path)
    except Exception:  # noqa: BLE001  pylint: disable=broad-exception-caught
        # Top-level CLI guard: convert any render failure into a clean exit code.
        logger.exception("Failed to render report from %s", args.result_path)
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
