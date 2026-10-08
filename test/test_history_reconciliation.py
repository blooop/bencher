"""Tests for schema-evolving over_time history (plans 09 + 14).

Covers the three plan-09 defects (order-sensitive keys, nameless identity,
silent invalidation) and the plan-14 retain+projection reconciliation model
(column birth/dormant/resume/retire, meaning_version, young-baseline gating).
"""

import logging
import os
import shutil
import tempfile
import unittest
import uuid
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

import numpy as np
import pytest
import xarray as xr

import bencher as bn
from bencher.bench_cfg import BenchCfg, BenchRunCfg
from bencher.example.benchmark_data import ExampleBenchCfg
from bencher.history import (
    BIRTH_ATTR,
    HistoryEvent,
    HistoryEventKind,
    HistoryResetError,
    OnHistoryReset,
    apply_policy,
    column_identity,
    data_var_columns,
    incompatible_reason,
    legacy_last_seen_key,
)
from bencher.regression import detect_regressions
from bencher.result_collector import ResultCollector
from bencher.variables.results import result_is_missing


def _result_float(name, units="s", meaning_version=1):
    rv = bn.ResultFloat(units=units, meaning_version=meaning_version)
    rv.name = name
    return rv


def _result_string(name):
    """An object-sentinel ('NAN') result column."""
    rv = bn.ResultString()
    rv.name = name
    return rv


def _result_reference(name):
    """An index-backed reference-sentinel (-1) result column."""
    rv = bn.ResultReference()
    rv.name = name
    return rv


def _float_sweep(name, units="m", bounds=(0.0, 1.0)):
    sweep = bn.FloatSweep(units=units, bounds=list(bounds))
    sweep.name = name
    return sweep


def _bench_cfg(result_vars, const_vars=(), input_vars=()):
    return BenchCfg(
        bench_name="demo",
        tag="demo",
        over_time=True,
        input_vars=list(input_vars),
        result_vars=list(result_vars),
        const_vars=list(const_vars),
    )


def _key(result_vars, const_vars=(), include_result_vars=True):
    return _bench_cfg(result_vars, const_vars).hash_persistent(
        True, include_result_vars=include_result_vars
    )


class TestOrderIndependentKeys(unittest.TestCase):
    """Plan 09 D1: reordering result_vars or const_vars must not move the key."""

    def test_result_var_reorder_is_noop(self):
        a = bn.ResultBool(units="ratio")
        b = bn.ResultFloat(units="s")
        assert _key([a, b]) == _key([b, a])

    def test_const_var_reorder_is_noop(self):
        a = bn.ResultBool(units="ratio")
        w = _float_sweep("width")
        g = _float_sweep("angle", units="deg", bounds=(0, 90))
        assert _key([a], [(w, 0.5), (g, 30.0)]) == _key([a], [(g, 30.0), (w, 0.5)])

    def test_input_var_order_still_matters(self):
        # Input order determines the dimension layout of the result arrays.
        w = _float_sweep("width")
        g = _float_sweep("angle", units="deg", bounds=(0, 90))
        a = bn.ResultBool(units="ratio")
        cfg_wg = _bench_cfg([a], input_vars=[w, g])
        cfg_gw = _bench_cfg([a], input_vars=[g, w])
        assert cfg_wg.hash_persistent(True) != cfg_gw.hash_persistent(True)

    def test_const_value_still_matters(self):
        a = bn.ResultBool(units="ratio")
        w = _float_sweep("width")
        assert _key([a], [(w, 0.5)]) != _key([a], [(w, 0.7)])


