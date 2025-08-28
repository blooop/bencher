"""Example demonstrating the fluent interface for ParametrizedSweep to BenchRunner."""

import bencher as bch
import math
import random


class SimpleBenchmark(bch.ParametrizedSweep):
    """Simple benchmark configuration for fluent interface demonstration."""
    
    threshold = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], samples=4)
    accuracy = bch.ResultVar(units="%", direction=bch.OptDir.maximize)
    
    @staticmethod
    def benchmark_function(cfg: 'SimpleBenchmark') -> dict:
        """Static benchmark function."""
        return {"accuracy": 50 + 30 * math.sin(cfg.threshold * math.pi)}


class AlgorithmEnum(bch.ClassEnum):
    quick = "quick"
    merge = "merge" 
    heap = "heap"


class PerformanceBenchmark(bch.ParametrizedSweep):
    """Performance benchmark configuration."""
    
    size = bch.IntSweep(default=100, bounds=[10, 1000], samples=3)
    algorithm = bch.EnumSweep(default=AlgorithmEnum.quick, enum_type=AlgorithmEnum)
    runtime = bch.ResultVar(units="ms", direction=bch.OptDir.minimize)
    
    @staticmethod
    def sort_benchmark(cfg: 'PerformanceBenchmark') -> dict:
        """Simulate sorting algorithm performance."""
        base_time = cfg.size * 0.1
        multiplier = {"quick": 1.2, "merge": 1.0, "heap": 1.1}[cfg.algorithm.value]
        return {"runtime": base_time * multiplier + random.random() * 10}


def demo_fluent_interface():
    """Demonstrate the fluent interface patterns."""
    
    print("=== Fluent Interface Examples ===\n")
    
    # Example 1: Basic fluent chaining
    print("1. Basic fluent chaining:")
    print("   SimpleBenchmark().to_bench_runner().run(level=2, max_level=3)")
    
    result1 = SimpleBenchmark().to_bench_runner().run(level=2, max_level=3)
    print(f"   ✓ Executed {len(result1)} run(s)\n")
    
    # Example 2: Adding additional benchmarks
    print("2. Adding additional benchmarks:")
    print("   SimpleBenchmark().to_bench_runner().add_bench(PerformanceBenchmark()).run(level=2)")
    
    result2 = (SimpleBenchmark()
               .to_bench_runner()
               .add_bench(PerformanceBenchmark())
               .run(level=2))
    print(f"   ✓ Executed {len(result2)} run(s) from multiple benchmarks\n")
    
    # Example 3: Multiple configurations with naming
    print("3. Multiple configurations with custom naming:")
    
    result3 = (SimpleBenchmark()
               .to_bench_runner(name="multi_benchmark")
               .add_bench(PerformanceBenchmark())
               .run(level=2))
    print(f"   ✓ Executed {len(result3)} run(s) with custom named runner\n")
    
    # Example 4: Progressive sampling strategies
    print("4. Progressive sampling strategies:")
    
    print("   a) Repeats-first strategy:")
    result4a = (PerformanceBenchmark()
                .to_bench_runner()
                .run_repeats_first(level=2, max_level=3, repeats=1, max_repeats=2))
    print(f"      ✓ {len(result4a)} run(s) with repeats-first")
    
    print("   b) Level-first strategy:")
    result4b = (PerformanceBenchmark()
                .to_bench_runner()
                .run_level_first(level=2, max_level=3, repeats=1, max_repeats=2))
    print(f"      ✓ {len(result4b)} run(s) with level-first")
    
    print("   c) Alternating strategy:")
    result4c = (PerformanceBenchmark()
                .to_bench_runner()
                .run_alternating(level=2, max_level=3, repeats=1, max_repeats=2))
    print(f"      ✓ {len(result4c)} run(s) with alternating\n")
    
    # Example 5: Single high-precision run
    print("5. Single high-precision run:")
    print("   SimpleBenchmark().to_bench_runner().run(level=4, repeats=3)")
    
    result5 = SimpleBenchmark().to_bench_runner().run(level=4, repeats=3)
    print(f"   ✓ Executed {len(result5)} run(s) with high precision\n")
    
    # Example 6: Comparison of patterns
    print("6. Pattern comparison:")
    print("   Old pattern:")
    print("     runner = bch.BenchRunner('name', SimpleBenchmark())")
    print("     result = runner.run(level=2)")
    print()
    print("   New fluent pattern:")
    print("     result = SimpleBenchmark().to_bench_runner().run(level=2)")
    print()
    print("   Complex chaining:")
    print("     result = (SimpleBenchmark()")
    print("              .to_bench_runner()")
    print("              .add_bench(PerformanceBenchmark())")
    print("              .run_repeats_first(level=2, max_level=4, repeats=1, max_repeats=3))")
    
    print()
    print("=== Fluent Interface Benefits ===")
    print("✓ Method chaining from ParametrizedSweep")
    print("✓ Cleaner, more readable code")
    print("✓ Less intermediate variables")
    print("✓ Natural left-to-right flow")
    print("✓ Easy to extend and modify")
    print("✓ Works with all BenchRunner features")


if __name__ == "__main__":
    demo_fluent_interface()