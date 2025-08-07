"""Example demonstrating the unified data filtering and plotting interface."""

from __future__ import annotations
import bencher as bch


class ExampleSweep(bch.ParametrizedSweep):
    """Example sweep for demonstrating unified plotting."""

    x = bch.FloatSweep(default=1.0, bounds=[0.0, 10.0], samples=10)
    y = bch.FloatSweep(default=2.0, bounds=[0.0, 5.0], samples=5)
    category = bch.StringSweep(["A", "B", "C"])

    def __call__(self, **kwargs):
        # Simple quadratic function with category-dependent offset
        category_offset = {"A": 0, "B": 10, "C": 20}[self.category]
        output_value = self.x**2 + self.y + category_offset
        noise = output_value * 0.1 * (hash(str(kwargs)) % 100 / 100.0)  # Reproducible noise

        return {
            "result": output_value + noise,
            "secondary": self.x * self.y + category_offset * 0.1,
            "error_metric": abs(noise),
        }


def example_unified_plotting():
    """Demonstrate the unified plotting interface."""

    # Create benchmark results using the to_bench method
    bench_cfg = bch.BenchRunCfg()
    bench_cfg.repeats = 3
    bench_cfg.over_time = False

    bench = ExampleSweep().to_bench(bench_cfg)
    bench.plot_sweep(
        title="Unified Plotting Example",
        description="Demonstrating the new unified filtering and plotting interface",
    )

    # Get the results - the actual BenchResult object
    bench_result = bench.results[0]  # Get the first (and only) result

    # Import unified interface and example plotters
    from bencher.results.unified_filter import UnifiedPlottingInterface, DataFilter
    from bencher.results.example_plotters import (
        ScatterPlotInterface,
        LinePlotInterface,
        HeatmapPlotInterface,
        CustomTableInterface,
    )

    # Create the unified interface
    unified = UnifiedPlottingInterface(bench_result)

    # Register example plotters
    unified.register_plotter(ScatterPlotInterface())
    unified.register_plotter(LinePlotInterface())
    unified.register_plotter(HeatmapPlotInterface())
    unified.register_plotter(CustomTableInterface())

    print("=== Unified Plotting Interface Example ===")
    print(f"Available plotters: {unified.plotter_registry.list_plotters()}")

    # Example 1: Basic filtering and plotting
    print("\n1. Basic Data Filtering:")

    # Create a filter to select only category "A" data
    basic_filter = DataFilter().select_dimension("category", "A")
    filtered_data = unified.filter_data(basic_filter)
    print(f"Original data shape: {bench_result.ds.sizes}")
    print(f"Filtered data shape: {filtered_data.sizes}")

    # Example 2: Complex filtering
    print("\n2. Complex Data Filtering:")

    # Filter for specific x range and categories
    complex_filter = (
        DataFilter()
        .slice_dimension("x", start=2.0, end=8.0)
        .select_dimension("category", ["A", "B"])
    )
    complex_filtered = unified.filter_data(complex_filter)
    print(f"Complex filtered data shape: {complex_filtered.sizes}")

    # Example 3: Check compatible plotters
    print("\n3. Compatible Plotters:")

    # Check which plotters work with full data
    full_compatible = unified.list_compatible_plotters()
    print(f"Plotters compatible with full data: {full_compatible}")

    # Check which plotters work with 2D slice (for heatmap)
    slice_2d_filter = (
        DataFilter().select_dimension("category", "A").isel_dimension("repeat", 0)
    )  # Remove repeat dimension
    slice_compatible = unified.list_compatible_plotters(slice_2d_filter)
    print(f"Plotters compatible with 2D slice: {slice_compatible}")

    # Example 4: Auto-plotting
    print("\n4. Auto-Plotting:")

    # Generate all compatible plots for filtered data
    auto_plots = unified.auto_plot(data_filter=basic_filter, width=500, height=300)
    print(f"Generated {len(auto_plots)} automatic plots")
    for plotter_name, plot in auto_plots:
        print(f"  - {plotter_name}: {type(plot).__name__}")

    # Example 5: Specific plotting
    print("\n5. Specific Plotting:")

    # Create a heatmap of the 2D data
    try:
        unified.create_plot(
            "heatmap", data_filter=slice_2d_filter, width=600, height=400, title="Custom Heatmap"
        )
        print("Successfully created heatmap")
    except ValueError as e:
        print(f"Could not create heatmap: {e}")

    # Create a table view of all data
    unified.create_plot("table", max_rows=20, width=800)
    print("Successfully created table")

    # Example 6: Result-specific plotting
    print("\n6. Result-Specific Plotting:")

    result_var = bench_result.bench_cfg.result_vars[0]  # Get first result variable
    specific_plots = unified.auto_plot(
        result_var=result_var, data_filter=basic_filter, prefer_plotters=["line", "scatter"]
    )
    print(f"Generated {len(specific_plots)} plots for specific result variable")

    return bench_result, unified


if __name__ == "__main__":
    result, unified_interface = example_unified_plotting()

    # You can continue to use the unified interface
    print("\n=== Interface Ready for Interactive Use ===")
    print("Use 'unified_interface' to experiment with filtering and plotting")
    print("Use 'result' to access the original benchmark result")
