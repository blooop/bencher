"""Tests for netCDF-backed history_dir in load_history_cache."""

import tempfile
from pathlib import Path

import numpy as np
import xarray as xr

from bencher.result_collector import ResultCollector


def _make_dataset(over_time_label: str, num_samples: int = 3) -> xr.Dataset:
    """Create a minimal over_time dataset for testing."""
    return xr.Dataset(
        data_vars={
            "total_ms": (
                ["num_samples", "over_time"],
                np.random.rand(num_samples, 1),
            ),
        },
        coords={
            "num_samples": np.arange(num_samples),
            "over_time": np.array([over_time_label], dtype=object),
        },
    )


def _over_time_labels(ds: xr.Dataset) -> list[str]:
    """Extract over_time labels as decoded strings (bytes → str)."""
    return [v.decode() if isinstance(v, bytes) else str(v) for v in ds.coords["over_time"].values]


class TestHistoryDirNetCDF:
    """Tests for the netCDF history_dir backend."""

    def test_creates_nc_file(self, tmp_path):
        """First run creates a .nc file in history_dir."""
        collector = ResultCollector()
        ds = _make_dataset("2024-01-01 10:00 abc12345")
        bench_hash = "testhash123"

        result = collector.load_history_cache(
            ds, bench_hash, clear_history=False, history_dir=str(tmp_path)
        )

        nc_file = tmp_path / f"{bench_hash}.nc"
        assert nc_file.exists()
        assert "over_time" in result.dims
        assert result.sizes["over_time"] == 1

    def test_accumulates_over_runs(self, tmp_path):
        """Second run concatenates with existing history."""
        collector = ResultCollector()
        bench_hash = "testhash123"

        ds1 = _make_dataset("2024-01-01 10:00 abc12345")
        collector.load_history_cache(
            ds1, bench_hash, clear_history=False, history_dir=str(tmp_path)
        )

        ds2 = _make_dataset("2024-01-02 10:00 def67890")
        result = collector.load_history_cache(
            ds2, bench_hash, clear_history=False, history_dir=str(tmp_path)
        )

        assert result.sizes["over_time"] == 2
        labels = _over_time_labels(result)
        assert "2024-01-01 10:00 abc12345" in labels
        assert "2024-01-02 10:00 def67890" in labels

    def test_max_time_events_trims(self, tmp_path):
        """max_time_events keeps only the most recent entries."""
        collector = ResultCollector()
        bench_hash = "testhash123"

        # Accumulate 3 runs
        for i in range(3):
            ds = _make_dataset(f"run_{i}")
            collector.load_history_cache(
                ds, bench_hash, clear_history=False, history_dir=str(tmp_path)
            )

        # Now run with max_time_events=2
        ds = _make_dataset("run_3")
        result = collector.load_history_cache(
            ds,
            bench_hash,
            clear_history=False,
            max_time_events=2,
            history_dir=str(tmp_path),
        )

        assert result.sizes["over_time"] == 2
        labels = _over_time_labels(result)
        # Should keep only the last 2
        assert "run_3" in labels

    def test_clear_history_removes_file(self, tmp_path):
        """clear_history=True removes the .nc file."""
        collector = ResultCollector()
        bench_hash = "testhash123"

        ds = _make_dataset("run_0")
        collector.load_history_cache(ds, bench_hash, clear_history=False, history_dir=str(tmp_path))

        nc_file = tmp_path / f"{bench_hash}.nc"
        assert nc_file.exists()

        ds2 = _make_dataset("run_1")
        result = collector.load_history_cache(
            ds2, bench_hash, clear_history=True, history_dir=str(tmp_path)
        )

        # Should have only the current run (history was cleared)
        assert result.sizes["over_time"] == 1
        labels = _over_time_labels(result)
        assert "run_1" in labels

    def test_history_dir_none_uses_diskcache(self, tmp_path):
        """When history_dir is None, falls back to diskcache."""
        collector = ResultCollector()
        bench_hash = "testhash_diskcache"

        ds = _make_dataset("run_0")
        result = collector.load_history_cache(ds, bench_hash, clear_history=True, history_dir=None)

        # No .nc file should be created in tmp_path
        assert not list(tmp_path.glob("*.nc"))
        assert "over_time" in result.dims

    def test_string_roundtrip(self, tmp_path):
        """String coordinates survive netCDF roundtrip after concat."""
        collector = ResultCollector()
        bench_hash = "testhash_string"

        ds1 = _make_dataset("v0.1.0")
        collector.load_history_cache(
            ds1, bench_hash, clear_history=False, history_dir=str(tmp_path)
        )

        ds2 = _make_dataset("v0.2.0")
        result = collector.load_history_cache(
            ds2, bench_hash, clear_history=False, history_dir=str(tmp_path)
        )

        # Verify the file can be re-read
        nc_file = tmp_path / f"{bench_hash}.nc"
        reloaded = xr.open_dataset(nc_file)
        assert reloaded.sizes["over_time"] == 2
        reloaded.close()

    def test_creates_directory_if_missing(self):
        """history_dir is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as base:
            history_dir = Path(base) / "nested" / "history"
            collector = ResultCollector()
            ds = _make_dataset("run_0")

            collector.load_history_cache(
                ds, "hash123", clear_history=False, history_dir=str(history_dir)
            )

            assert (history_dir / "hash123.nc").exists()
