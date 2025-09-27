from enum import auto

from strenum import StrEnum

import bencher as bch


class ExampleEnum(StrEnum):
    value_1 = auto()
    value_2 = auto()
    # value3 = auto()
    # value4 = auto()


class Cfg(bch.ParametrizedSweep):
    enum1 = bch.EnumSweep(ExampleEnum)
    result = bch.ResultVar()

    # def __call__(self,**kwargs) -> Any:
    #     self.update_params_from_kwargs(**kwargs)
    #     self.result = float(str(self.enum1)[-1])
    #     return self.get_results_values_as_dict()


def bench_function(cfg: Cfg):
    return {"result": float(str(cfg.enum1)[-1])}


def print_assert_equal(msg, first, second):
    print(f"{msg} {first}=={second}")
    assert first == second


def assert_call_counts(bencher, run_cfg, wrapper_calls=-1, fn_calls=-1, cache_calls=-1):
    print_assert_equal(
        "worker wrapper call count",
        bencher.sample_cache.worker_wrapper_call_count,
        wrapper_calls * run_cfg.repeats,
    )
    print_assert_equal(
        "worker fn call count",
        bencher.sample_cache.worker_fn_call_count,
        fn_calls * run_cfg.repeats,
    )
    print_assert_equal(
        "worker cache call count",
        bencher.sample_cache.worker_cache_call_count,
        cache_calls * run_cfg.repeats,
    )


def example_cache_context() -> bch.Bench:
    run_cfg = bch.BenchRunCfg()
    run_cfg.cache_samples = True
    run_cfg.only_hash_tag = True
    run_cfg.repeats = 2
    run_cfg.parallel = False

    bencher = bch.Bench("bench_context", bench_function, Cfg, run_cfg=run_cfg)

    # clear all tags from the cache at the beginning so that the example works the same not matter how many times the example is run.  When using this for you own code you probably don't want to clear the cache at the beginning because you will lose all the data you collected.
    bencher.clear_tag_from_sample_cache("example_tag1", run_cfg)
    bencher.clear_tag_from_sample_cache("example_tag2", run_cfg)

    # run a benchmark with a constant value and save results with example_tag1
    bencher.plot_sweep(
        title="Benchmark enum=value_1",
        const_vars=[Cfg.param.enum1.with_const(ExampleEnum.value_1)],
        result_vars=[Cfg.param.result],
        tag="example_tag1",
    )

    # there are not values in the cache, so we expect 1 fn call and 0 cache calls
    assert_call_counts(bencher, run_cfg, wrapper_calls=1, fn_calls=1, cache_calls=0)

    # now run another benchmark with the same tag but a different value
    bencher.clear_call_counts()
    bencher.plot_sweep(
        title="Benchmark enum=value_2",
        const_vars=[Cfg.param.enum1.with_const(ExampleEnum.value_2)],
        result_vars=[Cfg.param.result],
        tag="example_tag1",
    )

    # these values have not been calculated before so there should be 1 fn call
    assert_call_counts(bencher, run_cfg, wrapper_calls=1, fn_calls=1, cache_calls=0)

    # now create a new benchmark that calculates the values of the previous two benchmarks. The tag is the same so those values will be loaded from the cache instead of getting calculated again
    bencher.clear_call_counts()
    bencher.plot_sweep(
        title="Benchmark enum=[value_1,value_2] combined",
        input_vars=[Cfg.param.enum1],
        result_vars=[Cfg.param.result],
        tag="example_tag1",
    )

    # both calls hit the cache.
    assert_call_counts(bencher, run_cfg, wrapper_calls=2, fn_calls=0, cache_calls=2)

    # run the same benchmark as before but use a different tag.  The previously cached values will not be used and fresh values will be calculated instead
    bencher.clear_call_counts()
    bencher.plot_sweep(
        title="Benchmark enum=[value_1,value_2] with different tag",
        input_vars=[Cfg.param.enum1],
        result_vars=[Cfg.param.result],
        tag="example_tag2",
    )

    # Both calls are calculated because the tag is different so they don't hit the cache
    assert_call_counts(bencher, run_cfg, wrapper_calls=2, fn_calls=2, cache_calls=0)

    return bencher


if __name__ == "__main__":
    example_cache_context().report.show()
