from pathlib import Path
from bencher.variables.singleton_parametrized_sweep import ParametrizedSweepSingleton
import bencher as bch


# A module-scope class for the BenchRunner integration test must be picklable.
class MySingletonSweep(ParametrizedSweepSingleton):
    """Simple singleton sweep used to validate BenchRunner reruns."""

    theta = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0], samples=3, doc="angle")
    result = bch.ResultVar()

    def __init__(self):
        if self.first_time():
            self.init_count = 1
        super().__init__()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.result = float(self.theta)
        return super().__call__(**kwargs)


def benchable_singleton_fn(run_cfg: bch.BenchRunCfg, report: bch.BenchReport) -> bch.BenchCfg:
    sweep = MySingletonSweep()
    bench = sweep.to_bench(run_cfg=run_cfg, report=report)
    # Disable plotting to avoid hvplot/xarray requirements in headless tests
    # We still exercise the full compute path and BenchRunner integration
    return bench.plot_sweep(plot_callbacks=False)


def test_singleton_per_child():
    class ChildA(ParametrizedSweepSingleton):
        def __init__(self, value=1):
            if self.first_time():
                self.init_count = 1
                self.value = value
            super().__init__()

    class ChildB(ParametrizedSweepSingleton):
        def __init__(self, value=2):
            if self.first_time():
                self.init_count = 1
                self.value = value
            super().__init__()

    a1 = ChildA()
    a2 = ChildA()
    b1 = ChildB()
    b2 = ChildB()
    assert a1 is a2, "ChildA should return the same instance"
    assert b1 is b2, "ChildB should return the same instance"
    assert a1 is not b1, "ChildA and ChildB should have different singleton instances"


def test_singleton_init_only_once():
    class ChildA(ParametrizedSweepSingleton):
        def __init__(self, value=1):
            if self.first_time():
                self.init_count = 1
                self.value = value
            super().__init__()

    class ChildB(ParametrizedSweepSingleton):
        def __init__(self, value=2):
            if self.first_time():
                self.init_count = 1
                self.value = value
            super().__init__()

    a1 = ChildA()
    ChildA()  # second construction should not re-run init
    assert a1.init_count == 1, "__init__ should only run once for ChildA"
    b1 = ChildB()
    ChildB()  # second construction should not re-run init
    assert b1.init_count == 1, "__init__ should only run once for ChildB"


def test_singleton_value_persistence():
    class ChildA(ParametrizedSweepSingleton):
        def __init__(self, value=1):
            if self.first_time():
                self.init_count = 1
                self.value = value
            super().__init__()

    a1 = ChildA(value=10)
    a2 = ChildA(value=20)
    assert a1.value == 10, "Value should be set only on first init and persist"
    assert a2.value == 10, "Subsequent inits should not overwrite value"


def test_benchrunner_rerun_with_singleton():
    # Use a fixed run_tag so naming is deterministic and cache isolation is explicit
    run_cfg = bch.BenchRunCfg(run_tag="singleton_rerun_test")
    br = bch.BenchRunner(name="singleton_runner", run_cfg=run_cfg)
    br.add(benchable_singleton_fn)

    # First run
    results_first = br.run(level=1, repeats=1, cache_results=False)
    assert len(results_first) == 1

    # Second run of the same BenchRunner with the same benchable function
    results_second = br.run(level=1, repeats=1, cache_results=False)
    assert len(results_second) == 2  # BenchRunner returns cumulative results

    # Ensure rerunning appends results and does not error
    assert len(br.results) == 2

    # Verify the singleton was only initialised once across both runs
    assert MySingletonSweep().init_count == 1


def test_singleton_report_save_and_pickling():
    # Ensure running and saving the report works and the result is pickled
    run_cfg = bch.BenchRunCfg(run_tag="singleton_save_test")
    br = bch.BenchRunner(name="singleton_runner_save", run_cfg=run_cfg)
    br.add(benchable_singleton_fn)

    # Run and save report; also exercises diskcache pickling of results
    br.run(level=1, repeats=1, cache_results=False, save=True)

    expected_filename = f"MySingletonSweep_benchable_singleton_fn_{run_cfg.run_tag}.html"
    expected_path = Path("reports") / expected_filename
    assert expected_path.exists(), f"Report not saved at {expected_path}"
    # Cleanup saved report to avoid polluting workspace
    expected_path.unlink(missing_ok=True)
