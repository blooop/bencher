"""Concurrency and data-race behaviour of the blob store and its garbage collector.

The blob store is written by workers and read by renderers, and its GC deletes
files that a *snapshot* of the cache said nothing referenced. That combination has
three genuinely concurrent surfaces, and this module pins the behaviour of each:

1. **Two writers, one payload.** Content addressing means concurrent workers
   routinely materialize byte-identical payloads to the same filename.
   ``materialize_blob`` writes through a uniquely-named temp file and an atomic
   rename, so a reader must never observe a partial or interleaved blob.
2. **GC versus a writer.** ``clean_orphaned_blobs`` computes reachability and
   *then* lists the directory. Anything that becomes referenced inside that window
   is invisible to the snapshot but present in the listing. These tests establish
   exactly how far the guarantees reach: ``min_age_seconds`` protects both a blob
   the concurrent sweep *wrote* and one it *deduplicated onto* (a content hit
   refreshes mtime, so mtime means "last referenced"), but the **default**
   ``min_age_seconds=0`` offers no protection at all — that case stays pinned, and
   is why GC is still documented as a between-sessions operation.
3. **GC versus GC, and GC versus a reader.** Both must degrade rather than raise:
   a losing racer sees ``FileNotFoundError`` from its own ``unlink``, and a
   renderer whose blob vanished must produce a placeholder.

Interleavings are **injected deterministically** (a wrapper around the scan, or a
barrier) rather than produced by sleeping and hoping. A race test that only fails
under load is worse than no test, because it teaches the suite to be ignored.
"""

from __future__ import annotations

import hashlib
import os
import pickle
import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from diskcache import Cache

from bencher import cache_management
from bencher.blob_store import _HASH_CHARS, blob_name, load_blob, materialize_blob
from bencher.cache_management import blob_reachability, clean_orphaned_blobs

# Enough concurrency to interleave on a normal CI box without making the suite slow.
_THREADS = 16
_PROCESSES = 4


def frame(scale: float, rows: int = 64) -> pd.DataFrame:
    """A payload big enough that a torn write would be visible, not a single page."""
    return pd.DataFrame({"t": np.arange(rows), "v": np.arange(rows, dtype=float) * scale})


def write_reference(cachedir: Path, *blob_paths: str, cache_name: str = "history") -> None:
    """Store a history-shaped record naming *blob_paths*, as a real sweep would."""
    cells = np.array(list(blob_paths), dtype=object)
    ds = xr.Dataset(
        {"table": (("over_time",), cells)},
        coords={"over_time": np.arange(len(blob_paths))},
    )
    with Cache(str(cachedir / cache_name)) as cache:
        cache["record"] = {"format": 1, "dataset": ds, "columns": {}, "retired": {}}


