"""Tests for bencher.cache_management."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from diskcache import Cache

from bencher.cache_management import (
    CACHE_VERSION,
    DEFAULT_CACHE_SIZE_BYTES,
    CacheDirStats,
    CacheStats,
    cache_stats,
    clear_all,
    clear_media,
    clean_orphaned_media,
    cleanup_job_media,
    ensure_cache_version,
)


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
        return path

    def _make_job_media(self, folder, filename, job_key, content=b"x" * 100):
        """Create a per-job-key media file matching the v2 layout."""
        full_dir = os.path.join(self.cachedir, folder, filename, job_key)
        os.makedirs(full_dir, exist_ok=True)
        p = os.path.join(full_dir, f"{filename}.dat")
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
        vf.write_text("old_version")
        self._make_managed_cache("sample_cache", {"k": "v"})
        ensure_cache_version(self.cachedir)
        # Old cache should be gone, version updated
        self.assertEqual(vf.read_text().strip(), CACHE_VERSION)
        self.assertFalse((Path(self.cachedir) / "sample_cache").is_dir())

    def test_clears_when_no_version_file(self):
        self._make_managed_cache("sample_cache", {"k": "v"})
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


class TestGenPathWithJobKey(_TempCacheMixin, unittest.TestCase):
    """Test that gen_path uses per-job-key directories when context is set."""

    def test_with_job_key_context(self):
        from unittest.mock import patch

        from bencher.utils import gen_path, _current_job_key, _gen_path_counter

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

        from bencher.utils import gen_path, _current_job_key, _gen_path_counter

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
