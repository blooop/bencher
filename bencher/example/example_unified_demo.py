"""Quick demonstration of the unified plotting interface with working plots."""
from __future__ import annotations
import bencher as bch


class SimpleSweep(bch.ParametrizedSweep):
    """Simple 1D sweep for demonstrating unified plotting."""
    x = bch.FloatSweep(default=1.0, bounds=[0.0, 10.0], samples=20)
    
    def __call__(self, **kwargs):
        return {
            "result": self.x**2 + 1,
            "secondary": self.x * 2,
        }


def demo_unified_plotting():
    """Quick demonstration of the unified plotting interface."""
    
    # Create simple 1D benchmark
    bench_cfg = bch.BenchRunCfg()
    bench_cfg.repeats = 1  # Single repeat for simplicity
    
    bench = SimpleSweep().to_bench(bench_cfg) 
    bench.plot_sweep(title="Simple Unified Demo")
    
    bench_result = bench.results[0]
    
    # Import unified interface
    from bencher.results.unified_filter import UnifiedPlottingInterface, DataFilter
    from bencher.results.example_plotters import (
        ScatterPlotInterface, LinePlotInterface, CustomTableInterface
    )
    
    # Create and setup unified interface
    unified = UnifiedPlottingInterface(bench_result)
    unified.register_plotter(ScatterPlotInterface())
    unified.register_plotter(LinePlotInterface())
    unified.register_plotter(CustomTableInterface())
    
    print("=== Quick Unified Plotting Demo ===")
    print(f"Data shape: {bench_result.ds.sizes}")
    print(f"Available plotters: {unified.plotter_registry.list_plotters()}")
    
    # Test compatibility
    compatible = unified.list_compatible_plotters()
    print(f"Compatible plotters: {compatible}")
    
    # Try auto-plotting
    if compatible:
        plots = unified.auto_plot()
        print(f"Successfully generated {len(plots)} plots:")
        for plotter_name, plot_obj in plots:
            print(f"  - {plotter_name}: {type(plot_obj).__name__}")
    
    # Test specific plotting
    if "table" in compatible:
        unified.create_plot("table", max_rows=10)
        print("Successfully created table plot")
    
    # Test filtering
    data_filter = DataFilter().isel_dimension("x", slice(0, 10))  # First half of data
    filtered_data = unified.filter_data(data_filter)
    print(f"Filtered data shape: {filtered_data.sizes}")
    
    if compatible:
        filtered_plots = unified.auto_plot(data_filter=data_filter)
        print(f"Generated {len(filtered_plots)} plots with filtered data")
    
    print("\n🎉 Unified plotting interface is working correctly!")
    return bench_result, unified


if __name__ == "__main__":
    demo_unified_plotting()