class TestNamedIdentity(unittest.TestCase):
    """Plan 09 D2: the variable name is part of every per-var identity."""

    def test_result_var_rename_moves_per_var_hash(self):
        x = _result_float("duration")
        y = _result_float("latency")
        assert x.hash_persistent() != y.hash_persistent()

    def test_input_var_rename_moves_per_var_hash(self):
        p = _float_sweep("speed")
        q = _float_sweep("velocity")
        assert p.hash_persistent() != q.hash_persistent()

    def test_result_var_rename_moves_strict_key(self):
        assert _key([_result_float("duration")]) != _key([_result_float("latency")])

    def test_const_rename_moves_key(self):
        a = bn.ResultBool(units="ratio")
        assert _key([a], [(_float_sweep("width"), 0.5)]) != _key(
            [a], [(_float_sweep("depth"), 0.5)]
        )

    def test_meaning_version_moves_identity(self):
        v1 = _result_float("m")
        v2 = _result_float("m", meaning_version=2)
        assert v1.hash_persistent() != v2.hash_persistent()
        assert column_identity(v1, "m") != column_identity(v2, "m")


class TestHistoryKeyExcludesResultVars(unittest.TestCase):
    """Plan 14: the history key ignores the result-var set entirely."""

    def test_result_set_changes_share_history_key(self):
        a = bn.ResultBool(units="ratio")
        b = bn.ResultFloat(units="s")
        x = _result_float("duration")
        y = _result_float("latency")
        assert _key([a, b], include_result_vars=False) == _key([b], include_result_vars=False)
        assert _key([x], include_result_vars=False) == _key([y], include_result_vars=False)

    def test_input_change_moves_history_key(self):
        a = bn.ResultBool(units="ratio")
        cfg_p = _bench_cfg([a], input_vars=[_float_sweep("speed")])
        cfg_q = _bench_cfg([a], input_vars=[_float_sweep("velocity")])
        assert cfg_p.hash_persistent(True, include_result_vars=False) != cfg_q.hash_persistent(
            True, include_result_vars=False
        )


def _day(t):
    return np.datetime64("2026-01-01") + np.timedelta64(t, "D")


def _run_ds(names, t):
    data = {n: (("repeat", "over_time"), np.array([[float(t)]])) for n in names}
    return xr.Dataset(data, coords={"repeat": [1], "over_time": [_day(t)]})


def _run_ds_typed(values, t):
    """A single (repeat=1, over_time=1) run with explicit per-column dtypes.

    ``values`` maps column name -> (scalar, dtype), mirroring the typed backing
    arrays ``ResultCollector.setup_dataset`` builds for object/reference result
    types (object "NAN" sentinel, int -1 sentinel).
    """
    data = {
        name: (("repeat", "over_time"), np.array([[val]], dtype=dtype))
        for name, (val, dtype) in values.items()
    }
    return xr.Dataset(data, coords={"repeat": [1], "over_time": [_day(t)]})


class ReconcilerBase(unittest.TestCase):
    """Runs the collector against a throwaway cachedir."""

    def setUp(self):
        self._old_cwd = Path.cwd()
        self._tmp = tempfile.mkdtemp()
        os.chdir(self._tmp)
        self.collector = ResultCollector()
        self.key = f"history-{uuid.uuid4()}"
        self.kwargs = {
            "bench_name": f"bench-{uuid.uuid4()}",
            "tag": "t",
            "config_summary": {"inputs": [], "consts": [], "results": [], "repeats": 1},
        }

    def tearDown(self):
        self.collector.close_caches()
        os.chdir(self._old_cwd)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def load_ds(self, dataset, result_vars, **overrides):
        kwargs = {**self.kwargs, **overrides}
        return self.collector.load_history_cache(
            dataset, self.key, False, None, result_vars, **kwargs
        )

    def load(self, names, t, result_vars, **overrides):
        return self.load_ds(_run_ds(names, t), result_vars, **overrides)


