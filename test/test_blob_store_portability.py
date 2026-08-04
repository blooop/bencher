"""A blob cell must survive its cache dir moving, because CI moves it every run.

A cache dir is not pinned to a location: CI tars it on one runner and restores it
at another workspace path, developers copy one between checkouts, an offline
cull downloads a tarball and works on it wherever it landed, and a report can be
rendered from a different working directory than the sweep ran in.  A cell that
recorded an absolute path dangled in every one of those cases while its blob sat
intact under the same content-addressed name — the payload was reachable, the
reference was not.

So the cell stores the blob *name* and :func:`resolve_blob` resolves it against
the cache dir in use now.  ``cache_management`` already reasoned this way for
reachability GC (``blob_name`` matches on the basename precisely so a moved
cache dir does not read as a directory full of garbage); these tests hold the
render path to the same rule, and keep the two generations of cell loadable.
"""

from __future__ import annotations

import shutil
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import panel as pn
import pytest

import bencher as bn
from bencher.blob_store import blob_name, load_blob, materialize_blob, resolve_blob

PAYLOAD = pd.DataFrame({"v": [1.0, 2.0]})


def _relocate(src: Path, dst: Path) -> Path:
    """Copy a cache dir to *dst* and delete the original, as a tar round-trip does."""
    shutil.copytree(src, dst)
    shutil.rmtree(src)
    return dst


class TestNameIsTheCellFormat:
    def test_materialize_returns_a_bare_name(self, tmp_path):
        name = materialize_blob(PAYLOAD, tmp_path)
        assert name == Path(name).name, "a cell must carry no directory"
        assert (tmp_path / "blobs" / name).is_file()

    def test_name_is_the_content_hash_so_equal_payloads_share_it(self, tmp_path):
        other = tmp_path / "elsewhere"
        assert materialize_blob(PAYLOAD, tmp_path) == materialize_blob(PAYLOAD, other)


class TestRelocatedCacheDir:
    def test_bare_name_loads_from_wherever_the_cache_dir_is_now(self, tmp_path):
        origin = tmp_path / "runner_a"
        name = materialize_blob(PAYLOAD, origin)
        moved = _relocate(origin, tmp_path / "runner_b" / "nested" / "cachedir")
        pd.testing.assert_frame_equal(load_blob(name, moved), PAYLOAD)

    def test_legacy_absolute_path_is_repaired_by_content_name(self, tmp_path):
        """The pre-name cell shape, from a cache dir that no longer exists.

        This is the case the old format lost outright: the recorded directory is
        gone, so the cell is unloadable by its own path — but the blob it names
        was restored with the rest of the cache, so the name still finds it.
        """
        origin = tmp_path / "runner_a"
        legacy_cell = str(origin / "blobs" / materialize_blob(PAYLOAD, origin))
        moved = _relocate(origin, tmp_path / "runner_b")
        assert not Path(legacy_cell).exists(), "precondition: the recorded path is dead"
        pd.testing.assert_frame_equal(load_blob(legacy_cell, moved), PAYLOAD)

    def test_legacy_absolute_path_still_loads_where_it_points(self, tmp_path):
        """No cache dir at the active location, so the cell's own path is all there
        is — a result rendered from a directory that has no ``cachedir`` of its own."""
        origin = tmp_path / "runner_a"
        legacy_cell = str(origin / "blobs" / materialize_blob(PAYLOAD, origin))
        pd.testing.assert_frame_equal(load_blob(legacy_cell, tmp_path / "no_such_cache"), PAYLOAD)

    def test_active_cache_dir_wins_over_a_stale_path_that_still_exists(self, tmp_path):
        """Both locations hold the blob, and the active one is authoritative.

        Content addressing makes the bytes identical, so this costs nothing and
        stops a leftover directory — another checkout, a previous CI workspace —
        from serving reads for the cache actually in use.
        """
        stale = tmp_path / "stale"
        active = tmp_path / "active"
        name = materialize_blob(PAYLOAD, stale)
        materialize_blob(PAYLOAD, active)
        assert resolve_blob(str(stale / "blobs" / name), active) == active / "blobs" / name


class TestBlobNamePredicate:
    @pytest.mark.parametrize("suffix", [".parquet", ".nc", ".da.nc", ".bin", ".pkl"])
    def test_accepts_both_cell_generations(self, suffix):
        name = f"abcdef0123456789{suffix}"
        assert blob_name(name) == name
        assert blob_name(f"/gone/cachedir/blobs/{name}") == name

    @pytest.mark.parametrize(
        "value", ["notablob.txt", "abcdef0123456789", "abcdef0123456789.parquet.gz", "NAN"]
    )
    def test_rejects_non_references(self, value):
        assert blob_name(value) is None

    def test_rejects_a_name_that_is_not_a_content_hash(self):
        # Guards the GC as much as the render path: a stray file dropped in
        # blobs/ must not read as a blob in either direction.
        assert blob_name("payload.parquet") is None


