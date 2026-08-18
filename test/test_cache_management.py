"""Tests for bencher.cache_management."""

import contextlib
import io
import os
import pickle
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import xarray as xr
from diskcache import Cache

import bencher as bn
from bencher import cache_management
from bencher.blob_store import materialize_blob
from bencher.cache_management import (
    CACHE_VERSION,
    DEFAULT_CACHE_SIZE_BYTES,
    CacheDirStats,
    CacheStats,
    blob_reachability,
    cache_stats,
    clean_orphaned_blobs,
    clean_orphaned_media,
    cleanup_job_media,
    clear_all,
    clear_media,
    ensure_cache_version,
    print_orphaned_blobs,
)
from bencher.result_collector import ResultCollector


class TestConstant(unittest.TestCase):
    def test_default_cache_size(self):
        self.assertEqual(DEFAULT_CACHE_SIZE_BYTES, int(100e9))


class TestCacheDirStats(unittest.TestCase):
    def test_summary_line_gb(self):
        s = CacheDirStats("sample_cache", 10, 2_500_000_000, 100_000_000_000)
        line = s.summary_line()
        self.assertIn("2.5 GB", line)
        self.assertIn("100.0 GB", line)
        self.assertIn("10", line)

    def test_summary_line_mb(self):
        s = CacheDirStats("img", 5, 1_500_000)
        line = s.summary_line()
        self.assertIn("1.5 MB", line)

    def test_summary_line_kb(self):
        s = CacheDirStats("rrd", 2, 1_500)
        line = s.summary_line()
        self.assertIn("1.5 KB", line)

    def test_summary_line_bytes(self):
        s = CacheDirStats("x", 1, 42)
        line = s.summary_line()
        self.assertIn("42 B", line)


class TestCacheStats(unittest.TestCase):
    def test_summary(self):
        stats = CacheStats(
            managed=[CacheDirStats("sample_cache", 3, 1000, 100_000_000_000)],
            media=[CacheDirStats("img", 2, 500)],
            total_bytes=1500,
        )
        s = stats.summary()
        self.assertIn("Cache Statistics", s)
        self.assertIn("sample_cache", s)
        self.assertIn("img", s)
        self.assertIn("Total:", s)


