import pytest
from bencher.variables.singleton_parametrized_sweep import ParametrizedSweepSingleton
import bencher as bch


# Ensure singleton cache is cleared before each test for isolation
@pytest.fixture(autouse=True)
def clear_singleton_cache():
    # Use the public method to avoid touching protected members
    ParametrizedSweepSingleton.reset_singletons()


class ChildA(ParametrizedSweepSingleton):
    def __init__(self, value=1):
        # Use the helper to avoid boilerplate; only runs once
        if self.init_singleton():
            self.init_count = 1
            self.value = value
        # Call super for pylint; base no-ops on subsequent calls
        super().__init__()


class ChildB(ParametrizedSweepSingleton):
    def __init__(self, value=2):
        if self.init_singleton():
            self.init_count = 1
            self.value = value
        super().__init__()


def test_singleton_per_child():
    a1 = ChildA()
    a2 = ChildA()
    b1 = ChildB()
    b2 = ChildB()
    assert a1 is a2, "ChildA should return the same instance"
    assert b1 is b2, "ChildB should return the same instance"
    assert a1 is not b1, "ChildA and ChildB should have different singleton instances"


def test_singleton_init_only_once():
    a1 = ChildA()
    ChildA()  # second construction should not re-run init
    assert a1.init_count == 1, "__init__ should only run once for ChildA"
    b1 = ChildB()
    ChildB()  # second construction should not re-run init
    assert b1.init_count == 1, "__init__ should only run once for ChildB"


def test_singleton_value_persistence():
    a1 = ChildA(value=10)
    a2 = ChildA(value=20)
    assert a1.value == 10, "Value should be set only on first init and persist"
    assert a2.value == 10, "Subsequent inits should not overwrite value"


# ---- BenchRunner integration test with SingletonParametrizedSweep ----


class MySingletonSweep(ParametrizedSweepSingleton):
    """Simple singleton sweep used to validate BenchRunner reruns."""

    # One float input and a single numeric result
    theta = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0], samples=3, doc="angle")
    result = bch.ResultVar()

    def __init__(self):
        if self.init_singleton():
            self.init_count = 1
        super().__init__()

    def __call__(self, **kwargs):
        # Standard pattern: update params and report results
        self.update_params_from_kwargs(**kwargs)
        # Just echo theta as the result; minimal logic for the test
        self.result = float(self.theta)
        return super().__call__(**kwargs)


def benchable_singleton_fn(run_cfg: bch.BenchRunCfg, report: bch.BenchReport) -> bch.BenchCfg:
    sweep = MySingletonSweep()
    bench = sweep.to_bench(run_cfg=run_cfg, report=report)
    # Disable plotting to avoid hvplot/xarray requirements in headless tests
    # We still exercise the full compute path and BenchRunner integration
    return bench.plot_sweep(plot_callbacks=False)


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
