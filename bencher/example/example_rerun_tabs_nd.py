import rerun as rr
import rerun.blueprint as rrb
import bencher as bch
import math

rr.init("rerun_example_tabs_nd", spawn=True)


class SweepRerunTabsND(bch.ParametrizedSweep):
    """Multi-dimensional parameter sweep for rerun tabs demonstration"""

    # Define multiple parameters of different types
    theta = bch.FloatSweep(
        default=1, bounds=[0, math.pi], doc="Angle parameter", units="rad", samples=3
    )
    scale = bch.FloatSweep(default=1, bounds=[0.5, 2.0], doc="Scale factor", units="", samples=3)
    shape_type = bch.EnumSweep(["box", "circle", "triangle"], doc="Shape type")

    # Result variable for tracking
    result_value = bch.ResultVar(doc="Combined result for tracking")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        # Create entity path that includes all parameter values
        entity_path = f"sweep/{self.shape_type}/theta_{self.theta:.2f}_scale_{self.scale:.2f}"

        print(f"Logging to rerun path: {entity_path}")
        print(
            f"  Parameters: theta={self.theta:.2f}, scale={self.scale:.2f}, shape={self.shape_type}"
        )

        # Log different shapes based on shape_type
        if self.shape_type == "box":
            rr.log(
                f"{entity_path}/shape", rr.Boxes2D(half_sizes=[self.theta * self.scale, self.scale])
            )
        elif self.shape_type == "circle":
            # Create circle using points in a circle pattern
            import numpy as np

            angles = np.linspace(0, 2 * np.pi, 20)
            radius = self.theta * self.scale * 0.5
            x = radius * np.cos(angles)
            y = radius * np.sin(angles)
            points = np.column_stack([x, y])
            rr.log(f"{entity_path}/shape", rr.Points2D(points))
        elif self.shape_type == "triangle":
            # Create triangle using linestrips
            import numpy as np

            size = self.theta * self.scale
            triangle_points = np.array(
                [
                    [0, size],
                    [-size / 2, -size / 2],
                    [size / 2, -size / 2],
                    [0, size],  # Close the triangle
                ]
            )
            rr.log(f"{entity_path}/shape", rr.LineStrips2D([triangle_points]))

        # Log some metadata for each shape
        rr.log(
            f"{entity_path}/info",
            rr.TextDocument(
                f"Shape: {self.shape_type}\nTheta: {self.theta:.2f} rad\nScale: {self.scale:.2f}"
            ),
        )

        # Return combined result
        self.result_value = self.theta * self.scale
        return super().__call__(**kwargs)


def create_hierarchical_blueprint_tabs(bench_result):
    """Create a hierarchical blueprint with tabs organized by parameter dimensions"""

    # Get all input variables from the benchmark
    input_vars = bench_result.bench_cfg.input_vars

    # Get unique values for each parameter
    param_values = {}
    for var in input_vars:
        var_name = var.name
        unique_vals = bench_result.ds[var_name].values
        param_values[var_name] = unique_vals
        print(f"Parameter {var_name}: {unique_vals}")

    # Automatically detect parameter types using bencher's type system
    categorical_params = []
    continuous_params = []

    for var in input_vars:
        # Check if it's an EnumSweep or has enum-like behavior
        var_type = type(var).__name__
        if "Enum" in var_type or hasattr(var, "enum_values"):
            categorical_params.append(var)
        elif "Float" in var_type or "Int" in var_type:
            continuous_params.append(var)
        else:
            # Default to categorical for unknown types
            categorical_params.append(var)

    print(f"Categorical parameters: {[p.name for p in categorical_params]}")
    print(f"Continuous parameters: {[p.name for p in continuous_params]}")

    # Adaptive tab creation strategy based on parameter composition
    tab_views = []

    if categorical_params:
        # Strategy 1: Use categorical parameters as primary tab organizers
        primary_param = categorical_params[0]
        primary_values = param_values[primary_param.name]

        if len(categorical_params) > 1:
            # Multiple categorical: create nested organization
            secondary_param = categorical_params[1]
            secondary_values = param_values[secondary_param.name]

            for pval in primary_values:
                for sval in secondary_values:
                    view = rrb.Spatial2DView(
                        name=f"{primary_param.name}:{pval} | {secondary_param.name}:{sval}",
                        origin=f"sweep/{pval}",  # Could be enhanced to filter by both
                    )
                    tab_views.append(view)
        else:
            # Single categorical parameter
            for val in primary_values:
                view = rrb.Spatial2DView(name=f"{primary_param.name}: {val}", origin=f"sweep/{val}")
                tab_views.append(view)

    elif continuous_params:
        # Strategy 2: No categorical params, use continuous parameter ranges
        primary_param = continuous_params[0]
        primary_values = param_values[primary_param.name]

        # Create tabs for each unique value of the primary continuous parameter
        for val in primary_values:
            # Format the value appropriately
            if isinstance(val, float):
                val_str = f"{val:.2f}"
            else:
                val_str = str(val)

            view = rrb.Spatial2DView(
                name=f"{primary_param.name}: {val_str} {getattr(primary_param, 'units', '')}",
                origin="sweep",  # Show all, but could filter by parameter value
            )
            tab_views.append(view)

    else:
        # Fallback: single view
        tab_views = [rrb.Spatial2DView(name="All Results", origin="sweep")]

    # Create the blueprint with tabs
    blueprint = rrb.Blueprint(rrb.Tabs(*tab_views))

    return blueprint


