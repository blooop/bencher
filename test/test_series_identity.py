"""Plan 15 — a benchmark's trend must survive a rename, or say that it didn't.

The reset detector added by plan 09 was keyed on ``(bench_name, tag)`` — the two
fields whose change is the most common cause of a moved history key. The index
entry therefore moved together with the key it existed to watch, so a rename
missed on both sides and took the "first run ever" path: a silently orphaned
trend, no event, nothing to notice.

``series_id`` names the trend independently of what identifies the configuration,
which is what makes the two reasons a key can move distinguishable at all.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import unittest
import uuid

import numpy as np
import xarray as xr

import bencher as bn
from bencher.history import (
    HistoryResetError,
    default_series_id,
    last_seen_key,
    legacy_last_seen_key,
)
from bencher.result_collector import ResultCollector
from bencher.variables.results import ResultFloat


def _result_float(name: str) -> ResultFloat:
    rv = ResultFloat()
    rv.name = name
    return rv


def _run_ds(name: str, value: float, t: int) -> xr.Dataset:
    return xr.Dataset(
        {name: (("repeat", "over_time"), np.array([[value]], dtype=float))},
        coords={"repeat": [0], "over_time": [np.datetime64(f"2024-01-0{t}")]},
    )


class SeriesBase(unittest.TestCase):
    """Drives the collector directly against a throwaway cachedir."""

    def setUp(self) -> None:
        self._old_cwd = os.getcwd()
        self._tmp = tempfile.mkdtemp()
        os.chdir(self._tmp)
        self.collector = ResultCollector()
        self.summary = {"inputs": [], "consts": [], "results": [], "repeats": 1}

    def tearDown(self) -> None:
        self.collector.close_caches()
        os.chdir(self._old_cwd)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def load(self, key, t, *, bench_name, tag="t", series_id=None, summary=None, policy="warn"):
        rv = _result_float("a")
        return self.collector.load_history_cache(
            _run_ds("a", float(t), t),
            key,
            False,
            None,
            [rv],
            on_history_reset=policy,
            bench_name=bench_name,
            tag=tag,
            series_id=series_id,
            config_summary=self.summary if summary is None else summary,
        )


class TestDefaultsAreUnchanged(unittest.TestCase):
    """Phase 1's contract: declaring nothing changes nothing."""

    def test_series_defaults_to_bench_name_and_tag(self) -> None:
        cfg = bn.BenchCfg(bench_name="B", tag="t")
        self.assertIsNone(cfg.series_id)
        self.assertEqual(cfg.series, "B:t")
        self.assertEqual(cfg.series, default_series_id("B", "t"))

    def test_the_default_index_key_is_byte_identical_to_the_legacy_one(self) -> None:
        """Nothing moves on upgrade for a caller who declares no series_id."""
        self.assertEqual(last_seen_key(default_series_id("B", "t")), legacy_last_seen_key("B", "t"))

    def test_a_declared_series_id_replaces_the_default(self) -> None:
        cfg = bn.BenchCfg(bench_name="B", tag="t", series_id="latency")
        self.assertEqual(cfg.series, "latency")

    def test_explain_identity_names_series_id_as_excluded(self) -> None:
        """The pairing users need told: tag partitions storage, series_id names the
        trend. A field that is deliberately outside the hash is only useful if the
        surface that explains identity says so."""
        from bencher.example.benchmark_data import ExampleBenchCfg

        ident = bn.sweep_identity(
            worker=ExampleBenchCfg, input_vars=["theta"], result_vars=["out_sin"]
        )
        excluded = ident.explain().split("excluded on purpose")[1]
        self.assertIn("series_id", excluded)

    def test_series_id_never_reaches_the_hash(self) -> None:
        """It identifies a series, not a configuration; folding it in would re-key
        every existing cache and history on upgrade."""
        plain = bn.BenchCfg(bench_name="B", tag="t")
        declared = bn.BenchCfg(bench_name="B", tag="t", series_id="anything")
        other = bn.BenchCfg(bench_name="B", tag="t", series_id="something-else")
        for include_results in (True, False):
            self.assertEqual(
                plain.hash_persistent(True, include_results),
                declared.hash_persistent(True, include_results),
            )
            self.assertEqual(
                declared.hash_persistent(True, include_results),
                other.hash_persistent(True, include_results),
            )
        self.assertEqual(plain.hash_persistent(False), declared.hash_persistent(False))