class TestReconcilerLifecycle(ReconcilerBase):
    def test_added_column_backfills_and_records_birth(self):
        self.load(["a"], 1, [_result_float("a")])
        served = self.load(["a", "c"], 2, [_result_float("a"), _result_float("c")])
        assert set(served.data_vars) == {"a", "c"}
        assert served.sizes["over_time"] == 2
        assert np.isnan(served["c"].values[0, 0])
        assert served["c"].values[0, 1] == 2.0
        assert served["c"].attrs[BIRTH_ATTR] == _day(2)
        # the untouched column's history continues
        assert list(served["a"].values[0]) == [1.0, 2.0]

    def test_removed_column_goes_dormant_and_resumes(self):
        rv_a, rv_b = _result_float("a"), _result_float("b")
        self.load(["a", "b"], 1, [rv_a, rv_b])
        served = self.load(["a"], 2, [rv_a])
        # projection: consumers see exactly the current config's columns
        assert set(served.data_vars) == {"a"}
        # storage: nothing deleted
        record = self.collector.get_history_cache()[self.key]
        assert "b" in record["dataset"].data_vars
        # returning with the same identity resumes the old trend
        served = self.load(["a", "b"], 3, [rv_a, rv_b])
        b_vals = served["b"].values[0]
        assert b_vals[0] == 1.0
        assert np.isnan(b_vals[1])
        assert b_vals[2] == 3.0

    def test_meaning_version_bump_retires_and_restarts_column(self):
        self.load(["a"], 1, [_result_float("a")])
        self.load(["a"], 2, [_result_float("a")])
        served = self.load(["a"], 3, [_result_float("a", meaning_version=2)])
        a_vals = served["a"].values[0]
        assert np.isnan(a_vals[0])
        assert np.isnan(a_vals[1])
        assert a_vals[2] == 3.0
        assert served["a"].attrs[BIRTH_ATTR] == _day(3)
        record = self.collector.get_history_cache()[self.key]
        retired = [name for name in record["dataset"].data_vars if "__retired_" in name]
        assert len(retired) == 1
        assert list(record["dataset"][retired[0]].values[0][:2]) == [1.0, 2.0]

    def test_no_dead_columns_no_phantom_dims(self):
        """The two plan-09 D2 corruption modes must be structurally impossible."""
        rv_old, rv_new = _result_float("duration"), _result_float("latency")
        self.load(["duration"], 1, [rv_old])
        served = self.load(["latency"], 2, [rv_new])
        # rename == remove+add: no dead 'duration' column in what consumers see
        assert set(served.data_vars) == {"latency"}
        assert set(served.dims) == {"repeat", "over_time"}

    def test_incompatible_dims_discarded_not_broadcast(self):
        cache = self.collector.get_history_cache()
        alien = xr.Dataset(
            {"a": (("speed", "over_time"), np.ones((2, 3)))},
            coords={"speed": [0.1, 0.2], "over_time": [_day(0), _day(1), _day(2)]},
        )
        cache[self.key] = {"format": 1, "dataset": alien, "columns": {}, "retired": {}}
        served = self.load(["a"], 3, [_result_float("a")])
        assert "speed" not in served.dims
        assert served.sizes["over_time"] == 1

    def test_plain_dataset_record_adopted(self):
        cache = self.collector.get_history_cache()
        cache[self.key] = _run_ds(["a"], 1)
        served = self.load(["a"], 2, [_result_float("a")])
        assert list(served["a"].values[0]) == [1.0, 2.0]
        # adopted columns have no fabricated birth
        assert BIRTH_ATTR not in served["a"].attrs


