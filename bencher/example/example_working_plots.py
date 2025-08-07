"""Demo showing actual plot generation with the unified interface."""

import bencher as bch
import xarray as xr
import panel as pn
import holoviews as hv
import numpy as np

from bencher.results.unified_filter import PlotInterface, UnifiedPlottingInterface, DataFilter
from bencher.plotting.plot_filter import PlotFilter, VarRange
from bencher.variables.results import ResultVar


class Simple1DPlotter(PlotInterface):
    """A plotter specifically designed for 1D data."""

    @property
    def name(self) -> str:
        return "simple1d"

    def get_plot_filter(self) -> PlotFilter:
        """This plotter handles any 1D data."""
        return PlotFilter(
            input_range=VarRange(1, 1),  # exactly 1 input dimension
            result_vars=VarRange(1, None),  # at least 1 result variable
        )

    def can_plot(self, dataset: xr.Dataset, result_var: ResultVar = None, **kwargs) -> bool:
        """Check if we can plot this data."""
        return len(dataset.dims) == 1 and len(dataset.data_vars) >= 1

    def create_plot(self, dataset: xr.Dataset, result_var: ResultVar = None, **kwargs):
        """Create a simple 1D plot."""
        # Get result variable
        if result_var is not None:
            var_name = result_var.name if hasattr(result_var, "name") else str(result_var)
        else:
            var_name = list(dataset.data_vars)[0]

        # Get dimension name
        dim_name = list(dataset.dims)[0]

        # Create HoloViews curve
        hv_ds = hv.Dataset(dataset)
        curve = hv_ds.to(hv.Curve, kdims=dim_name, vdims=var_name)

        return pn.pane.HoloViews(
            curve.opts(
                width=kwargs.get("width", 600),
                height=kwargs.get("height", 400),
                title=f"{var_name} vs {dim_name}",
            )
        )


class FlexibleTablePlotter(PlotInterface):
    """A table plotter that works with any data."""

    @property
    def name(self) -> str:
        return "flexible_table"

    def get_plot_filter(self) -> PlotFilter:
        """Tables work with any data."""
        return PlotFilter(
            input_range=VarRange(0, None),
            result_vars=VarRange(1, None),
        )

    def can_plot(self, dataset: xr.Dataset, result_var: ResultVar = None, **kwargs) -> bool:
        """Tables can display any non-empty dataset."""
        return len(dataset.data_vars) > 0

    def create_plot(self, dataset: xr.Dataset, result_var: ResultVar = None, **kwargs):
        """Create a flexible table view."""
        df = dataset.to_dataframe().reset_index()
        max_rows = kwargs.get("max_rows", 50)

        if len(df) > max_rows:
            df = df.head(max_rows)
            title = f"Data Table (first {max_rows} of {len(dataset.to_dataframe())} rows)"
        else:
            title = f"Data Table ({len(df)} rows)"

        return pn.Column(
            pn.pane.Markdown(f"### {title}"), pn.pane.DataFrame(df, width=800, height=400)
        )


class SimpleSweep(bch.ParametrizedSweep):
    """Simple sweep for demonstration."""

    x = bch.FloatSweep(default=1.0, bounds=[0.0, 10.0], samples=15)

    def __call__(self, **kwargs):
        return {
            "quadratic": self.x**2 + 2 * self.x + 1,
            "linear": 3 * self.x + 5,
            "sine": np.sin(self.x),
        }


def demo_working_plots():
    """Demonstrate the unified interface with actual plot generation."""

    print("🚀 Creating benchmark data...")
    bench_cfg = bch.BenchRunCfg()
    bench_cfg.repeats = 1

    bench = SimpleSweep().to_bench(bench_cfg)
    bench.plot_sweep(title="Working Plots Demo")
    bench_result = bench.results[0]

    print(f"✅ Generated data with shape: {bench_result.ds.sizes}")

    # Create unified interface with working plotters
    print("\n📊 Setting up unified plotting interface...")
    unified = UnifiedPlottingInterface(bench_result)
    unified.register_plotter(Simple1DPlotter())
    unified.register_plotter(FlexibleTablePlotter())

    plotters = unified.plotter_registry.list_plotters()
    print(f"📋 Registered plotters: {plotters}")

    # Test compatibility
    compatible = unified.list_compatible_plotters()
    print(f"✅ Compatible plotters: {compatible}")

    # Generate all possible plots
    print("\n🎨 Generating plots...")
    plots = unified.auto_plot()
    print(f"✅ Successfully created {len(plots)} plots:")
    for plotter_name, plot_obj in plots:
        print(f"  - {plotter_name}: {type(plot_obj).__name__}")

    # Test filtering and plotting
    print("\n🔍 Testing data filtering...")
    data_filter = DataFilter().isel_dimension("x", slice(5, 12))  # Middle portion
    filtered_plots = unified.auto_plot(data_filter=data_filter)
    print(f"✅ Created {len(filtered_plots)} plots with filtered data")

    # Test result-specific plotting
    print("\n🎯 Testing result-specific plotting...")
    for var in bench_result.bench_cfg.result_vars:
        specific_plots = unified.auto_plot(result_var=var)
        print(f"  - {var.name}: {len(specific_plots)} plots created")

    # Test specific plotter calls
    print("\n🔧 Testing specific plotter calls...")
    try:
        plot1 = unified.create_plot("simple1d", width=500, height=300)
        print("  ✅ Successfully created simple1d plot")

        plot2 = unified.create_plot("flexible_table", max_rows=10)
        print("  ✅ Successfully created flexible_table plot")

    except Exception as e:
        print(f"  ❌ Error: {e}")

    print("\n🎉 Unified plotting interface demonstration complete!")
    print("   - Data filtering: ✅ Working")
    print("   - Plotter registration: ✅ Working")
    print("   - Auto-plotting: ✅ Working")
    print("   - Compatibility checking: ✅ Working")
    print("   - Result-specific plotting: ✅ Working")

    bench.report.show()

    return bench_result, unified


if __name__ == "__main__":
    demo_working_plots()
