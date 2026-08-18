from bencher.bench_cfg import CacheCfg, DisplayCfg, VisualizationCfg
import logging
import os
import random
import subprocess
import unittest
from copy import deepcopy
from datetime import datetime
from shutil import rmtree

import pytest
from diskcache import Cache
from hypothesis import given, settings
from hypothesis import strategies as st

from bencher import Bench, BenchCfg, BenchRunCfg
from bencher.example.benchmark_data import ExampleBenchCfg

logger = logging.getLogger(__name__)


def get_hash_isolated_process() -> bytes:
    """This sets up bencher in a new process and prints a hash of the input config to the terminal which is then returned by this function.  The purpose is to set up bench from two different python process and make sure the hashes match"""
    result = subprocess.run(
        [
            "python3",
            "-c",
            "'from bencher.example.benchmark_data import ExampleBenchCfg;import bencher as bn;cfg1 = bn.BenchCfg(input_vars=[ExampleBenchCfg.param.theta, ExampleBenchCfg.param.noise_distribution], result_vars=[ExampleBenchCfg.param.out_sin], const_vars=[ExampleBenchCfg.param.noisy], execution=bn.ExecutionCfg(repeats=5), time=bn.TimeCfg(over_time=False));print(cfg1.hash_persistent())'",
        ],
        stdout=subprocess.PIPE,
        check=False,
    )
    return result.stdout


def clear_autofig_folder() -> None:
    try:
        rmtree("autofig")
    except FileNotFoundError as e:
        logger.debug(e)
    os.mkdir("autofig")


# at the beginning of the test delete all the figures in the autofig folder.  At the end of the test they should be replaced with pixel perfect figures.  If the git repo is dirty at the end of the tests then CI will fail.
clear_autofig_folder()

# at the beginning of the tests clear the cache that checks for unique names
with Cache("unique_names") as c:
    c.clear()


# define a set of input variables that are used across multiple tests.  These configurations are
input_var_cat_permutations = [
    [ExampleBenchCfg.param.postprocess_fn],
    [ExampleBenchCfg.param.postprocess_fn, ExampleBenchCfg.param.noisy],
    [
        ExampleBenchCfg.param.postprocess_fn,
        ExampleBenchCfg.param.noisy,
        ExampleBenchCfg.param.noise_distribution,
    ],
]

# set up float variable permutations
input_var_float_permutations = [
    [ExampleBenchCfg.param.theta],
    [ExampleBenchCfg.param.theta, ExampleBenchCfg.param.postprocess_fn],
]

input_var_cat_float_permutations = input_var_cat_permutations + input_var_float_permutations

# Generating figures for the None case has some edge cases so make a separate variable to make it easier to debug
input_var_and_none_permutations = [] + input_var_cat_permutations

result_var_permutations = [
    [ExampleBenchCfg.param.out_sin],
    [ExampleBenchCfg.param.out_sin, ExampleBenchCfg.param.out_cos],
]


