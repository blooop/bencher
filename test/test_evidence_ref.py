"""Evidence images pushed to ``refs/bencher/evidence``, tested against a local bare repo."""

from __future__ import annotations

import os
import stat
import subprocess
from typing import TYPE_CHECKING

import pytest

from bencher.evidence_ref import (
    EVIDENCE_REF,
    EvidencePublishError,
    blob_url,
    github_repo,
    publish_evidence,
    push_evidence,
)

if TYPE_CHECKING:
    from pathlib import Path

# The 8-byte PNG signature, then enough bytes to look like a file.
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _git(cwd: Path, *args: str, check: bool = True) -> str:
    return subprocess.run(
        ["git", *args],  # noqa: S607 - git from PATH
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _identity(repo: Path) -> None:
    _git(repo, "config", "user.email", "ev@example.test")
    _git(repo, "config", "user.name", "ev")


@pytest.fixture(name="remote")
def bare_remote(tmp_path) -> Path:
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    return remote


def _clone(remote: Path, dest: Path) -> Path:
    _git(dest.parent, "clone", "-q", str(remote), str(dest))
    _identity(dest)
    return dest


@pytest.fixture(name="repo")
def work_repo(tmp_path, remote) -> Path:
    """A clone of *remote* with one commit on main and LFS rules for PNGs."""
    seed = tmp_path / "seed"
    seed.mkdir()
    _git(seed, "init", "-q", "-b", "main")
    _identity(seed)
    (seed / "README").write_text("hi\n", encoding="utf-8")
    (seed / ".gitattributes").write_text(
        "*.png filter=lfs diff=lfs merge=lfs -text\n", encoding="utf-8"
    )
    _git(seed, "add", ".")
    _git(seed, "commit", "-q", "-m", "seed")
    _git(seed, "push", "-q", str(remote), "main")
    repo = _clone(remote, tmp_path / "repo")
    # A filter that would turn any PNG into a pointer: --no-filters must bypass it.
    _git(repo, "config", "filter.lfs.clean", "echo lfs-pointer")
    _git(repo, "config", "filter.lfs.required", "true")
    return repo


def _png(dir_: Path, name: str, payload: bytes = PNG) -> Path:
    path = dir_ / name
    path.write_bytes(payload)
    return path


def _state(repo: Path) -> tuple[str, str, str]:
    return (
        _git(repo, "rev-parse", "HEAD"),
        _git(repo, "status", "--porcelain", "--untracked-files=all"),
        _git(repo, "symbolic-ref", "HEAD"),
    )


def test_push_stores_the_run_on_the_ref_and_leaves_the_checkout_alone(repo, remote, tmp_path):
    files = tmp_path / "files"
    files.mkdir()
    png = _png(files, "speed.png")
    before = _state(repo)

    commit = push_evidence(repo, {"speed.png": png}, run_dir="run-1")

    assert _git(remote, "rev-parse", EVIDENCE_REF) == commit
    stored = subprocess.run(
        ["git", "cat-file", "blob", f"{commit}:run-1/speed.png"],  # noqa: S607
        cwd=remote,
        check=True,
        capture_output=True,
    ).stdout
    assert stored == PNG  # the image, not an LFS pointer
    assert _state(repo) == before
    assert _git(remote, "for-each-ref", "--format=%(refname)", "refs/heads") == "refs/heads/main"


def test_a_plain_clone_does_not_fetch_the_evidence(repo, remote, tmp_path):
    files = tmp_path / "files"
    files.mkdir()
    commit = push_evidence(repo, {"a.png": _png(files, "a.png")}, run_dir="run-1")

    fresh = tmp_path / "fresh"
    # file:// makes git transfer objects as over a network, not copy the object store.
    _git(tmp_path, "clone", "-q", f"file://{remote}", str(fresh))

    assert EVIDENCE_REF in _git(fresh, "ls-remote", "origin", EVIDENCE_REF)
    assert "bencher" not in _git(fresh, "for-each-ref")
    missing = subprocess.run(
        ["git", "cat-file", "-e", commit],  # noqa: S607
        cwd=fresh,
        check=False,
        capture_output=True,
    )
    assert missing.returncode != 0


def test_each_run_adds_a_commit_on_top_of_the_last(repo, remote, tmp_path):
    files = tmp_path / "files"
    files.mkdir()
    first = push_evidence(repo, {"a.png": _png(files, "a.png")}, run_dir="run-1")
    second = push_evidence(repo, {"a.png": _png(files, "a.png", PNG + b"2")}, run_dir="run-2")

    assert _git(remote, "rev-parse", f"{second}^") == first
    # Each commit's tree holds only its own run; the older run stays reachable.
    assert _git(remote, "ls-tree", "--name-only", second) == "run-2"
    assert _git(remote, "ls-tree", "--name-only", first) == "run-1"


def _racing_git(tmp_path: Path, other: Path, files: Path, *, every: bool) -> Path:
    """A git dir for PATH that lets *other* push to the ref before our push.

    Before the first push only, or before every push when *every*; the file it
    returns holds the SHA of the other clone's latest commit.
    """
    real_git = subprocess.run(
        ["sh", "-c", "command -v git"],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    marker = tmp_path / "raced"
    racer = files / "racer.png"
    racer.write_bytes(PNG + b"racer")
    blob = _git(other, "hash-object", "-w", "--no-filters", str(racer))
    once = "" if every else f' && [ ! -e "{marker}" ]'
    script = f"""#!/bin/sh
if [ "$1" = "push" ]{once}; then
  touch "{marker}"
  (
    cd "{other}" || exit 1
    tree=$(printf '100644 blob {blob}\\tr.png\\n' | "{real_git}" mktree)
    root=$(printf '040000 tree %s\\tracer-1\\n' "$tree" | "{real_git}" mktree)
    "{real_git}" fetch -q origin {EVIDENCE_REF} || exit 1
    parent=$("{real_git}" rev-parse FETCH_HEAD)
    c=$("{real_git}" commit-tree "$root" -p "$parent" -m racer)
    "{real_git}" push -q origin "$c:{EVIDENCE_REF}" || exit 1
    echo "$c" > "{marker}"
  ) || exit 1
fi
exec "{real_git}" "$@"
"""
    shim = shim_dir / "git"
    shim.write_text(script, encoding="utf-8")
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR)
    return marker


def test_a_concurrent_push_is_reparented_not_overwritten(repo, remote, tmp_path, monkeypatch):
    """Another clone pushes between our fetch and our push; ours lands on top of it."""
    files = tmp_path / "files"
    files.mkdir()
    other = _clone(remote, tmp_path / "other")
    push_evidence(other, {"o.png": _png(files, "o.png")}, run_dir="other-1")
    marker = _racing_git(tmp_path, other, files, every=False)
    monkeypatch.setenv("PATH", f"{tmp_path / 'shim'}{os.pathsep}{os.environ['PATH']}")

    ours = push_evidence(repo, {"a.png": _png(files, "a.png")}, run_dir="ours-1")

    racer_commit = marker.read_text(encoding="utf-8").strip()
    assert racer_commit, "the racing push did not run"
    assert _git(remote, "rev-parse", EVIDENCE_REF) == ours
    assert _git(remote, "rev-parse", f"{ours}^") == racer_commit
    chain = _git(remote, "log", "--format=%s", EVIDENCE_REF).splitlines()
    assert len(chain) == 3


def test_push_gives_up_after_the_attempts_without_forcing(repo, remote, tmp_path, monkeypatch):
    """Another clone wins every race; ours gives up and never forces the ref."""
    files = tmp_path / "files"
    files.mkdir()
    other = _clone(remote, tmp_path / "other")
    push_evidence(other, {"o.png": _png(files, "o.png")}, run_dir="other-1")
    marker = _racing_git(tmp_path, other, files, every=True)
    monkeypatch.setenv("PATH", f"{tmp_path / 'shim'}{os.pathsep}{os.environ['PATH']}")

    with pytest.raises(EvidencePublishError, match="rejected 2 times"):
        push_evidence(repo, {"a.png": _png(files, "a.png")}, run_dir="run-1", attempts=2)

    racer_commit = marker.read_text(encoding="utf-8").strip()
    assert racer_commit, "the racing push did not run"
    assert _git(remote, "rev-parse", EVIDENCE_REF) == racer_commit


def test_a_push_the_server_refuses_is_not_retried(repo, remote, tmp_path):
    files = tmp_path / "files"
    files.mkdir()
    runs = tmp_path / "hook-runs"
    hook = remote / "hooks" / "pre-receive"
    hook.write_text(
        f'#!/bin/sh\necho run >> "{runs}"\necho protected ref >&2\nexit 1\n', encoding="utf-8"
    )
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)

    with pytest.raises(EvidencePublishError) as raised:
        push_evidence(repo, {"a.png": _png(files, "a.png")}, run_dir="run-1", attempts=3)

    assert "times" not in str(raised.value)
    assert "declined" in str(raised.value)
    assert runs.read_text(encoding="utf-8").splitlines() == ["run"]
    assert _git(remote, "for-each-ref", EVIDENCE_REF) == ""