class TestSentinelRestore(ReconcilerBase):
    """_restore_sentinel_fill: object 'NAN' / reference -1 gaps survive concat."""

    def test_object_and_reference_gap_holds_sentinel_after_resume(self):
        rv_a, rv_s, rv_r = _result_float("a"), _result_string("s"), _result_reference("r")
        # run 1: all present with real values
        self.load_ds(
            _run_ds_typed({"a": (1.0, float), "s": ("hello", object), "r": (3, int)}, 1),
            [rv_a, rv_s, rv_r],
        )
        # run 2: object + reference columns go dormant (excluded from the run)
        self.load_ds(_run_ds_typed({"a": (2.0, float)}, 2), [rv_a])
        # run 3: they return
        served = self.load_ds(
            _run_ds_typed({"a": (3.0, float), "s": ("world", object), "r": (7, int)}, 3),
            [rv_a, rv_s, rv_r],
        )
        s_vals, r_vals = served["s"].values[0], served["r"].values[0]
        # pre-gap real values intact
        assert s_vals[0] == "hello"
        assert r_vals[0] == 3
        # the dormant-run gap holds exactly the proper sentinel
        assert s_vals[1] == "NAN"
        assert r_vals[1] == -1
        assert result_is_missing(rv_s, s_vals[1])
        assert result_is_missing(rv_r, r_vals[1])
        # returned real values
        assert s_vals[2] == "world"
        assert r_vals[2] == 7
        # dtype preserved: object stays object; reference round-trips to int -1
        assert served["s"].dtype == object
        assert np.issubdtype(served["r"].dtype, np.integer)
        assert served["r"].values[0, 1] == -1

    def test_born_object_and_reference_columns_backfill_sentinel(self):
        rv_a, rv_s, rv_r = _result_float("a"), _result_string("s"), _result_reference("r")
        # run 1: only the float anchor exists
        self.load_ds(_run_ds_typed({"a": (1.0, float)}, 1), [rv_a])
        # run 2: object + reference columns are born after history exists
        served = self.load_ds(
            _run_ds_typed({"a": (2.0, float), "s": ("v", object), "r": (5, int)}, 2),
            [rv_a, rv_s, rv_r],
        )
        # the pre-birth backfill is the sentinel, not raw NaN
        assert served["s"].values[0, 0] == "NAN"
        assert served["r"].values[0, 0] == -1
        assert result_is_missing(rv_s, served["s"].values[0, 0])
        assert result_is_missing(rv_r, served["r"].values[0, 0])
        assert served["s"].dtype == object
        assert np.issubdtype(served["r"].dtype, np.integer)
        # the newly measured values are intact
        assert served["s"].values[0, 1] == "v"
        assert served["r"].values[0, 1] == 5


class TestLegacyRecordDormancy(ReconcilerBase):
    """Format-0 (bare xr.Dataset) records must obey the dormant lifecycle."""

    def _seed_legacy(self, t=1):
        """Seed a bare (format-0) record with columns 'a' and 'b'."""
        cache = self.collector.get_history_cache()
        cache[self.key] = _run_ds_typed({"a": (1.0, float), "b": (10.0, float)}, t)

    def test_legacy_missing_column_errors_before_persist(self):
        self._seed_legacy()
        cache = self.collector.get_history_cache()
        record_before = cache[self.key]  # bare xr.Dataset (format 0)
        with pytest.raises(HistoryResetError):
            self.load(["a"], 2, [_result_float("a")], on_history_reset="error")
        record_after = cache[self.key]
        # the raise happens before persist: the bare record is untouched
        assert isinstance(record_after, xr.Dataset)
        xr.testing.assert_identical(record_before, record_after)

    def test_legacy_missing_column_warn_records_dormant_stub(self):
        self._seed_legacy()
        with self.assertLogs("bencher.history", level=logging.WARNING) as logs:
            served = self.load(["a"], 2, [_result_float("a")])
        assert any("'b'" in line and "predat" in line for line in logs.output)
        assert set(served.data_vars) == {"a"}
        record = self.collector.get_history_cache()[self.key]
        stub = record["columns"]["b"]
        assert stub["dormant"]
        assert stub["identity"] is None
        # data retained, not deleted
        assert "b" in record["dataset"].data_vars

    def test_legacy_column_resumes_without_retire_or_duplicate(self):
        self._seed_legacy()
        self.load(["a"], 2, [_result_float("a")])  # b -> dormant (warns)
        with self.assertNoLogs("bencher.history", level=logging.WARNING):
            served = self.load(["a", "b"], 3, [_result_float("a"), _result_float("b")])
        assert set(served.data_vars) == {"a", "b"}
        b_vals = served["b"].values[0]
        assert b_vals[0] == 10.0  # legacy history served
        assert np.isnan(b_vals[1])  # gap while dormant
        assert b_vals[2] == 3.0  # returned value
        # adopt-in-place resume: no fabricated birth
        assert BIRTH_ATTR not in served["b"].attrs
        # no retired mangled column and no phantom duplicate of 'b'
        record = self.collector.get_history_cache()[self.key]
        data_vars = list(record["dataset"].data_vars)
        assert not any("__retired_" in name for name in data_vars)
        assert len(data_vars) == 2
        assert record["retired"] == {}


