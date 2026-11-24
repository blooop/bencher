"""The ``by-src/<hash>/index.html`` pages: every published run of one source file.

Each page belongs to one source hash (:mod:`bencher.source_link`) and lists every
published run of that version of the file, newest first: benchmark name, time,
source revision and a link to the run's report. A page holds **only links**. It
never copies a report, so each report is stored once, wherever its publisher put
it.

Pages are small and have no expiry. When a page is rewritten, each link already
on it is checked against the store and the links whose report is gone are
dropped, so a store can keep ``by-src/`` forever under no age rule while its
reports age out under theirs. To clean ``by-src/`` up in bulk, delete the whole
prefix: the next publish of each source writes its page again, with the runs
published from then on.

Two writers that publish the same source at once both land: a page is rewritten
with a conditional write (generation or version match) and re-read and merged on
conflict.

Three ways to write the pages, all through :class:`SourceIndex`:

* :class:`bencher.publishing.CompleteReportPublisher` routes
  (``bencher publish``, ``BENCHER_PUBLISH_*``) do it after each publish.
* An in-process :class:`bencher.bench_report.Publisher` calls
  :func:`report_entries` and :meth:`SourceIndex.add_all`.
* A repository that uploads a report tree with its own tooling calls
  :func:`index_tree`, or ``bencher source-index``, on the uploaded root.
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote, urlsplit

from bencher.object_store import (
    Absent,
    Conflict,
    CreateOnly,
    Listed,
    Match,
    ObjectStore,
    ReadFailed,
    WriteFailed,
    Written,
)
from bencher.report_inventory import safe_path
from bencher.source_link import INDEX_DIR, SourceIdentity, serving_root

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
_STATE = re.compile(
    r'<script id="bencher-source-index" type="application/json">(.*?)</script>', re.DOTALL
)
# Result summaries as bencher.report_export.result_to_json writes them.
_SUMMARY_SUFFIXES = (".summary.json", ".result.json")
_MAX_LISTING = 1000


@dataclass(frozen=True)
class IndexEntry:
    """One published run of a source file, as an index page links it.

    ``run`` is the store key prefix that holds the run's whole report tree and
    ``key`` the store key of the linked page under it: the dead-link check lists
    ``run`` and looks for ``key``. ``url`` is where that page is served.
    """

    url: str
    run: str
    key: str
    benchmark: str
    executed_at: str = ""
    source_revision: str | None = None
    source_path: str = ""

    def __post_init__(self) -> None:
        parts = urlsplit(self.url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError(f"index entry URL must be absolute http(s), not {self.url!r}")
        safe_path(self.run)
        safe_path(self.key)
        if not self.key.startswith(f"{self.run}/"):
            raise ValueError(f"index entry key {self.key!r} is not under its run {self.run!r}")

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def _order(self) -> tuple:
        try:
            moment = datetime.fromisoformat(self.executed_at).timestamp()
        except ValueError:
            moment = float("-inf")
        return (moment, self.url, self.benchmark)


@dataclass(frozen=True)
class IndexUpdated:
    url: str
    key: str
    entries: int
    dropped: int
    written: bool


@dataclass(frozen=True)
class IndexFailed:
    reason: str
    key: str


def _render(digest: str, entries: Sequence[IndexEntry]) -> bytes:
    state = json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "source_hash": digest,
            "entries": [entry.to_dict() for entry in entries],
        },
        indent=1,
        sort_keys=True,
    ).replace("<", "\\u003c")
    paths = sorted({entry.source_path for entry in entries if entry.source_path})
    title = html.escape(", ".join(paths) or digest)
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(entry.benchmark)}</td>"
        f"<td>{html.escape(entry.executed_at)}</td>"
        f"<td><code>{html.escape(entry.source_revision or '')}</code></td>"
        f'<td><a href="{html.escape(entry.url, quote=True)}">report</a></td>'
        "</tr>"
        for entry in entries
    )
    return (
        "<!doctype html>\n<html><head><meta charset=\"utf-8\">"
        f"<title>Reports: {title}</title>"
        "<style>body{font-family:sans-serif;margin:2em}"
        "td,th{padding:.2em .8em;text-align:left}</style>\n"
        f'<script id="bencher-source-index" type="application/json">{state}</script>\n'
        f"</head><body>\n<h1>Reports: {title}</h1>\n"
        f"<p>Source hash <code>{digest}</code>. Every published run of this version of "
        "the file, newest first. This page holds links only.</p>\n"
        "<table><thead><tr><th>Benchmark</th><th>Executed (UTC)</th>"
        "<th>Source revision</th><th></th></tr></thead><tbody>\n"
        f"{rows}\n</tbody></table>\n</body></html>\n"
    ).encode()


def read_index(data: bytes) -> list[IndexEntry]:
    """The entries of an index page :func:`_render` wrote.

    Raises:
        ValueError: If *data* is not a bencher source index of a known schema.
    """
    match = _STATE.search(data.decode("utf-8", errors="replace"))
    if not match:
        raise ValueError("object is not a bencher source index")
    state = json.loads(match.group(1))
    if state.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported source index schema")
    return [IndexEntry(**entry) for entry in state["entries"]]


class SourceIndex:
    """Writes ``<prefix>/by-src/<hash>/index.html`` in *store*, served at *http_base*.

    *prefix* is the store key root of ``by-src/`` ("" for the store's own root)
    and *http_base* the URL that serves that root, so a page is served at
    ``<http_base>/by-src/<hash>/index.html`` -- the URL ``bencher stamp`` writes
    when given the same root.
    """

    def __init__(
        self, store: ObjectStore, http_base: str, prefix: str = "", *, attempts: int = 5
    ) -> None:
        if prefix:
            safe_path(prefix)
        if attempts < 1:
            raise ValueError("index attempts must be positive")
        self.store = store
        self.http_base = serving_root(http_base)
        self.prefix = prefix
        self.attempts = attempts
        self._runs: dict[str, frozenset[str] | None] = {}

    def page_key(self, digest: str) -> str:
        if SourceIdentity.from_dict({"hash": digest, "path": ""}) is None:
            raise ValueError(f"not a source hash: {digest!r}")
        key = f"{INDEX_DIR}/{digest}/index.html"
        return f"{self.prefix}/{key}" if self.prefix else key

    def page_url(self, digest: str) -> str:
        return f"{self.http_base}/{INDEX_DIR}/{digest}/index.html"

    def _run_keys(self, run: str) -> frozenset[str] | None:
        """Every key under *run*, listed once per index; None when the listing failed."""
        if run not in self._runs:
            keys: set[str] = set()
            token = None
            result: frozenset[str] | None = None
            while True:
                listed = self.store.list(f"{run}/", token=token, limit=_MAX_LISTING)
                if not isinstance(listed, Listed):
                    logger.warning("source index: cannot list %s: %s", run, listed.reason)
                    break
                keys.update(item.key for item in listed.items)
                token = listed.next_token
                if token is None:
                    result = frozenset(keys)
                    break
            self._runs[run] = result
        return self._runs[run]

    def _alive(self, entry: IndexEntry) -> bool:
        # A failed listing proves nothing, so the link stays.
        keys = self._run_keys(entry.run)
        return keys is None or entry.key in keys

    def add(self, digest: str, entries: Iterable[IndexEntry]) -> IndexUpdated | IndexFailed:
        """Merge *entries* into the page for *digest*, dropping dead links.

        *entries* are runs just published, so they are not checked. Every link
        already on the page is checked once per :class:`SourceIndex`.
        """
        key = self.page_key(digest)
        new = {(entry.url, entry.benchmark): entry for entry in entries}
        for _ in range(self.attempts):
            current = self.store.read(key)
            if isinstance(current, ReadFailed):
                return IndexFailed(current.reason, key)
            old: list[IndexEntry] = []
            if not isinstance(current, Absent):
                try:
                    old = read_index(current.data)
                except (ValueError, TypeError, KeyError) as exc:
                    # Fail closed: never overwrite an object this module did not write.
                    return IndexFailed(f"invalid current index: {exc}", key)
            kept = [e for e in old if (e.url, e.benchmark) not in new and self._alive(e)]
            merged = sorted([*kept, *new.values()], key=lambda e: e._order, reverse=True)
            dropped = len(old) - len(kept) - sum((e.url, e.benchmark) in new for e in old)
            data = _render(digest, merged)
            url = self.page_url(digest)
            if not isinstance(current, Absent) and current.data == data:
                return IndexUpdated(url, key, len(merged), 0, written=False)
            condition = CreateOnly() if isinstance(current, Absent) else Match(current.version)
            result = self.store.write(
                key,
                data,
                condition,
                metadata={"contentType": "text/html; charset=utf-8", "cacheControl": "no-cache"},
            )
            if isinstance(result, Written):
                return IndexUpdated(url, key, len(merged), dropped, written=True)
            if isinstance(result, WriteFailed) and not result.outcome_unknown:
                return IndexFailed(result.reason, key)
            # Conflict, or an outcome nobody knows: re-read and merge again.
            assert isinstance(result, (Conflict, WriteFailed))  # noqa: S101 - narrowing
        return IndexFailed("index CAS retry budget exhausted", key)

    def add_all(
        self, pairs: Iterable[tuple[str, IndexEntry]]
    ) -> dict[str, IndexUpdated | IndexFailed]:
        """Add each ``(hash, entry)`` pair, one page write per hash."""
        grouped: dict[str, list[IndexEntry]] = {}
        for digest, entry in pairs:
            grouped.setdefault(digest, []).append(entry)
        return {digest: self.add(digest, entries) for digest, entries in grouped.items()}


# --- entries -------------------------------------------------------------------------


def _join(base: str, relative: str) -> str:
    return f"{base.rstrip('/')}/{quote(relative, safe='/')}"


def _entry(
    source: SourceIdentity,
    *,
    url: str,
    run: str,
    key: str,
    benchmark: str,
    execution: dict | None,
) -> tuple[str, IndexEntry]:
    execution = execution or {}
    return source.hash, IndexEntry(
        url=url,
        run=run,
        key=key,
        benchmark=benchmark,
        executed_at=str(execution.get("executed_at") or ""),
        source_revision=execution.get("source_revision"),
        source_path=source.path,
    )


def manifest_entries(
    manifest: dict, *, run: str, run_url: str
) -> list[tuple[str, IndexEntry]]:
    """``(hash, entry)`` for each result of a complete report's ``report.json``.

    *run* is the store key prefix the report directory was written under and
    *run_url* the URL that serves it. Results with no recorded source (a report
    from an older bencher, or a benchmark defined in a notebook) are skipped.
    """
    pairs = []
    for result in manifest.get("results", []):
        source = SourceIdentity.from_dict(result.get("source"))
        if source is None:
            continue
        page = str(safe_path(result.get("page") or manifest["entry_page"]))
        pairs.append(
            _entry(
                source,
                url=_join(run_url, page),
                run=run,
                key=f"{run}/{page}",
                benchmark=str(result.get("benchmark", "")),
                execution=manifest.get("execution"),
            )
        )
    return pairs


def report_entries(
    report: object, *, url: str, run: str, key: str
) -> list[tuple[str, IndexEntry]]:
    """``(hash, entry)`` for each result of a live ``BenchReport`` a publisher uploaded.

    For implementations of the in-process ``Publisher`` protocol: *run* is the
    store key prefix the publisher uploaded the report under, *key* the store key
    of its page and *url* the URL it returns.
    """
    pairs = []
    for result in getattr(report, "bench_results", []):
        cfg = getattr(result, "bench_cfg", None)
        source = getattr(cfg, "source", None)
        if not isinstance(source, SourceIdentity):
            continue
        execution = getattr(cfg, "execution", None)
        identity = getattr(result, "identity", None)
        pairs.append(
            _entry(
                source,
                url=url,
                run=run,
                key=key,
                benchmark=str(getattr(identity, "bench_name", "") or getattr(cfg, "bench_name", "")),
                execution=execution.to_dict() if execution is not None else None,
            )
        )
    return pairs


def _summary_page(path: Path) -> Path | None:
    name = path.name
    for suffix in _SUMMARY_SUFFIXES:
        if name.endswith(suffix):
            page = path.with_name(name.removesuffix(suffix) + ".html")
            if page.is_file():
                return page
    page = path.with_name("index.html")
    return page if page.is_file() else None


def tree_entries(directory: str | Path, *, run: str, run_url: str) -> list[tuple[str, IndexEntry]]:
    """``(hash, entry)`` for every report in a local tree uploaded to *run*.

    Reads complete reports (``report.json``) and result summaries
    (``*.summary.json``, ``*.result.json``, ``result.json``) that record a
    ``source``. A summary links the HTML page beside it with the same stem, or
    the ``index.html`` beside it. The tree is read, not verified: a sync that
    left out large media still indexes.
    """
    root = Path(directory)
    safe_path(run)
    pairs: list[tuple[str, IndexEntry]] = []
    complete: set[Path] = set()
    for manifest_path in sorted(root.rglob("report.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("schema_version") != 1 or "results" not in manifest:
                continue
            relative = manifest_path.parent.relative_to(root).as_posix()
            sub_run = run if relative == "." else f"{run}/{relative}"
            sub_url = run_url if relative == "." else _join(run_url, relative)
            pairs.extend(manifest_entries(manifest, run=sub_run, run_url=sub_url))
            complete.add(manifest_path.parent)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            logger.warning("source index: skipping %s: %s", manifest_path, exc)
    summaries = sorted(
        {*root.rglob("*.summary.json"), *root.rglob("*.result.json"), *root.rglob("result.json")}
    )
    for path in summaries:
        if any(parent in complete for parent in path.parents):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            source = SourceIdentity.from_dict(data.get("source"))
            page = _summary_page(path)
            if source is None or page is None:
                continue
            relative = page.relative_to(root).as_posix()
            pairs.append(
                _entry(
                    source,
                    url=_join(run_url, relative),
                    run=run,
                    key=f"{run}/{relative}",
                    benchmark=str(data.get("bench_name") or page.stem),
                    execution=data.get("provenance"),
                )
            )
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            logger.warning("source index: skipping %s: %s", path, exc)
    return pairs


def index_tree(
    store: ObjectStore,
    directory: str | Path,
    *,
    run: str,
    run_url: str,
    http_base: str,
    prefix: str = "",
) -> dict[str, IndexUpdated | IndexFailed]:
    """Write the index pages for a report tree uploaded with other tooling.

    Args:
        store: The store the tree was uploaded to.
        directory: The local tree that was uploaded.
        run: The store key prefix it was uploaded under.
        run_url: The URL that serves *run*.
        http_base: The URL that serves *prefix* (the index root).
        prefix: The store key root of ``by-src/``; "" for the store root.
    """
    index = SourceIndex(store, http_base, prefix)
    return index.add_all(tree_entries(directory, run=run, run_url=run_url))


def main(argv: list[str] | None = None) -> int:
    """``bencher source-index DIR --store URL --http-base URL --uploaded-prefix KEY``."""
    parser = argparse.ArgumentParser(
        prog="bencher source-index",
        description="Write by-src/<hash>/index.html pages for a report tree that was "
        "uploaded with other tooling (for example a plain object-store sync).",
    )
    parser.add_argument("directory", help="The local report tree that was uploaded")
    parser.add_argument("--store", required=True, help="Local object database or gs:// URL")
    parser.add_argument(
        "--http-base", required=True, help="URL that serves the root of --store"
    )
    parser.add_argument(
        "--uploaded-prefix",
        required=True,
        help="Store key prefix the tree was uploaded under, relative to --store",
    )
    parser.add_argument(
        "--index-prefix",
        default="",
        help="Store key root of by-src/ (default: the root of --store)",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    from bencher.publication_target import PublicationTarget

    try:
        uploaded = args.uploaded_prefix.strip("/")
        index_prefix = args.index_prefix.strip("/")
        http_base = serving_root(args.http_base)
        store = PublicationTarget(store=args.store, prefix=uploaded, http_base=http_base)
        outcomes = index_tree(
            store.open_store(),
            args.directory,
            run=uploaded,
            run_url=_join(http_base, uploaded),
            http_base=_join(http_base, index_prefix) if index_prefix else http_base,
            prefix=index_prefix,
        )
    except (OSError, ValueError) as exc:
        print(f"source-index failed: {exc}", file=sys.stderr)  # noqa: T201 - CLI output
        return 1
    failed = False
    for digest, outcome in sorted(outcomes.items()):
        if isinstance(outcome, IndexFailed):
            failed = True
            print(  # noqa: T201 - CLI output
                f"{digest}: index failed: {outcome.reason} ({outcome.key})", file=sys.stderr
            )
        else:
            print(  # noqa: T201 - CLI output
                f"{outcome.url}: {outcome.entries} runs, {outcome.dropped} dead links dropped"
            )
    return 1 if failed else 0
