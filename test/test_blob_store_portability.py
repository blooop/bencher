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

import pickle
import shutil
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import panel as pn
import pytest
import xarray as xr

import bencher as bn
from bencher.blob_store import (
    _BLOB_FORMATS,
    blob_cache_dir_hints,
    blob_name,
    load_blob,
    materialize_blob,
    record_blob_cache_dir,
    resolve_blob,
)

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


class TestCollectTimeCacheDirHint:
    """A name is a complete identity but not a complete address.

    Dropping the directory from the cell fixes the moved cache and breaks the
    *moved reader*: ``bencher <result.pkl> <out>`` renders from wherever it was
    invoked, and a bare name resolves only where a ``cachedir`` happens to sit in
    that working directory.  So the cache dir a result was collected under is
    recorded once on the dataset and tried after the active one.
    """

    def test_hint_resolves_a_bare_name_with_no_active_cache_dir(self, tmp_path):
        origin = tmp_path / "workspace" / "cachedir"
        name = materialize_blob(PAYLOAD, origin)
        elsewhere = tmp_path / "elsewhere"  # a cwd with no cachedir of its own
        with pytest.raises(FileNotFoundError):
            resolve_blob(name, elsewhere / "cachedir")
        pd.testing.assert_frame_equal(
            load_blob(name, elsewhere / "cachedir", fallback_cache_dirs=(origin,)), PAYLOAD
        )

    def test_active_cache_dir_still_wins_over_the_hint(self, tmp_path):
        """The hint is a fallback, never a redirect: a relocated cache still reads
        from where it is now even though the recorded dir also still exists."""
        recorded = tmp_path / "previous_workspace"
        active = tmp_path / "current_workspace"
        name = materialize_blob(PAYLOAD, recorded)
        materialize_blob(PAYLOAD, active)
        assert (
            resolve_blob(name, active, fallback_cache_dirs=(recorded,)) == active / "blobs" / name
        )

    def test_hint_is_tried_before_a_legacy_cells_own_path(self, tmp_path):
        """Ordering across all three: active, then recorded, then the literal cell."""
        literal = tmp_path / "cell_path"
        recorded = tmp_path / "recorded"
        name = materialize_blob(PAYLOAD, literal)
        materialize_blob(PAYLOAD, recorded)
        cell = str(literal / "blobs" / name)
        resolved = resolve_blob(cell, tmp_path / "no_such_cache", fallback_cache_dirs=(recorded,))
        assert resolved == recorded / "blobs" / name

    def test_missing_blob_lists_the_hint_and_never_repeats_a_location(self, tmp_path):
        """A legacy cell pointing into the active cache dir is one location, not two."""
        cell = str(tmp_path / "blobs" / "abcdef0123456789.parquet")
        with pytest.raises(FileNotFoundError) as excinfo:
            resolve_blob(cell, tmp_path, fallback_cache_dirs=(tmp_path / "recorded",))
        message = str(excinfo.value)
        assert str(tmp_path / "recorded" / "blobs" / "abcdef0123456789.parquet") in message
        assert message.count(cell) == 1, f"location listed more than once: {message}"

    def test_hints_read_back_what_was_recorded(self):
        dataset = xr.Dataset({"table": ("x", ["abcdef0123456789.parquet"])})
        assert blob_cache_dir_hints(dataset) == ()
        record_blob_cache_dir(dataset, "/ws/cachedir")
        assert blob_cache_dir_hints(dataset) == ("/ws/cachedir",)

    def test_no_hint_for_a_dataset_collected_before_the_attribute_existed(self):
        assert blob_cache_dir_hints(xr.Dataset()) == ()
        assert blob_cache_dir_hints(None) == ()

    def test_hint_survives_a_slice_and_a_pickle_round_trip(self):
        """It has to reach render: results are sliced per pane and pickled by
        ``save_result``, and both must carry the attribute across."""
        dataset = xr.Dataset({"v": ("x", [1.0, 2.0])}, coords={"x": [0, 1]})
        record_blob_cache_dir(dataset, "/ws/cachedir")
        assert blob_cache_dir_hints(dataset.sel(x=0)) == ("/ws/cachedir",)
        assert blob_cache_dir_hints(pickle.loads(pickle.dumps(dataset))) == ("/ws/cachedir",)