class TestResolveFailures:
    def test_non_reference_raises_valueerror(self, tmp_path):
        with pytest.raises(ValueError, match="is not a blob reference"):
            resolve_blob("results.csv", tmp_path)

    def test_missing_blob_names_every_location_tried(self, tmp_path):
        cell = "/gone/cachedir/blobs/abcdef0123456789.parquet"
        with pytest.raises(FileNotFoundError) as excinfo:
            resolve_blob(cell, tmp_path)
        message = str(excinfo.value)
        assert str(tmp_path / "blobs" / "abcdef0123456789.parquet") in message
        assert cell in message


def _tagged(scale: float, run_id: int) -> pd.DataFrame:
    return pd.DataFrame({"scale": [scale], "run": [float(run_id)]})


def _tagging_container(df: pd.DataFrame) -> pn.pane.Markdown:
    return pn.pane.Markdown(f"run={df['run'].iloc[0]:.0f} scale={df['scale'].iloc[0]:.0f}")


class RelocatedOverTimeSweep(bn.ParametrizedSweep):
    """A run-tagged payload, so a rendered pane says which run measured it."""

    scale = bn.FloatSweep(default=1.0, bounds=[1.0, 1.0], samples=1)
    table = bn.ResultDataSet(container=_tagging_container, doc="run-tagged frame")

    run_id = 0

    def benchmark(self):
        self.table = bn.ResultDataSet(_tagged(self.scale, self.run_id))


class TestOverTimeHistorySurvivesRelocation(unittest.TestCase):
    """The CI shape end to end: build a history, move the cache dir, render there.

    Every retained event must still render, and each pane must show the run that
    measured it.  Before names, the historical events resolved to the recorded
    absolute path and rendered as "could not be loaded" placeholders — a report
    that silently lost every event but the newest.
    """

    RUNS = 3

    def test_every_retained_event_renders_after_the_cache_dir_moves(self):
        with pytest.MonkeyPatch.context() as patch:
            origin = Path(self.enterContext(_tmpdir()))
            patch.chdir(origin)
            worker = RelocatedOverTimeSweep()
            bench = bn.Bench("test_blob_portability_over_time", worker)
            run_cfg = bn.BenchRunCfg()
            run_cfg.over_time = True
            run_cfg.repeats = 1
            run_cfg.auto_plot = False
            for i in range(self.RUNS):
                worker.run_id = i
                run_cfg.clear_cache = True
                run_cfg.clear_history = i == 0
                bench.plot_sweep(
                    "relocated_over_time",
                    input_vars=[],
                    result_vars=["table"],
                    run_cfg=run_cfg,
                    time_src=datetime(2000, 1, 1) + timedelta(seconds=i),
                )
            bench.report.clear()

        with pytest.MonkeyPatch.context() as patch:
            destination = Path(self.enterContext(_tmpdir()))
            _relocate(origin / "cachedir", destination / "cachedir")
            patch.chdir(destination)
            # A fresh Bench in the moved tree: no in-memory payloads, only what
            # the restored history and blob store carry.
            worker = RelocatedOverTimeSweep()
            worker.run_id = self.RUNS
            run_cfg = bn.BenchRunCfg()
            run_cfg.over_time = True
            run_cfg.repeats = 1
            run_cfg.auto_plot = False
            run_cfg.clear_cache = True
            run_cfg.clear_history = False
            result = bn.Bench("test_blob_portability_over_time", worker).plot_sweep(
                "relocated_over_time",
                input_vars=[],
                result_vars=["table"],
                run_cfg=run_cfg,
                time_src=datetime(2000, 1, 1) + timedelta(seconds=self.RUNS),
            )

            self.assertEqual(result.to_dataset().sizes["over_time"], self.RUNS + 1)
            rendered = [
                str(pane.object)
                for pane in result.to(bn.DataSetResult).select(pn.pane.Markdown)
                if str(pane.object).startswith("run=")
            ]
            self.assertEqual(
                rendered,
                [f"run={i} scale=1" for i in range(self.RUNS + 1)],
                "every event before the newest was collected under the old cache "
                "dir path; all of them must still render from the moved one",
            )


def _tmpdir():
    """A TemporaryDirectory as a context manager, for ``enterContext``."""
    import tempfile

    return tempfile.TemporaryDirectory()
