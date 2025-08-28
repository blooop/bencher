"""Example demonstrating ParametrizedSweepProvider protocol for reuse scenarios."""

import bencher as bch
import math


class TestCfg(bch.ParametrizedSweep):
    """Simple test configuration."""
    value = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], samples=3)
    result = bch.ResultVar(units="ul")

    @staticmethod 
    def test_fn(cfg: 'TestCfg') -> dict:
        return {"result": math.sin(cfg.value)}


class CustomReusableConfig(bch.ReusableParametrizedSweep):
    """Custom reusable config that can modify the underlying sweep."""
    
    def __init__(self, parametrized_sweep: bch.ParametrizedSweep, scale_factor: float = 1.0):
        super().__init__(parametrized_sweep)
        self.scale_factor = scale_factor
    
    def get_parametrized_sweep(self) -> bch.ParametrizedSweep:
        """Return the parametrized sweep, potentially modified."""
        # In a real scenario, you might modify parameters here
        # For this example, we'll just return the original
        return self._parametrized_sweep


def test_reuse_scenarios():
    """Test various reuse scenarios with the ParametrizedSweepProvider protocol."""
    
    print("=== ParametrizedSweepProvider Protocol Examples ===\n")
    
    # Test 1: Basic reuse wrapper
    print("1. Basic ReusableParametrizedSweep:")
    
    base_cfg = TestCfg()
    reusable_cfg = bch.ReusableParametrizedSweep(base_cfg)
    
    runner1 = bch.BenchRunner(reusable_cfg)
    print(f"   Reusable config → name: {runner1.name}")
    result1 = runner1.run(level=2)
    print(f"   ✓ Executed {len(result1)} run(s)\n")
    
    # Test 2: Custom reusable config
    print("2. Custom ReusableParametrizedSweep:")
    
    custom_cfg = CustomReusableConfig(TestCfg(), scale_factor=2.0)
    runner2 = bch.BenchRunner(custom_cfg)
    print(f"   Custom wrapper → name: {runner2.name}")
    result2 = runner2.run(level=2)
    print(f"   ✓ Executed {len(result2)} run(s)\n")
    
    # Test 3: Comparison of usage patterns
    print("3. Usage pattern comparison:")
    
    print("   a) Direct usage (creates new each time):")
    print("      BenchRunner(TestCfg())")
    
    print("   b) Reusable wrapper:")
    print("      reusable = ReusableParametrizedSweep(TestCfg())")
    print("      BenchRunner(reusable)")
    
    print("   c) Method chaining with add_bench():")
    print("      BenchRunner().add_bench(TestCfg())\n")
    
    # Test 4: Show the protocol in action
    print("4. Protocol implementation:")
    print("   ParametrizedSweepProvider protocol requires:")
    print("   - get_parametrized_sweep() -> ParametrizedSweep")
    print("   - Enables custom reuse strategies")
    print("   - Works seamlessly with BenchRunner constructor\n")
    
    print("=== Protocol Benefits ===")
    print("✓ Enables ParametrizedSweep reuse")
    print("✓ Extensible for custom reuse patterns") 
    print("✓ Clean separation of concerns")
    print("✓ Backward compatible with existing code")
    print("✓ Protocol-based design allows multiple implementations")


if __name__ == "__main__":
    test_reuse_scenarios()