class _TempCacheMixin:
    """Mixin providing a temporary cachedir."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cachedir = os.path.join(self.tmpdir, "cachedir")
        os.makedirs(self.cachedir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_managed_cache(self, name, items=None):
        path = os.path.join(self.cachedir, name)
        c = Cache(path)
        if items:
            for k, v in items.items():
                c[k] = v
        c.close()
        # Real cachedirs always carry the version stamp ensure_cache_version()
        # writes; reachability treats a cache tree without a matching stamp as
        # unreadable (see TestBlobReachabilityVersionGuard).
        Path(self.cachedir, "CACHE_VERSION").write_text(CACHE_VERSION, encoding="utf-8")
        return path

    def _make_job_media(self, folder, filename, job_key, content=b"x" * 100):
        """Create a per-job-key media file matching the v2 layout."""
        full_dir = os.path.join(self.cachedir, folder, filename, job_key)
        os.makedirs(full_dir, exist_ok=True)
        p = os.path.join(full_dir, f"{filename}.dat")
        with open(p, "wb") as f:
            f.write(content)
        return p

    def _make_blob(self, name, content=b"x" * 100):
        """Create a flat, sha256-named file matching the blob store layout."""
        blobs_dir = os.path.join(self.cachedir, "blobs")
        os.makedirs(blobs_dir, exist_ok=True)
        p = os.path.join(blobs_dir, name)
        with open(p, "wb") as f:
            f.write(content)
        return p

    def _make_legacy_media(self, folder, filename, content=b"x" * 100):
        """Create a legacy UUID-named file (pre-v2 layout)."""
        full_dir = os.path.join(self.cachedir, folder, filename)
        os.makedirs(full_dir, exist_ok=True)
        p = os.path.join(full_dir, f"{filename}_legacy.dat")
        with open(p, "wb") as f:
            f.write(content)
        return p


class TestCacheVersion(_TempCacheMixin, unittest.TestCase):
    def test_creates_version_on_fresh_dir(self):
        # Remove cachedir so ensure_cache_version creates it
        shutil.rmtree(self.cachedir)
        ensure_cache_version(self.cachedir)
        vf = Path(self.cachedir) / "CACHE_VERSION"
        self.assertTrue(vf.is_file())
        self.assertEqual(vf.read_text().strip(), CACHE_VERSION)

    def test_noop_when_version_matches(self):
        vf = Path(self.cachedir) / "CACHE_VERSION"
        vf.write_text(CACHE_VERSION)
        self._make_managed_cache("sample_cache", {"k": "v"})
        ensure_cache_version(self.cachedir)
        # Cache should still exist
        c = Cache(os.path.join(self.cachedir, "sample_cache"))
        self.assertEqual(c["k"], "v")
        c.close()

    def test_clears_on_version_mismatch(self):
        vf = Path(self.cachedir) / "CACHE_VERSION"
        self._make_managed_cache("sample_cache", {"k": "v"})
        vf.write_text("old_version")
        ensure_cache_version(self.cachedir)
        # Old cache should be gone, version updated
        self.assertEqual(vf.read_text().strip(), CACHE_VERSION)
        self.assertFalse((Path(self.cachedir) / "sample_cache").is_dir())

    def test_clears_when_no_version_file(self):
        self._make_managed_cache("sample_cache", {"k": "v"})
        (Path(self.cachedir) / "CACHE_VERSION").unlink()
        ensure_cache_version(self.cachedir)
        vf = Path(self.cachedir) / "CACHE_VERSION"
        self.assertEqual(vf.read_text().strip(), CACHE_VERSION)
        # Old data should be cleared
        self.assertFalse((Path(self.cachedir) / "sample_cache").is_dir())


class TestCacheStatsIntegration(_TempCacheMixin, unittest.TestCase):
    def test_stats_with_managed_and_media(self):
        self._make_managed_cache("sample_cache", {"k1": "v1", "k2": "v2"})
        self._make_job_media("img", "img", "key1")
        self._make_job_media("vid", "vid", "key2", b"y" * 200)

        stats = cache_stats(self.cachedir)
        self.assertIsInstance(stats, CacheStats)

        sc = next(s for s in stats.managed if s.path == "sample_cache")
        self.assertEqual(sc.entries, 2)
        self.assertGreater(sc.size_bytes, 0)

        img = next(s for s in stats.media if s.path == "img")
        self.assertEqual(img.entries, 1)
        self.assertEqual(img.size_bytes, 100)

        vid = next(s for s in stats.media if s.path == "vid")
        self.assertEqual(vid.entries, 1)
        self.assertEqual(vid.size_bytes, 200)

        self.assertGreater(stats.total_bytes, 0)

    def test_stats_empty(self):
        stats = cache_stats(self.cachedir)
        self.assertEqual(stats.total_bytes, 0)

    def test_blob_store_is_counted(self):
        """The blob store grows without per-job pruning, so it must not be
        invisible to anyone auditing cache size."""
        self._make_blob("abc123def456abcd.parquet")
        self._make_blob("0123456789abcdef.nc", b"y" * 300)

        stats = cache_stats(self.cachedir)
        blobs = next(s for s in stats.content if s.path == "blobs")
        self.assertEqual(blobs.entries, 2)
        self.assertEqual(blobs.size_bytes, 400)
        self.assertEqual(stats.total_bytes, 400)
        self.assertIn("blobs", stats.summary())


class TestCleanupJobMedia(_TempCacheMixin, unittest.TestCase):
    def test_removes_job_key_dirs(self):
        self._make_job_media("img", "polygon", "abc123")
        self._make_job_media("rrd", "rrd", "abc123")
        # Different job key should survive
        other = self._make_job_media("img", "polygon", "other_key")

        removed = cleanup_job_media("abc123", self.cachedir)
        self.assertEqual(removed, 2)
        self.assertFalse(Path(self.cachedir, "img/polygon/abc123").exists())
        self.assertFalse(Path(self.cachedir, "rrd/rrd/abc123").exists())
        self.assertTrue(os.path.exists(other))

    def test_noop_for_missing_key(self):
        removed = cleanup_job_media("nonexistent", self.cachedir)
        self.assertEqual(removed, 0)


class TestClearAll(_TempCacheMixin, unittest.TestCase):
    def test_clear_all(self):
        self._make_managed_cache("sample_cache", {"k": "v"})
        self._make_job_media("img", "img", "key1")
        self.assertTrue(os.path.isdir(self.cachedir))
        clear_all(self.cachedir)
        self.assertFalse(os.path.exists(self.cachedir))

    def test_clear_all_nonexistent(self):
        clear_all(os.path.join(self.tmpdir, "nonexistent"))


class TestClearMedia(_TempCacheMixin, unittest.TestCase):
    def test_clears_media_keeps_caches(self):
        self._make_managed_cache("sample_cache", {"k": "v"})
        self._make_job_media("img", "img", "key1")
        self._make_job_media("vid", "vid", "key2", b"z" * 50)

        deleted, freed = clear_media(self.cachedir)
        self.assertEqual(deleted, 2)
        self.assertEqual(freed, 150)

        # Managed cache still exists
        c = Cache(os.path.join(self.cachedir, "sample_cache"))
        self.assertEqual(c["k"], "v")
        c.close()

    def test_clears_blobs_too(self):
        """Blobs are payload files like images: clearing media reclaims them, and
        the cells that referenced them degrade to placeholders at render."""
        self._make_managed_cache("sample_cache", {"k": "v"})
        self._make_blob("abc123def456abcd.parquet", b"q" * 80)

        deleted, freed = clear_media(self.cachedir)
        self.assertEqual(deleted, 1)
        self.assertEqual(freed, 80)
        self.assertFalse(Path(self.cachedir, "blobs").exists())


class TestBlobsAreNotPerJobPruned(_TempCacheMixin, unittest.TestCase):
    """A blob is shared by every job whose payload hashes the same, so the
    per-job and orphan cleanup paths must never touch it — deleting one job's
    blob would strand another job's cell."""

    def test_cleanup_job_media_leaves_blobs(self):
        blob = self._make_blob("abc123def456abcd.parquet")
        self._make_job_media("img", "img", "abc123")

        cleanup_job_media("abc123", self.cachedir)
        self.assertTrue(os.path.exists(blob))

    def test_clean_orphaned_media_leaves_blobs(self):
        # No sample cache at all, so every job key is dead: maximally aggressive.
        blob = self._make_blob("abc123def456abcd.parquet")

        orphans, _ = clean_orphaned_media(self.cachedir, dry_run=False)
        self.assertEqual(orphans, [])
        self.assertTrue(os.path.exists(blob))