class TestRenameIsAdopted(SeriesBase):
    """D2 — a key that moves with an unchanged declaration is a rename."""

    def _first_run(self, series_id):
        key_a = f"history-{uuid.uuid4()}"
        self.load(key_a, 1, bench_name="OldName", series_id=series_id)
        return key_a

    def test_a_renamed_bench_keeps_its_history(self) -> None:
        series = "latency"
        self._first_run(series)
        key_b = f"history-{uuid.uuid4()}"
        served = self.load(key_b, 2, bench_name="NewName", series_id=series)
        self.assertEqual(served.sizes["over_time"], 2, "history was not carried over")
        self.assertEqual(list(served["a"].values[0]), [1.0, 2.0])

    def test_a_changed_tag_keeps_its_history(self) -> None:
        """D3 — tag partitions storage; series_id names the trend."""
        series = "latency"
        self.load(f"history-{uuid.uuid4()}", 1, bench_name="B", tag="t1", series_id=series)
        served = self.load(f"history-{uuid.uuid4()}", 2, bench_name="B", tag="t2", series_id=series)
        self.assertEqual(served.sizes["over_time"], 2)

    def test_adoption_is_informational_not_lossy(self) -> None:
        """Nothing was lost, so on_history_reset='error' must not raise."""
        series = "latency"
        self._first_run(series)
        served = self.load(
            f"history-{uuid.uuid4()}", 2, bench_name="NewName", series_id=series, policy="error"
        )
        self.assertEqual(served.sizes["over_time"], 2)

    def test_adoption_logs_at_info_naming_both_keys(self) -> None:
        series = "latency"
        key_a = self._first_run(series)
        with self.assertLogs("bencher.history", level=logging.INFO) as logs:
            self.load(f"history-{uuid.uuid4()}", 2, bench_name="NewName", series_id=series)
        adopted = [line for line in logs.output if "adopted" in line]
        self.assertTrue(adopted, logs.output)
        self.assertTrue(any(key_a in line for line in adopted))

    def test_no_warning_is_emitted_for_a_rename(self) -> None:
        series = "latency"
        self._first_run(series)
        with self.assertNoLogs("bencher.history", level=logging.WARNING):
            self.load(f"history-{uuid.uuid4()}", 2, bench_name="NewName", series_id=series)

    def test_the_old_record_is_moved_not_duplicated(self) -> None:
        series = "latency"
        key_a = self._first_run(series)
        key_b = f"history-{uuid.uuid4()}"
        self.load(key_b, 2, bench_name="NewName", series_id=series)
        cache = self.collector.get_history_cache()
        self.assertNotIn(key_a, cache, "the adopted record was left behind under the old key")
        self.assertIn(key_b, cache)

    def test_three_consecutive_renames_keep_one_series(self) -> None:
        series = "latency"
        served = None
        for i, name in enumerate(("A", "B", "C", "D"), start=1):
            served = self.load(f"history-{uuid.uuid4()}", i, bench_name=name, series_id=series)
        self.assertEqual(served.sizes["over_time"], 4)
        self.assertEqual(list(served["a"].values[0]), [1.0, 2.0, 3.0, 4.0])


class TestGenuineChangeStillResets(SeriesBase):
    """The other half of D2: a changed declaration is not a rename."""

    def test_a_changed_declaration_reports_a_full_reset(self) -> None:
        series = "latency"
        self.load(f"history-{uuid.uuid4()}", 1, bench_name="B", series_id=series)
        changed = {**self.summary, "inputs": [("x", "FloatSweep", "ul")]}
        with self.assertLogs("bencher.history", level=logging.WARNING) as logs:
            served = self.load(
                f"history-{uuid.uuid4()}", 2, bench_name="B", series_id=series, summary=changed
            )
        self.assertTrue(any("orphaned under the old key" in line for line in logs.output))
        self.assertTrue(any("inputs changed" in line for line in logs.output))
        self.assertEqual(served.sizes["over_time"], 1, "a reset must start a fresh series")

    def test_error_policy_still_raises_on_a_genuine_reset(self) -> None:
        series = "latency"
        self.load(f"history-{uuid.uuid4()}", 1, bench_name="B", series_id=series)
        changed = {**self.summary, "repeats": 3}
        with self.assertRaises(HistoryResetError):
            self.load(
                f"history-{uuid.uuid4()}",
                2,
                bench_name="B",
                series_id=series,
                summary=changed,
                policy="error",
            )

    def test_a_reset_leaves_the_stored_record_untouched(self) -> None:
        """Plan 14's pre-persist guarantee: an erroring run advances nothing."""
        series = "latency"
        key_a = f"history-{uuid.uuid4()}"
        self.load(key_a, 1, bench_name="B", series_id=series)
        cache = self.collector.get_history_cache()
        before = cache[key_a]["dataset"].copy(deep=True)
        index_before = cache.get(last_seen_key(series))
        with self.assertRaises(HistoryResetError):
            self.load(
                f"history-{uuid.uuid4()}",
                2,
                bench_name="B",
                series_id=series,
                summary={**self.summary, "repeats": 9},
                policy="error",
            )
        xr.testing.assert_identical(before, cache[key_a]["dataset"])
        self.assertEqual(index_before, cache.get(last_seen_key(series)))

    def test_different_series_ids_do_not_see_each_other(self) -> None:
        self.load(f"history-{uuid.uuid4()}", 1, bench_name="B", series_id="one")
        with self.assertNoLogs("bencher.history", level=logging.WARNING):
            served = self.load(f"history-{uuid.uuid4()}", 2, bench_name="B", series_id="two")
        self.assertEqual(served.sizes["over_time"], 1)


