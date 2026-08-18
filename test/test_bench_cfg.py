"""Tests for the bencher/bench_cfg package — sub-configs, BenchRunCfg and BenchCfg.

Subsampling helpers (subsampling_divisions_to_samples, samples_per_var) are
covered in test/test_usability.py, hash stability/golden hashes in
test/test_hash_persistent.py and normalize_show in test/test_run.py, so they
are not duplicated here.
"""

from datetime import datetime

import pytest

import bencher as bn
from bencher.bench_cfg import (
    BenchCfg,
    BenchRunCfg,
    CacheCfg,
    DisplayCfg,
    ExecutionCfg,
    RegressionCfg,
    ServerCfg,
    TimeCfg,
    VisualizationCfg,
)
from bencher.history import OnHistoryReset
from bencher.job import Executors
from bencher.results.composable_container.composable_container_base import PaneLayout

SUB_CFG_SLOTS = {
    "server": ServerCfg,
    "execution": ExecutionCfg,
    "cache": CacheCfg,
    "display": DisplayCfg,
    "visualization": VisualizationCfg,
    "time": TimeCfg,
    "regression": RegressionCfg,
}


# ── sub-config defaults ─────────────────────────────────────────────────────


class TestServerCfgDefaults:
    def test_defaults(self):
        cfg = ServerCfg()
        assert cfg.port is None
        assert cfg.allow_ws_origin is False
        assert cfg.show is True


class TestExecutionCfgDefaults:
    def test_defaults(self):
        cfg = ExecutionCfg()
        assert cfg.repeats == 1
        assert cfg.subsampling_divisions == 0
        assert cfg.samples_per_var is None
        assert cfg.executor == Executors.SERIAL
        assert cfg.nightly is False
        assert cfg.headless is False
        assert cfg.dry_run is False
        assert cfg.only_plot is False
        assert cfg.catch == ()
        assert cfg.fail_on_sample_error is False

    def test_subsampling_divisions_to_samples(self):
        assert ExecutionCfg.subsampling_divisions_to_samples(5) == 9

    def test_subsampling_divisions_to_samples_out_of_range(self):
        with pytest.raises(ValueError):
            ExecutionCfg.subsampling_divisions_to_samples(0)

    def test_level_to_samples_shim_is_gone(self):
        assert not hasattr(BenchRunCfg, "level_to_samples")
        assert not hasattr(ExecutionCfg, "level_to_samples")


class TestCacheCfgDefaults:
    def test_defaults(self):
        cfg = CacheCfg()
        assert cfg.results is False
        assert cfg.samples is False
        assert cfg.clear is False
        assert cfg.clear_samples is False
        assert cfg.overwrite_samples is False
        assert cfg.only_hash_tag is False
        assert cfg.size_mb is None


class TestDisplayCfgDefaults:
    def test_defaults(self):
        cfg = DisplayCfg()
        assert cfg.print_bench_inputs is True
        assert cfg.print_bench_results is True
        assert cfg.summarise_constant_inputs is True
        assert cfg.print_pandas is False
        assert cfg.print_xarray is False
        assert cfg.serve_pandas is False
        assert cfg.serve_pandas_flat is True
        assert cfg.serve_xarray is False


class TestVisualizationCfgDefaults:
    def test_defaults(self):
        cfg = VisualizationCfg()
        assert cfg.auto_plot is True
        assert cfg.use_holoview is False
        assert cfg.use_optuna is False
        assert cfg.plot_size is None
        assert cfg.plot_width is None
        assert cfg.plot_height is None
        assert cfg.pane_layout == PaneLayout.grid
        assert cfg.backend == "panel"


class TestTimeCfgDefaults:
    def test_defaults(self):
        cfg = TimeCfg()
        assert cfg.over_time is False
        assert cfg.clear_history is False
        assert cfg.on_history_reset == OnHistoryReset.WARN
        assert cfg.max_events is None
        assert cfg.max_slider_points == 10
        assert cfg.show_aggregated_tab is False
        assert cfg.show_aggregate_plots is True
        assert cfg.event is None


class TestRegressionCfgDefaults:
    def test_defaults(self):
        cfg = RegressionCfg()
        assert cfg.enabled is False
        assert cfg.method == "adaptive"
        assert cfg.min_history == 1
        assert cfg.mad == 3.5
        assert cfg.percentage == 10.0
        assert cfg.delta is None
        assert cfg.absolute is None
        assert cfg.overrides is None
        assert cfg.fail is False


# ── BenchRunCfg composition ─────────────────────────────────────────────────