class TestCleanOrphanedMedia(_TempCacheMixin, unittest.TestCase):
    def test_detects_orphan_job_dirs(self):
        # Job key present in cache — not an orphan
        self._make_managed_cache("sample_cache", {"live_key": "val"})
        self._make_job_media("img", "img", "live_key")
        # Job key NOT in cache — orphan
        self._make_job_media("rrd", "rrd", "dead_key")

        orphans, _ = clean_orphaned_media(self.cachedir, dry_run=True)
        self.assertEqual(len(orphans), 1)
        self.assertIn("dead_key", orphans[0])
        # Still exists (dry run)
        self.assertTrue(Path(self.cachedir, "rrd/rrd/dead_key").exists())

    def test_deletes_orphans(self):
        self._make_job_media("vid", "vid", "orphan_key")

        orphans, _ = clean_orphaned_media(self.cachedir, dry_run=False)
        self.assertEqual(len(orphans), 1)
        self.assertFalse(Path(self.cachedir, "vid/vid/orphan_key").exists())

    def test_cleans_legacy_files(self):
        """Legacy UUID-named files (pre-v2) with media extensions are treated as orphans."""
        self._make_legacy_media("img", "img")

        orphans, _ = clean_orphaned_media(self.cachedir, dry_run=False)
        self.assertEqual(len(orphans), 1)

    def test_ignores_non_media_files(self):
        """Non-media files like .gitkeep should not be treated as orphans."""
        full_dir = os.path.join(self.cachedir, "img", "polygon")
        os.makedirs(full_dir, exist_ok=True)
        gitkeep = os.path.join(full_dir, ".gitkeep")
        with open(gitkeep, "w", encoding="utf-8") as f:
            f.write("")

        orphans, _ = clean_orphaned_media(self.cachedir, dry_run=False)
        self.assertEqual(len(orphans), 0)
        self.assertTrue(os.path.exists(gitkeep))

    def test_no_orphans(self):
        self._make_managed_cache("sample_cache", {"my_key": "val"})
        self._make_job_media("img", "img", "my_key")

        orphans, _ = clean_orphaned_media(self.cachedir, dry_run=True)
        self.assertEqual(len(orphans), 0)


BLOB_A = "aaaa000000000000.parquet"
BLOB_B = "bbbb000000000000.nc"
BLOB_C = "cccc000000000000.pkl"

# The object sentinel setup_dataset fills object-dtype result columns with.
MISSING = "NAN"


def _cells(*rows) -> xr.Dataset:
    """A history-shaped dataset: one column ``table`` over (repeat, over_time).

    ``_cells(["a", "b"])`` is one repeat with two over_time events.
    """
    values = np.array(rows, dtype=object)
    return xr.Dataset(
        {"table": (("repeat", "over_time"), values)},
        coords={"repeat": list(range(values.shape[0])), "over_time": list(range(values.shape[1]))},
    )


def _record(dataset: xr.Dataset, columns=None, retired=None) -> dict:
    """The stored over_time history record shape (see bencher.history)."""
    return {
        "format": 1,
        "dataset": dataset,
        "columns": columns if columns is not None else {"table": {"identity": "x"}},
        "retired": retired or {},
    }


def _dataset_result_var(name: str, **kwargs) -> bn.ResultDataSet:
    """A named ResultDataSet, as the metaclass would produce on a class body."""
    rv = bn.ResultDataSet(**kwargs)
    rv.name = name
    return rv


def _bench_result(dataset: xr.Dataset) -> bn.BenchResult:
    """A BenchResult carrying *dataset*, as ``cache_results=True`` stores it."""
    result = bn.BenchResult(bn.BenchCfg())
    result.ds = dataset
    return result


