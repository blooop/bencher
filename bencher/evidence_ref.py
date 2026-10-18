"""Store evidence images on a git ref that no branch reaches, and link them from a PR.

``bencher ab --images`` puts each run's PNGs and CSVs in one commit on
:data:`EVIDENCE_REF` (``refs/bencher/evidence``) of the ``origin`` remote. The
ref holds a chain of commits: each run's commit has only that run's files, under
a directory of its own, and its parent is the ref's previous tip, so every older
run stays reachable and git never collects it. No branch reaches the ref, so a
plain ``git clone`` or ``git fetch`` does not download the images.

Only plumbing builds the commit (``hash-object -w --no-filters``, ``mktree``,
``commit-tree``): the work tree, the index and ``HEAD`` do not change, and a
``*.png filter=lfs`` rule in ``.gitattributes`` does not turn an image into an
LFS pointer. When another run pushes first, the push is rejected (it is never
forced): the commit is made again on the new tip and pushed again, a bounded
number of times.

A GitHub PR page draws an image from a ``blob/<sha>/<path>?raw=true`` link for
anyone who can read the repository, public or private (a
``raw.githubusercontent.com`` link does not draw in a private repository), so
:func:`blob_url` links each file by the commit's SHA.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

EVIDENCE_REF = "refs/bencher/evidence"
DEFAULT_ATTEMPTS = 5

# The fallback identity of an evidence commit when git has none configured.
_IDENTITY = {
    "GIT_AUTHOR_NAME": "bencher",
    "GIT_AUTHOR_EMAIL": "bencher@localhost",
    "GIT_COMMITTER_NAME": "bencher",
    "GIT_COMMITTER_EMAIL": "bencher@localhost",
}

_GITHUB_URL = re.compile(
    r"""^(?:
        (?:[\w.-]+@)?github\.com:                      # scp-like: git@github.com:owner/repo
      | (?:https?|ssh|git)://(?:[^@/]+@)?github\.com(?::\d+)?/  # URL form
    )
    (?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?/?$""",
    re.VERBOSE,
)


_USERINFO = re.compile(r"^(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)[^@/]*@")


class EvidencePublishError(Exception):
    """The images could not be stored on the ref or linked; nothing was linked."""


def github_repo(url: str) -> tuple[str, str] | None:
    """``(owner, repo)`` of a GitHub remote URL (ssh, scp-like or https), else None."""
    match = _GITHUB_URL.match(url.strip())
    if match is None:
        return None
    return match["owner"], match["repo"]


def _without_userinfo(url: str) -> str:
    """*url* with any ``user:password@`` removed, safe to print."""
    return _USERINFO.sub(r"\g<scheme>", url)


def blob_url(owner: str, repo: str, commit: str, path: str) -> str:
    """The SHA-pinned link that a GitHub PR page draws as an image, public or private."""
    return f"https://github.com/{owner}/{repo}/blob/{commit}/{quote(path)}?raw=true"


def _run(
    args: Sequence[str],
    cwd: Path,
    *,
    stdin: str | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],  # noqa: S607 - git from PATH
        cwd=cwd,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
        env=None if env is None else {**os.environ, **env},
    )


def _git(
    args: Sequence[str],
    cwd: Path,
    *,
    stdin: str | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    proc = _run(args, cwd, stdin=stdin, env=env)
    if proc.returncode != 0:
        raise EvidencePublishError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _tree(files: Mapping[str, Path], run_dir: str, cwd: Path) -> str:
    """A root tree holding *files* under *run_dir*; the blobs bypass every filter."""
    if not files:
        raise EvidencePublishError("no file to store")
    entries = []
    for name, path in sorted(files.items()):
        if "/" in name or name in ("", ".", ".."):
            raise EvidencePublishError(f"not a plain file name: {name!r}")
        blob = _git(["hash-object", "-w", "--no-filters", "--", str(path)], cwd)
        entries.append(f"100644 blob {blob}\t{name}\n")
    inner = _git(["mktree"], cwd, stdin="".join(entries))
    return _git(["mktree"], cwd, stdin=f"040000 tree {inner}\t{run_dir}\n")


def _remote_tip(remote: str, ref: str, cwd: Path) -> str | None:
    """Fetch *ref* from *remote* into the same local ref; its SHA, or None when absent."""
    listed = _run(["ls-remote", "--exit-code", remote, ref], cwd)
    if listed.returncode == 2:  # noqa: PLR2004 - ls-remote: no matching ref
        return None
    if listed.returncode != 0:
        raise EvidencePublishError(f"cannot read {remote}: {listed.stderr.strip()}")
    # The local ref mirrors the remote one; it keeps the fetched objects reachable here too.
    _git(["fetch", "--quiet", "--no-tags", remote, f"+{ref}:{ref}"], cwd)
    return _git(["rev-parse", "--verify", f"{ref}^{{commit}}"], cwd)


def _identity_env(cwd: Path) -> dict[str, str]:
    """No override when git has an identity, else a fixed one so commit-tree works."""
    if _run(["var", "GIT_COMMITTER_IDENT"], cwd).returncode == 0:
        return {}
    return dict(_IDENTITY)


def push_evidence(
    repo: str | Path,
    files: Mapping[str, Path],
    *,
    run_dir: str,
    remote: str = "origin",
    ref: str = EVIDENCE_REF,
    attempts: int = DEFAULT_ATTEMPTS,
) -> str:
    """Push one commit holding *files* under *run_dir* to *ref* on *remote*; return its SHA.

    The commit's parent is the remote ref's tip, so older runs stay reachable.
    A rejected push (another run pushed first) is made again on the new tip, up to
    *attempts* times; the push is never forced. Raises :class:`EvidencePublishError`
    when git fails or every attempt is rejected.
    """
    cwd = Path(repo)
    tree = _tree(files, run_dir, cwd)
    env = _identity_env(cwd)
    message = f"bencher evidence {run_dir}"
    reason = "no attempt was made"
    for _ in range(attempts):
        parent = _remote_tip(remote, ref, cwd)
        parents = ["-p", parent] if parent else []
        commit = _git(["commit-tree", "--no-gpg-sign", tree, *parents, "-m", message], cwd, env=env)
        pushed = _run(["push", "--quiet", "--no-verify", remote, f"{commit}:{ref}"], cwd)
        if pushed.returncode == 0:
            _run(["update-ref", ref, commit], cwd)
            return commit
        reason = pushed.stderr.strip()
        if "rejected" not in reason:
            raise EvidencePublishError(f"git push to {remote} failed: {reason}")
    raise EvidencePublishError(
        f"git push to {remote} {ref} was rejected {attempts} times: {reason}"
    )


def publish_evidence(
    repo: str | Path,
    files: Mapping[str, Path],
    *,
    run_dir: str,
    remote: str = "origin",
    ref: str = EVIDENCE_REF,
    attempts: int = DEFAULT_ATTEMPTS,
) -> dict[str, str]:
    """Push *files* with :func:`push_evidence` and return ``{name: GitHub image link}``.

    Raises :class:`EvidencePublishError`, before it pushes anything, when *remote*
    is not a GitHub repository.
    """
    cwd = Path(repo)
    url = _run(["config", "--get", f"remote.{remote}.url"], cwd).stdout.strip()
    named = github_repo(url)
    if named is None:
        raise EvidencePublishError(
            f"remote {remote!r} is not a GitHub repository ({_without_userinfo(url) or 'no URL'})"
        )
    commit = push_evidence(cwd, files, run_dir=run_dir, remote=remote, ref=ref, attempts=attempts)
    return {name: blob_url(*named, commit, f"{run_dir}/{name}") for name in files}
