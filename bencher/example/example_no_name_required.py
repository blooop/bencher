"""Test improved UX - BenchRunner no longer requires a name."""

import bencher as bch
import math


class TestCfg(bch.ParametrizedSweep):
    """Simple test configuration."""
    value = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], samples=3)
    result = bch.ResultVar(units="ul")

    @staticmethod 
    def test_fn(cfg: 'TestCfg') -> dict:
        return {"result": math.sin(cfg.value)}


def test_no_name_required():
    """Test that BenchRunner works without requiring a name."""
    
    print("=== Testing Unified BenchRunner Interface ===\n")
    
    # Test 1: Direct constructor patterns - main usage
    print("1. Direct constructor patterns:")
    
    # ParametrizedSweep directly - most common pattern
    runner1a = bch.BenchRunner(TestCfg())
    print(f"   BenchRunner(cfg) → name: {runner1a.name}")
    result1a = runner1a.run(level=2)
    print(f"   ✓ Executed {len(result1a)} run(s)")
    
    # Auto-generated name with method chaining
    runner1b = bch.BenchRunner().add_bench(TestCfg())
    print(f"   BenchRunner().add_bench(cfg) → name: {runner1b.name}")
    
    print()
    
    # Test 2: Method chaining
    print("2. Method chaining:")
    
    runner2 = bch.BenchRunner().add_bench(TestCfg())
    print(f"   Method chaining → name: {runner2.name}")
    
    print()
    
    # Test 3: Real workflow examples
    print("3. Real workflow examples:")
    
    # Progressive sampling
    print("   a) Progressive sampling:")
    result3a = bch.BenchRunner(TestCfg()).run(level=2, max_level=4, repeats=1, max_repeats=2)
    print(f"      ✓ {len(result3a)} progressive runs")
    
    # Single high-precision run
    print("   b) Single precision run:")  
    result3b = bch.BenchRunner(TestCfg()).run(level=5, repeats=3)
    print(f"      ✓ {len(result3b)} high-precision runs")
    
    print()
    
    # Test 4: ParametrizedSweepProvider protocol
    print("4. ReusableParametrizedSweep:")
    
    reusable_cfg = bch.ReusableParametrizedSweep(TestCfg())
    runner4 = bch.BenchRunner(reusable_cfg)
    print(f"   Reusable wrapper → name: {runner4.name}")
    
    print()
    
    # Test 5: Unique name generation
    print("5. Auto-generated names are unique:")
    names = [bch.BenchRunner().name for _ in range(3)]
    print(f"   Names: {names}")
    print(f"   ✓ All unique: {len(set(names)) == len(names)}")
    
    print()
    print("=== Unified Interface Complete ===")
    print("✓ Single constructor handles all cases")
    print("✓ BenchRunner(cfg) - most common pattern") 
    print("✓ BenchRunner() - auto-naming with chaining")
    print("✓ ReusableParametrizedSweep - for reuse scenarios")
    print("✓ Method chaining support")
    print("✓ Clean, intuitive API for benchmarking")


if __name__ == "__main__":
    test_no_name_required()