class TestBlobReachabilityVersionGuard(_TempCacheMixin, unittest.TestCase):
    """A cachedir whose stamp does not match the library is unreadable, not empty.

    A record written under another CACHE_VERSION may unpickle fine while storing
    its blob references in a shape the walker does not descend — yielding a
    silently empty live set and a GC that deletes every blob. Plan 26 item 2 /
    plan 27 L9: missing or mismatched stamps must abort the scan, and this must
    hold before any CACHE_VERSION bump ships.
    """

    def test_stale_version_stamp_aborts_the_scan(self):
        self._make_managed_cache("history", {"k": _record(_cells([f"/c/blobs/{BLOB_A}"]))})
        Path(self.cachedir, "CACHE_VERSION").write_text("0", encoding="utf-8")
        reach = blob_reachability(self.cachedir)
        self.assertFalse(reach.complete)
        self.assertEqual(reach.names, frozenset())
        self.assertTrue(any("CACHE_VERSION" in line for line in reach.unreadable))

    def test_missing_version_stamp_with_caches_present_aborts_the_scan(self):
        self._make_managed_cache("history", {"k": _record(_cells([f"/c/blobs/{BLOB_A}"]))})
        Path(self.cachedir, "CACHE_VERSION").unlink()
        reach = blob_reachability(self.cachedir)
        self.assertFalse(reach.complete)
        self.assertTrue(any("CACHE_VERSION" in line for line in reach.unreadable))

    def test_gc_deletes_nothing_under_a_stale_stamp(self):
        self._make_managed_cache("history", {"k": _record(_cells([]))})
        Path(self.cachedir, "CACHE_VERSION").write_text("0", encoding="utf-8")
        blob = Path(self.cachedir) / "blobs" / BLOB_A
        blob.parent.mkdir(parents=True, exist_ok=True)
        blob.write_bytes(b"payload")
        orphans, freed = clean_orphaned_blobs(self.cachedir, dry_run=False)
        self.assertEqual((orphans, freed), ([], 0))
        self.assertTrue(blob.exists(), "GC must not delete under a version mismatch")


class TestBlobReachability(_TempCacheMixin, unittest.TestCase):
    """The live set is the union of every blob name any root still names."""

    def test_missing_caches_are_empty_not_unreadable(self):
        reach = blob_reachability(self.cachedir)
        self.assertEqual(reach.names, frozenset())
        self.assertTrue(reach.complete)

    def test_history_and_benchmark_caches_are_both_roots(self):
        self._make_managed_cache("history", {"k": _record(_cells([f"/c/blobs/{BLOB_A}"]))})
        self._make_managed_cache(
            "benchmark_inputs", {"k": _bench_result(_cells([f"/c/blobs/{BLOB_B}"]))}
        )
        reach = blob_reachability(self.cachedir)
        self.assertEqual(reach.names, frozenset({BLOB_A, BLOB_B}))

    def test_non_blob_strings_are_not_references(self):
        """Only content-addressed names count, so ordinary media paths are ignored."""
        self._make_managed_cache(
            "history",
            {"k": _record(_cells(["cachedir/img/img/key/img.png", "not a path", MISSING]))},
        )
        self.assertEqual(blob_reachability(self.cachedir).names, frozenset())

    def test_bare_strings_arrays_and_dataarrays_are_all_scanned(self):
        """The walk does not assume a Dataset: any shape a cached value can take
        (a loose path string, a numpy array, a DataArray and its coords) counts."""
        self._make_managed_cache(
            "benchmark_inputs",
            {
                "loose_string": f"/c/blobs/{BLOB_A}",
                "array": np.array([f"/c/blobs/{BLOB_B}"], dtype=object),
                "data_array": xr.DataArray(
                    np.array([f"/c/blobs/{BLOB_C}"], dtype=object),
                    dims="i",
                    coords={"i": np.array(["label"], dtype=object)},
                ),
            },
        )
        reach = blob_reachability(self.cachedir)
        self.assertEqual(reach.names, frozenset({BLOB_A, BLOB_B, BLOB_C}))

    def test_every_managed_cache_is_a_gc_root_or_the_documented_exclusion(self):
        """Guard on the hand-maintained coupling between the two cache lists.

        ``_BLOB_REFERENCE_CACHES`` is a manually curated subset of
        ``_MANAGED_CACHES``: every managed diskcache must either be scanned as a
        GC root or be ``sample_cache``, whose exclusion is argued in the comment
        on ``_BLOB_REFERENCE_CACHES`` (it holds pre-materialization worker
        payloads, which cannot name a blob).  Adding a new managed cache that
        can hold datasets without also making it a root would let GC delete
        live blobs — this test forces that decision to be made explicitly.
        """
        # pylint: disable=protected-access  # the coupling of the two module constants is the subject
        managed = set(cache_management._MANAGED_CACHES)
        roots = set(cache_management._BLOB_REFERENCE_CACHES)
        self.assertEqual(managed, roots | {"sample_cache"})


