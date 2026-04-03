from pathlib import Path
import pytest
from bencher.variables.singleton_parametrized_sweep import ParametrizedSweepSingleton
import bencher as bn


# A module-scope class for the BenchRunner integration test must be picklable.
class MySingletonSweep(ParametrizedSweepSingleton):
    """Simple singleton sweep used to validate BenchRunner reruns."""

    theta = bn.FloatSweep(default=0.0, bounds=[0.0, 1.0], samples=3, doc="angle")
    result = bn.ResultFloat()

    def __init__(self):
        if self.init_singleton():
            self.init_count = 1
        super().__init__()

    def benchmark(self):
        self.result = float(self.theta)


def benchable_singleton_fn(run_cfg: bn.BenchRunCfg, report: bn.BenchReport) -> bn.BenchCfg:
    sweep = MySingletonSweep()
    bench = sweep.to_bench(run_cfg, report=report)
    # Disable plotting to avoid hvplot/xarray requirements in headless tests
    # We still exercise the full compute path and BenchRunner integration
    return bench.plot_sweep(plot_callbacks=False)


def benchable_singleton_fn_v2(run_cfg: bn.BenchRunCfg) -> bn.BenchCfg:
    sweep = MySingletonSweep()
    bench = sweep.to_bench(run_cfg=run_cfg)
    return bench.plot_sweep(plot_callbacks=False)


def test_singleton_per_child():
    class ChildA(ParametrizedSweepSingleton):
        def __init__(self, value=1):
            if self.init_singleton():
                self.init_count = 1
                self.value = value
            super().__init__()

    class ChildB(ParametrizedSweepSingleton):
        def __init__(self, value=2):
            if self.init_singleton():
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
            if self.init_singleton():
                self.init_count = 1
                self.value = value
            super().__init__()

    class ChildB(ParametrizedSweepSingleton):
        def __init__(self, value=2):
            if self.init_singleton():
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
            if self.init_singleton():
                self.init_count = 1
                self.value = value
            super().__init__()

    a1 = ChildA(value=10)
    a2 = ChildA(value=20)
    assert a1.value == 10, "Value should be set only on first init and persist"
    assert a2.value == 10, "Subsequent inits should not overwrite value"


def test_benchrunner_rerun_with_singleton():
    # Grab the singleton instance before any run
    singleton_before = MySingletonSweep()

    # Use a fixed run_tag so naming is deterministic and cache isolation is explicit
    run_cfg = bn.BenchRunCfg(run_tag="singleton_rerun_test")
    br = bn.BenchRunner(name="singleton_runner", run_cfg=run_cfg)
    br.add(benchable_singleton_fn)

    # First run
    results_first = br.run(level=1, repeats=1, cache_results=False)
    assert len(results_first) == 1

    # Second run of the same BenchRunner with the same benchable function
    results_second = br.run(level=1, repeats=1, cache_results=False)
    assert len(results_second) == 2  # BenchRunner returns cumulative results

    # Ensure rerunning appends results and does not error
    assert len(br.results) == 2

    # Verify the same instance is returned and init only happened once
    singleton_after = MySingletonSweep()
    assert singleton_before is singleton_after, "Singleton instance changed across reruns"
    assert singleton_after.init_count == 1, "Singleton reinitialised across reruns"
    # No reinitialization or instance change across reruns


def test_singleton_report_save_and_pickling():
    # Ensure running and saving the report works and the result is pickled
    run_cfg = bn.BenchRunCfg(run_tag="singleton_save_test")
    br = bn.BenchRunner(name="singleton_runner_save", run_cfg=run_cfg)
    br.add(benchable_singleton_fn)

    # Run and save report; also exercises diskcache pickling of results
    br.run(level=1, repeats=1, cache_results=False, save=True)

    expected_filename = f"MySingletonSweep_benchable_singleton_fn_{run_cfg.run_tag}.html"
    expected_path = Path("reports") / expected_filename
    assert expected_path.exists(), f"Report not saved at {expected_path}"
    # Cleanup saved report to avoid polluting workspace
    expected_path.unlink(missing_ok=True)


