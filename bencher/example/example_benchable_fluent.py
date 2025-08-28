"""Example demonstrating BenchableObject().add_run(bench_func).run(max_repeat=5) pattern."""

import bencher as bch
import math


class BenchableObject(bch.ParametrizedSweep):
    """A benchable object that can create a BenchRunner and chain operations."""
    
    threshold = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], samples=3)
    accuracy = bch.ResultVar(units="%", direction=bch.OptDir.maximize)
    
    @staticmethod
    def benchmark_function(cfg: 'BenchableObject') -> dict:
        """Default benchmark function."""
        return {"accuracy": 50 + 30 * math.sin(cfg.threshold * math.pi)}


def additional_benchmark_function(cfg: BenchableObject) -> dict:
    """Additional benchmark function with different behavior."""
    return {"accuracy": 75 + 25 * math.cos(cfg.threshold * math.pi)}


class AdditionalBenchable:
    """Example of a custom Benchable class."""
    
    def bench(self, run_cfg, report):
        """Implement the Benchable protocol."""
        # Create and run a simple benchmark
        return BenchableObject().to_bench().plot_sweep("additional_bench")


def demo_benchable_fluent():
    """Demonstrate the BenchableObject().add_run(bench_func).run(max_repeat=5) pattern."""
    
    print("=== BenchableObject Fluent Interface ===\n")
    
    # Example 1: Basic pattern - BenchableObject().to_bench_runner().run()
    print("1. Basic fluent pattern:")
    print("   BenchableObject().to_bench_runner().run(level=2, max_level=4)")
    
    result1 = BenchableObject().to_bench_runner().run(level=2, max_level=4)
    print(f"   ✓ Executed {len(result1)} run(s)\n")
    
    # Example 2: Add additional configuration and run with max_repeats
    print("2. Add additional config and run with max_repeats:")
    print("   BenchableObject().to_bench_runner().add_bench(config).run(max_repeats=3)")
    
    additional_config = BenchableObject()  # Another instance
    result2 = (BenchableObject()
               .to_bench_runner()
               .add_bench(additional_config)
               .run(level=2, repeats=1, max_repeats=3))
    print(f"   ✓ Executed {len(result2)} run(s) with max_repeats=3\n")
    
    # Example 3: Multiple chained operations
    print("3. Complex chaining with multiple operations:")
    print("   BenchableObject().to_bench_runner(name='complex')")
    print("                   .add_bench(AnotherConfig())")
    print("                   .run_repeats_first(level=2, max_level=3, max_repeats=4)")
    
    another_config = BenchableObject()  # Create another instance
    result3 = (BenchableObject()
               .to_bench_runner(name="complex_benchmark")
               .add_bench(another_config)
               .run_repeats_first(level=2, max_level=3, repeats=1, max_repeats=2))
    print(f"   ✓ Executed {len(result3)} run(s) with complex chaining\n")
    
    # Example 4: Different sampling strategies
    print("4. Different sampling strategies:")
    
    print("   a) Level-first with max_repeats=4:")
    result4a = (BenchableObject()
                .to_bench_runner()
                .run_level_first(level=2, max_level=3, repeats=1, max_repeats=2))
    print(f"      ✓ {len(result4a)} run(s)")
    
    print("   b) Alternating with max_repeats=3:")
    result4b = (BenchableObject()
                .to_bench_runner()
                .run_alternating(level=2, max_level=3, repeats=1, max_repeats=2))
    print(f"      ✓ {len(result4b)} run(s)\n")
    
    # Example 5: Single high-precision run
    print("5. Single high-precision run:")
    print("   BenchableObject().to_bench_runner().run(level=4, repeats=5)")
    
    result5 = BenchableObject().to_bench_runner().run(level=4, repeats=5)
    print(f"   ✓ Executed {len(result5)} run(s) with 5 repeats\n")
    
    # Example 6: Method comparison
    print("6. Method comparison:")
    print("   Traditional:")
    print("     cfg = BenchableObject()")
    print("     runner = bch.BenchRunner('name', cfg)")
    print("     runner.add_run(benchable)")
    print("     result = runner.run(level=2, max_repeats=5)")
    print()
    print("   Fluent:")
    print("     result = (BenchableObject()")
    print("              .to_bench_runner()")
    print("              .add_run(benchable)")
    print("              .run(level=2, max_repeats=5))")
    
    print()
    print("=== Fluent Interface Benefits ===")
    print("✓ Direct method chaining from ParametrizedSweep")
    print("✓ Natural left-to-right reading flow")
    print("✓ Less intermediate variable declarations")
    print("✓ Supports all BenchRunner features (add_run, add_bench)")
    print("✓ Works with all sampling strategies")
    print("✓ Enables max_repeats parameter usage")
    print("✓ Clean, expressive code")


if __name__ == "__main__":
    demo_benchable_fluent()