class TestCleanOrphanedBlobs(_TempCacheMixin, unittest.TestCase):
    """Reachability GC for the content-addressed blob store."""

    def _history(self, dataset, columns=None, retired=None):
        self._make_managed_cache("history", {"key": _record(dataset, columns, retired)})

    def test_referenced_blob_survives_and_unreferenced_is_collected(self):
        live = self._make_blob(BLOB_A)
        dead = self._make_blob(BLOB_B, b"y" * 40)
        self._history(_cells([f"{self.cachedir}/blobs/{BLOB_A}"]))

        orphans, freed = clean_orphaned_blobs(self.cachedir, dry_run=False)

        self.assertEqual(orphans, [dead])
        self.assertEqual(freed, 40)
        self.assertTrue(os.path.exists(live))
        self.assertFalse(os.path.exists(dead))

    def test_dry_run_is_the_default_and_deletes_nothing(self):
        dead = self._make_blob(BLOB_B, b"y" * 40)

        orphans, freed = clean_orphaned_blobs(self.cachedir)

        self.assertEqual(orphans, [dead])
        self.assertEqual(freed, 40)
        self.assertTrue(os.path.exists(dead))

    def test_blob_referenced_only_by_a_historical_event_survives(self):
        """The case a naive implementation gets wrong: an over_time history's
        oldest event is the sole reference, and looking at only the latest event
        (or the served projection) would declare the blob garbage."""
        old = self._make_blob(BLOB_A)
        self._history(_cells([f"/old/cachedir/blobs/{BLOB_A}", MISSING, MISSING]))

        orphans, _ = clean_orphaned_blobs(self.cachedir, dry_run=False)

        self.assertEqual(orphans, [])
        self.assertTrue(os.path.exists(old))

    def test_blob_referenced_only_by_a_retired_column_survives(self):
        """A ``meaning_version`` bump retires a column under a mangled name; the
        data stays in the stored superset dataset but is projected away from
        consumers, so only the raw record shows the reference."""
        retired_blob = self._make_blob(BLOB_A)
        dataset = xr.Dataset(
            {
                "table": (("repeat", "over_time"), np.array([[MISSING]], dtype=object)),
                "table__retired_deadbeef": (
                    ("repeat", "over_time"),
                    np.array([[f"/c/blobs/{BLOB_A}"]], dtype=object),
                ),
            },
            coords={"repeat": [0], "over_time": [0]},
        )
        self._history(
            dataset,
            columns={"table": {"identity": "new"}},
            retired={"table__retired_deadbeef": {"identity": "old", "retired_from": "table"}},
        )

        orphans, _ = clean_orphaned_blobs(self.cachedir, dry_run=False)

        self.assertEqual(orphans, [])
        self.assertTrue(os.path.exists(retired_blob))

    def test_blob_referenced_only_by_a_dormant_column_survives(self):
        """A column whose variable left the config is retained but not served,
        so it carries no entry in the record's ``columns`` metadata."""
        dormant_blob = self._make_blob(BLOB_A)
        dataset = xr.Dataset(
            {"gone": (("repeat", "over_time"), np.array([[f"/c/blobs/{BLOB_A}"]], dtype=object))},
            coords={"repeat": [0], "over_time": [0]},
        )
        self._history(dataset, columns={"table": {"identity": "x"}})

        orphans, _ = clean_orphaned_blobs(self.cachedir, dry_run=False)

        self.assertEqual(orphans, [])
        self.assertTrue(os.path.exists(dormant_blob))

    def test_deduplicated_blob_survives_while_another_cell_still_names_it(self):
        """Content addressing means one file backs many cells, which is exactly
        why per-cell (ownership) cleanup is unsound: the oldest event no longer
        references BLOB_A, but the newest still does."""
        shared = self._make_blob(BLOB_A)
        aged_out = self._make_blob(BLOB_C, b"z" * 10)
        path_a = f"/c/blobs/{BLOB_A}"
        self._history(_cells([MISSING, path_a, path_a]))

        orphans, _ = clean_orphaned_blobs(self.cachedir, dry_run=False)

        self.assertEqual(orphans, [aged_out])
        self.assertTrue(os.path.exists(shared))

    def test_reference_is_matched_by_name_so_a_moved_cachedir_still_protects(self):
        """A blob name *is* its content hash, so a stale absolute prefix from a
        cachedir that has since moved must not strand the payload."""
        blob = self._make_blob(BLOB_A)
        self._history(_cells([f"/somewhere/else/entirely/blobs/{BLOB_A}"]))

        orphans, _ = clean_orphaned_blobs(self.cachedir, dry_run=False)

        self.assertEqual(orphans, [])
        self.assertTrue(os.path.exists(blob))

    def test_partial_writes_and_stray_files_are_left_alone(self):
        """``materialize_blob`` renames from ``<name>.tmp-<uuid>``; one may belong
        to a worker writing right now, and neither it nor a stray file is a blob."""
        tmp_write = self._make_blob(f"{BLOB_A}.tmp-0123456789abcdef")
        stray = self._make_blob("README.txt")
        subdir = Path(self.cachedir, "blobs", "nested")
        subdir.mkdir()

        orphans, freed = clean_orphaned_blobs(self.cachedir, dry_run=False)

        self.assertEqual(orphans, [])
        self.assertEqual(freed, 0)
        self.assertTrue(os.path.exists(tmp_write))
        self.assertTrue(os.path.exists(stray))
        self.assertTrue(subdir.is_dir())

    def test_no_reference_caches_at_all_means_every_blob_is_garbage(self):
        """The default configuration writes neither cache (``cache_results`` and
        ``cache_samples`` both default to False), so a plain sweep leaves blobs
        that nothing on disk references — exactly as ``clean_orphaned_media``
        treats every media dir as orphaned when the sample cache is empty. GC is
        an offline maintenance step, not something to run beside a live sweep."""
        blob = self._make_blob(BLOB_A)

        orphans, _ = clean_orphaned_blobs(self.cachedir, dry_run=False)

        self.assertEqual(orphans, [blob])

    def test_min_age_seconds_protects_a_recently_written_blob(self):
        recent = self._make_blob(BLOB_A)
        old = self._make_blob(BLOB_B, b"y" * 40)
        os.utime(old, (time.time() - 7200, time.time() - 7200))

        orphans, freed = clean_orphaned_blobs(self.cachedir, dry_run=False, min_age_seconds=3600)

        self.assertEqual(orphans, [old])
        self.assertEqual(freed, 40)
        self.assertTrue(os.path.exists(recent))

    def test_empty_blob_store_is_a_noop(self):
        self.assertEqual(clean_orphaned_blobs(self.cachedir), ([], 0))