def test_push_to_an_unreachable_remote_raises(repo, tmp_path):
    files = tmp_path / "files"
    files.mkdir()
    _git(repo, "remote", "set-url", "origin", str(tmp_path / "nowhere.git"))

    with pytest.raises(EvidencePublishError):
        push_evidence(repo, {"a.png": _png(files, "a.png")}, run_dir="run-1")


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("git@github.com:blooop/bencher.git", ("blooop", "bencher")),
        ("git@github.com:blooop/bencher", ("blooop", "bencher")),
        ("https://github.com/blooop/bencher.git", ("blooop", "bencher")),
        ("https://github.com/blooop/bencher", ("blooop", "bencher")),
        ("https://github.com/blooop/bencher/", ("blooop", "bencher")),
        ("https://user@github.com/blooop/bench.er.git", ("blooop", "bench.er")),
        ("ssh://git@github.com/blooop/bencher.git", ("blooop", "bencher")),
        ("ssh://git@github.com:22/blooop/bencher.git", ("blooop", "bencher")),
        ("git@gitlab.com:blooop/bencher.git", None),
        ("https://example.com/blooop/bencher.git", None),
        ("/srv/git/remote.git", None),
        ("https://github.com/blooop", None),
    ],
)
def test_github_repo_reads_owner_and_name_from_a_remote_url(url, expected):
    assert github_repo(url) == expected


