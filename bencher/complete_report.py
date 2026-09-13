"""Frozen execution reports and their verified local asset closure."""

from __future__ import annotations

import fcntl
import hashlib
import html
import json
import os
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

from bencher.execution import Execution
from bencher.report_export import result_to_dict

if TYPE_CHECKING:
    from collections.abc import Sequence

    from bencher.bench_report import BenchReport
    from bencher.results.bench_result import BenchResult


def execution_for_results(results: Sequence[BenchResult]) -> Execution:
    """Require a nonempty bundle collected in one execution."""
    executions = {getattr(result.bench_cfg, "execution", None) for result in results}
    if len(executions) != 1 or None in executions:
        raise ValueError("a complete report requires results from one recorded execution")
    execution = next(iter(executions))
    assert execution is not None
    return execution


def safe_path(value: str) -> PurePosixPath:
    """Validate a canonical relative inventory path, without filesystem traversal."""
    path = PurePosixPath(value)
    invalid_syntax = not path.parts or path.is_absolute() or str(path) != value
    invalid_component = any(part in {".", ".."} for part in path.parts)
    if invalid_syntax or invalid_component or "\\" in value or "\x00" in value:
        raise ValueError(f"unsafe inventory path: {value!r}")
    return path


def file_digest(path: Path) -> str:
    """Hash report bytes without reading a whole recording into memory."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_report(directory: str | Path) -> dict:
    """Verify every inventoried file and reject unlisted files, symlinks and corruption."""
    root = Path(directory)
    manifest_path = root / "report.json"
    if manifest_path.is_symlink():
        raise ValueError("report manifest must not be a symlink")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported complete report schema")
    Execution(**manifest["execution"])
    seen = {"report.json"}
    for item in manifest["files"]:
        relative = safe_path(item["path"])
        if str(relative) in seen:
            raise ValueError(f"duplicate inventory path: {relative}")
        seen.add(str(relative))
        path = root / relative
        if any(part.is_symlink() for part in [path, *path.parents] if part != root.parent):
            raise ValueError(f"symlink in inventory: {relative}")
        if path.stat().st_size != item["size"] or file_digest(path) != item["sha256"]:
            raise ValueError(f"inventory digest mismatch: {relative}")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if seen != actual or manifest["entry_page"] not in seen - {"report.json"}:
        raise ValueError("report inventory does not match its directory")
    for result in manifest["results"]:
        if result["summary"] not in seen or result["page"] not in seen:
            raise ValueError("result references a file outside the inventory")
    return manifest


_ATTRIBUTE_URL = re.compile(r"""\b(?:src|href|poster)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_CSS_URL = re.compile(r"""url\(\s*["']?([^)'"\s]+)["']?\s*\)""", re.IGNORECASE)
_CSS_IMPORT = re.compile(r"""@import\s+["']([^"']+)["']""", re.IGNORECASE)
_SRCSET = re.compile(r"""\bsrcset\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


def _srcset_urls(value: str) -> list[str]:
    urls = []
    while value := value.lstrip(" ,\t\n\r"):
        parts = value.split(maxsplit=1)
        url = parts[0]
        urls.append(url.rstrip(","))
        value = parts[1] if len(parts) > 1 else ""
        if not url.endswith(","):
            value = value.partition(",")[2]
    return urls


class _Assets:
    """Copy and rewrite local URLs, including markup embedded in Bokeh JSON strings."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.copied: dict[Path, Path] = {}
        self.visited: set[Path] = set()

    def rewrite(self, destination: Path, source: Path | None = None) -> None:
        if destination in self.visited:
            return
        self.visited.add(destination)
        source = source or destination
        content = destination.read_text(encoding="utf-8")
        decoded = content.replace('\\"', '"')
        for _ in range(3):
            decoded = html.unescape(decoded)
        urls = {
            m.group(1)
            for regex in (_ATTRIBUTE_URL, _CSS_URL, _CSS_IMPORT)
            for m in regex.finditer(decoded)
        }
        for match in _SRCSET.finditer(decoded):
            urls.update(_srcset_urls(match.group(1)))
        replacements = {}
        for url in urls:
            new_url = self._url(url, source, destination)
            if new_url == url and urlsplit(url).scheme not in {"http", "https"}:
                continue
            old, new = url, new_url
            for _ in range(4):
                replacements[old] = new
                replacements[json.dumps(old)[1:-1]] = json.dumps(new)[1:-1]
                old, new = html.escape(old, quote=True), html.escape(new, quote=True)
        if replacements:
            pattern = "|".join(
                re.escape(url) for url in sorted(replacements, key=len, reverse=True)
            )
            content = re.sub(pattern, lambda match: replacements[match.group()], content)
        if "/rrd_static/" in content:
            raise ValueError(f"unresolved recording reference in {source}")
        destination.write_text(content, encoding="utf-8")

    def _url(self, url: str, source: Path, destination: Path) -> str:
        parts = urlsplit(url)
        if parts.scheme not in {"", "file"} or parts.netloc or not parts.path:
            return url
        path = Path(unquote(parts.path))
        candidates = [source.parent / path, Path.cwd() / path]
        if parts.path.startswith("/rrd_static/"):
            candidates = [Path("cachedir/rrd") / unquote(parts.path.removeprefix("/rrd_static/"))]
        original = next((p.resolve() for p in candidates if p.is_file()), None)
        if original is None:
            raise FileNotFoundError(f"report asset {url!r} referenced by {source}")
        target = self._copy(original)
        query = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if key == "url":
                value = self._url(value, original, target)
            query.append((key, value))
        relative = quote(Path(os.path.relpath(target, destination.parent)).as_posix(), safe="/")
        return urlunsplit(("", "", relative, urlencode(query), parts.fragment))

    def _copy(self, original: Path) -> Path:
        if original.is_relative_to(self.root):
            return original
        if original in self.copied:
            return self.copied[original]
        key = hashlib.sha256(os.fsencode(original)).hexdigest()
        target = self.root / "_assets" / key / original.name
        self.copied[original] = target
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        if target.suffix.lower() in {".html", ".htm", ".css", ".svg"}:
            self.rewrite(target, original)
        return target


def _result_entries(report: BenchReport) -> list[dict]:
    return [
        {
            "benchmark": result.identity.bench_name,
            "tag": result.identity.tag,
            "series": result.collected_series or result.bench_cfg.series,
            "configuration_key": result.identity.history_key,
            "history_namespace": result.bench_cfg.history_namespace,
            "summary": f"summaries/{index:04d}.json",
            "page": "index.html",
        }
        for index, result in enumerate(report.bench_results)
    ]


def save_complete_report(report: BenchReport, directory: str | Path) -> Path:
    """Finalize fresh output atomically; retries reuse the verified frozen directory."""
    execution = execution_for_results(report.bench_results)
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    final = root / execution.uuid
    entries = _result_entries(report)
    summaries = [result_to_dict(result, include_series=True) for result in report.bench_results]
    with (root / f".{execution.uuid}.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if final.exists():
            manifest = verify_report(final)
            recorded = [{**entry, "page": "index.html"} for entry in manifest["results"]]
            if manifest["execution"] != execution.to_dict() or recorded != entries:
                raise ValueError("frozen report execution identity conflict")
            for entry, summary in zip(entries, summaries, strict=True):
                if json.loads((final / entry["summary"]).read_text()) != summary:
                    raise ValueError("frozen report result content conflict")
            return final / "index.html"
        with tempfile.TemporaryDirectory(prefix=f".{execution.uuid}-", dir=root) as temporary:
            staging = Path(temporary) / "report"
            staging.mkdir()
            report.render_pending()
            report.save(staging, filename="index.html", in_html_folder=False, _process_rrd=False)
            for entry, result in zip(entries, report.bench_results, strict=True):
                entry["page"] = report.saved_page_for(result)
            assets = _Assets(staging)
            for path in sorted(staging.rglob("*.html")):
                assets.rewrite(path)
            for entry, summary in zip(entries, summaries, strict=True):
                path = staging / entry["summary"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
            manifest = {
                "schema_version": 1,
                "execution": execution.to_dict(),
                "entry_page": "index.html",
                "results": entries,
                "files": [
                    {
                        "path": path.relative_to(staging).as_posix(),
                        "size": path.stat().st_size,
                        "sha256": file_digest(path),
                    }
                    for path in sorted(staging.rglob("*"))
                    if path.is_file()
                ],
            }
            (staging / "report.json").write_text(
                json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8"
            )
            verify_report(staging)
            staging.rename(final)
    return final / "index.html"