class TestBlobGCDegradesSafely(_TempCacheMixin, unittest.TestCase):
    """An unreadable root makes absence-of-reference unprovable, so nothing goes."""

    def _corrupt_history_value(self):
        """Store a value large enough to live in its own file, then garble it.

        diskcache keeps values above ``disk_min_file_size`` in ``*.val`` files,
        so this reproduces a genuinely undeserializable cache entry.
        """
        self._make_managed_cache("history", {"key": {"payload": b"x" * 200_000}})
        vals = list(Path(self.cachedir, "history").rglob("*.val"))
        self.assertEqual(len(vals), 1)
        vals[0].write_bytes(b"not a pickle")

    def test_corrupt_record_collects_nothing_and_keeps_every_blob(self):
        blob = self._make_blob(BLOB_A)
        self._corrupt_history_value()

        orphans, freed = clean_orphaned_blobs(self.cachedir, dry_run=False)

        self.assertEqual((orphans, freed), ([], 0))
        self.assertTrue(os.path.exists(blob))

    def test_incomplete_scan_reports_the_offending_entry(self):
        self._corrupt_history_value()
        reach = blob_reachability(self.cachedir)
        self.assertFalse(reach.complete)
        self.assertEqual(len(reach.unreadable), 1)
        self.assertIn("cannot deserialize", reach.unreadable[0])

    def test_unopenable_cache_collects_nothing(self):
        blob = self._make_blob(BLOB_A)
        self._make_managed_cache("history", {"key": "value"})

        with mock.patch("bencher.cache_management.Cache", side_effect=OSError("disk on fire")):
            orphans, _ = clean_orphaned_blobs(self.cachedir, dry_run=False)

        self.assertEqual(orphans, [])
        self.assertTrue(os.path.exists(blob))

    def test_unenumerable_cache_collects_nothing(self):
        blob = self._make_blob(BLOB_A)
        self._make_managed_cache("history", {"key": "value"})

        with mock.patch.object(Cache, "iterkeys", side_effect=OSError("bad index")):
            orphans, _ = clean_orphaned_blobs(self.cachedir, dry_run=False)

        self.assertEqual(orphans, [])
        self.assertTrue(os.path.exists(blob))

    def test_undeletable_blob_is_still_reported(self):
        """Matching clean_orphaned_media: the report is what was identified as
        garbage, so a permission failure is logged rather than hidden."""
        blob = self._make_blob(BLOB_A)

        with mock.patch.object(Path, "unlink", side_effect=OSError("read-only")):
            orphans, _ = clean_orphaned_blobs(self.cachedir, dry_run=False)

        self.assertEqual(orphans, [blob])
        self.assertTrue(os.path.exists(blob))

    def test_dry_run_matches_the_real_run_when_the_scan_is_incomplete(self):
        """A dry run has to stay an accurate preview, so it reports nothing too."""
        self._make_blob(BLOB_A)
        self._corrupt_history_value()
        self.assertEqual(clean_orphaned_blobs(self.cachedir), ([], 0))


