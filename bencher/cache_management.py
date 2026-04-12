"""Cache management utilities for bencher.

Architecture
------------
Media files (images, videos, .rrd recordings) are stored in per-job-key
subdirectories under ``cachedir/{folder}/{filename}/{job_key}/``.  This
makes lifecycle management trivial:

* **Overwrite** — ``cleanup_job_media(job_key)`` deletes the directory
  before the new benchmark run writes fresh files.
* **LRU eviction** — ``clean_orphaned_media()`` walks the media tree,
  checks each job-key directory against the sample cache, and deletes
  directories whose entries are gone.
* **Full clear** — ``clear_all()`` removes the entire ``cachedir/``.

A ``CACHE_VERSION`` file inside ``cachedir/`` guards against stale data
from older formats.  ``ensure_cache_version()`` auto-clears on mismatch.
"""

from __future__ import annotations

import dataclasses
import logging
import shutil
from pathlib import Path

from diskcache import Cache

logger = logging.getLogger(__name__)

# Bump this when the cache layout changes in an incompatible way.
CACHE_VERSION = "3"

# Default cache size for benchmark results (100 GB).
# Used by ResultCollector, SweepExecutor, and Bench.
# FutureCache.__init__ uses a lower 20 GB default as a safety net for
# standalone usage; the 100 GB value is always passed through when
# FutureCache is created via SweepExecutor.init_sample_cache().
DEFAULT_CACHE_SIZE_BYTES = int(100e9)

# Managed diskcache directories (relative to cachedir root).
_MANAGED_CACHES = ("sample_cache", "benchmark_inputs", "history")

# Top-level media folders that contain per-job-key subdirectories.
_MEDIA_FOLDERS = ("img", "vid", "rrd", "generic")

# File extensions recognized as media when cleaning up legacy (pre-v2) files.
_MEDIA_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".svg",
        ".webp",
        ".mp4",
        ".avi",
        ".mov",
        ".webm",
        ".mkv",
        ".rrd",
        ".dat",
    }
)


# ---------------------------------------------------------------------------
# Cache versioning
# ---------------------------------------------------------------------------


