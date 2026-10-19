"""Store evidence images on a git ref that no branch reaches, and link them from a PR.

``bencher ab --images`` puts each run's PNGs and CSVs in one commit on
:data:`EVIDENCE_REF` (``refs/bencher/evidence``) of the ``origin`` remote. The
ref holds a chain of commits: each run's commit has only that run's files, under
a directory of its own, and its parent is the ref's previous tip, so every older
run stays reachable and git never collects it. No branch reaches the ref, so a
plain ``git clone`` or ``git fetch`` does not download the images. A throwaway
repo makes and pushes the commit, so the user's repo keeps no ref and no object of
it, and ``git log --all --not --remotes`` there stays empty.

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
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping, Sequence

EVIDENCE_REF = "refs/bencher/evidence"
DEFAULT_ATTEMPTS = 5

# A git call that reaches the remote fails, not prompts, on an https credential.
_NO_PROMPT = {"GIT_TERMINAL_PROMPT": "0"}

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


def _plain_name(name: str) -> None:
    """Raise unless *name* is one tree entry: no slash, not empty, not a dot name."""
    if "/" in name or name in ("", ".", ".."):
        raise EvidencePublishError(f"not a plain file name: {name!r}")


def _tree(files: Mapping[str, Path], run_dir: str, cwd: Path, env: Mapping[str, str]) -> str:
    """A root tree holding *files* under *run_dir*; the blobs bypass every filter."""
    if not files:
        raise EvidencePublishError("no file to store")
    _plain_name(run_dir)
    entries = []
    for name, path in sorted(files.items()):
        _plain_name(name)
        blob = _git(["hash-object", "-w", "--no-filters", "--", str(path)], cwd, env=env)
        entries.append(f"100644 blob {blob}\t{name}\n")
    inner = _git(["mktree"], cwd, stdin="".join(entries), env=env)
    return _git(["mktree"], cwd, stdin=f"040000 tree {inner}\t{run_dir}\n", env=env)


def _push_url(remote: str, cwd: Path) -> str:
    """The URL a push to *remote* goes to, as configured: its pushurl, else its url."""
    for key in ("pushurl", "url"):
        urls = _run(["config", "--get-all", f"remote.{remote}.{key}"], cwd).stdout.splitlines()
        if urls:
            return urls[0].strip()
    return ""


def _push_source(remote: str, cwd: Path) -> str:
    """Where a push to *remote* goes: a fork setup fetches from upstream, pushes to the fork."""
    resolved = _run(["remote", "get-url", "--push", remote], cwd)
    return resolved.stdout.strip() if resolved.returncode == 0 else remote


def _remote_tip(source: str, ref: str, cwd: Path, env: Mapping[str, str]) -> str | None:
    """The SHA of *ref* on *source*, or None when it has no such ref."""
    listed = _run(["ls-remote", "--exit-code", source, ref], cwd, env=env)
    if listed.returncode == 2:  # noqa: PLR2004 - ls-remote: no matching ref
        return None
    if listed.returncode != 0:
        raise EvidencePublishError(f"cannot read {source}: {listed.stderr.strip()}")
    return listed.stdout.split()[0]


@contextmanager
def _scratch_git_dir(cwd: Path) -> Generator[dict[str, str]]:
    """Env for git calls in a throwaway bare repo that reads the config of the one at *cwd*.

    The evidence commit is made and pushed from it, so the user's repo gets no ref,
    no object and no ``shallow`` file: ``git log --all --not --remotes`` stays empty
    there, and no clone keeps the images of older runs.
    """
    config = Path(_git(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd)) / "config"
    object_format = _git(["rev-parse", "--show-object-format"], cwd)
    with tempfile.TemporaryDirectory(prefix="bencher-evidence-") as scratch:
        _git(["init", "--quiet", "--bare", f"--object-format={object_format}", scratch], cwd)
        # Remotes, insteadOf rewrites, credential helpers and ssh settings come from here.
        _git(["config", "--file", f"{scratch}/config", "include.path", str(config)], cwd)
        yield {"GIT_DIR": scratch}


def _no_prompt_env(cwd: Path) -> dict[str, str]:
    """Env that makes a git call fail, not prompt, when it reaches the remote with no credential.

    ``GIT_TERMINAL_PROMPT=0`` stops an https prompt only. ssh runs in batch mode, so a
    passphrase or host-key question fails too, unless the user set their own ssh
    command (``GIT_SSH_COMMAND``, ``GIT_SSH`` or ``core.sshCommand``): that is left alone.
    """
    env = dict(_NO_PROMPT)
    own_ssh = "GIT_SSH_COMMAND" in os.environ or "GIT_SSH" in os.environ
    if not own_ssh and _run(["config", "core.sshCommand"], cwd).returncode != 0:
        env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"
    return env


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

    The commit's parent is the remote ref's tip, so older runs stay reachable. A
    throwaway repo makes and pushes the commit; it fetches only the tip
    (``--depth=1``), which the push needs, and the user's repo keeps no ref and no
    object of it. A rejected push (another run pushed first) is made again on the new
    tip, up to *attempts* times; the push is never forced. Raises
    :class:`EvidencePublishError` when git fails or every attempt is rejected.
    """
    cwd = Path(repo)
    identity = _identity_env(cwd)
    source = _push_source(remote, cwd)
    message = f"bencher evidence {run_dir}"
    reason = "no attempt was made"
    with _scratch_git_dir(cwd) as scratch:
        net = {**scratch, **_no_prompt_env(cwd)}
        tree = _tree(files, run_dir, cwd, scratch)
        for _ in range(attempts):
            parent = _remote_tip(source, ref, cwd, net)
            parents = []
            if parent:
                # The push walks the parent, so it must be here: only the tip, into FETCH_HEAD.
                _git(["fetch", "--quiet", "--no-tags", "--depth=1", source, ref], cwd, env=net)
                parents = ["-p", parent]
            commit = _git(
                ["commit-tree", "--no-gpg-sign", tree, *parents, "-m", message],
                cwd,
                env={**scratch, **identity},
            )
            pushed = _run(
                ["push", "--quiet", "--no-verify", remote, f"{commit}:{ref}"], cwd, env=net
            )
            if pushed.returncode == 0:
                return commit
            reason = pushed.stderr.strip()
            if "[rejected]" not in reason:
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
    url = _push_url(remote, cwd)
    named = github_repo(url)
    if named is None:
        raise EvidencePublishError(
            f"remote {remote!r} is not a GitHub repository ({_without_userinfo(url) or 'no URL'})"
        )
    commit = push_evidence(cwd, files, run_dir=run_dir, remote=remote, ref=ref, attempts=attempts)
    return {name: blob_url(*named, commit, f"{run_dir}/{name}") for name in files}