class TestBlobGCExtraRoots(_TempCacheMixin, unittest.TestCase):
    """Results saved outside the cache are invisible unless declared."""

    def _saved_result(self, name: str, blob_name: str) -> Path:
        path = Path(self.tmpdir, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fh:
            pickle.dump(_bench_result(_cells([f"/c/blobs/{blob_name}"])), fh)
        return path

    def test_saved_result_is_stranded_without_extra_roots(self):
        """The honest limitation: nothing records where save_result wrote."""
        blob = self._make_blob(BLOB_A)
        self._saved_result("archive/run.pkl", BLOB_A)

        orphans, _ = clean_orphaned_blobs(self.cachedir, dry_run=False)

        self.assertEqual(orphans, [blob])

    def test_extra_root_file_protects_a_saved_result(self):
        blob = self._make_blob(BLOB_A)
        saved = self._saved_result("archive/run.pkl", BLOB_A)

        orphans, _ = clean_orphaned_blobs(self.cachedir, dry_run=False, extra_roots=[saved])

        self.assertEqual(orphans, [])
        self.assertTrue(os.path.exists(blob))

    def test_extra_root_directory_protects_every_pickle_under_it(self):
        blob_a = self._make_blob(BLOB_A)
        blob_b = self._make_blob(BLOB_B)
        dead = self._make_blob(BLOB_C, b"z" * 5)
        self._saved_result("archive/one.pkl", BLOB_A)
        self._saved_result("archive/nested/two.pkl", BLOB_B)

        orphans, _ = clean_orphaned_blobs(
            self.cachedir, dry_run=False, extra_roots=[Path(self.tmpdir, "archive")]
        )

        self.assertEqual(orphans, [dead])
        self.assertTrue(os.path.exists(blob_a))
        self.assertTrue(os.path.exists(blob_b))

    def test_missing_extra_root_aborts_rather_than_running_unprotected(self):
        """A typo'd archive path must not silently become an unprotected GC run."""
        blob = self._make_blob(BLOB_A)

        orphans, _ = clean_orphaned_blobs(
            self.cachedir, dry_run=False, extra_roots=[Path(self.tmpdir, "nope")]
        )

        self.assertEqual(orphans, [])
        self.assertTrue(os.path.exists(blob))

    def test_unloadable_extra_root_aborts(self):
        blob = self._make_blob(BLOB_A)
        bad = Path(self.tmpdir, "bad.pkl")
        bad.write_bytes(b"not a pickle")

        self.assertEqual(
            clean_orphaned_blobs(self.cachedir, dry_run=False, extra_roots=[bad]), ([], 0)
        )
        self.assertTrue(os.path.exists(blob))


class TestPrintOrphanedBlobs(_TempCacheMixin, unittest.TestCase):
    def _output(self, **kwargs) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            print_orphaned_blobs(self.cachedir, **kwargs)
        return buf.getvalue()

    def test_dry_run_report_names_the_blob_and_says_nothing_was_deleted(self):
        dead = self._make_blob(BLOB_B, b"y" * 40)
        out = self._output()
        self.assertIn(dead, out)
        self.assertIn("Would reclaim 1", out)
        self.assertIn("nothing deleted", out)
        self.assertTrue(os.path.exists(dead))

    def test_real_run_report(self):
        self._make_blob(BLOB_B, b"y" * 40)
        out = self._output(dry_run=False)
        self.assertIn("Reclaimed 1", out)

    def test_long_report_is_truncated(self):
        for i in range(25):
            self._make_blob(f"{i:016x}.pkl")
        out = self._output()
        self.assertIn("Would reclaim 25", out)
        self.assertIn("... and 5 more", out)

    def test_incomplete_scan_report(self):
        self._make_managed_cache("history", {"key": {"payload": b"x" * 200_000}})
        for val in Path(self.cachedir, "history").rglob("*.val"):
            val.write_bytes(b"not a pickle")
        out = self._output(dry_run=False)
        self.assertIn("aborted", out)
        self.assertIn("Nothing was deleted", out)


class TestBlobGCReclaimsAgedOutHistory(unittest.TestCase):
    """``max_time_events`` aging is the real-world blob garbage source.

    ``_null_old_entries`` overwrites an aged-out cell with the sentinel and
    deliberately does not delete the file — ``ResultDataSet`` is absent from
    ``_MEDIA_RESULT_TYPES`` precisely because a deduplicated blob may still back
    another live cell.  So aging leaves reachable-by-nobody blobs, and this is
    what reachability GC is for.  Runs against a throwaway cachedir via chdir,
    matching test/test_history_reconciliation.py.
    """

    def setUp(self):
        self._old_cwd = os.getcwd()
        self._tmp = tempfile.mkdtemp()
        os.chdir(self._tmp)
        # This test drives ResultCollector directly, bypassing Bench.__init__'s
        # ensure_cache_version() — stamp the cachedir so reachability trusts it.
        ensure_cache_version("cachedir")
        self.collector = ResultCollector()

    def tearDown(self):
        self.collector.close_caches()
        os.chdir(self._old_cwd)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _event(self, payload, result_var, event: int) -> Path:
        """Materialize *payload*, append it as one over_time event, return its file.

        The cell stores the blob *name* (blob_store's cell format); the returned
        path is what the on-disk assertions below need.
        """
        name = materialize_blob(payload, Path("cachedir").absolute())
        dataset = xr.Dataset(
            {"table": (("repeat", "over_time"), np.array([[name]], dtype=object))},
            coords={"repeat": [0], "over_time": [np.datetime64(f"2020-01-0{event + 1}")]},
        )
        self.collector.load_history_cache(
            dataset,
            "history-key",
            False,
            None,
            [result_var],
            bench_name="aging",
            tag="t",
            config_summary={"inputs": [], "consts": [], "results": ["table"], "repeats": 1},
        )
        return Path("cachedir") / "blobs" / name

    def test_aged_out_blob_is_reclaimed_and_live_events_survive(self):
        rv = _dataset_result_var("table", max_time_events=2)
        blobs = [self._event({"event": i}, rv, i) for i in range(3)]
        self.assertEqual(len(set(blobs)), 3)
        # The oldest cell is nulled to the sentinel but its file is left behind.
        self.assertTrue(all(os.path.exists(b) for b in blobs))

        orphans, freed = clean_orphaned_blobs("cachedir", dry_run=False)

        self.assertEqual([Path(p).name for p in orphans], [blobs[0].name])
        self.assertGreater(freed, 0)
        self.assertFalse(os.path.exists(blobs[0]))
        self.assertTrue(os.path.exists(blobs[1]))
        self.assertTrue(os.path.exists(blobs[2]))

    def test_aged_out_cell_sharing_a_blob_with_a_live_cell_keeps_the_file(self):
        """Identical payloads deduplicate to one file, so the aged-out event and
        the newest event can be the same blob — a per-cell delete would strand
        the live reference."""
        rv = _dataset_result_var("table", max_time_events=2)
        shared = self._event({"event": "same"}, rv, 0)
        other = self._event({"event": "middle"}, rv, 1)
        again = self._event({"event": "same"}, rv, 2)
        self.assertEqual(shared, again)

        orphans, _ = clean_orphaned_blobs("cachedir", dry_run=False)

        self.assertEqual(orphans, [])
        self.assertTrue(os.path.exists(shared))
        self.assertTrue(os.path.exists(other))


class TestGenPathWithJobKey(_TempCacheMixin, unittest.TestCase):
    """Test that gen_path uses per-job-key directories when context is set."""

    def test_with_job_key_context(self):
        from unittest.mock import patch

        from bencher.utils import _current_job_key, _gen_path_counter, gen_path

        token = _current_job_key.set("test_key_123")
        counter_token = _gen_path_counter.set({})
        try:
            with patch("bencher.utils.Path") as MockPath:
                # Redirect cachedir into our tmpdir
                real_path = Path
                MockPath.side_effect = lambda p: real_path(
                    p.replace("cachedir/", f"{self.cachedir}/", 1)
                )
                path = gen_path("myfile", "testfolder", ".txt")
            self.assertIn("test_key_123", path)
            self.assertTrue(path.endswith("myfile.txt"))
            self.assertNotIn("_", real_path(path).stem.split("myfile")[-1])
        finally:
            _gen_path_counter.reset(counter_token)
            _current_job_key.reset(token)

    def test_multiple_calls_same_args_get_unique_paths(self):
        """Multiple gen_path calls with the same args should not collide."""
        from unittest.mock import patch

        from bencher.utils import _current_job_key, _gen_path_counter, gen_path

        token = _current_job_key.set("dup_key")
        counter_token = _gen_path_counter.set({})
        try:
            with patch("bencher.utils.Path") as MockPath:
                real_path = Path
                MockPath.side_effect = lambda p: real_path(
                    p.replace("cachedir/", f"{self.cachedir}/", 1)
                )
                path1 = gen_path("img", "img", ".png")
                path2 = gen_path("img", "img", ".png")
            self.assertNotEqual(path1, path2)
            self.assertTrue(path1.endswith("img.png"))
            self.assertTrue(path2.endswith("img_1.png"))
        finally:
            _gen_path_counter.reset(counter_token)
            _current_job_key.reset(token)

    def test_without_job_key_context(self):
        from unittest.mock import patch

        from bencher.utils import gen_path

        with patch("bencher.utils.Path") as MockPath:
            real_path = Path
            MockPath.side_effect = lambda p: real_path(
                p.replace("cachedir/", f"{self.cachedir}/", 1)
            )
            path = gen_path("myfile", "testfolder2", ".txt")
        # Should have UUID in it (legacy fallback)
        stem = real_path(path).stem
        self.assertIn("myfile_", stem)


if __name__ == "__main__":
    unittest.main()
