"""Test deprecation warnings and basic functionality."""

import warnings
import bencher as bch
import math


class TestCfg(bch.ParametrizedSweep):
    """Simple test configuration."""
    value = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], samples=3)
    result = bch.ResultVar(units="ul")

    @staticmethod 
    def test_fn(cfg: 'TestCfg') -> dict:
        return {"result": math.sin(cfg.value)}


def test_new_interface():
    """Test the new interface and deprecation warnings."""
    
    print("=== Testing New Interface ===\n")
    
    # Test 1: New interface (no warnings)
    print("1. New interface (should be silent):")
    runner1 = bch.BenchRunner("test1", TestCfg())
    result1 = runner1.run(level=2, max_level=3)
    print(f"   ✓ Completed {len(result1)} runs\n")
    
    # Test 2: Method chaining
    print("2. Method chaining:")
    result2 = (bch.BenchRunner("chained_test")
              .add_bench(TestCfg())
              .run(level=2, repeats=1, max_repeats=2))
    print(f"   ✓ Chained execution: {len(result2)} runs\n")
    
    # Test 3: Different sampling strategies
    print("3. Sampling strategies:")
    
    # Should create different execution orders
    strategies = ["repeats_first", "level_first", "alternating"]
    for strategy in strategies:
        runner = bch.BenchRunner("strategy_test", TestCfg())
        method = getattr(runner, f"run_{strategy}")
        result = method(level=2, max_level=3, repeats=1, max_repeats=2)
        print(f"   ✓ {strategy}: {len(result)} runs")
    
    print("\n4. Testing deprecation warnings:")
    
    # Enable all warnings for testing
    warnings.filterwarnings("always", category=DeprecationWarning)
    
    # Test deprecated parameters
    print("   Using min_level (should show deprecation warning):")
    runner_dep = bch.BenchRunner("deprecated_test", TestCfg())
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result_dep = runner_dep.run(min_level=2, max_level=3)  # Should trigger warning
        if w and any("min_level parameter is deprecated" in str(warning.message) for warning in w):
            print("   ✓ Deprecation warning shown correctly")
        else:
            print("   ⚠ Deprecation warning not shown")
        print(f"   ✓ Still works: {len(result_dep)} runs")
    
    print(f"\n=== All tests completed ===")


if __name__ == "__main__":
    test_new_interface()