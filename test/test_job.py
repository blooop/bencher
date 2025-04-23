import multiprocessing

# Set the start method to 'spawn' to avoid fork-related warnings and potential deadlocks
if hasattr(multiprocessing, "set_start_method"):
    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        # Method might already be set
        pass

import unittest
import bencher as bch
import random
from bencher.job import JobFunctionCache

from hypothesis import given, strategies as st, settings


class CachedParamExample(bch.CachedParams):
    var1 = bch.FloatSweep(default=0, bounds=[0, 10])
    var2 = bch.IntSweep(default=10, bounds=[0, 10])

    result = bch.ResultVar()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.result = self.var1 + self.var2 + random.uniform(0, 1)
        return self.get_results_values_as_dict()


class TestJob(unittest.TestCase):
    @settings(deadline=None)  # Setting deadline=None due to variable timing with 'spawn' method
    @given(st.sampled_from([bch.Executors.SERIAL, bch.Executors.MULTIPROCESSING]))
    def test_basic(self, executor):
        cp = CachedParamExample()  # clears cache by default

        jc = JobFunctionCache(cp.__call__, executor=executor, cache_name="test_cache")
        jc.clear_cache()

        res1 = jc.call(var1=1).result()
        res2 = jc.call(var1=1).result()
        res3 = jc.call(var1=2).result()
        res4 = jc.call(var2=2).result()

        # will only be equal if cache is used because of the randomness
        self.assertEqual(res1["result"], res2["result"])
        self.assertNotEqual(res1["result"], res3["result"], f"{res1}")
        self.assertNotEqual(res1["result"], res4["result"], f"{res1}")

        # create new class, make sure it has the same results
        cp2 = CachedParamExample()
        jc2 = JobFunctionCache(cp2.__call__, executor=executor, cache_name="test_cache")
        res1cp2 = jc2.call(var1=1).result()
        self.assertEqual(res1["result"], res1cp2["result"])

        # create cache with a different name and check it does not have the same results
        cp3 = CachedParamExample()
        jc3 = JobFunctionCache(cp3.__call__, executor=executor, cache_name="test_cache2")
        res1cp3 = jc3.call(var1=1).result()
        self.assertNotEqual(res1["result"], res1cp3["result"])

    @settings(
        deadline=3000
    )  # Increased from 2000ms to 3000ms to accommodate slower 'spawn' startup
    @given(st.sampled_from([bch.Executors.SERIAL, bch.Executors.MULTIPROCESSING]))
    def test_overwrite(self, executor):
        cp = CachedParamExample()  # clears cache by default

        jc = JobFunctionCache(cp.__call__, executor=executor, cache_name="test_cache1")
        jc.clear_cache()

        res1 = jc.call(var1=1).result()

        self.assertEqual(jc.worker_wrapper_call_count, 1)
        self.assertEqual(jc.worker_cache_call_count, 0)
        self.assertEqual(jc.worker_fn_call_count, 1)

        jc.clear_call_counts()
        res2 = jc.call(var1=1).result()

        self.assertEqual(jc.worker_wrapper_call_count, 1)
        self.assertEqual(jc.worker_cache_call_count, 1)
        self.assertEqual(jc.worker_fn_call_count, 0)

        self.assertEqual(res1["result"], res2["result"])

        jc.clear_call_counts()
        jc.overwrite = True
        res3 = jc.call(var1=1).result()
        self.assertEqual(jc.worker_wrapper_call_count, 1)
        self.assertEqual(jc.worker_cache_call_count, 0)
        self.assertEqual(jc.worker_fn_call_count, 1)

        self.assertNotEqual(res1["result"], res3["result"], f"{res1}")

    @settings(deadline=None)  # Setting deadline=None due to variable timing with 'spawn' method
    @given(st.sampled_from([bch.Executors.SERIAL, bch.Executors.MULTIPROCESSING]))
    def test_bench_runner_parallel(self, executor):
        run_cfg = bch.BenchRunCfg()
        run_cfg.overwrite_sample_cache = True
        run_cfg.executor = executor
        bench_run = bch.BenchRunner("test_bench_runner", run_cfg=run_cfg)

        bench_run.add_bench(CachedParamExample())

        bench_run.run(level=2)


if __name__ == "__main__":
    TestJob().test_bench_runner_parallel(True).report.show()
