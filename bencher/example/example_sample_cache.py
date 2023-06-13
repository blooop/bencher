import bencher as bch


class UnreliableClass(bch.ParametrizedSweep):
    """This class helps demonstrated benchmarking a function that sometimes crashes during sampling.  By using BenchRunCfg.use_sample_cache you can store the results of every call to the benchmark function so data is not lost in the event of a crash.  However because cache invalidation is hard (https://martinfowler.com/bliki/TwoHardThings.html) you need to be mindful of how you could get bad results due to incorrect cache data.  I.e if you change your benchmark function and use the sample cache you will not get correct values.  You will need to use BenchRunCfg.clear_sample_cache to purge any out of date results."""

    input_val = bch.IntSweep(
        default=0,
        bounds=[0, 3],
        doc="If check limit=True the crashy_fn will crash if this value is >1",
    )
    return_value = bch.ResultVar(
        units="ul",
        doc="This is a dummy result variable. In this example it is the same as the value passed in.",
    )
    trigger_crash = bch.ResultVar(
        units="True/False",
        doc="In the example the first time the benchmark is run we set the value to 0.  After the code crashes the value is set to 1. The plots show the values >1 are calculated on the second attempt",
    )

    def crashy_fn(self, input_val: int = 0, **kwargs) -> float:  # pylint-ignore W0613
        if self.trigger_crash:
            if input_val > 1:
                raise RuntimeError("I crashed for no good reason ;P")

        return {"return_value": input_val, "trigger_crash": self.trigger_crash}


def example_sample_cache(run_cfg: bch.BenchRunCfg, trigger_crash: bool) -> bch.Bench:
    """This example shows how to use the use_sample_cache option to deal with unreliable functions and to continue benchmarking using previously calculated results even if the code crashing during the run

    Args:
        run_cfg (BenchRunCfg): configuration of how to perform the param sweep
        trigger_crash: (bool): Turn on/off code to artificially trigger a crash

    Returns:
        Bench: results of the parameter sweep
    """

    instance = UnreliableClass()
    instance.trigger_crash = trigger_crash

    bencher = bch.Bench("example_sample_cache", instance.crashy_fn)

    bencher.plot_sweep(
        title="Example Crashy Function with the sample_cache",
        input_vars=[UnreliableClass.param.input_val],
        result_vars=[UnreliableClass.param.return_value, UnreliableClass.param.trigger_crash],
        description="""This example shows how to use the use_sample_cache option to deal with unreliable functions and to continue benchmarking using previously calculated results even if the code crashing during the run""",
        run_cfg=run_cfg,
        post_description="The input_val vs return value graph is a straigh line as expected and there is no record of the fact the benchmark crashed halfway through. The second graph shows that for values >1 the trigger_crash value had to be 0 in order to proceed",
    )
    return bencher


if __name__ == "__main__":
    ex_run_cfg = bch.BenchRunCfg()
    ex_run_cfg.repeats = 1

    ex_run_cfg.use_sample_cache = True  # this will store the result of of every call to crashy_fn
    ex_run_cfg.clear_sample_cache = True

    try:
        # this will crash after iteration 2 because we are checking the crash_threshold >1.  We don't want to lose those (potentially expensive to calculate) datapoints so they are stored in the sample_cache
        example_sample_cache(ex_run_cfg, trigger_crash=True)
    except RuntimeError as e:
        print(f"caught the exception {e}")

    print(
        "Running the same benchmark but without checking the limit.  The benchmarking should load the previously calculated values and continue to finish calculate the values that were missed due to the crash"
    )
    ex_run_cfg.clear_sample_cache = False
    example_sample_cache(ex_run_cfg, trigger_crash=False)

    ex_run_cfg.repeats = 2

    bencher = example_sample_cache(ex_run_cfg, trigger_crash=False)
