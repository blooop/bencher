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
from contextlib import ExitStack
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO

from bencher.bench_report import BenchReport
from bencher.complete_report import execution_for_results
from bencher.optional_deps import FullInstallRequiredError, full_install_required
from bencher.results.bench_result import BenchResult

if TYPE_CHECKING:
    from collections.abc import Sequence

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


class _MainPlaceholder:
    """Stands in for a class that a result's script defined in its ``__main__``."""

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        # An enum member pickles as a call of its class with its value; the value
        # is what a coordinate or a label needs.
        if len(args) == 1 and not kwargs:
            return args[0]
        return super().__new__(cls)


class _ResultUnpickler(pickle.Unpickler):
    """Load a result whose sweep class was defined in another process's ``__main__``.

    A bench script that defines its sweep class and runs it directly pickles that
    class as ``__main__.<Name>``, which no other process has: ``bencher compare``
    and ``bencher ab`` would fail before reading a number. The class is only the
    owner of the result's parameters, so a placeholder of the same name stands in
    for it and the dataset, result vars and claims load intact. Only a missing
    ``__main__`` attribute is replaced; any other unknown name still raises.
    """

    def __init__(self, file: BinaryIO) -> None:
        super().__init__(file)
        self._placeholders: dict[str, type] = {}

    def find_class(self, module: str, name: str) -> Any:
        try:
            with full_install_required():
                return super().find_class(module, name)
        except AttributeError:
            if module != "__main__":
                raise
        if name not in self._placeholders:
            logger.debug("result references __main__.%s; loading it as a placeholder", name)
            self._placeholders[name] = type(name, (_MainPlaceholder,), {"__module__": "__main__"})
        return self._placeholders[name]


def load_result(path: str | Path) -> BenchResult:
    """Load a :class:`BenchResult` previously written by :func:`save_result`.

    A result saved by a script whose sweep class lives in its ``__main__`` loads
    in any process, with a placeholder standing in for that class.
    """
    with Path(path).open("rb") as fh:
        return _ResultUnpickler(fh).load()


def save_results(results: Sequence[BenchResult], path: str | Path) -> Path:
    """Persist one execution's collected results, without a live Bench or its worker.

    Pickles are a trusted-input format, as for ``save_result``. Object indexes
    are restored even if serialization fails.
    """
    results = tuple(results)
    execution_for_results(results)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        for result in results:
            stack.callback(setattr, result, "object_index", result.object_index)
            result.object_index = []
        with path.open("wb") as stream:
            pickle.dump(results, stream, protocol=pickle.HIGHEST_PROTOCOL)
    return path