class TestResetPolicy(ReconcilerBase):
    def test_error_policy_raises_before_persisting(self):
        rv_a, rv_b = _result_float("a"), _result_float("b")
        self.load(["a", "b"], 1, [rv_a, rv_b])
        cache = self.collector.get_history_cache()
        ls_key = legacy_last_seen_key(self.kwargs["bench_name"], self.kwargs["tag"])
        record_before = cache[self.key]
        last_before = cache.get(ls_key)
        with pytest.raises(HistoryResetError):
            self.load(["a"], 2, [rv_a], on_history_reset="error")
        record_after = cache[self.key]
        last_after = cache.get(ls_key)
        # column + retire metadata, dataset values, and the last-seen index
        # entry must all be byte-identical: an erroring run advances nothing.
        assert record_before["columns"] == record_after["columns"]
        assert record_before["retired"] == record_after["retired"]
        xr.testing.assert_identical(record_before["dataset"], record_after["dataset"])
        assert last_before == last_after

    def test_warn_policy_names_the_change(self):
        rv_a, rv_b = _result_float("a"), _result_float("b")
        self.load(["a", "b"], 1, [rv_a, rv_b])
        with self.assertLogs("bencher.history", level=logging.WARNING) as logs:
            self.load(["a"], 2, [rv_a])
        assert any("'b' removed" in line for line in logs.output)

    def test_ignore_policy_is_quiet(self):
        rv_a, rv_b = _result_float("a"), _result_float("b")
        self.load(["a", "b"], 1, [rv_a, rv_b])
        with self.assertNoLogs("bencher.history", level=logging.WARNING):
            self.load(["a"], 2, [rv_a], on_history_reset="ignore")

    def test_full_reset_reported_via_last_seen_index(self):
        """A key move with a *changed* declaration is still a reported reset.

        The declaration has to actually change: a key that moves while the stored
        config summary is *unchanged* is a rename, and is adopted instead (see
        TestSeriesIdentity). This harness passes config_summary explicitly, so the
        changed declaration is expressed there.
        """
        self.load(["a"], 1, [_result_float("a")])
        self.key = f"history-{uuid.uuid4()}"
        changed = {**self.kwargs["config_summary"], "inputs": [("x", "FloatSweep", "ul")]}
        with self.assertLogs("bencher.history", level=logging.WARNING) as logs:
            self.load(["a"], 2, [_result_float("a")], config_summary=changed)
        assert any("orphaned under the old key" in line for line in logs.output)

    def test_born_column_is_not_lossy(self):
        self.load(["a"], 1, [_result_float("a")])
        with self.assertNoLogs("bencher.history", level=logging.WARNING):
            self.load(
                ["a", "c"], 2, [_result_float("a"), _result_float("c")], on_history_reset="error"
            )

    def test_unknown_policy_raises_before_touching_the_cache(self):
        """An unknown policy string used to silently mean 'ignore'; now it is a
        config error raised at the parse, before any history-cache read or write.

        Keep the invalid value out of codespell's dictionary. A plausible
        misspelling of a policy name is usually a dictionary entry, and the
        repo's hook runs with --write-changes: it would rewrite the value here
        into the correctly-spelled *valid* policy, silently turning this
        assertion into one that can never fail.
        """
        with pytest.raises(ValueError, match="is not a valid OnHistoryReset"):
            self.load(["a"], 1, [_result_float("a")], on_history_reset="silently-ignore")
        # nothing was persisted: the bad-config run advanced no history state
        cache = self.collector.get_history_cache()
        assert self.key not in cache
        ls_key = legacy_last_seen_key(self.kwargs["bench_name"], self.kwargs["tag"])
        assert cache.get(ls_key) is None

    def test_enum_policy_value_accepted(self):
        served = self.load(["a"], 1, [_result_float("a")], on_history_reset=OnHistoryReset.ERROR)
        assert set(served.data_vars) == {"a"}