class TestBencher(unittest.TestCase):
    def setUp(self) -> None:
        # ExampleBenchCfg.param.theta is a *class-level* param shared by the whole
        # suite, and test_const_hashing overwrites `samples`. Restoring it in tearDown
        # rather than via addCleanup because that test is hypothesis-driven: the body
        # runs once per example, so a cleanup registered inside it would capture the
        # already-mutated value on every example after the first.
        self._theta_samples = ExampleBenchCfg.param.theta.samples

    def tearDown(self) -> None:
        ExampleBenchCfg.param.theta.samples = self._theta_samples

    def create_bench(self) -> Bench:
        return Bench("test_bencher", ExampleBenchCfg())

    @settings(deadline=10000)
    @given(
        input_vars=st.sampled_from(
            [
                [ExampleBenchCfg.param.theta],
                [ExampleBenchCfg.param.postprocess_fn],
                [ExampleBenchCfg.param.theta, ExampleBenchCfg.param.postprocess_fn],
            ]
        ),
        result_vars=st.sampled_from(result_var_permutations),
        const_vars=st.sampled_from([[]]),
        repeats=st.sampled_from([1, 2]),
        over_time=st.booleans(),
    )
    def test_bench_cfg_hash(self, input_vars, result_vars, const_vars, repeats, over_time):
        """check that identical inputs result in the same hash even if the object instances are not the same (this does not work by default with param and requires a custom hash function)"""

        cfg1 = BenchCfg(
            title="test_bencher_hash",
            input_vars=deepcopy(input_vars),
            result_vars=deepcopy(result_vars),
            const_vars=deepcopy(const_vars),
            execution=ExecutionCfg(repeats=repeats),
            visualization=VisualizationCfg(auto_plot=False),
            time=TimeCfg(over_time=over_time, clear_history=True),
        )

        cfg2 = BenchCfg(
            title="test_bencher_hash",
            input_vars=deepcopy(input_vars),
            result_vars=deepcopy(result_vars),
            const_vars=deepcopy(const_vars),
            execution=ExecutionCfg(repeats=repeats),
            visualization=VisualizationCfg(auto_plot=False),
            time=TimeCfg(over_time=over_time, clear_history=False),
        )

        self.assertEqual(
            cfg1.hash_persistent(include_repeats=True),
            cfg2.hash_persistent(include_repeats=True),
        )

    def test_bench_cfg_hash_isolated(self):
        """hash values only seem to not match if run in a separate process, so run the hash test in separate processes"""
        self.assertEqual(get_hash_isolated_process(), get_hash_isolated_process())

    # @pytest.mark.skip
    @settings(deadline=30000)
    @given(
        input_vars=st.sampled_from(input_var_cat_permutations),
        result_vars=st.sampled_from([[ExampleBenchCfg.param.out_sin]]),
    )
    def test_combinations_over_time(self, input_vars, result_vars) -> None:
        """check that up to 3 categorical values over time can be plotted"""
        # needed her instead of init because hypothesis calls this function multiple times after init() and the randomly generated data need to be the same each time to produce identical results to match the hand check plot images
        random.seed(42)
        bench = self.create_bench()
        for i in range(2):
            bench.plot_sweep(
                title="test_combinations_over_time",
                input_vars=input_vars,
                result_vars=result_vars,
                run_cfg=BenchRunCfg(
                    execution=ExecutionCfg(repeats=2),
                    display=DisplayCfg(print_pandas=False),
                    time=TimeCfg(over_time=True, clear_history=i == 0),
                ),
                time_src=datetime(1970, 1, i + 1),  # repeatable time
            )

    # @pytest.mark.skip
    @settings(deadline=10000)
    @given(
        input_vars=st.sampled_from(input_var_cat_permutations),
        result_vars=st.sampled_from(
            [[ExampleBenchCfg.param.out_sin, ExampleBenchCfg.param.out_cos]]
        ),
        repeats=st.sampled_from([20]),
        # repeats=st.sampled_from([1, 2]), #TODO this fails at the moment
    )
    def test_combinations(self, input_vars, result_vars, repeats) -> None:
        """check that up to 3 categorical and 1 float value without time can be plotted"""
        # needed her instead of init because hypothesis calls this function multiple times after init() and the randomly generated data need to be the same each time to produce identical results to match the hand check plot images
        random.seed(42)
        bench = self.create_bench()
        bench.plot_sweep(
            title="test_combinations",
            input_vars=input_vars,
            result_vars=result_vars,
            run_cfg=BenchRunCfg(
                execution=ExecutionCfg(repeats=repeats),
                display=DisplayCfg(print_pandas=False),
                time=TimeCfg(over_time=False),
            ),
        )

    @settings(deadline=10000)
    @given(
        input_vars=st.sampled_from([[ExampleBenchCfg.param.theta, ExampleBenchCfg.param.offset]]),
        result_vars=st.sampled_from(
            [[ExampleBenchCfg.param.out_sin, ExampleBenchCfg.param.out_cos]]
        ),
        repeats=st.sampled_from([2]),
    )
    def test_pareto(self, input_vars, result_vars, repeats) -> None:
        """check that pareto optimisation works"""
        # needed her instead of init because hypothesis calls this function multiple times after init() and the randomly generated data need to be the same each time to produce identical results to match the hand check plot images
        random.seed(42)
        bench = self.create_bench()
        bench.plot_sweep(
            title="test_pareto_opt",
            input_vars=input_vars,
            result_vars=result_vars,
            run_cfg=BenchRunCfg(
                execution=ExecutionCfg(repeats=repeats),
                display=DisplayCfg(print_pandas=False),
                visualization=VisualizationCfg(use_optuna=True),
            ),
        )

    @pytest.mark.skip(
        reason="name collisions across input permutations; see plans/05-test-coverage.md task 4"
    )
    @settings(deadline=10000)
    @given(
        input_vars=st.sampled_from(input_var_cat_permutations),
        result_vars=st.sampled_from(result_var_permutations),
        repeats=st.sampled_from([2]),
        # repeats=st.sampled_from([1, 2]), #TODO this fails at the moment
        over_time=st.booleans(),
    )
    def test_unique_file_names(self, input_vars, result_vars, repeats, over_time):
        """This tests that every single plot has a unique but meaningful (not just a hash) name."""
        bench = self.create_bench()
        if over_time:
            for i in range(3):
                bench_cfg = bench.plot_sweep(
                    title="test_unique_filenames",
                    input_vars=input_vars,
                    result_vars=result_vars,
                    run_cfg=BenchRunCfg(
                        execution=ExecutionCfg(repeats=2),
                        display=DisplayCfg(print_pandas=False),
                        visualization=VisualizationCfg(auto_plot=False),
                        time=TimeCfg(over_time=True, clear_history=i == 0),
                    ),
                    time_src=datetime(
                        1970, 1, i + 1
                    ),  # repeatable time so outputs are same at the pixel level
                )

        else:
            bench_cfg = bench.plot_sweep(
                title="test_unique_filenames",
                input_vars=input_vars,
                result_vars=result_vars,
                run_cfg=BenchRunCfg(
                    execution=ExecutionCfg(repeats=repeats),
                    visualization=VisualizationCfg(auto_plot=False),
                    time=TimeCfg(over_time=False),
                ),
            )

        with Cache("unique_names") as name_cache:
            bench_repr = bench_cfg.__repr__()
            plots = bench_cfg.to_auto_plots()
            for p in plots:
                if p.name is not None and p.name in name_cache:
                    self.fail(
                        f"this name already exists: \n\n\nA:{p.name}\n\n\nreprA:{bench_cfg.__repr__()}\n\n\nB:{name_cache[p.name]}",
                    )
                name_cache[p.name] = bench_cfg.__repr__()
            name_cache[bench_repr] = True

    @settings(deadline=10000)
    @given(
        over_time=st.booleans(),
    )
    def test_benching_cache_without_time(self, over_time) -> None:
        """check that the correct benching cache loads"""

        # set up inputs and results that are shared across runs
        title = "test_benching_cache"
        iv = [ExampleBenchCfg.param.theta]
        rv = [ExampleBenchCfg.param.out_sin]

        bench = self.create_bench()

        # run without caching and make sure any old caches are cleared
        bench.plot_sweep(
            title=title,
            input_vars=iv,
            result_vars=rv,
            run_cfg=BenchRunCfg(
                cache=CacheCfg(clear=True),
                visualization=VisualizationCfg(auto_plot=False),
                time=TimeCfg(over_time=over_time, clear_history=True),
            ),
        )

        self.assertEqual(
            bench.sample_cache.worker_wrapper_call_count, ExampleBenchCfg.param.theta.samples
        )

        bench2 = self.create_bench()
        # run again without caching, the function should be called again
        bench2.plot_sweep(
            title=title,
            input_vars=iv,
            result_vars=rv,
            run_cfg=BenchRunCfg(
                cache=CacheCfg(results=False),
                visualization=VisualizationCfg(auto_plot=False),
                time=TimeCfg(over_time=over_time),
            ),
        )
        self.assertEqual(
            bench2.sample_cache.worker_wrapper_call_count, ExampleBenchCfg.param.theta.samples
        )

        # bench3 = self.create_bench()
        # run again with the cache turned on. The worker_wrapper_call_count should not increase because it loads cached results
        bench2.plot_sweep(
            title=title,
            input_vars=iv,
            result_vars=rv,
            run_cfg=BenchRunCfg(
                cache=CacheCfg(results=True),
                visualization=VisualizationCfg(auto_plot=False),
                time=TimeCfg(over_time=over_time),
            ),
        )
        self.assertEqual(
            bench2.sample_cache.worker_wrapper_call_count, ExampleBenchCfg.param.theta.samples
        )

    @settings(deadline=10000)
    @given(noisy=st.booleans())
    def test_const_hashing(self, noisy) -> None:
        """check that const variables are hashed correctly. This test was created because setting a const variable was resulting in a hash value that changed over time even though the inputs were not changing.  The source of the problem was that the input config had a native param instead of a paramSweep object.  The native param objects don't have a constant hash because they include the .name field which changes for every instance of the param.  the paramSweep objects have the .name field removed from the hash so that hashes for the same inputs remain constant"""

        # Restored by tearDown. Left unrestored this leaked samples=5 into every later
        # test relying on the default of 30 -- unnoticed because the assertions that
        # would have caught it compare `result_samples()`, which returned an xr.Dataset
        # whose `bool()` is always True (plan 23 P12).
        ExampleBenchCfg.param.theta.samples = 5

        logger.info(f"starting with const value noisy:{noisy}")

        bench = self.create_bench()

        # run without caching and make sure any old caches are cleared
        bench.plot_sweep(
            title="test_const_hashing",
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            const_vars=[
                (ExampleBenchCfg.param.noisy, noisy),
            ],
            run_cfg=BenchRunCfg(
                cache=CacheCfg(clear=True),
                visualization=VisualizationCfg(auto_plot=False),
                time=TimeCfg(clear_history=True),
            ),
        )
        self.assertEqual(
            bench.sample_cache.worker_wrapper_call_count,
            ExampleBenchCfg.param.theta.samples,
            "no cache used so the function should sample again",
        )
        logger.info("re-run and attempt to load from cache")

        bench2 = self.create_bench()
        # run again without caching, the function should be called again
        bench2.plot_sweep(
            title="test_const_hashing",
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            const_vars=[
                (ExampleBenchCfg.param.noisy, noisy),
            ],
            run_cfg=BenchRunCfg(
                cache=CacheCfg(results=True), visualization=VisualizationCfg(auto_plot=False)
            ),
        )
        # the result should be cached so the call count should be the same as before
        self.assertEqual(
            bench2.sample_cache.worker_wrapper_call_count,
            0,
            "the worker should not be sampled as it should be loaded from the cache",
        )

    def test_const_vars_hash_chains_accumulated_hash(self) -> None:
        """Const vars hashing must chain the accumulated hash_val, not overwrite it.

        Two configs that differ only in input_vars but share the same const_vars must
        produce different hashes. Without chaining, the const_vars loop overwrites hash_val
        and the difference in input_vars is lost.
        """
        cfg_a = BenchCfg(
            title="test_chain",
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            const_vars=[(ExampleBenchCfg.param.noisy, True)],
            visualization=VisualizationCfg(auto_plot=False),
        )
        cfg_b = BenchCfg(
            title="test_chain",
            input_vars=[ExampleBenchCfg.param.theta, ExampleBenchCfg.param.noise_distribution],
            result_vars=[ExampleBenchCfg.param.out_sin],
            const_vars=[(ExampleBenchCfg.param.noisy, True)],
            visualization=VisualizationCfg(auto_plot=False),
        )
        self.assertNotEqual(
            cfg_a.hash_persistent(include_repeats=True),
            cfg_b.hash_persistent(include_repeats=True),
            "Configs with different input_vars but same const_vars must have different hashes",
        )

    def test_forgetting_to_use_param(self) -> None:
        bench = self.create_bench()

        with self.assertRaises(TypeError):
            bench.plot_sweep(
                title="test_param_usage",
                input_vars=[ExampleBenchCfg.param.theta],
                result_vars=[ExampleBenchCfg.out_sin],  # forgot to use param here
            )

        with self.assertRaises(TypeError):
            bench.plot_sweep(
                title="test_param_usage",
                input_vars=[ExampleBenchCfg.theta],  # forgot to use param here
                result_vars=[ExampleBenchCfg.param.out_sin],
            )

        with self.assertRaises(TypeError):
            bench.plot_sweep(
                title="test_param_usage",
                input_vars=[ExampleBenchCfg.param.theta],
                result_vars=[ExampleBenchCfg.param.out_sin],
                const_vars=[(ExampleBenchCfg.offset, 0.1)],  # forgot to use param here
            )

    def test_cache_size_propagation(self) -> None:
        """Check that cache_size from BenchRunCfg propagates to bench internals."""
        bench = self.create_bench()
        cache_size_mb = 500
        expected_bytes = cache_size_mb * 1_000_000

        bench.plot_sweep(
            title="test_cache_size",
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=BenchRunCfg(
                cache=CacheCfg(size_mb=cache_size_mb),
                visualization=VisualizationCfg(auto_plot=False),
            ),
        )

        self.assertEqual(bench.cache_size, expected_bytes)
        self.assertEqual(bench._executor.cache_size, expected_bytes)  # pylint: disable=protected-access
        self.assertEqual(bench._collector.cache_size, expected_bytes)  # pylint: disable=protected-access
        self.assertEqual(
            bench._executor.sample_cache.size_limit,  # pylint: disable=protected-access
            expected_bytes,
        )


