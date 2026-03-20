"""Git metadata helpers for benchmark time tracking."""

from __future__ import annotations

import subprocess
from datetime import datetime


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
    """Return a time-event label combining wall-clock time and short commit hash.

    Example return value: ``"2024-06-15 14:59 abc1234d"``

    Intended to be used with ``BenchRunCfg(over_time=True, time_event=...)``
    so the over-time slider shows *when* and *which commit* produced the data.

    Wall-clock time is used instead of commit time so that multiple benchmark
    runs on the same commit produce distinct labels.

    For fork-safety in multithreaded environments (ROS 2, DDS, etc.),
    call this at module level before starting background threads::

        _TIME_EVENT = bch.git_time_event()  # safe: no threads yet

    Falls back to just the timestamp if not inside a git repository.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    commit = _run_git(["rev-parse", "HEAD"], repo_path)
    if not commit:
        return timestamp
    short = commit[:8]
    return f"{timestamp} {short}"
