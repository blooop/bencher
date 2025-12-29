import unittest
import bencher as bch
from bencher.example.example_sample_cache import UnreliableClass
from bencher.example.example_sample_cache_context import example_cache_context


class TestSampleCache(unittest.TestCase):
    def call_bencher(self, bencher, run_cfg):
        bencher.plot_sweep(
            title="Example Crashy Function with the sample_cache",
            input_vars=[UnreliableClass.param.input_val],
            result_vars=[
                UnreliableClass.param.return_value,
                UnreliableClass.param.trigger_crash,
            ],
            description="""This example shows how to use the cache_samples option to deal with unreliable functions and to continue benchmarking using previously calculated results even if the code crashing during the run""",
            run_cfg=run_cfg,
            post_description="The input_val vs return value graph is a straight line as expected and there is no record of the fact the benchmark crashed halfway through. The second graph shows that for values >1 the trigger_crash value had to be 0 in order to proceed",
            tag="testing_tag3",
        )

    def test_sample_cache(self):
        """The sample cache function needs to be run twice because the first run can pass when there is no cache, but will fail the second time when the cache exists"""
        self.sample_cache()
        self.sample_cache()

    def sample_cache(self):
        run_cfg = bch.BenchRunCfg()
        run_cfg.execution.repeats = 1
        run_cfg.execution.executor = (
            bch.Executors.SERIAL
        )  # THE ASSERTS WILL ONLY WORK IF RUN SERIALLY!!!

        run_cfg.cache.cache_samples = True  # this will store the result of every call
        run_cfg.cache.only_hash_tag = True
        run_cfg.visualization.auto_plot = False

        instance = UnreliableClass()
        instance.trigger_crash = True

        bencher = bch.Bench("example_sample_cache", instance.crashy_fn)
        bencher.clear_tag_from_sample_cache("testing_tag3", run_cfg)

        # the benchmark is set up to clear the previous sample cache and to cache the intermediate results from each benchmark sample.  It will throw an exception because the class has been set up to crash after the 2nd sample
        with self.assertRaises(RuntimeError):
            self.call_bencher(bencher, run_cfg)

        # worker is called 3 times (and crashes on the 3rd), there should be no values in the cache
        self.assertEqual(bencher.sample_cache.worker_wrapper_call_count, 3)
        self.assertEqual(bencher.sample_cache.worker_fn_call_count, 3)
        self.assertEqual(bencher.sample_cache.worker_cache_call_count, 0)

        # now turn off the clearing of the sample cache.  Previously calculated values will be used now

        # turn off the trigger to crash so the remaining values can be calculated
        instance.trigger_crash = False

        # clear the call counts from the previous run
        bencher.clear_call_counts()
        # this will calculate the remaining values
        self.call_bencher(bencher, run_cfg)

        # the wrapped call count should be 4 because there are 4 samples
        self.assertEqual(bencher.sample_cache.worker_wrapper_call_count, 4)
        # the fn_call count should be 2 because 2 values were left uncalculated
        self.assertEqual(bencher.sample_cache.worker_fn_call_count, 2)
        # the cache call count should be 2 because 2 values were successfully calculated last time (3rd one crashed before the result was stored)
        self.assertEqual(bencher.sample_cache.worker_cache_call_count, 2)

        # now increase the number of repeats to 2.  This will use the previously calculated values for repeat 1 and only calculate the new values for repeat=2
        run_cfg.execution.repeats = 2
        bencher.clear_call_counts()
        self.call_bencher(bencher, run_cfg)

        # 4 samples x 2 repeats = 8 calls
        self.assertEqual(bencher.sample_cache.worker_wrapper_call_count, 8)
        # there should be 4 new calls for each point of the sweep for the second repeat
        self.assertEqual(bencher.sample_cache.worker_fn_call_count, 4)
        # the first 4 values from repeat=1 are loaded from the cache
        self.assertEqual(bencher.sample_cache.worker_cache_call_count, 4)

        # create a new benchmark and clear the cache (for this new benchmark only)
        run_cfg.cache.clear_sample_cache = True
        bencher.clear_call_counts()
        bencher.plot_sweep(
            title="new benchmark", result_vars=[UnreliableClass.param.return_value], run_cfg=run_cfg
        )

        # 1 sample x 2 repeats
        self.assertEqual(bencher.sample_cache.worker_wrapper_call_count, 2)
        # 1 sample x 2 repeats which are not in the cache because this is a different benchmark
        self.assertEqual(bencher.sample_cache.worker_fn_call_count, 2)
        # sample cache is cleared so no values from the cache
        self.assertEqual(bencher.sample_cache.worker_cache_call_count, 0)

        # check that the previous benchmark still has the cached values, and that they were not removed by clearing the sample cache of an unrelated benchmark

        run_cfg.cache.clear_sample_cache = False
        bencher.clear_call_counts()
        self.call_bencher(bencher, run_cfg)

        # 4 samples x 2 repeats
        self.assertEqual(bencher.sample_cache.worker_wrapper_call_count, 8)
        # all the results should be in the cache and not been cleared by the previous clear_sample_cache=True call because this is a different benchmark
        self.assertEqual(bencher.sample_cache.worker_fn_call_count, 0)
        # all 8 previously calculated results already in the cache
        self.assertEqual(bencher.sample_cache.worker_cache_call_count, 8)

    def test_sample_cache_context(self):
        """The sample cache function needs to be run twice because the first run can pass when there is no cache, but will fail the second time when the cache exists"""
        example_cache_context()
        example_cache_context()


# TestSampleCache().sample_cache()
