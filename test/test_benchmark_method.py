"""Tests for the new benchmark() method on ParametrizedSweep."""

import math
import warnings

import bencher as bn


class NewStyleBench(bn.ParametrizedSweep):
    """Uses the new benchmark() interface."""

    x = bn.FloatSweep(default=0, bounds=[0, math.pi], samples=5)
    result = bn.ResultFloat(units="v")

    def benchmark(self):
        self.result = math.sin(self.x)


class LegacyStyleBench(bn.ParametrizedSweep):
    """Uses the old __call__() interface for backward compat testing."""

    x = bn.FloatSweep(default=0, bounds=[0, math.pi], samples=5)
    result = bn.ResultFloat(units="v")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.result = math.sin(self.x)
        return super().__call__()


class NoOverrideBench(bn.ParametrizedSweep):
    """Neither benchmark() nor __call__() overridden — returns defaults."""

    x = bn.FloatSweep(default=0, bounds=[0, 1], samples=3)
    result = bn.ResultFloat(units="v")


def test_benchmark_method_works():
    """Test that benchmark() override works: params auto-populated, results auto-collected."""
    bench = NewStyleBench()
    output = bench(x=math.pi / 2)
    assert abs(output["result"] - 1.0) < 1e-9


def test_benchmark_method_full_sweep():
    """Test that benchmark() works in a full sweep."""
    bench = NewStyleBench().to_bench(bn.BenchRunCfg())
    bench.plot_sweep()
    assert len(bench.results) > 0


def test_legacy_call_still_works():
    """Test that legacy __call__ override still works (backward compat)."""
    bench = LegacyStyleBench()
    output = bench(x=math.pi / 2)
    assert abs(output["result"] - 1.0) < 1e-9


def test_legacy_call_deprecation_warning():
    """Test that deprecation warning is emitted for legacy __call__ override."""
    worker = LegacyStyleBench()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        bn.Bench("test", worker)
        dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep_warnings) == 1
        assert "benchmark()" in str(dep_warnings[0].message)


def test_no_override_returns_defaults():
    """Test that a class with neither override returns default results."""
    bench = NoOverrideBench()
    output = bench(x=0.5)
    assert "result" in output


def test_new_style_no_deprecation_warning():
    """Test that new-style benchmark() does NOT emit deprecation warning."""
    worker = NewStyleBench()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        bn.Bench("test", worker)
        dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep_warnings) == 0
