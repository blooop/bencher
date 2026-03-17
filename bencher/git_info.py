"""Git metadata helpers for benchmark time tracking."""

from __future__ import annotations

import subprocess


def _run_git(args: list[str], repo_path: str | None = None) -> str:
    """Run a git subcommand and return its stripped stdout, or empty string on failure."""
    try:
        return (
            subprocess.check_output(  # noqa: S603
                ["git", *args], cwd=repo_path, stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return ""


def git_time_event(repo_path: str | None = None) -> str:
    """Return a time-event label combining the commit date and short hash.

    Example return value: ``"2024-06-15 abc1234d"``

    Intended to be used with ``BenchRunCfg(over_time=True, time_event=...)``
    so the over-time slider shows *when* and *which commit* produced the data.

    Falls back to just the short hash if the commit date is unavailable,
    or an empty string if not inside a git repository.
    """
    commit = _run_git(["rev-parse", "HEAD"], repo_path)
    if not commit:
        return ""
    short = commit[:8]
    date = _run_git(["log", "-1", "--format=%cI"], repo_path)
    date_part = date.split("T")[0] if date else ""
    if date_part:
        return f"{date_part} {short}"
    return short
