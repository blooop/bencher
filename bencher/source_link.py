r"""Link a benchmark's source file to its published reports, by hash or by path.

A file that defines a benchmark carries one comment line. The line has two
forms, the *report key* modes:

``hash`` (the default)::

    # report: https://reports.example.org/by-src/3f9a1c2e7b4d5e60/index.html

  The hash in that URL comes from the file's own bytes, so the URL is known
  before any run. ``by-src/<hash>/index.html`` lists every published run of that
  version of the file. Before a run is published at that version, the URL gives
  a 404. Every edit makes the line stale, so two branches that edit one file can
  merge and leave a stale line behind.

``path``::

    # report: https://reports.example.org/by-path/pkg/bench_x.py/index.html

  The path is the file's path from the git root (:func:`repo_relative`). The
  line does not change when the file changes, only when it moves.
  ``by-path/<path>/index.html`` lists every published run of every version of
  the file, newest first, with the source hash and revision of each run. A run
  takes its path from this line (:func:`path_from_line`), so a bench that runs
  from an install tree or Bazel runfiles, with no ``.git`` above it, still
  records its repository path.

Publication writes both pages for each run (see :mod:`bencher.source_index`),
whatever line the file carries. ``bencher stamp --key {hash,path}`` picks the
mode; the default comes from ``report_key`` under ``[tool.bencher]`` in
``pyproject.toml``, then ``BENCHER_REPORT_KEY``, else ``hash``.

A path is a store key, so :func:`safe_source_path` checks it before any use:
relative POSIX, no empty, ``.`` or ``..`` segment, and only letters, digits and
``._-/+@``.

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
HASH_INDEX_DIR = "by-src"
#: The directory, under a serving root, that holds one index page per source path.
PATH_INDEX_DIR = "by-path"
#: The name 2.2.0 used for :data:`HASH_INDEX_DIR`.
INDEX_DIR = HASH_INDEX_DIR
#: The report key modes: what the report line's URL is keyed by.
REPORT_KEYS = ("hash", "path")
#: The environment variable that names the report key mode for ``bencher stamp``.
REPORT_KEY_ENV = "BENCHER_REPORT_KEY"
#: How many hex digits of the SHA-256 the URL carries.
HASH_LENGTH = 16
#: The environment variable that names the serving root for ``bencher stamp``.
REPORT_ROOT_ENV = "BENCHER_REPORT_ROOT"
#: What a report line starts with when ``bencher stamp`` writes it.
REPORT_LINE_PREFIX = "# report: "
#: A report line, as the hash rule and ``bencher stamp`` recognise it.
REPORT_LINE = re.compile(rb"^#[ \t]*report:")
# A path-keyed report line: the URL's path part, between "/by-path/" and "/index.html".
_PATH_LINE = re.compile(
    rb"^#[ \t]*report:[ \t]*https?://[^/\s]+\S*?/by-path/(\S+)/index\.html[ \t]*$"
)
_PATH_SEGMENT = re.compile(r"[A-Za-z0-9._+@-]+")

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


def safe_source_path(path: str) -> str:
    """Return *path* if it is safe as a ``by-path/`` store key and URL part.

    Safe: a relative POSIX path of one or more segments, each made of letters,
    digits and ``._-+@`` only, and none of them ``.`` or ``..``. So no empty
    segment, leading ``/``, backslash, whitespace or control character.

    Raises:
        ValueError: If *path* is not safe.
    """
    if not isinstance(path, str) or not path:
        raise ValueError(f"source path must be a non-empty string, not {path!r}")
    for segment in path.split("/"):
        if segment in {".", ".."} or not _PATH_SEGMENT.fullmatch(segment):
            raise ValueError(
                f"unsafe source path {path!r}: use a relative POSIX path of letters, "
                "digits and ._-+@ with no empty, '.' or '..' segment"
            )
    return path


def index_url(root: str, digest: str) -> str:
    """The URL of the index page for *digest* under the serving *root*."""
    return f"{serving_root(root)}/{HASH_INDEX_DIR}/{digest}/index.html"


def path_index_url(root: str, path: str) -> str:
    """The URL of the index page for source *path* under the serving *root*.

    Raises:
        ValueError: If *path* fails :func:`safe_source_path`.
    """
    return f"{serving_root(root)}/{PATH_INDEX_DIR}/{safe_source_path(path)}/index.html"


def report_line(root: str, digest: str) -> str:
    """The comment line a source file with hash *digest* carries."""
    return f"{REPORT_LINE_PREFIX}{index_url(root, digest)}"


def path_report_line(root: str, path: str) -> str:
    """The comment line a source file at repo-relative *path* carries in path mode."""
    return f"{REPORT_LINE_PREFIX}{path_index_url(root, path)}"


def path_from_line(data: bytes) -> str | None:
    """The source path that the first by-path report line in *data* names, or None.

    None when there is no by-path report line, or its path fails
    :func:`safe_source_path`.
    """
    for line in _lines(data):
        match = _PATH_LINE.match(line)
        if match:
            try:
                return safe_source_path(match.group(1).decode("ascii"))
            except (UnicodeDecodeError, ValueError):
                return None
    return None


def git_relative(path: Path) -> str | None:
    """*path* relative to the nearest directory above it that holds ``.git``, or None."""
    resolved = path.resolve()
    for parent in resolved.parents:
        if (parent / ".git").exists():
            return resolved.relative_to(parent).as_posix()
    return None


def repo_relative(path: Path) -> str:
    """*path* relative to the nearest directory above it that holds ``.git``.

    With no such directory, the file name alone: a path relative to wherever the
    process started would differ between machines.
    """
    return git_relative(path) or path.resolve().name


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
        """The identity of the file at *path*.

        The path comes from the file's by-path report line when it has a valid
        one (:func:`path_from_line`), else from :func:`repo_relative`.
        """
        data = Path(path).read_bytes()
        return cls(source_hash_bytes(data), path_from_line(data) or repo_relative(Path(path)))


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


def expected_line(data: bytes, root: str, key: str = "hash", path: str | None = None) -> str:
    """The report line *data* should carry in report key mode *key*.

    *path* is the file's repo-relative path, which path mode needs.

    Raises:
        ValueError: If *key* is not a report key, or path mode has no safe *path*.
    """
    if key == "hash":
        return report_line(root, source_hash_bytes(data))
    if key == "path":
        if path is None:
            raise ValueError("path mode needs the file's repo-relative path")
        return path_report_line(root, path)
    raise ValueError(f"report key must be one of {', '.join(REPORT_KEYS)}, not {key!r}")


def stamp_bytes(data: bytes, root: str, key: str = "hash", path: str | None = None) -> bytes:
    """*data* with exactly one current report line (see :func:`expected_line`).

    An existing report line is replaced in place and any others are removed. With
    none, the line goes after a shebang and a PEP 263 encoding line, and before
    everything else; a comment before a module docstring leaves it the docstring.
    The file keeps its own line endings.
    """
    newline = _newline(data)
    line = expected_line(data, root, key, path).encode()
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


def check_bytes(data: bytes, root: str, key: str = "hash", path: str | None = None) -> str:
    """``"current"``, ``"missing"`` or ``"stale"`` for the report line(s) in *data*.

    Current means exactly one report line, equal to :func:`expected_line`. In path
    mode a renamed or copied file is stale: its line names another path.
    """
    found = [line for line in _lines(data) if REPORT_LINE.match(line)]
    if not found:
        return "missing"
    expected = expected_line(data, root, key, path).encode()
    return "current" if found == [expected] else "stale"


def has_report_line(data: bytes) -> bool:
    return any(REPORT_LINE.match(line) for line in _lines(data))


def _pyproject_setting(start: Path, name: str) -> str | None:
    for directory in (start, *start.parents):
        candidate = directory / "pyproject.toml"
        if candidate.is_file():
            try:
                config = tomllib.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None
            value = config.get("tool", {}).get("bencher", {}).get(name)
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
        or _pyproject_setting((start or Path.cwd()).resolve(), "report_root")
    )
    if not value:
        raise ValueError(
            f"no report root: pass --root, set {REPORT_ROOT_ENV}, or set report_root "
            "under [tool.bencher] in pyproject.toml"
        )
    return serving_root(value)


def resolve_key(
    explicit: str | None = None,
    env: Mapping[str, str] | None = None,
    start: Path | None = None,
) -> str:
    """The report key mode, ``"hash"`` or ``"path"``.

    In order: *explicit* (``--key``), ``report_key`` under ``[tool.bencher]`` in the
    nearest ``pyproject.toml`` above *start* (the working directory by default),
    the ``BENCHER_REPORT_KEY`` variable, then ``"hash"``. The repository's own
    setting wins over the environment, so every checkout writes the same lines.

    Raises:
        ValueError: If the value is not a report key.
    """
    source = os.environ if env is None else env
    value = (
        explicit
        or _pyproject_setting((start or Path.cwd()).resolve(), "report_key")
        or source.get(REPORT_KEY_ENV, "").strip()
        or "hash"
    )
    if value not in REPORT_KEYS:
        raise ValueError(f"report key must be one of {', '.join(REPORT_KEYS)}, not {value!r}")
    return value


def stamp_path(path: Path) -> str:
    """The repo-relative path that path mode writes for the file at *path*.

    Raises:
        ValueError: If no directory above *path* holds ``.git``, or the path is
            not safe (:func:`safe_source_path`).
    """
    relative = git_relative(path)
    if relative is None:
        raise ValueError(f"{path}: path mode needs a git repository above the file")
    return safe_source_path(relative)


def stamp_files(
    paths: Sequence[str | Path],
    root: str,
    *,
    check: bool = False,
    only_stamped: bool = False,
    key: str = "hash",
) -> list[StampStatus]:
    """Stamp (or with *check*, only inspect) each file in *paths*.

    With *only_stamped*, a file with no report line is skipped (state
    ``"unstamped"``): a repository can opt files in one at a time. *key* is the
    report key mode; path mode takes each path from the git root above the file
    (:func:`stamp_path`).

    Raises:
        ValueError: In path mode, for a file with no git root or an unsafe path.
    """
    statuses = []
    for raw in paths:
        path = Path(raw)
        data = path.read_bytes()
        relative = stamp_path(path) if key == "path" else None
        expected = expected_line(data, root, key, relative)
        if only_stamped and not has_report_line(data):
            statuses.append(StampStatus(path, "unstamped", expected))
            continue
        state = check_bytes(data, root, key, relative)
        if not check and state != "current":
            path.write_bytes(stamp_bytes(data, root, key, relative))
        statuses.append(StampStatus(path, state, expected))
    return statuses


def main(argv: list[str] | None = None) -> int:
    """``bencher stamp [--check] [--root URL] [--key hash|path] [--only-stamped] FILE...``."""
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
        "--key",
        choices=REPORT_KEYS,
        help="What the report URL is keyed by: the file's content hash (by-src/) or its "
        "repo-relative path (by-path/). Default: [tool.bencher] report_key in "
        f"pyproject.toml, then ${REPORT_KEY_ENV}, then hash",
    )
    parser.add_argument(
        "--only-stamped",
        action="store_true",
        help="Skip files that have no report line yet",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        root = resolve_root(args.root)
        key = resolve_key(args.key)
        statuses = stamp_files(
            args.files, root, check=args.check, only_stamped=args.only_stamped, key=key
        )
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
                f"  run: bencher stamp --key {key} {status.path}",
                file=sys.stderr,
            )
        else:
            print(f"{status.path}: stamped ({status.state})")  # noqa: T201 - CLI output
    # Like a formatter, a run that changed files exits 1, so a pre-commit hook
    # stops the commit until the stamped files are added.
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
