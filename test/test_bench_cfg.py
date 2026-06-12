"""Tests for bencher/bench_cfg.py — BenchPlotSrvCfg, BenchRunCfg and BenchCfg.

Subsampling helpers (subsampling_divisions_to_samples, samples_per_var) are
covered in test/test_usability.py, hash stability/golden hashes in
test/test_hash_persistent.py and normalize_show in test/test_run.py, so they
are not duplicated here.
"""

import math
from datetime import datetime
from types import SimpleNamespace

import panel as pn
import pytest

import bencher as bn
from bencher.bench_cfg import BenchCfg, BenchPlotSrvCfg, BenchRunCfg, DimsCfg
from bencher.job import Executors
from bencher.variables.results import OptDir


class SweepCfg(bn.ParametrizedSweep):
    """Small sweep used to populate BenchCfg input/result/const vars."""

    theta = bn.FloatSweep(default=0, bounds=[0, math.pi], samples=4)
    offset = bn.FloatSweep(default=0, bounds=[0, 1], samples=3)
    out_sin = bn.ResultFloat(units="v")


class SweepCfgNoOptDir(bn.ParametrizedSweep):
    """Result variable that is not an optimization target."""

    out_fixed = bn.ResultFloat(units="v", direction=OptDir.none)


def make_bench_cfg(**overrides) -> BenchCfg:
    """Build a fully-populated BenchCfg for describe/hash tests."""
    params = dict(
        input_vars=[SweepCfg.param.theta],
        result_vars=[SweepCfg.param.out_sin],
        const_vars=[(SweepCfg.param.offset, 0.5)],
        meta_vars=[],
        all_vars=[SweepCfg.param.theta],
        bench_name="bench_cfg_test",
        title="My Title",
        description="A longer description of the benchmark",
        post_description="Comments on the output",
    )
    params.update(overrides)
    return BenchCfg(**params)


# ── BenchPlotSrvCfg defaults ────────────────────────────────────────────────


class TestBenchPlotSrvCfgDefaults:
    def test_defaults(self):
        cfg = BenchPlotSrvCfg()
        assert cfg.port is None
        assert cfg.allow_ws_origin is False
        assert cfg.show is True


# ── BenchRunCfg defaults ────────────────────────────────────────────────────


class TestBenchRunCfgDefaults:
    def test_execution_defaults(self):
        cfg = BenchRunCfg()
        assert cfg.repeats == 1
        assert cfg.subsampling_divisions == 0
        assert cfg.samples_per_var is None
        assert cfg.executor == Executors.SERIAL
        assert cfg.nightly is False
        assert cfg.headless is False
        assert cfg.dry_run is False

    def test_cache_defaults_all_false(self):
        cfg = BenchRunCfg()
        assert cfg.cache_results is False
        assert cfg.cache_samples is False
        assert cfg.clear_cache is False
        assert cfg.clear_sample_cache is False
        assert cfg.overwrite_sample_cache is False
        assert cfg.only_hash_tag is False
        assert cfg.only_plot is False
        assert cfg.cache_size is None

    def test_display_defaults(self):
        cfg = BenchRunCfg()
        assert cfg.print_bench_inputs is True
        assert cfg.print_bench_results is True
        assert cfg.summarise_constant_inputs is True
        assert cfg.print_pandas is False
        assert cfg.print_xarray is False
        assert cfg.serve_pandas is False
        assert cfg.serve_pandas_flat is True
        assert cfg.serve_xarray is False

    def test_visualization_defaults(self):
        cfg = BenchRunCfg()
        assert cfg.auto_plot is True
        assert cfg.use_holoview is False
        assert cfg.use_optuna is False
        assert cfg.plot_size is None
        assert cfg.plot_width is None
        assert cfg.plot_height is None
        assert cfg.backend == "panel"

    def test_time_defaults(self):
        cfg = BenchRunCfg()
        assert cfg.over_time is False
        assert cfg.clear_history is False
        assert cfg.max_time_events is None
        assert cfg.max_slider_points == 10
        assert cfg.show_aggregated_time_tab is False
        assert cfg.show_aggregate_plots is True
        assert cfg.time_event is None
        assert cfg.run_tag == ""

    def test_run_date_autopopulated(self):
        before = datetime.now()
        cfg = BenchRunCfg()
        after = datetime.now()
        assert isinstance(cfg.run_date, datetime)
        assert before <= cfg.run_date <= after

    def test_regression_defaults(self):
        cfg = BenchRunCfg()
        assert cfg.regression_detection is False
        assert cfg.regression_method == "adaptive"
        assert cfg.regression_fail is False