def example_rerun_tabs_nd(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Example showing how to organize multi-dimensional rerun results in tabs using blueprint system"""

    # Create the sweep configuration
    sweep = SweepRerunTabsND()

    # Set default run config if not provided
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg(
            level=2
        )  # Start with level 2 for manageable number of combinations

    print(f"Running N-dimensional sweep with level {run_cfg.level}")

    # Run the actual sweep first (this will log all data to rerun)
    bench = sweep.to_bench(run_cfg, report)
    results = bench.plot_sweep()

    print("Finished logging data to rerun")
    print("Creating hierarchical blueprint...")

    # Create hierarchical blueprint based on the actual parameter space
    blueprint = create_hierarchical_blueprint_tabs(results)
    rr.send_blueprint(blueprint)

    print("Blueprint sent to rerun")
    print("Check the Rerun viewer window - it should show tabs organized by parameter dimensions!")

    return bench


# Demo classes defined at module level to avoid pickling issues
class Sweep2D(bch.ParametrizedSweep):
    x = bch.FloatSweep(default=0, bounds=[-1, 1], samples=3)
    y = bch.FloatSweep(default=0, bounds=[-1, 1], samples=3)
    result = bch.ResultVar()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        entity_path = f"2d_test/x_{self.x:.1f}_y_{self.y:.1f}"
        rr.log(f"{entity_path}/point", rr.Points2D([[self.x, self.y]]))
        self.result = self.x + self.y
        return super().__call__(**kwargs)


class SweepCategorical(bch.ParametrizedSweep):
    color = bch.EnumSweep(["red", "green", "blue"])
    size = bch.EnumSweep(["small", "large"])
    result = bch.ResultVar()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        entity_path = f"cat_test/{self.color}/{self.size}"
        # Use different shapes for different combinations
        if self.size == "small":
            rr.log(f"{entity_path}/shape", rr.Points2D([[0, 0]]))
        else:
            rr.log(f"{entity_path}/shape", rr.Boxes2D(half_sizes=[0.5, 0.5]))
        self.result = 1.0
        return super().__call__(**kwargs)


def demo_different_dimensions():
    """Demonstrate the system with different parameter combinations"""

    print("\n" + "=" * 60)
    print("DEMO: Testing different dimensional parameter combinations")
    print("=" * 60)

    print("\nTest 1: 2D Continuous Parameters")
    bench_2d = Sweep2D().to_bench(bch.BenchRunCfg(level=2))
    results_2d = bench_2d.plot_sweep()
    blueprint_2d = create_hierarchical_blueprint_tabs(results_2d)
    rr.send_blueprint(blueprint_2d)

    print("\nTest 2: Pure Categorical Parameters")
    bench_cat = SweepCategorical().to_bench(bch.BenchRunCfg(level=2))
    results_cat = bench_cat.plot_sweep()
    blueprint_cat = create_hierarchical_blueprint_tabs(results_cat)
    rr.send_blueprint(blueprint_cat)

    print("\nCompleted dimensional tests. Check rerun viewer for organized results!")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        # Run comprehensive demo
        demo_different_dimensions()
    else:
        # Run main example
        bench = example_rerun_tabs_nd(bch.BenchRunCfg(level=2))
        print("Example completed successfully!")
        print("The Rerun viewer window shows tabs organized by the shape_type parameter.")
        print("Each tab contains visualizations for different theta/scale combinations.")
        print("\nTry running with --demo flag to see different dimensional combinations!")

    # Keep the script running briefly so the rerun viewer stays open
    import time

    time.sleep(2)
    print("Script completed. The Rerun viewer window should remain open.")
