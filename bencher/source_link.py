r"""Link a benchmark's source file to its published reports, by content hash.

A file that defines a benchmark carries one comment line::

    # report: https://reports.example.org/by-src/3f9a1c2e7b4d5e60/index.html

The hash in that URL comes from the file's own bytes, so the URL is known before
any run. Publication writes ``by-src/<hash>/index.html`` (see
:mod:`bencher.source_index`), which lists every published run of that version of
the file. Before a run is published at that version, the URL gives a 404.

The hash rule (:func:`source_hash_bytes`), exactly:

1. Read the file as bytes. Do not decode it.
2. Replace every ``\r\n``, then every remaining ``\r``, with ``\n``.
3. Split on ``\n`` and drop every line that starts with ``#`` and then, after
   optional spaces or tabs, ``report:`` (the report line, see
   :data:`REPORT_LINE`). Indented lines are code, not report lines.
4. Join the remaining lines with ``\n`` and take the SHA-256 of the bytes.
5. Keep the first 16 hex digits.

So writing, moving or updating the report line does not change the hash, and the
same file hashes the same on every machine. The hash covers this one file only: a
change to a helper module it imports, a dependency or a data file does not change
it. The index shows each run's source revision, so a reader can see how old a
result is.

This module uses the standard library only, so a pre-commit hook can run
``bencher stamp --check`` without the plotting stack.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import os
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

#: The directory, under a serving root, that holds one index page per source hash.
INDEX_DIR = "by-src"
#: How many hex digits of the SHA-256 the URL carries.
HASH_LENGTH = 16
#: The environment variable that names the serving root for ``bencher stamp``.
REPORT_ROOT_ENV = "BENCHER_REPORT_ROOT"
#: What a report line starts with when ``bencher stamp`` writes it.
REPORT_LINE_PREFIX = "# report: "
#: A report line, as the hash rule and ``bencher stamp`` recognise it.
REPORT_LINE = re.compile(rb"^#[ \t]*report:")

_SHEBANG = b"#!"
_CODING = re.compile(rb"^[ \t\f]*#.*?coding[:=][ \t]*[-\w.]+")
# PEP 263 allows the encoding declaration on the first or second line only.
_CODING_LINES = 2
# Characters below this code point are ASCII control characters.
_FIRST_PRINTABLE_ASCII = 32


def _lines(data: bytes) -> list[bytes]:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n").split(b"\n")


def source_hash_bytes(data: bytes) -> str:
    """Hash source bytes by the rule in this module's docstring."""
    kept = [line for line in _lines(data) if not REPORT_LINE.match(line)]
    return hashlib.sha256(b"\n".join(kept)).hexdigest()[:HASH_LENGTH]


def source_hash(path: str | Path) -> str:
    """Hash the source file at *path*; see :func:`source_hash_bytes`."""
    return source_hash_bytes(Path(path).read_bytes())


def serving_root(value: str) -> str:
    """Return *value* as a serving root: an absolute http(s) URL, no trailing slash.

    Raises:
        ValueError: If *value* is not an absolute http(s) URL without
            credentials, query or fragment.
    """
    parts = urlsplit(value)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.netloc
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or any(ord(char) < _FIRST_PRINTABLE_ASCII or char.isspace() for char in value)
    ):
        raise ValueError(
            f"report root must be an absolute http(s) URL without credentials or query, "
            f"not {value!r}"
        )
    return value.rstrip("/")


def index_url(root: str, digest: str) -> str:
    """The URL of the index page for *digest* under the serving *root*."""
    return f"{serving_root(root)}/{INDEX_DIR}/{digest}/index.html"


def report_line(root: str, digest: str) -> str:
    """The comment line a source file with hash *digest* carries."""
    return f"{REPORT_LINE_PREFIX}{index_url(root, digest)}"


def repo_relative(path: Path) -> str:
    """*path* relative to the nearest directory above it that holds ``.git``.

    With no such directory, the file name alone: a path relative to wherever the
    process started would differ between machines.
    """
    resolved = path.resolve()
    for parent in resolved.parents:
        if (parent / ".git").exists():
            return resolved.relative_to(parent).as_posix()
    return resolved.name


@dataclass(frozen=True)
class SourceIdentity:
    """The source file that defines a benchmark: its hash and repo-relative path."""

    hash: str
    path: str

    def to_dict(self) -> dict:
        return {"hash": self.hash, "path": self.path}

    @classmethod
    def from_dict(cls, value: object) -> SourceIdentity | None:
        """Read :meth:`to_dict` back; None for anything else, such as an older report."""
        if not isinstance(value, dict):
            return None
        digest, path = value.get("hash"), value.get("path")
        if not isinstance(digest, str) or not isinstance(path, str):
            return None
        if len(digest) != HASH_LENGTH or any(c not in "0123456789abcdef" for c in digest):
            return None
        return cls(digest, path)

    @classmethod
    def of_file(cls, path: str | Path) -> SourceIdentity:
        return cls(source_hash(path), repo_relative(Path(path)))


def source_of(benchmark: object) -> SourceIdentity | None:
    """The source identity of the file that defines *benchmark*, or None.

    *benchmark* is a function, a class, or an instance of a class (a
    ``ParametrizedSweep``, say), whose class's file is used. Returns None when the
    source file cannot be found: a builtin, an interactive session, a notebook
    cell.
    """
    target = benchmark
    if not (inspect.isfunction(target) or inspect.isclass(target) or inspect.ismethod(target)):
        target = type(benchmark)
    if inspect.ismethod(target):
        owner = target.__self__
        target = owner if inspect.isclass(owner) else type(owner)
    try:
        filename = inspect.getsourcefile(target)  # ty: ignore[invalid-argument-type]
    except (TypeError, OSError):
        # A builtin, or a class defined in `python -c` or a notebook cell.
        return None
    if filename is None or not Path(filename).is_file():
        return None
    try:
        return SourceIdentity.of_file(filename)
    except OSError:
        return None