# ── BenchRunCfg construction round-trips ────────────────────────────────────


class TestBenchRunCfgRoundTrip:
    def test_values_round_trip_through_construction(self):
        cfg = BenchRunCfg(repeats=5, over_time=True, cache_results=True, cache_samples=True)
        assert cfg.repeats == 5
        assert cfg.over_time is True
        assert cfg.cache_results is True
        assert cfg.cache_samples is True

    def test_explicit_run_date_preserved(self):
        stamp = datetime(2024, 1, 2, 3, 4, 5)
        cfg = BenchRunCfg(run_date=stamp)
        assert cfg.run_date == stamp

    def test_deprecated_level_kwarg_maps_to_subsampling_divisions(self):
        with pytest.warns(DeprecationWarning):
            cfg = BenchRunCfg(level=3)
        assert cfg.subsampling_divisions == 3

    def test_deep_returns_independent_copy(self):
        cfg = BenchRunCfg(repeats=4)
        copy = cfg.deep()
        assert copy is not cfg
        assert copy.repeats == 4
        copy.repeats = 9
        assert cfg.repeats == 4


# ── BenchRunCfg.with_defaults ───────────────────────────────────────────────


class TestWithDefaults:
    def test_none_run_cfg_creates_new_instance(self):
        cfg = BenchRunCfg.with_defaults(None, repeats=7, over_time=True)
        assert isinstance(cfg, BenchRunCfg)
        assert cfg.repeats == 7
        assert cfg.over_time is True

    def test_explicit_caller_value_not_overridden(self):
        base = BenchRunCfg(repeats=3)
        merged = BenchRunCfg.with_defaults(base, repeats=7)
        assert merged.repeats == 3

    def test_default_value_is_overridden(self):
        base = BenchRunCfg()  # repeats still at its param default of 1
        merged = BenchRunCfg.with_defaults(base, repeats=7)
        assert merged.repeats == 7

    def test_original_cfg_not_mutated(self):
        base = BenchRunCfg()
        BenchRunCfg.with_defaults(base, repeats=7)
        assert base.repeats == 1

    def test_unknown_key_raises_value_error(self):
        with pytest.raises(ValueError, match="not_a_real_param"):
            BenchRunCfg.with_defaults(None, not_a_real_param=1)

    def test_deprecated_level_key_warns_and_maps(self):
        with pytest.warns(DeprecationWarning):
            cfg = BenchRunCfg.with_defaults(None, level=4)
        assert cfg.subsampling_divisions == 4


# ── BenchCfg.hash_persistent ────────────────────────────────────────────────


class TestBenchCfgHashPersistent:
    def test_same_config_same_hash(self):
        assert make_bench_cfg().hash_persistent(
            include_repeats=True
        ) == make_bench_cfg().hash_persistent(include_repeats=True)

    def test_different_repeats_different_hash(self):
        h1 = make_bench_cfg(repeats=1).hash_persistent(include_repeats=True)
        h2 = make_bench_cfg(repeats=2).hash_persistent(include_repeats=True)
        assert h1 != h2

    def test_repeats_ignored_when_include_repeats_false(self):
        h1 = make_bench_cfg(repeats=1).hash_persistent(include_repeats=False)
        h2 = make_bench_cfg(repeats=2).hash_persistent(include_repeats=False)
        assert h1 == h2

    def test_different_tag_different_hash(self):
        h1 = make_bench_cfg(tag="a").hash_persistent(include_repeats=True)
        h2 = make_bench_cfg(tag="b").hash_persistent(include_repeats=True)
        assert h1 != h2

    def test_different_bench_name_different_hash(self):
        h1 = make_bench_cfg(bench_name="bench_a").hash_persistent(include_repeats=True)
        h2 = make_bench_cfg(bench_name="bench_b").hash_persistent(include_repeats=True)
        assert h1 != h2

    def test_const_var_value_changes_hash(self):
        h1 = make_bench_cfg(
            const_vars=[(SweepCfg.param.offset, 0.5)],
        ).hash_persistent(include_repeats=True)
        h2 = make_bench_cfg(
            const_vars=[(SweepCfg.param.offset, 0.9)],
        ).hash_persistent(include_repeats=True)
        assert h1 != h2


# ── BenchCfg describe/summary helpers ───────────────────────────────────────