class TestEventKindLossiness(unittest.TestCase):
    """Every HistoryEventKind is classified through apply_policy under 'error'.

    Exhaustive over the enum: adding a kind without classifying it in
    ``HistoryEvent.lossy`` fails here (and in ty's exhaustiveness check)
    instead of silently defeating the on_history_reset='error' CI gate the
    way the old ``_LOSSY_KINDS`` set did for a typo'd kind.
    """

    LOSSY = frozenset(
        {
            HistoryEventKind.FULL_RESET,
            HistoryEventKind.COLUMN_DORMANT,
            HistoryEventKind.COLUMN_RETIRED,
            HistoryEventKind.HISTORY_DISCARDED,
        }
    )
    NON_LOSSY = frozenset(
        {
            HistoryEventKind.HISTORY_RENAMED,
            HistoryEventKind.COLUMN_BORN,
            HistoryEventKind.COLUMN_RESUMED,
        }
    )

    def test_partition_covers_every_kind(self):
        assert set(HistoryEventKind) == self.LOSSY | self.NON_LOSSY
        assert set() == self.LOSSY & self.NON_LOSSY

    def test_lossy_kinds_raise_under_error_policy(self):
        for kind in self.LOSSY:
            with self.subTest(kind=kind):
                event = HistoryEvent(kind, f"synthetic {kind} event")
                assert event.lossy
                with pytest.raises(HistoryResetError):
                    apply_policy([event], "error")

    def test_non_lossy_kinds_pass_under_error_policy(self):
        for kind in self.NON_LOSSY:
            with self.subTest(kind=kind):
                event = HistoryEvent(kind, f"synthetic {kind} event")
                assert not event.lossy
                apply_policy([event], "error")  # must not raise

    def test_apply_policy_rejects_unknown_policy_even_with_no_events(self):
        with pytest.raises(ValueError, match="is not a valid OnHistoryReset"):
            apply_policy([], "silently-ignore")

    def test_raw_string_kinds_are_parsed_to_members(self):
        """HistoryEvent is public API; a valid raw-string kind still classifies."""
        for kind in HistoryEventKind:
            with self.subTest(kind=kind):
                event = HistoryEvent(str(kind), "from a raw string")
                assert event.kind is kind
                assert event.lossy == HistoryEvent(kind, "x").lossy

    def test_unknown_kind_raises_naming_the_value(self):
        """A bad kind is a ValueError naming it, not the misdirecting
        "Expected code to be unreachable" of a reached assert_never arm."""
        with pytest.raises(ValueError, match="is not a valid HistoryEventKind") as ctx:
            HistoryEvent("not_a_real_kind", "detail")
        assert "not_a_real_kind" in str(ctx.value)


class _CountingSweep(bn.ParametrizedSweep):
    """Module-level (so results stay pickleable) sweep that records each sample."""

    calls: ClassVar[list] = []

    x = bn.FloatSweep(default=0.0, bounds=[0.0, 1.0])
    out = bn.ResultFloat()

    def benchmark(self):
        _CountingSweep.calls.append(self.x)
        return {"out": self.x}