class TestBenchRunCfgWithDefaults(unittest.TestCase):
    """Tests for BenchRunCfg.with_defaults merging behavior."""

    def test_none_creates_fresh_instance(self):
        cfg = BenchRunCfg.with_defaults(None, execution=dict(repeats=5, subsampling_divisions=4))
        self.assertEqual(cfg.execution.repeats, 5)
        self.assertEqual(cfg.execution.subsampling_divisions, 4)

    def test_defaults_applied_to_param_default_fields(self):
        cfg = BenchRunCfg()
        cfg = BenchRunCfg.with_defaults(cfg, execution=dict(repeats=5, subsampling_divisions=4))
        self.assertEqual(cfg.execution.repeats, 5)
        self.assertEqual(cfg.execution.subsampling_divisions, 4)

    def test_caller_set_fields_not_overwritten(self):
        cfg = BenchRunCfg(execution=ExecutionCfg(repeats=10))
        cfg = BenchRunCfg.with_defaults(cfg, execution=dict(repeats=5, subsampling_divisions=4))
        self.assertEqual(cfg.execution.repeats, 10)  # caller's value preserved
        self.assertEqual(cfg.execution.subsampling_divisions, 4)  # default still applied

    def test_multiple_defaults_in_one_call(self):
        cfg = BenchRunCfg(execution=ExecutionCfg(subsampling_divisions=2))
        cfg = BenchRunCfg.with_defaults(
            cfg, execution=dict(repeats=3, subsampling_divisions=7, headless=True)
        )
        self.assertEqual(cfg.execution.repeats, 3)  # was at default, so applied
        self.assertEqual(cfg.execution.subsampling_divisions, 2)  # caller set, so preserved
        self.assertTrue(cfg.execution.headless)  # was at default, so applied

    def test_does_not_mutate_original(self):
        original = BenchRunCfg()
        original_repeats = original.execution.repeats
        result = BenchRunCfg.with_defaults(original, execution=dict(repeats=99))
        self.assertEqual(result.execution.repeats, 99)
        self.assertEqual(original.execution.repeats, original_repeats)  # unchanged
        self.assertIsNot(result, original)

    def test_unknown_key_raises(self):
        with self.assertRaises(ValueError, msg="Unknown BenchRunCfg parameter"):
            BenchRunCfg.with_defaults(None, not_a_real_param=42)
