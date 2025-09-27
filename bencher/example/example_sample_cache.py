import bencher as bch


class UnreliableClass(bch.ParametrizedSweep):
    """This class helps demonstrate benchmarking a function that sometimes crashes during sampling.  By using BenchRunCfg.cache_samples you can store the results of every call to the benchmark function so data is not lost in the event of a crash.  However, because cache invalidation is hard (https://martinfowler.com/bliki/TwoHardThings.html) you need to be mindful of how you could get bad results due to incorrect cache data.  For example if you change your benchmark function and use the sample cache you will not get correct values; you will need to use BenchRunCfg.clear_sample_cache to purge any out of date results."""

    input_val = bch.IntSweep(
        default=0,
        bounds=[0, 3],
        doc="If check limit=True the crashy_fn will crash if this value is >1",
    )
    return_value = bch.ResultVar(
        units="ul",
        doc="This is a dummy result variable. In this example, it is the same as the value passed in.",
    )
    trigger_crash = bch.ResultVar(
        units="True/False",
        doc="if true crashy_fn will crash when input_val >1",
    )

    def crashy_fn(self, input_val: int = 0, **kwargs) -> float:  # pylint: disable=unused-argument
        if self.trigger_crash:
            if input_val > 1:
                raise RuntimeError("I crashed for no good reason ;P")

        return {"return_value": input_val, "trigger_crash": self.trigger_crash}


def example_sample_cache(
    run_cfg: bch.BenchRunCfg = None,
    report: bch.BenchReport = None,
    trigger_crash: bool = False,
) -> bch.Bench:
    """This example shows how to use the cache_samples option to deal with unreliable functions and to continue benchmarking using previously calculated results even if the code crashed during the run

    Args:
        run_cfg (BenchRunCfg): configuration of how to perform the param sweep
        trigger_crash: (bool): Turn on/off code to artificially trigger a crash

    Returns:
        Bench: results of the parameter sweep
    """

    instance = UnreliableClass()
    instance.trigger_crash = trigger_crash

    bencher = bch.Bench("example_sample_cache", instance.crashy_fn, run_cfg=run_cfg, report=report)

    bencher.plot_sweep(
        title="Example Crashy Function with the sample_cache",
        input_vars=[UnreliableClass.param.input_val],
        result_vars=[UnreliableClass.param.return_value, UnreliableClass.param.trigger_crash],
        description="""This example shows how to use the cache_samples option to deal with unreliable functions and to continue benchmarking using previously calculated results even if the code crashed during the run""",
        run_cfg=run_cfg,
        post_description="The input_val vs return value graph is a straight line as expected and there is no record of the fact the benchmark crashed halfway through. The second graph shows that for values >1 the trigger_crash value had to be 0 in order to proceed",
    )
    return bencher


if __name__ == "__main__":
    ex_run_cfg = bch.BenchRunCfg()
    ex_run_cfg.repeats = 1
    ex_run_cfg.executor = bch.Executors.SCOOP

    # this will store the result of of every call to crashy_fn
    ex_run_cfg.cache_samples = True
    ex_run_cfg.clear_sample_cache = True

    try:
        # this will crash after iteration 2 because we are checking the crash_threshold >1.  We don't want to lose those (potentially expensive to calculate) datapoints so they are stored in the sample_cache
        example_sample_cache(ex_run_cfg, trigger_crash=True)
    except RuntimeError as e:
        print(f"caught the exception {e}")

    print(
        "Running the same benchmark but without checking the limit.  The benchmarking should load the previously calculated values and continue to finish calculating the values that were missed due to the crash"
    )
    ex_run_cfg.clear_sample_cache = False
    example_sample_cache(ex_run_cfg, trigger_crash=False)

    ex_run_cfg.repeats = 2

    example_sample_cache(ex_run_cfg, trigger_crash=False).report.show()

    # see the test_sample_cache for a more detailed explanation of the mechanisms of the cache
