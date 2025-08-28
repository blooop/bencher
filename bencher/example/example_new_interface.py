"""Example demonstrating the new unified BenchRunner interface with clean parameter naming."""

from __future__ import annotations
import math
import bencher as bch


class SimpleBenchmark(bch.ParametrizedSweep):
    """Simple benchmark configuration."""
    
    threshold = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], samples=4)
    accuracy = bch.ResultVar(units="%", direction=bch.OptDir.maximize)
    
    @staticmethod
    def benchmark_function(cfg: 'SimpleBenchmark') -> dict:
        """Static benchmark function."""
        return {"accuracy": 50 + 30 * math.sin(cfg.threshold * math.pi)}


def demo_new_interface():
    """Demonstrate the new clean interface."""
    
    print("=== New Unified BenchRunner Interface ===\n")
    
    # 1. Single run (level=3, repeats=2)
    print("1. Single Run:")
    print("   BenchRunner(cfg).run(level=3, repeats=2)")
    
    result1 = bch.BenchRunner(SimpleBenchmark()).run(level=3, repeats=2)
    print(f"   → Executed {len(result1)} run(s) at level 3 with 2 repeats\n")
    
    # 2. Progressive from level 2 to 4 (single repeats)
    print("2. Progressive Levels:")
    print("   BenchRunner(cfg).run(level=2, max_level=4)")
    
    result2 = bch.BenchRunner(SimpleBenchmark()).run(level=2, max_level=4, repeats=1)
    print(f"   → Executed {len(result2)} run(s) progressing levels 2→4\n")
    
    # 3. Progressive repeats at fixed level
    print("3. Progressive Repeats:")
    print("   BenchRunner(cfg).run(level=3, repeats=1, max_repeats=3)")
    
    result3 = bch.BenchRunner(SimpleBenchmark()).run(level=3, repeats=1, max_repeats=3)
    print(f"   → Executed {len(result3)} run(s) progressing repeats 1→3 at level 3\n")
    
    # 4. Full progression (both level and repeats)
    print("4. Full Progression (repeats-first strategy):")
    print("   BenchRunner(cfg).run(level=2, max_level=4, repeats=1, max_repeats=2)")
    
    result4 = bch.BenchRunner(SimpleBenchmark()).run(level=2, max_level=4, repeats=1, max_repeats=2)
    print(f"   → Executed {len(result4)} run(s) with full progression\n")
    
    # 5. Method chaining for multiple configs
    print("5. Method Chaining:")
    print("   BenchRunner().add_bench(cfg1).add_bench(cfg2).run(level=2, max_level=3)")
    
    cfg1 = SimpleBenchmark()
    cfg2 = SimpleBenchmark()
    cfg2.threshold.default = 0.8  # Different starting point
    
    result5 = (bch.BenchRunner()
              .add_bench(cfg1)
              .add_bench(cfg2)
              .run(level=2, max_level=3))
    print(f"   → Executed {len(result5)} run(s) from chained setup\n")
    
    # 6. Sampling strategy methods
    print("6. Sampling Strategy Methods:")
    print("   BenchRunner(cfg).run_repeats_first(level=2, max_level=3, repeats=1, max_repeats=2)")
    
    result6 = bch.BenchRunner(SimpleBenchmark()).run_repeats_first(level=2, max_level=3, repeats=1, max_repeats=2)
    print(f"   → Executed {len(result6)} run(s) with repeats-first strategy\n")
    
    print("=== Unified Interface Summary ===")
    print("Key improvements:")
    print("• BenchRunner(cfg) - most common pattern, no name needed")
    print("• BenchRunner() - auto-naming with method chaining")
    print("• level/repeats are starting values (clean parameter naming)")
    print("• max_level/max_repeats define progression endpoints")
    print("• Single constructor handles all cases")
    print("• Method chaining: add_bench() returns self for fluent API")


if __name__ == "__main__":
    demo_new_interface()