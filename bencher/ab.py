"""``bencher ab``: run one bench command before and after a change, then compare.

::

    bencher ab [--base REF] [--out DIR] [--png-url-base URL] -- <command...>

The *base* side runs the command in a temporary, detached ``git worktree`` of the
base revision; the *candidate* side runs it in the current working tree as it is,
so uncommitted changes count. The base run puts the worktree's ``src`` directory
(when it has one) and its root first on ``PYTHONPATH``, so it imports the base's
package even where an editable install or an absolute ``PYTHONPATH`` entry points
into the candidate tree. If the base run still loads a module from the candidate's
repository (:data:`~bencher.launch_env.FORBIDDEN_ROOT_ENV`), it saves no result and
fails. Each run is told where to save its result
(:data:`~bencher.launch_env.RESULT_PATH_ENV`) and runs with the sample and result
caches off (:data:`~bencher.launch_env.NO_CACHE_ENV`): the caches are keyed by
inputs, not code, so a cache filled by one revision would otherwise answer for the
other. It also shows no report (:data:`~bencher.launch_env.NO_SHOW_ENV`), so a
``bn.run`` bench exits when it finishes. The provenance variables name each side's
revision.

The base revision is ``--base`` when given, else the merge-base of ``HEAD`` with
``origin/HEAD``, falling back to ``origin/main`` and then ``main``.

``--out`` (default ``./bencher-ab``) receives ``base.pkl``, ``candidate.pkl``,
``comparison.json``, ``evidence.md``, one PNG per metric, and each side's log.
A metric that only one side declares is named in a warning on stderr and in
``evidence.md``; a claim on it is still judged.
Exit status is 0 when both sides ran and were compared, whatever the verdict and
whatever the claims say; 1 when a side failed (its log is kept and named); 2 for
a usage or git problem.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from bencher.execution import PROVENANCE_ENV
from bencher.launch_env import (
    BASE_TREE_ENV,
    FORBIDDEN_ROOT_ENV,
    NO_CACHE_ENV,
    NO_SHOW_ENV,
    RESULT_PATH_ENV,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

_DEFAULT_UPSTREAMS = ("origin/HEAD", "origin/main", "main")
_LOG_TAIL_LINES = 20


class AbError(Exception):
    """A usage or git problem: nothing was measured."""


class SideFailedError(Exception):
    """One side's command failed or saved no result; its log is kept."""

    def __init__(self, side: str, reason: str, log: Path) -> None:
        super().__init__(f"the {side} run {reason}; its output is in {log}")
        self.side = side
        self.log = log


def _git(args: Sequence[str], cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args],  # noqa: S607 - git from PATH
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AbError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _commit_exists(ref: str, cwd: Path) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],  # noqa: S607 - git from PATH
        cwd=cwd,
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def resolve_base(ref: str | None, cwd: Path) -> str:
    """The base commit: *ref* as given, else the merge-base with the default upstream."""
    if ref is not None:
        if not _commit_exists(ref, cwd):
            raise AbError(f"--base {ref!r} does not name a commit")
        return _git(["rev-parse", f"{ref}^{{commit}}"], cwd)
    for upstream in _DEFAULT_UPSTREAMS:
        if _commit_exists(upstream, cwd):
            return _git(["merge-base", "HEAD", upstream], cwd)
    raise AbError(
        f"no base revision: none of {', '.join(_DEFAULT_UPSTREAMS)} exists; pass --base REF"
    )


def _candidate_revision(top: Path, out: Path) -> str:
    short = _git(["rev-parse", "--short", "HEAD"], top)
    pathspec = ["--", "."]
    if out.is_relative_to(top):
        pathspec.append(f":(exclude){out.relative_to(top).as_posix()}")
    dirty = _git(["status", "--porcelain", *pathspec], top)
    return f"{short}+dirty" if dirty else short


def _tail(log: Path) -> str:
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-_LOG_TAIL_LINES:])


def run_side(
    side: str,
    command: Sequence[str],
    cwd: Path,
    revision: str,
    out: Path,
    extra_env: Mapping[str, str] | None = None,
) -> Path:
    """Run *command* for one side; return its saved result path or raise SideFailedError."""
    result = out / f"{side}.pkl"
    log = out / f"{side}.log"
    result.unlink(missing_ok=True)
    inherited = {
        key: value
        for key, value in os.environ.items()
        if key not in (FORBIDDEN_ROOT_ENV, BASE_TREE_ENV)
    }
    env = {
        **inherited,
        **(extra_env or {}),
        RESULT_PATH_ENV: str(result),
        NO_CACHE_ENV: "1",
        NO_SHOW_ENV: "1",
        PROVENANCE_ENV["source_revision"]: revision,
        PROVENANCE_ENV["display_label"]: f"{side} {revision}",
    }
    print(f"bencher ab: running {side} ({revision}) in {cwd}", file=sys.stderr)  # noqa: T201 - CLI output
    with log.open("w", encoding="utf-8") as stream:
        try:
            code = subprocess.run(
                list(command),
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
            ).returncode
        except OSError as exc:
            stream.write(f"{exc}\n")
            code = 127
    if code != 0:
        raise SideFailedError(side, f"exited with status {code}", log)
    if not result.exists():
        raise SideFailedError(
            side, f"saved no result (did the command collect a sweep? {RESULT_PATH_ENV})", log
        )
    return result


