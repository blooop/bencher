import os
import subprocess
import pytest
import unittest
import random
from shutil import rmtree
from copy import deepcopy
import logging

from hypothesis import given, settings, strategies as st

from datetime import datetime
from diskcache import Cache

from bencher.example.benchmark_data import ExampleBenchCfg
from bencher import Bench, BenchCfg, BenchRunCfg


def get_hash_isolated_process() -> bytes:
    """This sets up bencher in a new process and prints a hash of the input config to the terminal which is then returned by this function.  The purpose is to set up bench from two different python process and make sure the hashes match"""
    result = subprocess.run(
        [
            "python3",
            "-c",
            "'from bencher.example.benchmark_data import ExampleBenchCfg;import bencher as bch;cfg1 = bch.BenchCfg(input_vars=[ExampleBenchCfg.param.theta, ExampleBenchCfg.param.noise_distribution],result_vars=[ExampleBenchCfg.param.out_sin],const_vars=[ExampleBenchCfg.param.noisy],repeats=5,over_time=False);print(cfg1.hash_persistent())'",
        ],
        stdout=subprocess.PIPE,
        check=False,
    )
    return result.stdout


def clear_autofig_folder() -> None:
    try:
        rmtree("autofig")
    except FileNotFoundError as e:
        logging.debug(e)
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
            repeats=repeats,
            over_time=over_time,
            clear_history=True,  # should not affect hash
            auto_plot=False,
        )

        cfg2 = BenchCfg(
            title="test_bencher_hash",
            input_vars=deepcopy(input_vars),
            result_vars=deepcopy(result_vars),
            const_vars=deepcopy(const_vars),
            repeats=repeats,
            over_time=over_time,
            clear_history=False,  # should not affect hash
            auto_plot=False,
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
                    repeats=2,
                    over_time=True,
                    clear_history=i == 0,
                    print_pandas=False,
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
                repeats=repeats,
                print_pandas=False,
                over_time=False,
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
                repeats=repeats,
                print_pandas=False,
                use_optuna=True,
            ),
        )

    # TODO There are still name collisions when run on all possible inputs, but at the moment the name collisions end up plotting an identical graph anyway so it doesn't matter that much. Future work is to enable this test to confirm that all graph names are fully unique even if they have the same pixels.
    @pytest.mark.skip()
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
                        repeats=2,
                        over_time=True,
                        clear_history=i == 0,
                        print_pandas=False,
                        auto_plot=False,
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
                    repeats=repeats,
                    over_time=False,
                    auto_plot=False,
                ),
            )

        bench_cfg.raise_duplicate_exception = False
        with Cache("unique_names") as name_cache:
            bench_repr = bench_cfg.__repr__()
            plots = bench_cfg.to_auto_plots()
            for p in plots:
                if p.name is not None:
                    if p.name in name_cache:
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
                over_time=over_time, clear_cache=True, clear_history=True, auto_plot=False
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
            run_cfg=BenchRunCfg(over_time=over_time, cache_results=False, auto_plot=False),
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
            run_cfg=BenchRunCfg(over_time=over_time, cache_results=True, auto_plot=False),
        )
        self.assertEqual(
            bench2.sample_cache.worker_wrapper_call_count, ExampleBenchCfg.param.theta.samples
        )

    @settings(deadline=10000)
    @given(noisy=st.booleans())
    def test_const_hashing(self, noisy) -> None:
        """check that const variables are hashed correctly. This test was created because setting a const variable was resulting in a hash value that changed over time even though the inputs were not changing.  The source of the problem was that the input config had a native param instead of a paramSweep object.  The native param objects don't have a constant hash because they include the .name field which changes for every instance of the param.  the paramSweep objects have the .name field removed from the hash so that hashes for the same inputs remain constant"""

        ExampleBenchCfg.param.theta.samples = 5

        logging.info(f"starting with const value noisy:{noisy}")

        bench = self.create_bench()

        # run without caching and make sure any old caches are cleared
        bench.plot_sweep(
            title="test_const_hashing",
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            const_vars=[
                (ExampleBenchCfg.param.noisy, noisy),
            ],
            run_cfg=BenchRunCfg(clear_cache=True, clear_history=True, auto_plot=False),
        )
        self.assertEqual(
            bench.sample_cache.worker_wrapper_call_count,
            ExampleBenchCfg.param.theta.samples,
            "no cache used so the function should sample again",
        )
        logging.info("re-run and attempt to load from cache")

        bench2 = self.create_bench()
        # run again without caching, the function should be called again
        bench2.plot_sweep(
            title="test_const_hashing",
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            const_vars=[
                (ExampleBenchCfg.param.noisy, noisy),
            ],
            run_cfg=BenchRunCfg(cache_results=True, auto_plot=False),
        )
        # the result should be cached so the call count should be the same as before
        self.assertEqual(
            bench2.sample_cache.worker_wrapper_call_count,
            0,
            "the worker should not be sampled as it should be loaded from the cache",
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