class TestDescribeBenchmark:
    def test_mentions_input_and_result_vars(self):
        desc = make_bench_cfg().describe_benchmark()
        assert "Input Variables:" in desc
        assert "theta" in desc
        assert "Result Variables:" in desc
        assert "out_sin" in desc

    def test_mentions_constants_with_value(self):
        desc = make_bench_cfg().describe_benchmark()
        assert "Constants:" in desc
        assert "offset" in desc
        assert "value: 0.5" in desc

    def test_constants_hidden_when_summarise_disabled(self):
        desc = make_bench_cfg(summarise_constant_inputs=False).describe_benchmark()
        assert "Constants:" not in desc
        assert "offset" not in desc

    def test_includes_meta_information(self):
        cfg = make_bench_cfg(run_tag="my_run_tag")
        desc = cfg.describe_benchmark()
        assert f"run date: {cfg.run_date}" in desc
        assert "run tag: my_run_tag" in desc
        assert "cache_results: False" in desc

    def test_reports_sample_counts(self):
        desc = make_bench_cfg().describe_benchmark()
        assert "number of samples: 4" in desc


class TestSweepSentence:
    def test_sentence_mentions_vars_and_shape(self):
        sentence = make_bench_cfg().sweep_sentence()
        assert isinstance(sentence, pn.pane.Markdown)
        text = sentence.object
        assert "theta" in text
        assert "out_sin" in text
        # theta has 4 samples; a second dimension of 1 is appended
        assert "4x1" in text

    def test_sentence_two_dims(self):
        cfg = make_bench_cfg(all_vars=[SweepCfg.param.theta, SweepCfg.param.offset])
        text = cfg.sweep_sentence().object
        assert "theta by offset" in text
        # reversed order of all_vars: offset (3 samples) x theta (4 samples)
        assert "3x4" in text


class TestPanelHelpers:
    def test_to_title(self):
        title = make_bench_cfg().to_title()
        assert isinstance(title, pn.pane.Markdown)
        assert title.object == "# My Title"
        assert title.name == "My Title"

    def test_to_description(self):
        desc = make_bench_cfg().to_description(width=600)
        assert isinstance(desc, pn.pane.Markdown)
        assert desc.object == "A longer description of the benchmark"
        assert desc.width == 600

    def test_to_post_description(self):
        post = make_bench_cfg().to_post_description()
        assert post.object == "Comments on the output"

    def test_to_description_empty_when_none(self):
        assert make_bench_cfg(description=None).to_description().object == ""

    def test_inputs_as_str(self):
        assert make_bench_cfg().inputs_as_str() == ["theta"]


# ── input var partitioning and optuna targets ───────────────────────────────


class TestPartitionInputVars:
    def test_partition_by_optimize_flag(self):
        opt_var = SimpleNamespace(optimize=True)
        non_opt_var = SimpleNamespace(optimize=False)
        no_flag_var = SimpleNamespace()
        opt, non_opt = BenchCfg.partition_input_vars([opt_var, non_opt_var, no_flag_var])
        assert opt == [opt_var, no_flag_var]  # missing flag defaults to optimized
        assert non_opt == [non_opt_var]

    def test_optimized_input_vars_properties(self):
        non_opt_var = SimpleNamespace(optimize=False)
        cfg = make_bench_cfg(input_vars=[SweepCfg.param.theta, non_opt_var])
        assert cfg.optimized_input_vars == [SweepCfg.param.theta]
        assert cfg.non_optimized_input_vars == [non_opt_var]

    def test_properties_handle_none_input_vars(self):
        cfg = make_bench_cfg(input_vars=None)
        assert cfg.optimized_input_vars == []
        assert cfg.non_optimized_input_vars == []


class TestOptunaTargets:
    def test_targets_exclude_direction_none(self):
        cfg = make_bench_cfg(result_vars=[SweepCfg.param.out_sin, SweepCfgNoOptDir.param.out_fixed])
        assert cfg.optuna_targets() == ["out_sin"]

    def test_targets_as_var_returns_objects(self):
        cfg = make_bench_cfg(result_vars=[SweepCfg.param.out_sin])
        assert cfg.optuna_targets(as_var=True) == [SweepCfg.param.out_sin]


# ── DimsCfg ─────────────────────────────────────────────────────────────────


class TestDimsCfg:
    def test_dims_extracted_from_bench_cfg(self):
        cfg = make_bench_cfg(all_vars=[SweepCfg.param.theta, SweepCfg.param.offset])
        dims = DimsCfg(cfg)
        assert dims.dims_name == ["theta", "offset"]
        assert dims.dims_size == [4, 3]
        assert dims.dim_ranges_index == [[0, 1, 2, 3], [0, 1, 2]]
        assert list(dims.coords.keys()) == ["theta", "offset"]
        assert len(dims.coords["theta"]) == 4