class TestBenchRunCfgComposition:
    def test_sub_config_slots(self):
        cfg = BenchRunCfg()
        for slot, cls in SUB_CFG_SLOTS.items():
            assert isinstance(getattr(cfg, slot), cls)

    def test_instances_do_not_share_sub_configs(self):
        a, b = BenchRunCfg(), BenchRunCfg()
        for slot in SUB_CFG_SLOTS:
            assert getattr(a, slot) is not getattr(b, slot)

    def test_instance_sub_configs_are_not_the_class_defaults(self):
        cfg = BenchRunCfg()
        for slot in SUB_CFG_SLOTS:
            assert getattr(cfg, slot) is not BenchRunCfg.param[slot].default

    def test_run_date_autopopulated(self):
        before = datetime.now()
        cfg = BenchRunCfg()
        after = datetime.now()
        assert isinstance(cfg.run_date, datetime)
        assert before <= cfg.run_date <= after

    def test_explicit_run_date_preserved(self):
        stamp = datetime(2024, 1, 2, 3, 4, 5)
        cfg = BenchRunCfg(run_date=stamp)
        assert cfg.run_date == stamp

    def test_run_tag_default(self):
        assert BenchRunCfg().run_tag == ""

    def test_construction_from_groups(self):
        cfg = BenchRunCfg(
            execution=ExecutionCfg(subsampling_divisions=4, repeats=3),
            cache=CacheCfg(results=True, samples=True),
            time=TimeCfg(over_time=True),
        )
        assert cfg.execution.subsampling_divisions == 4
        assert cfg.execution.repeats == 3
        assert cfg.cache.results is True
        assert cfg.cache.samples is True
        assert cfg.time.over_time is True

    def test_mutation_in_place(self):
        cfg = BenchRunCfg()
        cfg.cache.results = True
        cfg.time.over_time = True
        assert cfg.cache.results is True
        assert cfg.time.over_time is True


# ── the clean break: flat access is gone ────────────────────────────────────


class TestFlatAccessIsGone:
    def test_flat_kwargs_rejected(self):
        with pytest.raises(TypeError):
            BenchRunCfg(repeats=5)

    def test_flat_attribute_read_rejected(self):
        cfg = BenchRunCfg()
        with pytest.raises(AttributeError):
            _ = cfg.cache_results

    def test_deprecated_level_kwarg_is_gone(self):
        with pytest.raises(TypeError):
            BenchRunCfg(level=3)

    def test_raise_duplicate_exception_is_gone(self):
        assert "raise_duplicate_exception" not in BenchRunCfg.param
        assert "raise_duplicate_exception" not in BenchCfg.param

    def test_sub_configs_exported_from_bencher(self):
        for cls in SUB_CFG_SLOTS.values():
            assert getattr(bn, cls.__name__) is cls


# ── BenchRunCfg.with_defaults ───────────────────────────────────────────────


class TestWithDefaults:
    def test_none_run_cfg_creates_new_instance(self):
        cfg = BenchRunCfg.with_defaults(
            None, execution=dict(repeats=7), time=dict(over_time=True)
        )
        assert isinstance(cfg, BenchRunCfg)
        assert cfg.execution.repeats == 7
        assert cfg.time.over_time is True

    def test_explicit_caller_value_not_overridden(self):
        base = BenchRunCfg(execution=ExecutionCfg(repeats=3))
        merged = BenchRunCfg.with_defaults(base, execution=dict(repeats=7))
        assert merged.execution.repeats == 3

    def test_default_value_is_overridden(self):
        base = BenchRunCfg()  # repeats still at its param default of 1
        merged = BenchRunCfg.with_defaults(base, execution=dict(repeats=7))
        assert merged.execution.repeats == 7

    def test_original_cfg_not_mutated(self):
        base = BenchRunCfg()
        BenchRunCfg.with_defaults(base, execution=dict(repeats=7))
        assert base.execution.repeats == 1

    def test_multiple_groups_merge_independently(self):
        base = BenchRunCfg(cache=CacheCfg(results=True))
        merged = BenchRunCfg.with_defaults(
            base, cache=dict(results=False, samples=True), execution=dict(repeats=5)
        )
        assert merged.cache.results is True  # explicitly set by caller, kept
        assert merged.cache.samples is True  # still default, merged
        assert merged.execution.repeats == 5

    def test_top_level_param_merges(self):
        merged = BenchRunCfg.with_defaults(BenchRunCfg(), run_tag="tagged")
        assert merged.run_tag == "tagged"

    def test_unknown_group_raises_value_error(self):
        with pytest.raises(ValueError, match="not_a_real_group"):
            BenchRunCfg.with_defaults(None, not_a_real_group=dict(x=1))

    def test_unknown_key_within_group_raises_value_error(self):
        with pytest.raises(ValueError, match="not_a_real_param"):
            BenchRunCfg.with_defaults(None, execution=dict(not_a_real_param=1))

    def test_flat_key_raises_value_error(self):
        with pytest.raises(ValueError, match="repeats"):
            BenchRunCfg.with_defaults(None, repeats=5)


# ── BenchRunCfg.deep ────────────────────────────────────────────────────────


class TestDeep:
    def test_deep_copies_sub_configs_independently(self):
        cfg = BenchRunCfg(execution=ExecutionCfg(repeats=4))
        copy = cfg.deep()
        assert copy is not cfg
        for slot in SUB_CFG_SLOTS:
            assert getattr(copy, slot) is not getattr(cfg, slot)
        assert copy.execution.repeats == 4
        copy.execution.repeats = 9
        assert cfg.execution.repeats == 4
