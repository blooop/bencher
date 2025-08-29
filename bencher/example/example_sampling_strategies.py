"""Demo of different sampling strategies showing order of level vs repeats increases."""

from __future__ import annotations
import bencher as bch
from bencher.sampling_strategy import (
    REPEATS_LEVELS_BENCHMARKS,
    REPEATS_BENCHMARKS_LEVELS,
    LEVELS_REPEATS_BENCHMARKS,
    LEVELS_BENCHMARKS_REPEATS,
    BENCHMARKS_REPEATS_LEVELS,
    BENCHMARKS_LEVELS_REPEATS,
)


class SimpleCfg(bch.ParametrizedSweep):
    """Simple configuration for demonstration."""

    value = bch.FloatSweep(default=1.0, bounds=[0.0, 2.0], samples=3)

    @staticmethod
    def simple_function(cfg: SimpleCfg) -> dict:
        """Simple function that returns the input value."""
        return {"output": cfg.value}


def demo_sampling_strategies():
    """Demonstrate the order of sampling with different strategies."""

    print("=== Modern Sampling Strategy Demo ===\n")

    # Create benchmark runner for testing
    def simple_benchmark(run_cfg: bch.BenchRunCfg, report: bch.BenchReport):  # pylint: disable=unused-argument
        bench = bch.Bench("demo", SimpleCfg.simple_function, SimpleCfg)
        return bench.plot_sweep(input_vars=[SimpleCfg.param.value], run_cfg=run_cfg)

    runner = bch.BenchRunner("demo")
    runner.add(simple_benchmark)

    # Test the 6 basic sampling strategies
    strategies = [
        ("Repeats → Levels → Benchmarks", REPEATS_LEVELS_BENCHMARKS),
        ("Repeats → Benchmarks → Levels", REPEATS_BENCHMARKS_LEVELS),
        ("Levels → Repeats → Benchmarks", LEVELS_REPEATS_BENCHMARKS),
        ("Levels → Benchmarks → Repeats", LEVELS_BENCHMARKS_REPEATS),
        ("Benchmarks → Repeats → Levels", BENCHMARKS_REPEATS_LEVELS),
        ("Benchmarks → Levels → Repeats", BENCHMARKS_LEVELS_REPEATS),
    ]

    for name, strategy in strategies:
        print(f"{name} Strategy:")
        try:
            results = runner.run(
                sampling=strategy,
                level=2,
                max_level=3,
                repeats=1,
                max_repeats=2,
                show=False,
                save=False,
            )
            print(f"  ✅ Generated {len(results)} configurations")
        except Exception:  # pylint: disable=broad-except
            print(f"  ❌ Failed: {str(strategy)}")
        print()

    print("Key differences:")
    print("• Repeats → Levels → Benchmarks: Vary repeats first (fastest inner loop)")
    print("• Levels → Repeats → Benchmarks: Vary levels first")
    print("• Benchmarks → * : Vary benchmarks first (run all benchmarks at each config)")
    print()
    print("Use cases:")
    print("• Repeats first: Get statistical confidence quickly at lower fidelity")
    print("• Levels first:  Explore full parameter space quickly with minimal repeats")
    print("• Benchmarks first: Compare all benchmarks at each parameter combination")


if __name__ == "__main__":
    demo_sampling_strategies()