def test_blob_url_is_sha_pinned_and_raw():
    assert (
        blob_url("blooop", "bencher", "abc123", "run 1/a b.png")
        == "https://github.com/blooop/bencher/blob/abc123/run%201/a%20b.png?raw=true"
    )


def test_publish_links_each_file_on_github(repo, remote, tmp_path):
    files = tmp_path / "files"
    files.mkdir()
    # The remote is named as GitHub; git reaches it through the local bare repo.
    github = "git@github.com:someone/proj.git"
    _git(repo, "remote", "set-url", "origin", github)
    _git(repo, "config", f"url.{remote}.insteadOf", github)

    urls = publish_evidence(repo, {"a.png": _png(files, "a.png")}, run_dir="run-1")

    commit = _git(remote, "rev-parse", EVIDENCE_REF)
    assert urls == {"a.png": f"https://github.com/someone/proj/blob/{commit}/run-1/a.png?raw=true"}


def test_publish_without_a_github_remote_pushes_nothing(repo, remote, tmp_path):
    files = tmp_path / "files"
    files.mkdir()

    with pytest.raises(EvidencePublishError, match="GitHub"):
        publish_evidence(repo, {"a.png": _png(files, "a.png")}, run_dir="run-1")

    assert _git(remote, "for-each-ref", EVIDENCE_REF) == ""


def test_a_token_in_a_non_github_remote_url_stays_out_of_the_error(repo, tmp_path):
    files = tmp_path / "files"
    files.mkdir()
    _git(repo, "remote", "set-url", "origin", "https://gitlab-ci-token:SECRET@host/o/r.git")

    with pytest.raises(EvidencePublishError) as raised:
        publish_evidence(repo, {"a.png": _png(files, "a.png")}, run_dir="run-1")

    assert "SECRET" not in str(raised.value)
    assert "gitlab-ci-token" not in str(raised.value)
    assert "host/o/r.git" in str(raised.value)


@pytest.mark.parametrize("run_dir", ["..", "a/b", "", "."])
def test_a_run_dir_that_is_not_a_plain_name_pushes_nothing(repo, remote, tmp_path, run_dir):
    files = tmp_path / "files"
    files.mkdir()

    with pytest.raises(EvidencePublishError, match="plain"):
        push_evidence(repo, {"a.png": _png(files, "a.png")}, run_dir=run_dir)

    assert _git(remote, "for-each-ref", EVIDENCE_REF) == ""
