"""Tests for the content-addressed blob store (plan 22, design D1, test item 1)."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from bencher.blob_store import load_blob, materialize_blob


@dataclass
class ArbitraryPayload:
    """A picklable payload with no dedicated blob format."""

    name: str
    value: float


def _blob_files(cache_dir: Path) -> list[Path]:
    return sorted((cache_dir / "blobs").glob("*"))


class TestMaterializeRoundTrip:
    def test_dataframe_parquet(self, tmp_path):
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        path = materialize_blob(df, tmp_path)
        assert isinstance(path, str)
        assert path.endswith(".parquet")
        assert Path(path).parent == tmp_path / "blobs"
        pd.testing.assert_frame_equal(load_blob(path), df)

    def test_xarray_dataset_netcdf(self, tmp_path):
        # int32 coords: int64 is not netCDF3-safe and would take the pickle path.
        ds = xr.Dataset(
            {"speed": ("x", [1.0, 2.0, 3.0])},
            coords={"x": np.array([10, 20, 30], dtype="int32")},
        )
        path = materialize_blob(ds, tmp_path)
        assert path.endswith(".nc")
        loaded = load_blob(path)
        xr.testing.assert_identical(loaded, ds)

    def test_xarray_dataarray_netcdf(self, tmp_path):
        da = xr.DataArray([1.0, 2.0], dims=["x"], name="metric")
        path = materialize_blob(da, tmp_path)
        assert path.endswith(".da.nc")
        loaded = load_blob(path)
        # F4: DataArrays keep their identity — loaded back as a DataArray
        # with .name preserved, not as a single-variable Dataset.
        assert isinstance(loaded, xr.DataArray)
        assert loaded.name == "metric"
        xr.testing.assert_identical(loaded, da)

    def test_xarray_dataarray_unnamed_round_trips(self, tmp_path):
        da = xr.DataArray([3.5, 4.5], dims=["x"])
        path = materialize_blob(da, tmp_path)
        assert path.endswith(".da.nc")
        loaded = load_blob(path)
        assert isinstance(loaded, xr.DataArray)
        assert loaded.name is None
        xr.testing.assert_identical(loaded, da)

    def test_bytes_bin(self, tmp_path):
        payload = b"\x00\x01raw bytes\xff"
        path = materialize_blob(payload, tmp_path)
        assert path.endswith(".bin")
        assert load_blob(path) == payload

    def test_picklable_dataclass_pkl(self, tmp_path):
        obj = ArbitraryPayload(name="test", value=1.5)
        path = materialize_blob(obj, tmp_path)
        assert path.endswith(".pkl")
        assert load_blob(path) == obj

    def test_netcdf_blob_is_rereadable(self, tmp_path):
        """load_blob must close the netCDF handle so the file can be read again."""
        ds = xr.Dataset({"a": ("x", [1.0])})
        path = materialize_blob(ds, tmp_path)
        first = load_blob(path)
        second = load_blob(path)
        xr.testing.assert_identical(first, second)


class TestContentAddressing:
    def test_identical_payloads_identical_paths(self, tmp_path):
        df = pd.DataFrame({"a": [1, 2]})
        path1 = materialize_blob(df, tmp_path)
        path2 = materialize_blob(df.copy(), tmp_path)
        assert path1 == path2
        assert _blob_files(tmp_path) == [Path(path1)]

    def test_file_written_once(self, tmp_path):
        payload = b"same content"
        path1 = materialize_blob(payload, tmp_path)
        mtime = Path(path1).stat().st_mtime_ns
        path2 = materialize_blob(payload, tmp_path)
        assert path1 == path2
        assert Path(path2).stat().st_mtime_ns == mtime  # not rewritten

    def test_differing_payloads_differing_paths(self, tmp_path):
        path1 = materialize_blob(b"payload one", tmp_path)
        path2 = materialize_blob(b"payload two", tmp_path)
        assert path1 != path2
        assert len(_blob_files(tmp_path)) == 2

    def test_filename_is_16_hex_chars(self, tmp_path):
        path = materialize_blob(b"abc", tmp_path)
        stem = Path(path).stem
        assert len(stem) == 16
        int(stem, 16)  # raises ValueError if not hex

    def test_no_leftover_temp_files(self, tmp_path):
        materialize_blob(b"abc", tmp_path)
        assert not list((tmp_path / "blobs").glob("*.tmp*"))


class TestStringPayloadPickled:
    """F3: no path passthrough — a str/Path payload is an ordinary pickled object."""

    def test_existing_file_str_is_pickled(self, tmp_path):
        existing = tmp_path / "already_materialized.rrd"
        existing.write_bytes(b"data")
        path = materialize_blob(str(existing), tmp_path)
        assert path != str(existing)
        assert path.endswith(".pkl")
        assert Path(path).parent == tmp_path / "blobs"
        loaded = load_blob(path)
        assert isinstance(loaded, str)
        assert loaded == str(existing)

    def test_existing_pathlib_path_is_pickled(self, tmp_path):
        existing = tmp_path / "file.nc"
        existing.write_bytes(b"data")
        path = materialize_blob(existing, tmp_path)
        assert path.endswith(".pkl")
        assert load_blob(path) == existing

    def test_nonexistent_path_string_is_pickled(self, tmp_path):
        """A str that is not an existing file is an ordinary picklable payload."""
        path = materialize_blob("/no/such/file.parquet", tmp_path)
        assert path.endswith(".pkl")
        assert load_blob(path) == "/no/such/file.parquet"


class TestSerializationFallbacks:
    """F1/F2: structured-format failures fall back to pickle, never raise."""

    def test_nested_object_dataframe_pickled(self, tmp_path):
        """pyarrow raises ArrowInvalid on nested-object columns; pickle round-trips."""
        df = pd.DataFrame({"a": [{"nested": 1}, [1, 2]]})
        path = materialize_blob(df, tmp_path)
        assert path.endswith(".pkl")
        pd.testing.assert_frame_equal(load_blob(path), df)

    def test_plain_float_dataframe_still_parquet(self, tmp_path):
        df = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
        path = materialize_blob(df, tmp_path)
        assert path.endswith(".parquet")
        pd.testing.assert_frame_equal(load_blob(path), df)

    def test_int64_dataset_round_trips_exactly_via_pickle(self, tmp_path):
        """scipy netCDF3 silently narrows int64→int32 (or raises); pickle preserves it."""
        ds = xr.Dataset(
            {"count": ("x", np.array([2**40, 1], dtype="int64"))},
            coords={"x": np.array([0, 1], dtype="int64")},
        )
        path = materialize_blob(ds, tmp_path)
        assert path.endswith(".pkl")
        loaded = load_blob(path)
        assert loaded["count"].dtype == np.dtype("int64")
        assert loaded["x"].dtype == np.dtype("int64")
        xr.testing.assert_identical(loaded, ds)

    def test_int64_coord_alone_forces_pickle(self, tmp_path):
        """Coords are checked as well as data vars (a python-int coord is int64)."""
        ds = xr.Dataset({"speed": ("x", [1.0, 2.0])}, coords={"x": [10, 20]})
        assert ds["x"].dtype == np.dtype("int64")
        path = materialize_blob(ds, tmp_path)
        assert path.endswith(".pkl")
        xr.testing.assert_identical(load_blob(path), ds)

    def test_str_coord_dataset_pickled(self, tmp_path):
        """netCDF3 loads <U coords back as object dtype, so they take the pickle path."""
        ds = xr.Dataset({"v": ("x", [1.0, 2.0])}, coords={"x": np.array(["a", "b"])})
        path = materialize_blob(ds, tmp_path)
        assert path.endswith(".pkl")
        loaded = load_blob(path)
        assert loaded["x"].dtype == ds["x"].dtype
        xr.testing.assert_identical(loaded, ds)

    def test_int64_dataarray_round_trips_via_pickle(self, tmp_path):
        da = xr.DataArray(np.array([-(2**35), 5], dtype="int64"), dims=["x"], name="metric")
        path = materialize_blob(da, tmp_path)
        assert path.endswith(".pkl")
        loaded = load_blob(path)
        assert isinstance(loaded, xr.DataArray)
        assert loaded.dtype == np.dtype("int64")
        xr.testing.assert_identical(loaded, da)


class TestLoadBlobDispatch:
    def test_unknown_extension_raises(self, tmp_path):
        weird = tmp_path / "blob.xyz"
        weird.write_bytes(b"data")
        with pytest.raises(ValueError, match=r"unknown blob extension '\.xyz'"):
            load_blob(weird)

    def test_no_extension_raises(self, tmp_path):
        bare = tmp_path / "blob"
        bare.write_bytes(b"data")
        with pytest.raises(ValueError, match="unknown blob extension"):
            load_blob(bare)

    def test_accepts_str_and_path(self, tmp_path):
        path = materialize_blob(b"data", tmp_path)
        assert load_blob(path) == b"data"
        assert load_blob(Path(path)) == b"data"