def render_report(
    result_or_path: BenchResult | Sequence[BenchResult] | str | Path,
    output_dir: str | Path,
    *,
    report: BenchReport | None = None,
    filename: str | None = None,
    in_html_folder: bool = False,
    portable: bool = False,
    emit_json: bool | str = False,
    cache_dir: str | Path | None = None,
    complete: bool = False,
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
        result_or_path: A result or saved result path. Complete mode also accepts
            a sequence or a bundle written by :func:`save_results`.
        output_dir: Directory to write the report into.
        report: An existing :class:`BenchReport` to append to. A new one is
            created (named after the benchmark) when omitted.
        filename: Output HTML filename. Defaults to ``<bench_name>.html``.
        in_html_folder: Forwarded to :meth:`BenchReport.save`.
        portable: Forwarded to :meth:`BenchReport.save` (base64-inline assets).
        emit_json: Forwarded to :meth:`BenchReport.save`; when truthy also writes
            a machine-readable ``result.json`` next to the HTML.
        cache_dir: Where to find the ``cachedir`` holding this result's
            ``ResultDataSet`` blob payloads. Defaults to ``BENCHER_CACHE_DIR``,
            then to ``./cachedir``, then to the cache dir recorded on the result
            at collect time. Pass it when neither inference can be right — a
            cache dir restored to a new path *and* rendered from somewhere else
            again, such as an offline cull working on a downloaded tarball.
            Without it those cells render as placeholders.
        complete: Export a frozen execution directory with a manifest, per-result
            summaries and local assets. Requires collection-time provenance.

    Returns:
        The path to the saved report.
    """
    if complete:
        loaded = (
            load_result(result_or_path)
            if isinstance(result_or_path, (str, Path))
            else result_or_path
        )
        results = (loaded,) if isinstance(loaded, BenchResult) else tuple(loaded)
        execution_for_results(results)
        if filename is not None or emit_json or portable or in_html_folder:
            raise ValueError("complete reports use a fixed layout and inventoried sidecar assets")
        if report is None:
            report = BenchReport(results[0].bench_cfg.bench_name)
        for result in results:
            result.blob_cache_dir = cache_dir
            result.post_setup()
            report.record_result(result)
        return report.save_report(output_dir)

    bench_res = (
        result_or_path if isinstance(result_or_path, BenchResult) else load_result(result_or_path)
    )
    bench_res.blob_cache_dir = cache_dir

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


def _prog() -> str:
    """Program name for ``--help``/usage text.

    Resolves to ``bencher`` when invoked via the installed console script and
    to the explicit ``python -m bencher.render`` form otherwise, so the usage
    line always names a command the reader can actually run.

    Matches a ``bencher`` prefix rather than an exact name so platform/packaging
    variants of the launcher still resolve (``bencher.exe`` on Windows,
    ``bencher-3.12`` for a versioned install); the module form's ``render.py``
    never matches.
    """
    exe = Path(sys.argv[0]).name
    return "bencher" if exe.startswith("bencher") else "python -m bencher.render"


def _render_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=_prog(),
        description="Render a saved benchmark result to HTML (and optionally JSON).",
    )
    parser.add_argument("result_path", nargs="?", help="Path to a saved .pkl result")
    parser.add_argument("output_dir", nargs="?", help="Directory to write the report into")
    parser.add_argument(
        "--report", action="store_true", help="Export a complete frozen execution bundle"
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        metavar="PATH",
        help="Also write a machine-readable result.json to PATH",
    )
    parser.add_argument(
        "--cachedir",
        dest="cache_dir",
        metavar="DIR",
        help=(
            "Cache dir holding this result's blob payloads. Defaults to "
            "$BENCHER_CACHE_DIR, then ./cachedir, then the dir recorded at "
            "collect time. Needed when the cache dir moved AND you are "
            "rendering from somewhere other than where the sweep ran."
        ),
    )
    return parser


def _compare_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"{_prog()} compare",
        description=(
            "Diff two saved results into a comparison JSON and/or PR-ready evidence: "
            "a Markdown block with a text chart per metric, and optional PNG charts."
        ),
    )
    parser.add_argument("baseline", help="Path to the baseline .pkl result")
    parser.add_argument("candidate", help="Path to the candidate .pkl result")
    parser.add_argument(
        "--json", dest="json_path", metavar="PATH", help="Write comparison JSON here"
    )
    parser.add_argument(
        "--markdown",
        dest="markdown_path",
        metavar="PATH",
        help=(
            "Write a Markdown block for a PR's Evidence section here. It is text only: "
            "every chart is drawn by GitHub, and no image is linked"
        ),
    )
    parser.add_argument(
        "--png",
        "--png-dir",
        dest="png_dir",
        metavar="DIR",
        help="Write one before/after PNG per metric here, for local viewing",
    )
    parser.add_argument(
        "--png-url-base",
        dest="png_url_base",
        metavar="URL",
        help="Deprecated and ignored: evidence is text only and links no image",
    )
    return parser


def _needs_full_install(exc: FullInstallRequiredError) -> int:
    # The message says what to install; a traceback would only bury it.
    print(f"{_prog()}: {exc}", file=sys.stderr)  # noqa: T201 - CLI error output
    return 1


def _load_or_fail(path: str, label: str) -> tuple[BenchResult | None, int]:
    """Load a saved result, returning ``(result, 0)`` or ``(None, exit_code)``.

    Centralizes the existence check + load + error logging shared by the
    render and compare flows, preserving their exit-code contract (``2`` for a
    missing file, ``1`` for a load failure).
    """
    if not Path(path).exists():
        print(f"{label} file not found: {path}", file=sys.stderr)  # noqa: T201 - CLI error output
        return None, 2
    try:
        return load_result(path), 0
    except FullInstallRequiredError as exc:
        return None, _needs_full_install(exc)
    except Exception:
        logger.exception("Failed to load %s from %s", label, path)
        return None, 1


def _run_compare(argv: list[str]) -> int:
    from bencher.evidence import PNG_URL_BASE_FLAG_DEPRECATED, unpaired_warnings, write_evidence

    parser = _compare_parser()
    args = parser.parse_args(argv)
    if not (args.json_path or args.markdown_path or args.png_dir):
        parser.error("give at least one of --json, --markdown or --png")
    if args.png_url_base is not None:
        print(f"{_prog()} compare: warning: {PNG_URL_BASE_FLAG_DEPRECATED}", file=sys.stderr)  # noqa: T201 - CLI output
    baseline, code = _load_or_fail(args.baseline, "baseline result")
    if baseline is None:
        return code
    candidate, code = _load_or_fail(args.candidate, "candidate result")
    if candidate is None:
        return code
    try:
        files = write_evidence(
            baseline,
            candidate,
            json_path=args.json_path,
            markdown_path=args.markdown_path,
            png_dir=args.png_dir,
        )
    except ValueError as exc:
        # Surface the specific, actionable message (e.g. no shared metrics) to
        # the user rather than only logging a generic "failed to compare".
        print(f"compare failed: {exc}", file=sys.stderr)  # noqa: T201 - CLI error output
        logger.exception("Failed to compare %s vs %s", args.baseline, args.candidate)
        return 1
    except Exception:
        logger.exception("Failed to compare %s vs %s", args.baseline, args.candidate)
        return 1
    for warning in unpaired_warnings(files.comparison):
        print(f"compare: warning: {warning}", file=sys.stderr)  # noqa: T201 - CLI warning output
    for path in (files.json_path, files.markdown_path, *files.pngs.values()):
        if path is not None:
            print(path)  # noqa: T201 - CLI prints the output paths
    return 0


def _run_subcommand(name: str, argv: list[str]) -> int:
    if name == "compare":
        return _run_compare(argv)
    if name == "ab":
        from bencher.ab import main as ab_main

        return ab_main(argv)
    from bencher.publishing_cli import main as publish_main

    return publish_main(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint.

    Invoke via the installed ``bencher`` console script, or equivalently with
    ``python -m bencher.render`` when running from a source checkout.

    Render: ``bencher <result.pkl> <output_dir> [--json PATH] [--cachedir DIR]``
    Compare: ``bencher compare <a.pkl> <b.pkl> [--json PATH] [--markdown PATH]
    [--png DIR]``
    A/B: ``bencher ab [--base REF] [--out DIR] [--png-dir DIR] -- <command...>``
    """
    argv = sys.argv[1:] if argv is None else argv

    if argv and argv[0] in ("compare", "ab", "publish"):
        return _run_subcommand(argv[0], argv[1:])

    args = _render_parser().parse_args(argv)

    if not args.result_path or not args.output_dir:
        print(  # noqa: T201 - CLI usage message
            f"Usage: {_prog()} <result_path> <output_dir> [--json PATH] [--cachedir DIR]",
            file=sys.stderr,
        )
        return 2
    bench_res, code = _load_or_fail(args.result_path, "result")
    if bench_res is None:
        return code
    if args.report and args.json_path:
        logger.error("--report includes summaries; --json is only for legacy rendering")
        return 1
    try:
        from bencher.report_export import result_to_json

        try:
            out = render_report(
                bench_res, args.output_dir, cache_dir=args.cache_dir, complete=args.report
            )
        except FullInstallRequiredError:
            # The JSON needs no plotting package, so a light install still gets it.
            if args.json_path:
                result_to_json(bench_res, args.json_path)
            raise
        if args.json_path:
            result_to_json(bench_res, args.json_path)
    except FullInstallRequiredError as exc:
        return _needs_full_install(exc)
    except Exception:
        # Top-level CLI guard: convert any render failure into a clean exit code.
        logger.exception("Failed to render report from %s", args.result_path)
        return 1
    print(out)  # noqa: T201 - CLI prints the output path
    return 0


if __name__ == "__main__":
    sys.exit(main())