class TestPolicyVocabularySingleSource(unittest.TestCase):
    """The policy vocabulary is defined once, by OnHistoryReset (plan 23 §9)."""

    def setUp(self):
        self._old_cwd = Path.cwd()
        self._tmp = tempfile.mkdtemp()
        os.chdir(self._tmp)
        _CountingSweep.calls = []

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_run_cfg_selector_objects_come_from_the_enum(self):
        """The Selector's objects must be the enum *members*, not equal strings.

        Asserting equality alone would not gate this: OnHistoryReset is a
        StrEnum, so a hardcoded ["warn", "error", "ignore"] compares equal to
        list(OnHistoryReset). Only an identity/type check catches a second,
        drifting definition of the vocabulary.
        """
        objects = list(BenchRunCfg.param.on_history_reset.objects)
        assert objects == list(OnHistoryReset)
        for obj in objects:
            assert isinstance(obj, OnHistoryReset)

    def test_run_cfg_default_is_an_enum_member(self):
        assert BenchRunCfg().on_history_reset is OnHistoryReset.WARN

    def test_plot_sweep_normalizes_a_string_policy_to_a_member(self):
        """plot_sweep assigns the member back, so downstream readers see the enum.

        This is the half of the fix that param cannot provide: a raw string
        passes the Selector (StrEnum members compare equal to their values), so
        without the normalization the field stays a ``str`` all the way into
        ``load_history_cache``.
        """
        bench = bn.Bench("policy-normalize", _CountingSweep())
        run_cfg = BenchRunCfg(over_time=True, repeats=1, on_history_reset="ignore")
        bench.plot_sweep(input_vars=[_CountingSweep.param.x], run_cfg=run_cfg)
        assert run_cfg.on_history_reset is OnHistoryReset.IGNORE
        assert _CountingSweep.calls, "the sweep should have run"

    def test_bad_policy_raises_before_any_sample_is_collected(self):
        """A bad policy must never cost a fully-collected run.

        ``load_history_cache`` runs *after* ``calculate_benchmark_results`` and
        before ``cache_results``, and ``cache_samples`` defaults False — so a
        parse that only happened there would discard every sample it just paid
        for. Two independent guards now sit ahead of sampling: param's own
        Selector check (whose vocabulary is the enum, per the test above) and
        ``plot_sweep``'s normalization. This disables the former on both config
        classes to prove the latter alone is early enough.
        """
        bench = bn.Bench("policy-presample", _CountingSweep())
        run_cfg = BenchRunCfg(over_time=True, repeats=1)
        run_params = (run_cfg.param.on_history_reset, BenchCfg.param.on_history_reset)
        for p in run_params:
            p.check_on_set = False
        self.addCleanup(lambda: [setattr(p, "check_on_set", True) for p in run_params])
        run_cfg.on_history_reset = "silently-ignore"
        with pytest.raises(ValueError, match="is not a valid OnHistoryReset"):
            bench.plot_sweep(input_vars=[_CountingSweep.param.x], run_cfg=run_cfg)
        assert _CountingSweep.calls == [], "samples were collected before the policy was parsed"


class TestYoungBaselineGating(unittest.TestCase):
    def _dataset(self, values, birth_idx=None):
        n = len(values)
        coords = {"repeat": [1], "over_time": [_day(i) for i in range(n)]}
        ds = xr.Dataset(
            {"m": (("repeat", "over_time"), np.array(values, dtype=float).reshape(1, n))},
            coords=coords,
        )
        if birth_idx is not None:
            ds["m"].attrs[BIRTH_ATTR] = ds["over_time"].values[birth_idx]
        return ds

    def _detect(self, values, birth_idx=None, min_history=1, overrides=None):
        rv = _result_float("m")
        bench_cfg = _bench_cfg([rv])
        run_cfg = BenchRunCfg(
            over_time=True,
            regression_detection=True,
            regression_method="percentage",
            regression_percentage=10.0,
            regression_min_history=min_history,
            regression_overrides=overrides,
        )
        return detect_regressions(self._dataset(values, birth_idx), bench_cfg, run_cfg)

    def test_mature_baseline_blocks(self):
        report = self._detect([1.0, 1.0, 10.0], min_history=2)
        assert report.has_regressions
        assert report.has_blocking_regressions

    def test_young_baseline_notifies_but_does_not_block(self):
        report = self._detect([1.0, 1.0, 10.0], birth_idx=1, min_history=2)
        assert report.has_regressions
        assert not report.has_blocking_regressions
        assert all(r.young_baseline for r in report.regressed_variables)
        assert "young baseline" in report.summary()

    def test_default_min_history_preserves_existing_behavior(self):
        report = self._detect([1.0, 1.0, 10.0], birth_idx=1, min_history=1)
        assert report.has_blocking_regressions

    def test_per_var_min_history_override(self):
        report = self._detect(
            [1.0, 1.0, 10.0],
            birth_idx=1,
            min_history=1,
            overrides={"m": {"min_history": 3}},
        )
        assert report.has_regressions
        assert not report.has_blocking_regressions

    def test_young_baseline_in_dict_export(self):
        report = self._detect([1.0, 1.0, 10.0], birth_idx=1, min_history=2)
        exported = [r.to_dict() for r in report.regressed_variables]
        assert all(entry.get("young_baseline") for entry in exported)
        mature = self._detect([1.0, 1.0, 10.0], min_history=1)
        exported = [r.to_dict() for r in mature.regressed_variables]
        assert all("young_baseline" not in entry for entry in exported)