# --- stamp -------------------------------------------------------------------------


def _newline(data: bytes) -> bytes:
    if b"\r\n" in data:
        return b"\r\n"
    if b"\r" in data:
        return b"\r"
    return b"\n"


def stamp_bytes(data: bytes, root: str) -> bytes:
    """*data* with exactly one current report line.

    An existing report line is replaced in place and any others are removed. With
    none, the line goes after a shebang and a PEP 263 encoding line, and before
    everything else; a comment before a module docstring leaves it the docstring.
    The file keeps its own line endings.
    """
    newline = _newline(data)
    line = report_line(root, source_hash_bytes(data)).encode()
    lines = _lines(data)
    positions = [i for i, text in enumerate(lines) if REPORT_LINE.match(text)]
    if positions:
        lines[positions[0]] = line
        for index in reversed(positions[1:]):
            del lines[index]
    else:
        at = 0
        if lines and lines[0].startswith(_SHEBANG):
            at = 1
        while at < min(len(lines), _CODING_LINES) and _CODING.match(lines[at]):
            at += 1
        # Only inserted or removed report lines differ, so the hash is unchanged.
        lines.insert(at, line)
    return newline.join(lines)


@dataclass(frozen=True)
class StampStatus:
    """What ``bencher stamp --check`` found in one file."""

    path: Path
    state: str  # "current", "missing", "stale" or "unstamped" (skipped)
    expected: str


def check_bytes(data: bytes, root: str) -> str:
    """``"current"``, ``"missing"`` or ``"stale"`` for the report line(s) in *data*."""
    found = [line for line in _lines(data) if REPORT_LINE.match(line)]
    if not found:
        return "missing"
    expected = report_line(root, source_hash_bytes(data)).encode()
    return "current" if found == [expected] else "stale"


def has_report_line(data: bytes) -> bool:
    return any(REPORT_LINE.match(line) for line in _lines(data))


def _pyproject_root(start: Path) -> str | None:
    for directory in (start, *start.parents):
        candidate = directory / "pyproject.toml"
        if candidate.is_file():
            try:
                config = tomllib.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None
            value = config.get("tool", {}).get("bencher", {}).get("report_root")
            return value if isinstance(value, str) and value else None
    return None


def resolve_root(
    explicit: str | None = None,
    env: Mapping[str, str] | None = None,
    start: Path | None = None,
) -> str:
    """The serving root for report lines.

    In order: *explicit* (``--root``), the ``BENCHER_REPORT_ROOT`` variable, then
    ``report_root`` under ``[tool.bencher]`` in the nearest ``pyproject.toml``
    above *start* (the working directory by default).

    Raises:
        ValueError: If none of them is set, or the value is not a serving root.
    """
    source = os.environ if env is None else env
    value = (
        explicit
        or source.get(REPORT_ROOT_ENV, "").strip()
        or _pyproject_root((start or Path.cwd()).resolve())
    )
    if not value:
        raise ValueError(
            f"no report root: pass --root, set {REPORT_ROOT_ENV}, or set report_root "
            "under [tool.bencher] in pyproject.toml"
        )
    return serving_root(value)


def stamp_files(
    paths: Sequence[str | Path], root: str, *, check: bool = False, only_stamped: bool = False
) -> list[StampStatus]:
    """Stamp (or with *check*, only inspect) each file in *paths*.

    With *only_stamped*, a file with no report line is skipped (state
    ``"unstamped"``): a repository can opt files in one at a time.
    """
    statuses = []
    for raw in paths:
        path = Path(raw)
        data = path.read_bytes()
        expected = report_line(root, source_hash_bytes(data))
        if only_stamped and not has_report_line(data):
            statuses.append(StampStatus(path, "unstamped", expected))
            continue
        state = check_bytes(data, root)
        if not check and state != "current":
            path.write_bytes(stamp_bytes(data, root))
        statuses.append(StampStatus(path, state, expected))
    return statuses


def main(argv: list[str] | None = None) -> int:
    """``bencher stamp [--check] [--root URL] [--only-stamped] FILE...``."""
    parser = argparse.ArgumentParser(
        prog="bencher stamp",
        description="Write or check the '# report:' line in benchmark source files.",
    )
    parser.add_argument("files", nargs="*", help="Source files that define benchmarks")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Change nothing; exit 1 when a line is missing or stale",
    )
    parser.add_argument(
        "--root",
        help=f"Serving root of the reports (default: ${REPORT_ROOT_ENV}, "
        "then [tool.bencher] report_root in pyproject.toml)",
    )
    parser.add_argument(
        "--only-stamped",
        action="store_true",
        help="Skip files that have no report line yet",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        root = resolve_root(args.root)
        statuses = stamp_files(args.files, root, check=args.check, only_stamped=args.only_stamped)
    except (OSError, ValueError) as exc:
        print(f"bencher stamp: {exc}", file=sys.stderr)  # noqa: T201 - CLI output
        return 2
    failed = False
    for status in statuses:
        if status.state in {"current", "unstamped"}:
            continue
        failed = True
        if args.check:
            print(  # noqa: T201 - CLI output
                f"{status.path}: report line is {status.state}; expected\n  {status.expected}\n"
                f"  run: bencher stamp {status.path}",
                file=sys.stderr,
            )
        else:
            print(f"{status.path}: stamped ({status.state})")  # noqa: T201 - CLI output
    # Like a formatter, a run that changed files exits 1, so a pre-commit hook
    # stops the commit until the stamped files are added.
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