class TestConcurrentMaterialize:
    """Many writers, one content-addressed directory."""

    def test_threads_writing_identical_payload_produce_one_intact_blob(self, tmp_path):
        """The dedup case: every worker computes the same name, so they all race on
        one filename. Exactly one file must exist and it must be complete."""
        payload = frame(1.0)
        barrier = threading.Barrier(_THREADS)

        def worker() -> str:
            barrier.wait()  # maximise overlap on the write window
            return materialize_blob(payload, tmp_path)

        with ThreadPoolExecutor(max_workers=_THREADS) as pool:
            paths = list(pool.map(lambda _: worker(), range(_THREADS)))

        assert len(set(paths)) == 1, "identical payloads must map to one path"
        blobs = sorted((tmp_path / "blobs").iterdir())
        assert len(blobs) == 1, f"expected exactly one blob, got {[b.name for b in blobs]}"
        pd.testing.assert_frame_equal(load_blob(paths[0], tmp_path), payload)

    def test_no_temp_files_survive_a_concurrent_write_storm(self, tmp_path):
        """Every temp file must have been renamed away, not left as garbage the GC
        deliberately refuses to touch."""
        payload = frame(2.0)
        with ThreadPoolExecutor(max_workers=_THREADS) as pool:
            list(pool.map(lambda _: materialize_blob(payload, tmp_path), range(_THREADS)))

        leftovers = [p.name for p in (tmp_path / "blobs").iterdir() if ".tmp-" in p.name]
        assert leftovers == []

    def test_threads_writing_distinct_payloads_all_round_trip(self, tmp_path):
        """No cross-talk: concurrent distinct payloads keep their own contents."""
        payloads = {i: frame(float(i + 1)) for i in range(_THREADS)}
        barrier = threading.Barrier(_THREADS)

        def worker(i: int) -> tuple[int, str]:
            barrier.wait()
            return i, materialize_blob(payloads[i], tmp_path)

        with ThreadPoolExecutor(max_workers=_THREADS) as pool:
            results = dict(pool.map(worker, range(_THREADS)))

        assert len(set(results.values())) == _THREADS, "distinct payloads must not collide"
        for i, path in results.items():
            pd.testing.assert_frame_equal(load_blob(path, tmp_path), payloads[i])

    def test_blob_is_published_by_atomic_rename_not_a_partial_write(self, tmp_path):
        """Deterministic guard on the publish mechanism.

        The stress test below cannot reliably *lose* this race — a small payload is
        often a single write syscall — and mutation testing confirmed it still passes
        when the temp-file rename is replaced by a direct write. Atomic publication
        has no black-box signature, so assert the mechanism itself: at the instant
        before the rename the final name must not yet exist, and the complete bytes
        must already be in a temp sibling. If publication stops going through
        ``Path.replace`` at all, the hook never fires and this fails.
        """
        payload = frame(3.5, rows=256)

        # A `dict[str, object]` bag here made every read `object`, so even
        # `".tmp-" in observed["tmp_name"]` was not a legal expression. Three
        # differently-typed observations are a record, not a mapping.
        @dataclass
        class Observed:
            fired: bool = False
            final_existed_before_rename: bool = True
            tmp_name: str = ""
            tmp_bytes: bytes = b""

        observed = Observed()
        real_replace = Path.replace

        def watching_replace(self, target):
            observed.fired = True
            observed.final_existed_before_rename = Path(target).exists()
            observed.tmp_name = self.name
            observed.tmp_bytes = self.read_bytes()
            return real_replace(self, target)

        with mock.patch.object(Path, "replace", watching_replace):
            path = _blob(tmp_path, materialize_blob(payload, tmp_path))

        assert observed.fired, "blob was published without going through an atomic rename"
        assert observed.final_existed_before_rename is False
        assert ".tmp-" in observed.tmp_name, "staged file is not a temp sibling"
        # The staged bytes were already complete before the name became visible.
        assert observed.tmp_bytes == path.read_bytes()
        pd.testing.assert_frame_equal(load_blob(path, tmp_path), payload)

    def test_reader_racing_a_writer_never_sees_a_partial_blob(self, tmp_path):
        """Stress companion to the mechanism test above: under sustained read
        pressure a reader must only ever see complete bytes or a clean miss.

        This cannot *prove* atomicity (it may simply never hit the window), so it
        guards against gross regressions while the test above pins the mechanism.
        """
        payload = frame(3.0, rows=512)
        expected_path = _blob(tmp_path, materialize_blob(payload, tmp_path))
        expected_bytes = expected_path.read_bytes()
        expected_path.unlink()  # re-materialize below while readers hammer it

        errors: list[Exception] = []
        torn: list[int] = []
        stop = threading.Event()

        def reader() -> None:
            while not stop.is_set():
                try:
                    data = expected_path.read_bytes()
                except FileNotFoundError:
                    continue  # legitimate: the rename has not landed yet
                except OSError as exc:  # pragma: no cover - would be a real defect
                    errors.append(exc)
                    return
                if data and data != expected_bytes:
                    torn.append(len(data))
                    return

        threads = [threading.Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        try:
            for _ in range(40):
                materialize_blob(payload, tmp_path)
                expected_path.unlink(missing_ok=True)
        finally:
            stop.set()
            for t in threads:
                t.join()

        assert errors == [], f"reader saw unexpected OS errors: {errors}"
        assert torn == [], f"reader observed {len(torn)} partial blob(s), sizes {torn}"


def _materialize_in_subprocess(args: tuple[str, int]) -> str:
    """Module-level so it is picklable for ProcessPoolExecutor."""
    cache_dir, rows = args
    return materialize_blob(frame(1.0, rows=rows), cache_dir)


class TestCrossProcessMaterialize:
    """Real sweeps run workers in separate processes, so the atomic-rename
    guarantee has to hold across processes, not just threads."""

    def test_processes_writing_identical_payload_produce_one_intact_blob(self, tmp_path):
        args = [(str(tmp_path), 128)] * _PROCESSES
        with ProcessPoolExecutor(max_workers=_PROCESSES) as pool:
            paths = list(pool.map(_materialize_in_subprocess, args))

        assert len(set(paths)) == 1
        blobs = [p for p in (tmp_path / "blobs").iterdir() if ".tmp-" not in p.name]
        assert len(blobs) == 1
        pd.testing.assert_frame_equal(load_blob(paths[0], tmp_path), frame(1.0, rows=128))
        assert [p.name for p in (tmp_path / "blobs").iterdir() if ".tmp-" in p.name] == []


class TestGCRacingAWriter:
    """``clean_orphaned_blobs`` snapshots reachability, then lists the directory.

    These tests pin what happens to work that lands inside that window. They are
    deterministic: the interleaving is injected by wrapping the scan, so the exact
    window is hit on every run rather than occasionally.
    """

    def _inject_after_scan(self, monkeypatch, hook) -> None:
        """Run *hook* immediately after reachability is computed, before deletion."""
        real = cache_management.blob_reachability

        def wrapper(*args, **kwargs):
            result = real(*args, **kwargs)
            hook()
            return result

        monkeypatch.setattr(cache_management, "blob_reachability", wrapper)

    def test_blob_written_after_the_scan_is_deleted_despite_being_referenced(
        self, tmp_path, monkeypatch
    ):
        """**Known hazard, pinned deliberately.** A sweep that materializes a blob
        and records its reference *after* the scan is invisible to that snapshot, so
        the default ``min_age_seconds=0`` collects a live blob. This is why GC is
        documented as a between-sessions operation; the test exists so the exposure
        cannot change silently."""

        def concurrent_sweep() -> None:
            path = materialize_blob(frame(9.0), tmp_path)
            write_reference(tmp_path, path)

        self._inject_after_scan(monkeypatch, concurrent_sweep)
        orphans, _ = clean_orphaned_blobs(str(tmp_path), dry_run=False)

        assert len(orphans) == 1, "the post-scan blob is collected (documented hazard)"
        # And the reference recorded by that sweep is now dangling.
        assert blob_reachability(str(tmp_path)).names, "sweep did record a reference"
        assert not Path(orphans[0]).exists()

    def test_min_age_seconds_closes_the_window_for_a_freshly_written_blob(
        self, tmp_path, monkeypatch
    ):
        """The documented mitigation: a grace period longer than the write window
        protects the blob the previous test loses."""

        def concurrent_sweep() -> None:
            path = materialize_blob(frame(9.0), tmp_path)
            write_reference(tmp_path, path)

        self._inject_after_scan(monkeypatch, concurrent_sweep)
        orphans, nbytes = clean_orphaned_blobs(str(tmp_path), dry_run=False, min_age_seconds=3600)

        assert orphans == [] and nbytes == 0
        assert len(list((tmp_path / "blobs").iterdir())) == 1

    def test_min_age_protects_a_new_reference_to_an_old_deduplicated_blob(
        self, tmp_path, monkeypatch
    ):
        """**The gap ``min_age_seconds`` used to leave open, now closed.** Dedup
        lets a *new* sweep reference an *old* blob without rewriting it —
        ``materialize_blob`` returns the existing path — but a content hit now
        refreshes the blob's mtime, so mtime means "last referenced" rather than
        "created" and the grace period protects this blob exactly as it protects
        a freshly written one. The deletion loop stats each blob immediately
        before its unlink, so the touch is visible to the age check even though
        it lands after the reachability scan."""
        old_name = materialize_blob(frame(7.0), tmp_path)
        old_path = _blob(tmp_path, old_name)
        os.utime(old_path, (1, 1))  # backdate far beyond the grace period below

        def concurrent_sweep_dedups_onto_it() -> None:
            again = materialize_blob(frame(7.0), tmp_path)  # same content -> same name
            assert again == old_name, "precondition: this is the dedup path"
            write_reference(tmp_path, again)

        self._inject_after_scan(monkeypatch, concurrent_sweep_dedups_onto_it)
        orphans, nbytes = clean_orphaned_blobs(str(tmp_path), dry_run=False, min_age_seconds=3600)

        assert orphans == [] and nbytes == 0, "the dedup touch must protect the old blob"
        assert old_path.exists()
        # The reference the sweep recorded is intact, not dangling.
        assert blob_reachability(str(tmp_path)).names == {old_name}

    def test_a_blob_referenced_before_the_scan_is_never_at_risk(self, tmp_path):
        """The ordinary, safe case: reference recorded first, so GC sees it."""
        path = materialize_blob(frame(4.0), tmp_path)
        write_reference(tmp_path, path)

        orphans, nbytes = clean_orphaned_blobs(str(tmp_path), dry_run=False)

        assert orphans == [] and nbytes == 0
        assert _blob(tmp_path, path).exists()


class TestGCRacingGC:
    """Two collectors over one directory must both survive."""

    def test_concurrent_collectors_do_not_raise_on_double_delete(self, tmp_path):
        """Each racer deletes from its own listing, so the loser's ``unlink`` hits a
        file that is already gone. That is an ``OSError`` the loop must swallow."""
        for i in range(24):
            materialize_blob(frame(float(i)), tmp_path)  # all unreferenced

        results: list[tuple[list[str], int]] = []
        errors: list[Exception] = []
        barrier = threading.Barrier(2)

        def collector() -> None:
            try:
                barrier.wait()
                results.append(clean_orphaned_blobs(str(tmp_path), dry_run=False))
            # pylint: disable=broad-exception-caught  # any raise at all is the failure
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=collector) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"concurrent GC raised: {errors}"
        assert len(results) == 2
        blobs = [p for p in (tmp_path / "blobs").iterdir() if _blob_like(p)]
        assert blobs == [], "every unreferenced blob should be gone"

    def test_blob_vanishing_between_listing_and_stat_is_skipped(self, tmp_path, monkeypatch):
        """The narrower window inside the loop: the file disappears after
        ``iterdir`` but before ``stat``. It must be skipped, not raise."""
        doomed = _blob(tmp_path, materialize_blob(frame(5.0), tmp_path))
        real_stat = Path.stat
        removed = threading.Event()

        def vanishing_stat(self, *args, **kwargs):
            # One-shot, and never re-enter Path.exists()/is_file() from here: those
            # call stat() themselves, which would recurse into this very patch.
            if self == doomed and not removed.is_set():
                removed.set()
                os.unlink(doomed)  # simulate the other racer winning right here
            return real_stat(self, *args, **kwargs)

        monkeypatch.setattr(Path, "stat", vanishing_stat)
        orphans, nbytes = clean_orphaned_blobs(str(tmp_path), dry_run=False)

        assert orphans == [] and nbytes == 0
        assert not doomed.exists()