class TestUpgradePath(SeriesBase):
    """D4 — the first run after upgrade must find its predecessor."""

    def test_a_legacy_index_entry_is_found_and_migrated(self) -> None:
        key_a = f"history-{uuid.uuid4()}"
        # A run from before series_id existed: the index lands under the legacy key,
        # which for an undeclared series is the same string.
        self.load(key_a, 1, bench_name="B", tag="t")
        cache = self.collector.get_history_cache()
        self.assertIn(legacy_last_seen_key("B", "t"), cache)

        # Now the same benchmark declares a series_id for the first time. Its index
        # entry does not exist under the new key yet.
        self.assertNotIn(last_seen_key("latency"), cache)
        served = self.load(key_a, 2, bench_name="B", tag="t", series_id="latency")
        self.assertEqual(served.sizes["over_time"], 2)
        self.assertIn(last_seen_key("latency"), cache, "the index was not migrated")

        # From here the legacy entry is read-only: it still records the pre-upgrade
        # run while only the series key advances. It is left in place rather than
        # deleted -- an undeclared run under the same name still reads that string
        # as its own series key -- so "read-only" is the contract to pin, and a
        # regression that wrote both would leave two live indices for one trend.
        self.load(key_a, 3, bench_name="B", tag="t", series_id="latency")
        self.assertEqual(cache[legacy_last_seen_key("B", "t")]["events"], 1)
        self.assertEqual(cache[last_seen_key("latency")]["events"], 3)

    def test_declare_the_series_before_renaming_then_the_rename_is_adopted(self) -> None:
        """The supported sequence, and the reason the order matters.

        Declaring ``series_id`` writes the index under the series key while the old
        ``bench_name`` is still in force; the rename then finds it. Doing both in
        one run cannot work — see the next test — so this ordering is the migration
        procedure, not an implementation detail.
        """
        key_a = f"history-{uuid.uuid4()}"
        self.load(key_a, 1, bench_name="OldName", tag="t", series_id="latency")
        served = self.load(
            f"history-{uuid.uuid4()}", 2, bench_name="NewName", tag="t", series_id="latency"
        )
        self.assertEqual(served.sizes["over_time"], 2)

    def test_renaming_and_declaring_in_one_run_cannot_find_the_old_entry(self) -> None:
        """The limit of the legacy fallback, pinned so it is not mistaken for a bug.

        The fallback key is ``(bench_name, tag)`` of the *current* run, and
        bench_name is precisely what moved, so the pre-series_id entry — written
        under the old name — is unreachable. Recovering it would need the old
        identity, which nothing records. Declare the series first (previous test).
        """
        self.load(f"history-{uuid.uuid4()}", 1, bench_name="OldName", tag="t")
        served = self.load(
            f"history-{uuid.uuid4()}", 2, bench_name="NewName", tag="t", series_id="latency"
        )
        self.assertEqual(served.sizes["over_time"], 1)

    def test_a_rename_without_a_declared_series_id_is_still_undetectable(self) -> None:
        """The honest limit of the design.

        Without a declared series_id the series *is* bench_name:tag, so a rename
        moves the index with the key exactly as before. This is the case series_id
        exists to let a user opt out of -- it cannot be fixed by default without
        guessing which of two benchmarks is the continuation of a third.
        """
        self.load(f"history-{uuid.uuid4()}", 1, bench_name="OldName", tag="t")
        with self.assertNoLogs("bencher.history", level=logging.WARNING):
            served = self.load(f"history-{uuid.uuid4()}", 2, bench_name="NewName", tag="t")
        self.assertEqual(served.sizes["over_time"], 1)


class TestPlotSweepSurface(unittest.TestCase):
    """The field is reachable from the public declaration surface."""

    def test_plot_sweep_accepts_series_id_and_stores_it(self) -> None:
        from bencher.example.benchmark_data import ExampleBenchCfg

        cfg = bn.BenchRunCfg()
        cfg.auto_plot = False
        cfg.cache_results = False
        cfg.cache_samples = False
        bench = ExampleBenchCfg().to_bench(cfg)
        try:
            res = bench.plot_sweep(
                input_vars=["theta"],
                result_vars=["out_sin"],
                series_id="latency",
                plot_callbacks=False,
            )
        finally:
            bench.close()
        self.assertEqual(res.bench_cfg.series_id, "latency")
        self.assertEqual(res.bench_cfg.series, "latency")

    def test_series_id_does_not_move_the_run_key(self) -> None:
        from bencher.example.benchmark_data import ExampleBenchCfg

        keys = []
        for series_id in (None, "latency"):
            cfg = bn.BenchRunCfg()
            cfg.auto_plot = False
            cfg.cache_results = False
            cfg.cache_samples = False
            bench = ExampleBenchCfg().to_bench(cfg)
            try:
                res = bench.plot_sweep(
                    input_vars=["theta"],
                    result_vars=["out_sin"],
                    series_id=series_id,
                    plot_callbacks=False,
                )
                keys.append(res.bench_cfg.hash_persistent(True))
            finally:
                bench.close()
        self.assertEqual(keys[0], keys[1])


if __name__ == "__main__":
    unittest.main()