def _absent_from_worktree(path: Path, top: Path) -> bool:
    """True for a path a worktree of *top* never has: outside the repository, or ignored."""
    if not path.is_relative_to(top):
        return True
    proc = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", str(path)],  # noqa: S607 - git from PATH
        cwd=top,
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def _pin_paths(command: Sequence[str], here: Path, top: Path) -> list[str]:
    """Make absolute each relative argument naming a path outside the repository or ignored by git.

    A ``.venv/bin/python`` or a ``../data`` directory exists only where ``ab`` runs;
    a tracked file such as the bench itself stays relative, so the base runs its own.
    """
    return [
        str(path)
        if not arg.startswith("-")
        and not Path(arg).is_absolute()
        and os.path.lexists(path := Path(os.path.normpath(here / arg)))
        and _absent_from_worktree(path, top)
        else arg
        for arg in command
    ]


def _base_pythonpath(tree: Path) -> str:
    """PYTHONPATH with the worktree's ``src`` and root ahead of the inherited entries.

    PYTHONPATH comes before site-packages, so these shadow an editable install or an
    absolute PYTHONPATH entry that points into the candidate tree.
    """
    entries = [str(path) for path in (tree / "src", tree) if path.is_dir()]
    if inherited := os.environ.get("PYTHONPATH"):
        entries.append(inherited)
    return os.pathsep.join(entries)


def _run_base(command: Sequence[str], base: str, top: Path, rel: Path, out: Path) -> Path:
    revision = _git(["rev-parse", "--short", base], top)
    with tempfile.TemporaryDirectory(prefix="bencher-ab-") as tmp:
        tree = Path(tmp) / "base"
        _git(["worktree", "add", "--detach", str(tree), base], top)
        try:
            cwd = tree / rel
            if not cwd.is_dir():
                log = out / "base.log"
                log.write_text(f"{rel} does not exist at {revision}\n", encoding="utf-8")
                raise SideFailedError("base", f"has no directory {rel}", log)
            base_env = {
                "PYTHONPATH": _base_pythonpath(tree),
                FORBIDDEN_ROOT_ENV: str(top),
                BASE_TREE_ENV: str(tree),
            }
            return run_side("base", command, cwd, revision, out, base_env)
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(tree)],  # noqa: S607 - git from PATH
                cwd=top,
                capture_output=True,
                check=False,
            )
            subprocess.run(
                ["git", "worktree", "prune"],  # noqa: S607 - git from PATH
                cwd=top,
                capture_output=True,
                check=False,
            )


def _parser() -> argparse.ArgumentParser:
    from bencher.render import _prog

    parser = argparse.ArgumentParser(
        prog=f"{_prog()} ab",
        description=(
            "Run a bench command on the base revision and on the working tree, then "
            "compare them into PR-ready evidence."
        ),
    )
    parser.add_argument("--base", metavar="REF", help="Base revision (default: merge-base)")
    parser.add_argument(
        "--out", metavar="DIR", default="bencher-ab", help="Output directory (./bencher-ab)"
    )
    parser.add_argument(
        "--png-url-base", metavar="URL", help="URL prefix for image links in evidence.md"
    )
    parser.add_argument("command", nargs=argparse.REMAINDER, help="-- <command...>")
    return parser


def main(argv: list[str]) -> int:
    """CLI entry for ``bencher ab``; see the module docstring for the contract."""
    parser = _parser()
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("give the bench command after --, e.g. bencher ab -- python bench.py")

    here = Path.cwd().resolve()
    out = Path(args.out).resolve()
    try:
        top = Path(_git(["rev-parse", "--show-toplevel"], here)).resolve()
        base = resolve_base(args.base, top)
        candidate_revision = _candidate_revision(top, out)
    except AbError as exc:
        print(f"bencher ab: {exc}", file=sys.stderr)  # noqa: T201 - CLI output
        return 2
    out.mkdir(parents=True, exist_ok=True)

    try:
        base_command = _pin_paths(command, here, top)
        base_pkl = _run_base(base_command, base, top, here.relative_to(top), out)
        candidate_pkl = run_side("candidate", command, here, candidate_revision, out)
    except SideFailedError as exc:
        print(_tail(exc.log), file=sys.stderr)  # noqa: T201 - CLI output
        print(f"bencher ab: {exc}", file=sys.stderr)  # noqa: T201 - CLI output
        return 1
    except AbError as exc:
        print(f"bencher ab: {exc}", file=sys.stderr)  # noqa: T201 - CLI output
        return 2

    from bencher.evidence import unpaired_warnings, write_evidence
    from bencher.render import load_result

    try:
        files = write_evidence(
            load_result(base_pkl),
            load_result(candidate_pkl),
            json_path=out / "comparison.json",
            markdown_path=out / "evidence.md",
            png_dir=out,
            png_url_base=args.png_url_base,
        )
    except ValueError as exc:
        print(f"bencher ab: compare failed: {exc}", file=sys.stderr)  # noqa: T201 - CLI output
        return 1
    for warning in unpaired_warnings(files.comparison):
        print(f"bencher ab: warning: {warning}", file=sys.stderr)  # noqa: T201 - CLI output
    for path in (
        base_pkl,
        candidate_pkl,
        files.json_path,
        files.markdown_path,
        *files.pngs.values(),
    ):
        print(path)  # noqa: T201 - CLI output
    return 0