class TestOverTimeDtypeGuard(unittest.TestCase):
    """Pin the naive-to-tz-aware transition as incompatible history.

    A tz-aware time_src makes the over_time coordinate dtype ``object`` rather
    than ``datetime64[us]``, because xarray has nowhere to put the tzinfo. That
    dtype difference is the only signal incompatible_reason has, and it is what
    makes the first tz-aware run throw away the naive history instead of
    merging with it.

    Do not "fix" the object dtype by normalising aware datetimes to UTC inside
    TimeSnapshot. Matching the dtypes silences this guard, and old history
    recorded against a local wall clock then concatenates with new UTC history
    at a fixed offset with nothing to flag it. Measured under
    TZ=America/New_York, the normalising version produced a merged coordinate
    of ['2000-01-01T00:00:00', '2000-01-01T05:00:01'] and no reason string at
    all. Dropping the history loudly beats merging it wrong quietly, so the
    object dtype stays put until someone versions the history format.
    """

    def _over_time_dataset(self, time_src):
        instance = ExampleBenchCfg()
        bench_cfg = _bench_cfg([instance.param.out_sin], input_vars=[instance.param.theta])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            bench_res, _, _, _ = ResultCollector().setup_dataset(bench_cfg, time_src)
        return bench_res.ds

    def test_naive_to_aware_over_time_is_incompatible(self):
        naive = self._over_time_dataset(datetime(2000, 1, 1))
        aware = self._over_time_dataset(datetime(2000, 1, 1, 0, 0, 1, tzinfo=UTC))
        reason = incompatible_reason(naive, aware)
        assert reason is not None
        assert "over_time dtype changed" in reason

    def test_naive_to_naive_over_time_is_compatible(self):
        """Control: two naive runs still merge, so the guard is not firing on everything."""
        first = self._over_time_dataset(datetime(2000, 1, 1))
        second = self._over_time_dataset(datetime(2000, 1, 1, 0, 0, 1))
        assert incompatible_reason(first, second) is None

    def test_aware_to_aware_over_time_is_compatible(self):
        """An always-tz-aware caller has a mergeable history: object matches object."""
        first = self._over_time_dataset(datetime(2000, 1, 1, tzinfo=UTC))
        second = self._over_time_dataset(datetime(2000, 1, 1, 0, 0, 1, tzinfo=UTC))
        assert incompatible_reason(first, second) is None

    def test_aware_to_naive_over_time_is_incompatible(self):
        """...and one naive run destroys it, which is why the warning must not ask for one."""
        aware = self._over_time_dataset(datetime(2000, 1, 1, tzinfo=UTC))
        naive = self._over_time_dataset(datetime(2000, 1, 1, 0, 0, 1))
        reason = incompatible_reason(aware, naive)
        assert reason is not None
        assert "over_time dtype changed" in reason


class TestDataVarColumns(unittest.TestCase):
    def test_result_vec_expands(self):
        vec = bn.ResultVec(2, units="m")
        vec.name = "pos"
        cols = data_var_columns([vec, _result_float("a")])
        assert set(cols) == {"pos_x", "pos_y", "a"}


if __name__ == "__main__":
    unittest.main()
