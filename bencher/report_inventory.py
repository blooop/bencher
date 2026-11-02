"""Verify a frozen complete report against its inventory, with the standard library only.

Kept apart from :mod:`bencher.complete_report` (which writes reports and so imports
:mod:`bencher.report_export`, numpy and xarray) so that readers of a report --
:mod:`bencher.scorecard`, the publishing and object-store code -- can check one
without importing the numerical stack. :mod:`bencher.complete_report` re-exports
every name here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

from bencher.execution import Execution


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
