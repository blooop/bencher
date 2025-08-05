"""
Example demonstrating how to use the Bencher extension system.

This example shows:
1. How extensions are automatically discovered and loaded
2. How to manually control extension loading
3. How to create benchmarks that use extensions
4. How extensions integrate with the existing workflow
"""

import numpy as np
import bencher as bch

# Import the example extensions (they auto-register)


def benchmark_function(cfg):
    """Simple benchmark function for demonstration."""
    # Create some synthetic 3D data that would benefit from 3D visualization
    x, y = cfg.x, cfg.y

    # Simple function with some noise
    z = np.sin(x) * np.cos(y) + np.random.normal(0, 0.1)

    return {"performance": z, "error_rate": abs(z) * 0.1 + np.random.normal(0, 0.05)}


class BenchmarkConfig(bch.ParametrizedSweep):
    """Configuration for 3D benchmark."""

    # Input variables - perfect for 3D plotting
    x = bch.FloatSweep(default=0, bounds=(-2, 2))
    y = bch.FloatSweep(default=0, bounds=(-2, 2))

    # Result variables
    performance = bch.ResultVar(units="score", direction=bch.OptDir.maximize)
    error_rate = bch.ResultVar(units="rate", direction=bch.OptDir.minimize)


def example_automatic_extension_usage():
    """Demonstrate automatic extension discovery and usage."""
    print("=== Automatic Extension Usage ===")

    # Create benchmark - extensions are automatically discovered
    bench = bch.Bench("3d_demo", BenchmarkConfig, benchmark_function)

    # Run benchmark
    bench_cfg = BenchmarkConfig().update(level=2)  # Small dataset for demo
    results = bench.plot_sweep(bench_cfg, run_cfg=bch.BenchRunCfg(repeats=1, save_db=False))

    # Show which extensions were loaded
    if hasattr(results, "list_loaded_extensions"):
        loaded = results.list_loaded_extensions()
        print(f"Loaded extensions: {loaded}")

    # The results now include extension plots automatically
    return results


def example_manual_extension_control():
    """Demonstrate manual extension control."""
    print("\n=== Manual Extension Control ===")

    # Get the extension registry
    registry = bch.get_registry()

    # List available extensions
    print("Available extensions:")
    for metadata in registry.list_extensions():
        print(f"  - {metadata.name} v{metadata.version}: {metadata.description}")

    # Create benchmark
    bench = bch.Bench("3d_demo_manual", BenchmarkConfig, benchmark_function)
    bench_cfg = BenchmarkConfig().update(level=2)
    results = bench.plot_sweep(bench_cfg, run_cfg=bch.BenchRunCfg(repeats=1, save_db=False))

    # Use specific extensions
    if hasattr(results, "to_plot_with_extensions"):
        # Try to use Plotly extension specifically
        plotly_plot = results.to_plot_with_extensions(
            prefer_extensions=["plotly_3d_example"], fallback=True
        )

        if plotly_plot:
            print("Created plot using Plotly extension")
        else:
            print("Plotly extension not available, used fallback")

    return results


def example_extension_callbacks():
    """Demonstrate getting callbacks from extensions."""
    print("\n=== Extension Callbacks ===")

    # Create benchmark
    bench = bch.Bench("callback_demo", BenchmarkConfig, benchmark_function)
    bench_cfg = BenchmarkConfig().update(level=2)
    results = bench.plot_sweep(bench_cfg, run_cfg=bch.BenchRunCfg(repeats=1, save_db=False))

    # Get all available callbacks (including extensions)
    if hasattr(results, "get_all_plot_callbacks"):
        all_callbacks = results.get_all_plot_callbacks()
        print(f"Total available plot callbacks: {len(all_callbacks)}")

        # Get just extension callbacks
        if hasattr(results, "get_extension_plot_callbacks"):
            ext_callbacks = results.get_extension_plot_callbacks()
            print(f"Extension callbacks: {len(ext_callbacks)}")

            # Try each extension callback
            for i, callback in enumerate(ext_callbacks):
                try:
                    plot = callback()
                    if plot:
                        print(f"  Extension callback {i + 1}: Success")
                    else:
                        print(f"  Extension callback {i + 1}: Not applicable")
                except Exception as e:
                    print(f"  Extension callback {i + 1}: Error - {e}")

    return results


def example_extension_validation():
    """Demonstrate extension validation and dependency checking."""
    print("\n=== Extension Validation ===")

    registry = bch.get_registry()

    # Check which extensions are properly validated
    for ext_name in registry.list_extension_names():
        instance = registry.get_extension_instance(ext_name)
        if instance and hasattr(instance, "validate_dependencies"):
            is_valid = instance.validate_dependencies()
            print(f"Extension '{ext_name}': {'Valid' if is_valid else 'Invalid dependencies'}")

    # Create benchmark and check extension validation
    bench = bch.Bench("validation_demo", BenchmarkConfig, benchmark_function)
    bench_cfg = BenchmarkConfig().update(level=2)
    results = bench.plot_sweep(bench_cfg, run_cfg=bch.BenchRunCfg(repeats=1, save_db=False))

    if hasattr(results, "validate_extensions"):
        validation_results = results.validate_extensions()
        print("Extension validation results:")
        for ext_name, is_valid in validation_results.items():
            print(f"  {ext_name}: {'✓' if is_valid else '✗'}")


def main():
    """Run all extension examples."""
    print("Bencher Extension System Examples")
    print("=" * 40)

    try:
        # Example 1: Automatic usage
        results1 = example_automatic_extension_usage()

        # Example 2: Manual control
        results2 = example_manual_extension_control()

        # Example 3: Callbacks
        results3 = example_extension_callbacks()

        # Example 4: Validation
        example_extension_validation()

        print("\n✓ All examples completed successfully!")

    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