class TestGCRacingAReader:
    """A renderer holding a path whose blob is collected mid-flight."""

    def test_load_blob_raises_a_catchable_error_when_the_blob_is_collected(self, tmp_path):
        """The render path catches per-cell load failures and substitutes a
        placeholder, so ``load_blob`` only has to fail catchably rather than
        crash the process or return corrupt data."""
        path = materialize_blob(frame(6.0), tmp_path)
        clean_orphaned_blobs(str(tmp_path), dry_run=False)  # unreferenced -> collected

        with pytest.raises((FileNotFoundError, OSError)):
            load_blob(path, tmp_path)

    def test_readers_and_a_collector_interleave_without_corruption(self, tmp_path):
        """Under sustained read pressure a collector must produce only two outcomes
        per read: the correct payload, or a clean miss. Never wrong bytes."""
        payload = frame(8.0, rows=256)
        path = materialize_blob(payload, tmp_path)
        write_reference(tmp_path, path)  # keep it live, so reads should mostly succeed

        wrong: list[str] = []
        stop = threading.Event()

        def reader() -> None:
            while not stop.is_set():
                try:
                    got = load_blob(path, tmp_path)
                except (FileNotFoundError, OSError):
                    continue
                try:
                    pd.testing.assert_frame_equal(got, payload)
                except AssertionError as exc:  # pragma: no cover - real defect
                    wrong.append(str(exc))
                    return

        threads = [threading.Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        try:
            for _ in range(20):
                clean_orphaned_blobs(str(tmp_path), dry_run=False)
        finally:
            stop.set()
            for t in threads:
                t.join()

        assert wrong == [], f"reader observed corrupt payloads: {wrong[:1]}"
        assert _blob(tmp_path, path).exists(), "a referenced blob must survive every GC pass"


def _blob(cache_dir: Path, name: str) -> Path:
    """The file a ``materialize_blob`` name refers to under *cache_dir*."""
    return Path(cache_dir) / "blobs" / name


def _blob_like(path: Path) -> bool:
    """True for a real blob filename, excluding temp and stray files.

    Reuses the production predicate rather than restating it, so a change to what
    counts as a blob cannot silently desynchronise this helper from the collector.
    """
    return blob_name(path.name) is not None


class TestContentAddressingUnderConcurrency:
    """Invariants that must hold no matter how writers interleave."""

    def test_filename_is_always_the_digest_of_the_bytes_on_disk(self, tmp_path):
        """A blob whose name did not match its contents would make dedup unsound
        and every reachability decision meaningless."""
        payloads = [frame(float(i)) for i in range(8)] + [
            xr.Dataset({"v": ("x", np.arange(4, dtype="float64"))}),
            b"raw-bytes-payload",
            {"picklable": "object"},
        ]
        with ThreadPoolExecutor(max_workers=_THREADS) as pool:
            list(pool.map(lambda p: materialize_blob(p, tmp_path), payloads))

        for blob in (tmp_path / "blobs").iterdir():
            digest = hashlib.sha256(blob.read_bytes()).hexdigest()[:_HASH_CHARS]
            stem = blob.name.split(".")[0]
            assert stem == digest, f"{blob.name} does not match its content digest"

    def test_repeated_materialize_refreshes_mtime_but_never_rewrites_the_bytes(self, tmp_path):
        """The content-hit contract: the bytes are never rewritten (what makes
        concurrent dedup cheap and tear-free), but the mtime **is** refreshed —
        a hit is a new reference, and mtime is the GC grace period's signal for
        "recently referenced" (see the dedup/min_age test above).

        "Never rewritten" is asserted on the mechanism: publication only ever
        happens through the temp-file ``Path.replace``, so zero replace calls
        during the hits means zero writes — mtime can no longer stand in as the
        no-rewrite witness, since the touch moves it by design.
        """
        payload = frame(1.5)
        path = _blob(tmp_path, materialize_blob(payload, tmp_path))
        original_bytes = path.read_bytes()
        backdated = 1_000_000_000  # far in the past, so a refresh is unmistakable
        os.utime(path, (backdated, backdated))

        replace_calls: list[str] = []
        real_replace = Path.replace

        def counting_replace(self, target):
            replace_calls.append(self.name)
            return real_replace(self, target)

        with mock.patch.object(Path, "replace", counting_replace):
            for _ in range(5):
                assert materialize_blob(payload, tmp_path) == path.name

        assert replace_calls == [], "a content hit must not rewrite the blob"
        assert path.read_bytes() == original_bytes
        assert path.stat().st_mtime > backdated, (
            "a content hit must refresh mtime — it is a new reference, and the GC "
            "grace period reasons about last-referenced time"
        )


class TestPickleRoundTripUnderConcurrency:
    """The pickle fallback shares the same write path, so it needs the same guarantee."""

    def test_concurrent_pickle_fallback_payloads_stay_intact(self, tmp_path):
        """int64 datasets take the pickle branch; concurrent writers must not tear
        each other's files."""
        payloads = [
            xr.Dataset({"v": ("x", np.arange(32, dtype="int64") + i)}) for i in range(_THREADS)
        ]
        barrier = threading.Barrier(_THREADS)

        def worker(i: int) -> tuple[int, str]:
            barrier.wait()
            return i, materialize_blob(payloads[i], tmp_path)

        with ThreadPoolExecutor(max_workers=_THREADS) as pool:
            results = dict(pool.map(worker, range(_THREADS)))

        for i, path in results.items():
            assert path.endswith(".pkl"), "int64 must take the pickle fallback"
            xr.testing.assert_identical(load_blob(path, tmp_path), payloads[i])
        # Sanity: pickle bytes are deterministic here, so all names are distinct.
        assert len(set(results.values())) == _THREADS

    def test_unpicklable_payload_fails_loudly_rather_than_writing_a_bad_blob(self, tmp_path):
        """A lambda is outside the documented 'any picklable object' contract. It
        must raise rather than silently persist something unloadable, and must not
        leave a temp file behind."""
        with pytest.raises((pickle.PicklingError, AttributeError, TypeError)):
            materialize_blob(lambda x: x, tmp_path)

        blobs_dir = tmp_path / "blobs"
        leftovers = list(blobs_dir.iterdir()) if blobs_dir.is_dir() else []
        assert leftovers == [], f"failed write left files behind: {leftovers}"