class TestFormatTableIsTheSingleSourceOfTruth:
    """``blob_name``'s pattern, the suffix prefilter and ``load_blob``'s dispatch
    all derive from ``_BLOB_FORMATS``, so a format cannot be half-added — which is
    what lets ``load_blob`` be total instead of guarded by an unreachable raise."""

    def test_every_format_in_the_table_is_accepted_as_a_name(self):
        for fmt in _BLOB_FORMATS:
            name = f"abcdef0123456789{fmt.suffix}"
            assert blob_name(name) == name, f"{fmt.suffix} is in the table but not the pattern"

    def test_no_suffix_shadows_a_longer_one(self):
        """``.da.nc`` must be matched before ``.nc``, or a DataArray blob loads
        back as a single-variable Dataset."""
        for i, fmt in enumerate(_BLOB_FORMATS):
            for later in _BLOB_FORMATS[i + 1 :]:
                assert not later.suffix.endswith(fmt.suffix), (
                    f"{later.suffix} is shadowed by the earlier {fmt.suffix}"
                )

    def test_dataarray_takes_the_da_nc_branch_not_the_nc_one(self, tmp_path):
        da = xr.DataArray([1.0, 2.0], dims=["x"], name="metric")
        loaded = load_blob(materialize_blob(da, tmp_path), tmp_path)
        assert isinstance(loaded, xr.DataArray)

    def test_rejection_message_lists_every_known_suffix(self, tmp_path):
        with pytest.raises(ValueError) as excinfo:
            resolve_blob("results.csv", tmp_path)
        for fmt in _BLOB_FORMATS:
            assert fmt.suffix in str(excinfo.value)


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


class TestRenderFromAnotherWorkingDirectory(unittest.TestCase):
    """The other half of portability: the *reader* moves and the cache dir does not.

    ``bencher <result.pkl> <out_dir>`` is the documented collect/render split, and
    it runs in a fresh process whose working directory is whatever the user
    invoked it from.  A bare-name cell resolves against the reader's own
    ``./cachedir``, so without the collect-time cache dir recorded on the result,
    every cell of a report rendered from anywhere but the sweep's own directory
    becomes a "could not be loaded" placeholder — the same loss as a moved cache,
    along a different axis.  Media cells (``gen_path`` returns absolute paths) do
    not have this failure mode, so a blob cell must not either.
    """

    def test_every_cell_renders_from_a_foreign_working_directory(self):
        workspace = Path(self.enterContext(_tmpdir()))
        elsewhere = Path(self.enterContext(_tmpdir()))
        result_pkl = elsewhere / "result.pkl"

        with pytest.MonkeyPatch.context() as patch:
            patch.chdir(workspace)
            worker = RelocatedOverTimeSweep()
            worker.run_id = 0
            run_cfg = bn.BenchRunCfg()
            run_cfg.repeats = 1
            run_cfg.auto_plot = False
            run_cfg.clear_cache = True
            result = bn.Bench("test_blob_foreign_cwd", worker).plot_sweep(
                "foreign_cwd", input_vars=[], result_vars=["table"], run_cfg=run_cfg
            )
            cell = result.to_dataset()["table"].values.flat[0]
            self.assertEqual(cell, Path(cell).name, "precondition: the cell is a bare name")
            bn.save_result(result, result_pkl)

        self.assertTrue(
            (workspace / "cachedir" / "blobs").is_dir(),
            "precondition: the cache dir stayed where the sweep wrote it",
        )
        with pytest.MonkeyPatch.context() as patch:
            patch.chdir(elsewhere)
            self.assertFalse(Path("cachedir").exists(), "precondition: no cachedir at the reader")
            loaded = bn.load_result(result_pkl)
            rendered = [
                str(pane.object)
                for pane in loaded.to(bn.DataSetResult).select(pn.pane.Markdown)
                if str(pane.object).startswith("run=")
            ]
        self.assertEqual(rendered, ["run=0 scale=1"])


def _tmpdir():
    """A TemporaryDirectory as a context manager, for ``enterContext``."""
    import tempfile

    return tempfile.TemporaryDirectory()