def test_singleton_init_failure_consistency():
    class FailingChild(ParametrizedSweepSingleton):
        def __init__(self, value=1):
            # Intentionally fail before calling base __init__ for value==1
            if value == 1:
                raise RuntimeError("Intentional failure during init")
            self.value = value
            super().__init__()

    # First instantiation should fail
    with pytest.raises(RuntimeError, match="Intentional failure during init"):
        FailingChild(value=1)

    # Second instantiation with a non-failing value should succeed
    instance = FailingChild(value=2)
    assert isinstance(instance, FailingChild)
    assert instance.value == 2

    # Third instantiation with the same non-failing value should return the same instance
    instance2 = FailingChild(value=2)
    assert instance is instance2


def test_single_argument_benchable_supported():
    run_cfg = bn.BenchRunCfg(run_tag="singleton_single_arg_test")
    br = bn.BenchRunner(name="singleton_runner_v2", run_cfg=run_cfg)
    br.add(benchable_singleton_fn_v2)

    results = br.run(level=1, repeats=1, cache_results=False)
    assert len(results) == 1


def test_context_manager_resets_on_first_init_failure():
    """with init_singleton() auto-resets _seen/_instances when first init raises."""

    class FailCM(ParametrizedSweepSingleton):
        def __init__(self, fail=True):
            with self.init_singleton() as is_first:
                if is_first:
                    if fail:
                        raise RuntimeError("boom")
                    self.value = 42
            super().__init__()

    # First attempt — should fail and reset singleton state
    with pytest.raises(RuntimeError, match="boom"):
        FailCM(fail=True)

    # Retry — singleton was rolled back, so init_singleton() is truthy again
    obj = FailCM(fail=False)
    assert obj.value == 42

    # Third call — singleton is now established
    obj2 = FailCM(fail=False)
    assert obj2 is obj


def test_context_manager_no_reset_on_success():
    """Successful first init must NOT be rolled back."""

    class SuccessCM(ParametrizedSweepSingleton):
        def __init__(self):
            with self.init_singleton() as is_first:
                if is_first:
                    self.value = 99
            super().__init__()

    obj = SuccessCM()
    assert obj.value == 99

    obj2 = SuccessCM()
    assert obj2 is obj
    assert obj2.value == 99


def test_context_manager_no_reset_on_non_first_error():
    """Error inside `with` on a non-first call must NOT reset the singleton."""

    class NonFirstCM(ParametrizedSweepSingleton):
        call_count = 0

        def __init__(self):
            with self.init_singleton() as is_first:
                NonFirstCM.call_count += 1
                if is_first:
                    self.value = 7
                elif NonFirstCM.call_count == 2:
                    raise RuntimeError("second-call error")
            super().__init__()

    obj = NonFirstCM()
    assert obj.value == 7

    # Second construction — raises inside `with` but is_first is False
    with pytest.raises(RuntimeError, match="second-call error"):
        NonFirstCM()

    # Singleton must still be intact
    obj3 = NonFirstCM()
    assert obj3 is obj
    assert obj3.value == 7


def test_reset_singleton_public_api():
    """reset_singleton() clears state so the next construction re-inits."""

    class Resettable(ParametrizedSweepSingleton):
        def __init__(self, val=1):
            if self.init_singleton():
                self.val = val
            super().__init__()

    obj1 = Resettable(val=10)
    assert obj1.val == 10

    Resettable.reset_singleton()

    obj2 = Resettable(val=20)
    assert obj2.val == 20
    assert obj2 is not obj1


def test_init_singleton_boolean_backward_compat():
    """init_singleton() result works in boolean context (if/elif/not/and/or)."""

    class BoolCompat(ParametrizedSweepSingleton):
        def __init__(self):
            result = self.init_singleton()
            if result:
                self.init_count = 1
            super().__init__()

    obj = BoolCompat()
    assert obj.init_count == 1

    # Second call — init_singleton() is falsy, init_count stays 1
    obj2 = BoolCompat()
    assert obj2 is obj
    assert obj.init_count == 1
