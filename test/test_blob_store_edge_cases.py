"""Edge cases of blob serialization, loading, and reachability classification.

Complements ``test_blob_store.py`` (the happy-path round trips) and the blob-GC
tests in ``test_cache_management.py`` (the reachability shapes) by pushing on the
boundaries where a wrong answer is silent rather than loud:

* **Sentinels that look like data.** A ``ResultDataSet`` cell can hold the string
  ``"NAN"``, a legacy ``-1`` index, or a float ``NaN``. None of them is a blob
  reference, and none is a filename. Misclassifying one either strands a live blob
  or, worse, protects nothing and deletes it. This class of bug is easy to write
  and invisible in normal use — a scan that treats ``"NAN"`` as a reference simply
  protects one blob too few, silently.
* **Payloads the structured formats cannot hold.** The contract is that anything
  inside "any picklable object" round-trips *exactly*; the dtype whitelist and the
  fallbacks exist to keep that promise, so the interesting cases are the ones that
  fall between formats.
* **Files that are not blobs.** Everything in ``blobs/`` that is not a blob must be
  left strictly alone, because it may belong to a writer running right now.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from diskcache import Cache

from bencher import cache_management
from bencher.blob_store import load_blob, materialize_blob
from bencher.cache_management import blob_reachability, clean_orphaned_blobs
from bencher.variables.results import ResultDataSet, result_is_missing


@pytest.fixture(autouse=True)
def _stamp_cache_version(tmp_path):
    """Reachability aborts on a missing/stale CACHE_VERSION stamp; real cachedirs
    get theirs from ensure_cache_version, so stamp the test dirs up front."""
    (tmp_path / "CACHE_VERSION").write_text(cache_management.CACHE_VERSION)



def blob_basename(path: str) -> str:
    """Basename of *path*, which is the identity the reachability scan matches on."""
    return Path(path).name


def store_dataset(cachedir, cells, dtype=object, cache_name="history"):
    """Store a history-shaped record whose ``table`` cells are *cells*."""
    arr = np.array(cells, dtype=dtype)
    ds = xr.Dataset({"table": (("over_time",), arr)}, coords={"over_time": np.arange(len(cells))})
    with Cache(str(cachedir / cache_name)) as cache:
        cache["record"] = {"format": 1, "dataset": ds, "columns": {}, "retired": {}}


class TestSentinelsAreNotReferences:
    """Missing-value sentinels must never be mistaken for blob paths.

    Both generations of sentinel coexist permanently in a mixed ``over_time``
    history, so the scan meets them routinely.
    """

    @pytest.mark.parametrize(
        "sentinel",
        ["NAN", "nan", "", "-1", "None", "null"],
        ids=["NAN", "lower-nan", "empty", "str-minus-1", "None", "null"],
    )
    def test_string_sentinels_contribute_no_reference(self, tmp_path, sentinel):
        store_dataset(tmp_path, [sentinel])
        assert blob_reachability(str(tmp_path)).names == frozenset()

    def test_legacy_int_and_float_cells_contribute_no_reference(self, tmp_path):
        """Pre-plan-22 cells are ``-1``/index ints, and an over_time concat can
        promote them to float. Numeric dtypes cannot name a blob."""
        store_dataset(tmp_path, [-1, 0, 3], dtype=np.int64)
        assert blob_reachability(str(tmp_path)).names == frozenset()

        store_dataset(tmp_path, [-1.0, np.nan, 2.0], dtype=np.float64)
        assert blob_reachability(str(tmp_path)).names == frozenset()

    def test_none_cells_contribute_no_reference(self, tmp_path):
        store_dataset(tmp_path, [None, None])
        assert blob_reachability(str(tmp_path)).names == frozenset()

    def test_a_sentinel_next_to_a_real_path_does_not_hide_it(self, tmp_path):
        """The mixed-history shape: the real reference must still be found, and the
        sentinel must not add a bogus name."""
        real = materialize_blob(pd.DataFrame({"v": [1.0]}), tmp_path)
        store_dataset(tmp_path, ["NAN", real, -1])

        names = blob_reachability(str(tmp_path)).names
        assert names == frozenset({blob_basename(real)})

        orphans, _ = clean_orphaned_blobs(str(tmp_path), dry_run=False)
        assert orphans == []

    def test_sentinel_semantics_match_the_result_variable_oracle(self):
        """Guard on the assumption above: these values really are the sentinels the
        result layer calls missing, so this suite tests the right strings."""
        rv = ResultDataSet()
        for missing in ("NAN", -1, -1.0, float("nan"), None):
            assert result_is_missing(rv, missing)
        assert not result_is_missing(rv, "cachedir/blobs/abcdef0123456789.parquet")


class TestPathsThatAreNotBlobs:
    """Strings that resemble a path but do not name a blob."""

    @pytest.mark.parametrize(
        "value",
        [
            "cachedir/img/plot/key/plot.png",  # a media path
            "cachedir/blobs/not-hex.parquet",  # right place, wrong stem
            "cachedir/blobs/ABCDEF0123456789.parquet",  # uppercase hex
            "cachedir/blobs/abcdef0123456789.txt",  # unknown extension
            "cachedir/blobs/abcdef0123456789",  # no extension
            "/etc/passwd",
            "abcdef0123456789.parquet.bak",
            "some prose mentioning .parquet in passing",
        ],
    )
    def test_non_blob_strings_are_not_references(self, tmp_path, value):
        store_dataset(tmp_path, [value])
        assert blob_reachability(str(tmp_path)).names == frozenset()

    def test_a_blob_name_is_recognised_from_any_directory(self, tmp_path):
        """Matching is by basename so a stored absolute path from a moved cachedir
        still protects its payload."""
        store_dataset(tmp_path, ["/somewhere/else/entirely/abcdef0123456789.parquet"])
        assert blob_reachability(str(tmp_path)).names == frozenset({"abcdef0123456789.parquet"})

    @pytest.mark.parametrize("ext", [".parquet", ".nc", ".da.nc", ".bin", ".pkl"])
    def test_every_emitted_extension_is_recognised(self, tmp_path, ext):
        """A format the store can write but the scan cannot recognise would be
        deleted while live — the whitelist must cover every emitted suffix."""
        store_dataset(tmp_path, [f"cachedir/blobs/abcdef0123456789{ext}"])
        assert blob_reachability(str(tmp_path)).names == frozenset({f"abcdef0123456789{ext}"})


class TestSerializationBoundaries:
    """Payloads that sit between the structured formats and the pickle fallback."""

    def test_empty_dataframe_round_trips(self, tmp_path):
        payload = pd.DataFrame({"v": pd.Series([], dtype="float64")})
        loaded = load_blob(materialize_blob(payload, tmp_path), tmp_path)
        pd.testing.assert_frame_equal(loaded, payload)

    def test_dataframe_with_integer_column_names_round_trips(self, tmp_path):
        payload = pd.DataFrame({0: [1.0, 2.0], 1: [3.0, 4.0]})
        loaded = load_blob(materialize_blob(payload, tmp_path), tmp_path)
        pd.testing.assert_frame_equal(loaded, payload)

    def test_dataframe_with_duplicate_column_names_round_trips(self, tmp_path):
        """Parquet cannot represent duplicate names; the fallback must catch it
        rather than let the sweep die."""
        payload = pd.DataFrame([[1.0, 2.0]], columns=["v", "v"])
        loaded = load_blob(materialize_blob(payload, tmp_path), tmp_path)
        pd.testing.assert_frame_equal(loaded, payload)

    def test_dataframe_with_nan_and_inf_round_trips(self, tmp_path):
        payload = pd.DataFrame({"v": [np.nan, np.inf, -np.inf, 0.0]})
        loaded = load_blob(materialize_blob(payload, tmp_path), tmp_path)
        pd.testing.assert_frame_equal(loaded, payload)

    def test_dataframe_with_a_datetime_index_round_trips(self, tmp_path):
        payload = pd.DataFrame(
            {"v": [1.0, 2.0]}, index=pd.to_datetime(["2024-01-01", "2024-01-02"])
        )
        loaded = load_blob(materialize_blob(payload, tmp_path), tmp_path)
        pd.testing.assert_frame_equal(loaded, payload)

    def test_dataset_with_a_zero_length_dimension_round_trips(self, tmp_path):
        payload = xr.Dataset({"v": ("x", np.array([], dtype="float64"))})
        xr.testing.assert_identical(
            load_blob(materialize_blob(payload, tmp_path), tmp_path), payload
        )

    def test_dataset_mixing_safe_and_unsafe_dtypes_round_trips_exactly(self, tmp_path):
        """One unsafe variable must divert the *whole* payload to pickle: writing
        part as netCDF would silently narrow it."""
        payload = xr.Dataset(
            {
                "safe": ("x", np.arange(3, dtype="float64")),
                "unsafe": ("x", np.arange(3, dtype="int64")),
            }
        )
        path = materialize_blob(payload, tmp_path)
        assert path.endswith(".pkl")
        loaded = load_blob(path, tmp_path)
        xr.testing.assert_identical(loaded, payload)
        assert loaded["unsafe"].dtype == np.dtype("int64"), "dtype was narrowed"

    def test_dataset_attrs_survive(self, tmp_path):
        payload = xr.Dataset({"v": ("x", np.arange(3, dtype="float64"))})
        payload.attrs["units"] = "metres"
        payload["v"].attrs["long_name"] = "value"
        loaded = load_blob(materialize_blob(payload, tmp_path), tmp_path)
        assert loaded.attrs.get("units") == "metres"
        assert loaded["v"].attrs.get("long_name") == "value"

    def test_bool_dataset_keeps_its_dtype(self, tmp_path):
        """bool is on the netCDF3 whitelist, so it must survive as bool rather than
        come back as int8."""
        payload = xr.Dataset({"v": ("x", np.array([True, False, True]))})
        loaded = load_blob(materialize_blob(payload, tmp_path), tmp_path)
        assert loaded["v"].dtype == np.dtype("bool")
        xr.testing.assert_identical(loaded, payload)

    def test_empty_bytes_round_trip(self, tmp_path):
        path = materialize_blob(b"", tmp_path)
        assert path.endswith(".bin")
        assert load_blob(path, tmp_path) == b""

    def test_nested_result_dataset_wrapper_round_trips(self, tmp_path):
        """A per-sample ``container=`` travels as a pickled wrapper, so the wrapper
        itself must survive as a payload."""
        inner = pd.DataFrame({"v": [1.0, 2.0]})
        wrapper = ResultDataSet(inner, container=len)
        path = materialize_blob(wrapper, tmp_path)
        assert path.endswith(".pkl")
        loaded = load_blob(path, tmp_path)
        assert isinstance(loaded, ResultDataSet)
        pd.testing.assert_frame_equal(loaded.obj, inner)
        assert loaded.container is len

    def test_distinct_payloads_of_different_types_do_not_share_a_name(self, tmp_path):
        """Content addressing is over the serialized bytes, and the extension
        distinguishes formats, so unrelated payloads must not collide."""
        paths = {
            materialize_blob(pd.DataFrame({"v": [1.0]}), tmp_path),
            materialize_blob(xr.Dataset({"v": ("x", [1.0])}), tmp_path),
            materialize_blob(b"\x01\x02", tmp_path),
            materialize_blob({"a": 1}, tmp_path),
        }
        assert len(paths) == 4


class TestLoadBlobFailureModes:
    """A corrupt or truncated blob must fail catchably; the render path turns any
    exception into a placeholder, but it must not hang or return junk."""

    @pytest.mark.parametrize("ext", [".parquet", ".nc", ".da.nc", ".pkl"])
    def test_empty_file_raises_rather_than_returning_junk(self, tmp_path, ext):
        blobs = tmp_path / "blobs"
        blobs.mkdir()
        bad = blobs / f"abcdef0123456789{ext}"
        bad.write_bytes(b"")
        with pytest.raises(Exception):  # noqa: B017 - any failure is acceptable here
            load_blob(bad, tmp_path)

    @pytest.mark.parametrize("ext", [".parquet", ".nc", ".pkl"])
    def test_truncated_file_raises(self, tmp_path, ext):
        good = materialize_blob(
            pd.DataFrame({"v": [1.0, 2.0]}) if ext == ".parquet" else {"a": 1}, tmp_path
        )
        data = (tmp_path / "blobs" / blob_basename(good)).read_bytes()
        bad = tmp_path / "blobs" / f"abcdef0123456789{ext}"
        bad.write_bytes(data[: max(1, len(data) // 2)])
        with pytest.raises(Exception):  # noqa: B017
            load_blob(bad, tmp_path)

    def test_empty_bin_is_valid_and_not_an_error(self, tmp_path):
        """Raw bytes have no header, so an empty ``.bin`` is legitimately empty."""
        blobs = tmp_path / "blobs"
        blobs.mkdir()
        blob = blobs / "abcdef0123456789.bin"
        blob.write_bytes(b"")
        assert load_blob(blob, tmp_path) == b""

    def test_missing_file_raises_filenotfound(self, tmp_path):
        # Explicit cache dir: with the default the first candidate is the cwd's
        # own ``cachedir``, which would make this assertion depend on where the
        # suite runs from.
        with pytest.raises((FileNotFoundError, OSError)):
            load_blob(tmp_path / "blobs" / "abcdef0123456789.parquet", tmp_path)

    @pytest.mark.parametrize("name", ["x.txt", "x", "x.parquet.gz", "x.nc.old"])
    def test_non_blob_name_raises_valueerror_not_something_vaguer(self, tmp_path, name):
        # Rejected on the name, before any file is opened, so a stray file that
        # happens to sit in blobs/ can never be loaded as a blob.
        blobs = tmp_path / "blobs"
        blobs.mkdir()
        (blobs / name).write_bytes(b"data")
        with pytest.raises(ValueError, match="is not a blob reference"):
            load_blob(blobs / name, tmp_path)


class TestGCLeavesNonBlobsAlone:
    """Everything in ``blobs/`` that is not a blob may belong to a live writer."""

    def test_temp_files_subdirectories_and_strays_are_untouched(self, tmp_path):
        blobs = tmp_path / "blobs"
        blobs.mkdir()
        keep = {
            blobs / "abcdef0123456789.parquet.tmp-deadbeef": b"in-flight write",
            blobs / "README": b"notes",
            blobs / "not-hex.parquet": b"not ours",
            blobs / "ABCDEF0123456789.parquet": b"uppercase stem",
        }
        for path, data in keep.items():
            path.write_bytes(data)
        (blobs / "subdir").mkdir()
        (blobs / "subdir" / "abcdef0123456789.parquet").write_bytes(b"nested")
        collectable = blobs / "0123456789abcdef.parquet"
        collectable.write_bytes(b"garbage")

        orphans, _ = clean_orphaned_blobs(str(tmp_path), dry_run=False)

        assert orphans == [str(collectable)]
        for path in keep:
            assert path.exists(), f"{path.name} should not have been touched"
        assert (blobs / "subdir" / "abcdef0123456789.parquet").exists()

    def test_missing_blobs_directory_is_a_noop(self, tmp_path):
        assert clean_orphaned_blobs(str(tmp_path), dry_run=False) == ([], 0)

    def test_blobs_path_that_is_a_file_is_a_noop(self, tmp_path):
        """A stray ``blobs`` *file* must not crash the walk."""
        (tmp_path / "blobs").write_bytes(b"not a directory")
        assert clean_orphaned_blobs(str(tmp_path), dry_run=False) == ([], 0)


class TestReachabilityWalkRobustness:
    """The walk descends arbitrary pickled objects, so it must not hang or explode."""

    def test_self_referential_structure_terminates_and_still_finds_the_reference(self, tmp_path):
        """A cycle must not loop forever.

        Note what actually provides termination here: the **depth bound**, not the
        ``seen`` set — mutation-testing this file showed the cycle case still passes
        with ``seen`` removed entirely. ``seen`` is what keeps the walk from
        exploding on shared substructure, which the next test covers; this one pins
        that a cycle is survivable and does not swallow the real reference.
        """
        cyclic: dict = {"name": "cachedir/blobs/abcdef0123456789.parquet"}
        cyclic["self"] = cyclic
        with Cache(str(tmp_path / "history")) as cache:
            cache["record"] = cyclic

        names = blob_reachability(str(tmp_path)).names
        assert names == frozenset({"abcdef0123456789.parquet"})

    def test_shared_substructure_is_visited_once_not_exponentially(self, tmp_path):
        """The real job of the ``seen`` set.

        A DAG where every node fans out to the *same* child is linear to walk if
        visited nodes are remembered and exponential if they are not. With fan-out 4
        inside the depth bound that is a handful of visits versus thousands, so
        counting visits detects a missing ``seen`` set — which a cycle test cannot.
        """
        leaf = "cachedir/blobs/abcdef0123456789.parquet"
        node: object = {"cell": leaf}
        for _ in range(6):
            node = {f"child{i}": node for i in range(4)}
        with Cache(str(tmp_path / "history")) as cache:
            cache["record"] = node

        calls = 0
        # pylint: disable=protected-access  # the walk's internals are the subject here
        real_children = cache_management._blob_reference_children

        def counting_children(value):
            nonlocal calls
            calls += 1
            return real_children(value)

        with mock.patch.object(cache_management, "_blob_reference_children", counting_children):
            names = blob_reachability(str(tmp_path)).names

        assert names == frozenset({"abcdef0123456789.parquet"})
        # Linear in unique nodes (~8) rather than 4**6 = 4096. The bound is loose so
        # it cannot fail spuriously, but it is far below any exponential walk.
        assert calls < 100, f"walk visited {calls} nodes — shared substructure re-walked"

    def test_reference_nested_deeper_than_the_walk_limit_is_not_found(self, tmp_path):
        """**Pinned limitation.** The walk is depth-bounded, so a pathologically
        nested reference is missed and its blob looks like garbage. Real roots are
        shallow (record -> Dataset), so this documents the bound rather than
        endorsing it: if a future root nests deeper, this test is the alarm."""
        deep: object = "cachedir/blobs/abcdef0123456789.parquet"
        for _ in range(20):
            deep = {"next": deep}
        with Cache(str(tmp_path / "history")) as cache:
            cache["record"] = deep

        assert blob_reachability(str(tmp_path)).names == frozenset()

    def test_reference_inside_a_list_tuple_and_set_is_found(self, tmp_path):
        with Cache(str(tmp_path / "history")) as cache:
            cache["record"] = {
                "list": ["cachedir/blobs/1111111111111111.parquet"],
                "tuple": ("cachedir/blobs/2222222222222222.nc",),
                "set": {"cachedir/blobs/3333333333333333.pkl"},
            }
        assert blob_reachability(str(tmp_path)).names == frozenset(
            {
                "1111111111111111.parquet",
                "2222222222222222.nc",
                "3333333333333333.pkl",
            }
        )

    def test_reference_in_a_dataset_coordinate_is_found(self, tmp_path):
        """Coordinates are scanned as well as data variables."""
        ds = xr.Dataset(
            {"v": ("k", np.array([1.0]))},
            coords={"k": np.array(["cachedir/blobs/abcdef0123456789.pkl"], dtype=object)},
        )
        with Cache(str(tmp_path / "history")) as cache:
            cache["record"] = {"dataset": ds}
        assert blob_reachability(str(tmp_path)).names == frozenset({"abcdef0123456789.pkl"})