def ensure_cache_version(cachedir: str = "cachedir") -> None:
    """Check the cache version file; clear everything on mismatch.

    Called automatically when a :class:`Bench` is instantiated.  If the
    version file is missing or doesn't match ``CACHE_VERSION``, the entire
    cache tree is deleted so stale data from incompatible layouts doesn't
    linger.
    """
    root = Path(cachedir)
    version_file = root / "CACHE_VERSION"
    if version_file.is_file():
        stored = version_file.read_text().strip()
        if stored == CACHE_VERSION:
            return
        logger.info(
            "Cache version mismatch (%s on disk, %s expected) — clearing %s",
            stored,
            CACHE_VERSION,
            root,
        )
    elif not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        version_file.write_text(CACHE_VERSION)
        return
    else:
        logger.info(
            "No cache version file found — clearing %s for clean start",
            root,
        )
    # Wipe everything and write the new version marker.
    clear_all(cachedir)
    root.mkdir(parents=True, exist_ok=True)
    version_file.write_text(CACHE_VERSION)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def _fmt_size(n: int) -> str:
    """Format a byte count as a human-readable string."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f} GB"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} MB"
    if n >= 1_000:
        return f"{n / 1_000:.1f} KB"
    return f"{n} B"


@dataclasses.dataclass
class CacheDirStats:
    """Statistics for a single cache or media directory."""

    path: str
    entries: int
    size_bytes: int
    size_limit_bytes: int | None = None

    def summary_line(self) -> str:
        size = _fmt_size(self.size_bytes)
        limit = f" / {_fmt_size(self.size_limit_bytes)}" if self.size_limit_bytes else ""
        return f"  {self.path:<30} {self.entries:>6} entries  {size:>10}{limit}"


@dataclasses.dataclass
class CacheStats:
    """Aggregate cache statistics."""

    managed: list[CacheDirStats]
    media: list[CacheDirStats]
    total_bytes: int

    def summary(self) -> str:
        lines = ["Cache Statistics", "=" * 60]
        if self.managed:
            lines.append("Managed caches (diskcache):")
            for s in self.managed:
                lines.append(s.summary_line())
        if self.media:
            lines.append("Media directories:")
            for s in self.media:
                lines.append(s.summary_line())
        lines.append("-" * 60)
        lines.append(f"  Total: {_fmt_size(self.total_bytes)}")
        return "\n".join(lines)


def _dir_stats(path: Path) -> tuple[int, int]:
    """Return (file_count, total_bytes) for all files under *path*."""
    count = 0
    total = 0
    if path.is_dir():
        for f in path.rglob("*"):
            if f.is_file():
                count += 1
                total += f.stat().st_size
    return count, total


def cache_stats(cachedir: str = "cachedir") -> CacheStats:
    """Collect statistics for all managed caches and media directories."""
    root = Path(cachedir)
    managed: list[CacheDirStats] = []
    total = 0

    for name in _MANAGED_CACHES:
        cache_path = root / name
        if cache_path.is_dir():
            try:
                c = Cache(str(cache_path))
                vol = c.volume()
                entries = len(c)
                limit = getattr(c, "size_limit", None)
                c.close()
                managed.append(CacheDirStats(name, entries, vol, size_limit_bytes=limit))
                total += vol
            except (OSError, ValueError) as exc:
                logger.warning("Could not open cache %s: %s", cache_path, exc)
        else:
            managed.append(CacheDirStats(name, 0, 0, size_limit_bytes=None))

    media: list[CacheDirStats] = []
    for folder in _MEDIA_FOLDERS:
        media_path = root / folder
        count, size = _dir_stats(media_path)
        media.append(CacheDirStats(folder, count, size))
        total += size

    return CacheStats(managed=managed, media=media, total_bytes=total)


def print_cache_stats(cachedir: str = "cachedir") -> None:
    """Print a human-readable cache statistics summary."""
    print(cache_stats(cachedir).summary())


# ---------------------------------------------------------------------------
# Per-job-key media cleanup
# ---------------------------------------------------------------------------


def cleanup_job_media(job_key: str, cachedir: str = "cachedir") -> int:
    """Delete the per-job-key media directories for *job_key*.

    Called automatically before a cache entry is overwritten so that
    stale media files from the previous run are removed.

    Returns the number of directories removed.
    """
    root = Path(cachedir)
    removed = 0
    for folder in _MEDIA_FOLDERS:
        # Media layout: cachedir/{folder}/{filename}/{job_key}/
        # We need to search one level down since {filename} varies.
        folder_root = root / folder
        if not folder_root.is_dir():
            continue
        for subfolder in folder_root.iterdir():
            if not subfolder.is_dir():
                continue
            job_dir = subfolder / job_key
            if job_dir.is_dir():
                try:
                    shutil.rmtree(job_dir)
                except OSError as exc:
                    logger.warning("Failed to remove job media directory %s: %s", job_dir, exc)
                else:
                    removed += 1
    return removed


# ---------------------------------------------------------------------------
# Bulk cleanup utilities
# ---------------------------------------------------------------------------


def clear_all(cachedir: str = "cachedir") -> None:
    """Remove the entire cache directory tree."""
    p = Path(cachedir)
    if p.is_dir():
        shutil.rmtree(p)
        logger.info("Removed %s", p)
    else:
        logger.info("Nothing to remove: %s does not exist", p)


def clear_media(cachedir: str = "cachedir") -> tuple[int, int]:
    """Delete all files in media directories.

    Returns (files_deleted, bytes_freed).
    """
    root = Path(cachedir)
    deleted = 0
    freed = 0
    for folder in _MEDIA_FOLDERS:
        media_path = root / folder
        if not media_path.is_dir():
            continue
        count, size = _dir_stats(media_path)
        try:
            shutil.rmtree(media_path)
        except OSError as exc:
            logger.warning("Failed to remove media directory %s: %s", media_path, exc)
            continue
        deleted += count
        freed += size
    logger.info("Deleted %d media files, freed %d bytes", deleted, freed)
    return deleted, freed


# ---------------------------------------------------------------------------
# Orphan reconciliation
# ---------------------------------------------------------------------------


def _collect_sample_cache_keys(cachedir: str) -> set[str]:
    """Return all keys currently in the sample cache."""
    cache_path = Path(cachedir) / "sample_cache"
    if not cache_path.is_dir():
        return set()
    try:
        c = Cache(str(cache_path))
        keys = set(c.iterkeys())
        c.close()
        return keys
    except (OSError, ValueError) as exc:
        logger.warning("Could not open sample cache: %s", exc)
        return set()


def clean_orphaned_media(cachedir: str = "cachedir", dry_run: bool = True) -> tuple[list[str], int]:
    """Find and optionally delete per-job-key media dirs with no cache entry.

    Walks the media tree looking for job-key subdirectories.  If the key
    is not present in the sample cache, the directory is an orphan (its
    cache entry was evicted by LRU or cleared).

    Args:
        cachedir: Root cache directory.
        dry_run: If True, only report orphans without deleting.

    Returns:
        (orphan_dirs, total_bytes) — list of orphaned directory paths and
        their combined size.
    """
    live_keys = _collect_sample_cache_keys(cachedir)
    root = Path(cachedir)
    orphans: list[str] = []
    orphan_bytes = 0

    for folder in _MEDIA_FOLDERS:
        folder_root = root / folder
        if not folder_root.is_dir():
            continue
        for subfolder in folder_root.iterdir():
            if not subfolder.is_dir():
                continue
            for job_dir in subfolder.iterdir():
                if not job_dir.is_dir():
                    # Legacy UUID-named file — orphan in v2, but only
                    # touch files with recognized media extensions.
                    if job_dir.is_file() and job_dir.suffix.lower() in _MEDIA_EXTENSIONS:
                        size = job_dir.stat().st_size
                        orphans.append(str(job_dir))
                        orphan_bytes += size
                        if not dry_run:
                            try:
                                job_dir.unlink()
                            except OSError as exc:
                                logger.warning("Failed to remove orphan %s: %s", job_dir, exc)
                    continue
                job_key = job_dir.name
                if job_key not in live_keys:
                    _, size = _dir_stats(job_dir)
                    orphans.append(str(job_dir))
                    orphan_bytes += size
                    if not dry_run:
                        try:
                            shutil.rmtree(job_dir)
                        except OSError as exc:
                            logger.warning("Failed to remove orphan dir %s: %s", job_dir, exc)

    action = "Dry run: found" if dry_run else "Deleted"
    logger.info(
        "%s %d orphaned media entries (%d bytes)",
        action,
        len(orphans),
        orphan_bytes,
    )
    return orphans, orphan_bytes
