"""Example demonstrating the unified BenchRunner interface with different sampling strategies."""

from __future__ import annotations
import math
import random
from enum import auto
from strenum import StrEnum
import bencher as bch
from bencher.sampling_strategy import single_run, progressive_sampling


# Define simple test classes
class OutputCfg(bch.ParametrizedSweep):
    """Example output configuration."""
    accuracy = bch.ResultVar(units="%", direction=bch.OptDir.maximize, doc="Algorithm accuracy")


class AlgorithmType(StrEnum):
    """Algorithm type enum."""
    fast = auto()
    accurate = auto()
    balanced = auto()


class InputCfg(bch.ParametrizedSweep):
    """Example input configuration."""
    algorithm = bch.EnumSweep(AlgorithmType, default=AlgorithmType.balanced)
    threshold = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], samples=5)
    
    @staticmethod
    def benchmark_function(cfg: InputCfg) -> OutputCfg:
        """Example benchmark function."""
        output = OutputCfg()
        
        # Base accuracy based on threshold
        base_accuracy = 50 + math.sin(cfg.threshold * math.pi) * 20
        
        # Algorithm-specific modifiers
        match cfg.algorithm:
            case AlgorithmType.fast:
                output.accuracy = base_accuracy + random.uniform(-5, 5)  # Fast but noisy
            case AlgorithmType.accurate:
                output.accuracy = base_accuracy + 15  # More accurate
            case AlgorithmType.balanced:
                output.accuracy = base_accuracy + 5  # Balanced
                
        return output


def demonstrate_unified_interface():
    """Demonstrate different usage patterns with the unified interface."""
    
    print("=== Unified BenchRunner Interface Demo ===\n")
    
    # 1. Single run (like calling benchmark function directly)
    print("1. Single Run Example:")
    runner1 = bch.BenchRunner("single_run_demo", InputCfg())
    
    # Use convenience method
    results1 = runner1.run_single(
        level=3,
        repeats=2,
        input_vars=[InputCfg.param.algorithm],
        result_vars=[OutputCfg.param.accuracy],
        title="Single Run - Algorithm Comparison"
    )
    print(f"   Completed {len(results1)} benchmark runs\n")
    
    # 2. Progressive sampling (traditional BenchRunner usage)
    print("2. Progressive Sampling Example:")
    runner2 = bch.BenchRunner("progressive_demo", InputCfg())
    
    # Use convenience method
    results2 = runner2.run_progressive(
        min_level=2,
        max_level=4,
        mode="linear",
        input_vars=[InputCfg.param.threshold],
        result_vars=[OutputCfg.param.accuracy],
        title="Progressive Sampling - Threshold Analysis"
    )
    print(f"   Completed {len(results2)} benchmark runs with progressive sampling\n")
    
    # 3. Custom sampling strategy
    print("3. Custom Sampling Strategy Example:")
    custom_strategy = progressive_sampling(min_level=2, max_level=5, mode="exponential")
    runner3 = bch.BenchRunner("custom_demo", InputCfg(), sampling_strategy=custom_strategy)
    
    results3 = runner3.run(
        input_vars=[InputCfg.param.algorithm, InputCfg.param.threshold],
        result_vars=[OutputCfg.param.accuracy],
        title="Custom Strategy - Full 2D Sweep"
    )
    print(f"   Completed {len(results3)} benchmark runs with exponential sampling\n")
    
    # 4. Enhanced benchmark function approach
    print("4. Enhanced Benchmark Function Example:")
    enhanced_fn = bch.BenchRunner.create_enhanced_benchmark(
        InputCfg.benchmark_function,
        input_vars=[InputCfg.param.algorithm],
        result_vars=[OutputCfg.param.accuracy],
        title="Enhanced Function Demo"
    )
    
    runner4 = bch.BenchRunner("enhanced_demo")
    runner4.add_run(enhanced_fn)
    
    results4 = runner4.run_single(level=2, repeats=1)
    print(f"   Completed {len(results4)} benchmark runs with enhanced function\n")
    
    print("=== All demos completed successfully! ===")
    print(f"Total benchmark results: {len(results1) + len(results2) + len(results3) + len(results4)}")


if __name__ == "__main__":
    # Run the demonstration
    demonstrate_unified_interface()