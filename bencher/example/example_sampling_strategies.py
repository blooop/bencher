"""Demo of different sampling strategies showing order of level vs repeats increases."""

from __future__ import annotations
import bencher as bch
from bencher.sampling_strategy import repeats_first, level_first, alternating


class SimpleCfg(bch.ParametrizedSweep):
    """Simple configuration for demonstration."""
    value = bch.FloatSweep(default=1.0, bounds=[0.0, 2.0], samples=3)

    @staticmethod
    def simple_function(cfg: SimpleCfg) -> dict:
        """Simple function that returns the input value."""
        return {"output": cfg.value}


def demo_sampling_strategies():
    """Demonstrate the order of sampling with different strategies."""
    
    print("=== Sampling Strategy Order Demo ===\n")
    
    # Create a simple benchmark function to use
    def simple_benchmark(run_cfg: bch.BenchRunCfg, report: bch.BenchReport):
        bench = bch.Bench("demo", SimpleCfg.simple_function, SimpleCfg)
        return bench.plot_sweep(
            input_vars=[SimpleCfg.param.value],
            run_cfg=run_cfg
        )
    
    # Show execution order for each strategy
    strategies = {
        "Repeats First": repeats_first(level=2, max_level=4, repeats=1, max_repeats=3),
        "Level First": level_first(level=2, max_level=4, repeats=1, max_repeats=3),
        "Alternating": alternating(level=2, max_level=4, repeats=1, max_repeats=3)
    }
    
    base_cfg = bch.BenchRunCfg()
    
    for name, strategy in strategies.items():
        print(f"{name} Strategy:")
        configs = strategy.generate_configs(base_cfg)
        for i, cfg in enumerate(configs, 1):
            print(f"  {i:2d}. Level={cfg.level}, Repeats={cfg.repeats}")
        print()
    
    print("Key differences:")
    print("• Repeats First: Increases repeats to max (3) at each level before moving to next level")
    print("• Level First:   Increases level to max (4) at each repeat count before increasing repeats") 
    print("• Alternating:   Alternates between increasing level and repeats")
    print()
    print("Use cases:")
    print("• Repeats First: Get statistical confidence quickly at lower fidelity")
    print("• Level First:   Explore full parameter space quickly with minimal repeats")
    print("• Alternating:   Balanced approach for both statistical confidence and space exploration")


if __name__ == "__main__":
    demo_sampling_strategies()