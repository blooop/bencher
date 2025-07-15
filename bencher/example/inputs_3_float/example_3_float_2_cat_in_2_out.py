"""Demonstration of benchmarking with 3 float and 2 categorical inputs producing visually distinct patterns.

Each categorical input has 2 conditions that create distinctly different surface shapes in 3D space.
"""

import random
import math
import bencher as bch
import holoviews as hv

random.seed(0)


class Pattern3DModel2Cat(bch.ParametrizedSweep):
    """Benchmark demonstrating 3D patterns with distinctive shapes based on 2 categorical settings."""

    # Float input parameters
    x_value = bch.FloatSweep(default=50, bounds=[0, 100], doc="X value parameter")
    y_value = bch.FloatSweep(default=50, bounds=[0, 100], doc="Y value parameter")
    z_value = bch.FloatSweep(default=50, bounds=[0, 100], doc="Z value parameter")

    # Categorical input parameters - each with 2 conditions
    geometry_type = bch.StringSweep(["spherical", "cylindrical"], doc="Geometry model")
    scaling_type = bch.StringSweep(["linear", "quadratic"], doc="Scaling behavior")
    # Removed composition_type categorical

    # Output metrics
    contrast = bch.ResultVar(units="ratio", doc="Secondary contrast measure")
    intensity = bch.ResultVar(units="units", doc="Primary response intensity")

    def __call__(self, **kwargs) -> dict:
        """Generate 3D responses with distinctly different patterns based on categorical inputs."""
        self.update_params_from_kwargs(**kwargs)

        # Normalize inputs to [0,1]
        x = self.x_value / 100
        y = self.y_value / 100
        z = self.z_value / 100

        # Calculate radial components based on geometry_type
        if self.geometry_type == "spherical":
            # Spherical geometry creates radial patterns from center
            r = math.sqrt(x**2 + y**2 + z**2) / math.sqrt(3)
            theta = math.atan2(y, x) / (2 * math.pi) + 0.5  # normalized [0,1]
            phi = math.acos(z / max(0.001, math.sqrt(x**2 + y**2 + z**2))) / math.pi
        else:  # cylindrical
            # Cylindrical geometry creates patterns based on distance from z-axis
            r = math.sqrt(x**2 + y**2) / math.sqrt(2)
            theta = math.atan2(y, x) / (2 * math.pi) + 0.5
            phi = z  # z directly affects the height

        # Apply scaling function
        if self.scaling_type == "linear":
            # Linear scaling creates more uniform patterns
            scale_factor = 1.5 * r + 0.8 * phi + 0.5 * theta
            scale_factor2 = 0.7 * r + 1.2 * phi + 0.9 * theta
        else:  # quadratic
            # Quadratic scaling creates more concentrated effects
            scale_factor = 1.5 * r**2 + 0.8 * phi**2 + 0.5 * theta
            scale_factor2 = 0.7 * r**2 + 1.2 * phi**2 + 0.9 * theta

        # Create wave patterns
        wave1 = math.sin(5 * math.pi * r) * math.cos(4 * math.pi * theta)
        wave2 = math.sin(3 * math.pi * phi) * math.sin(6 * math.pi * r * theta)

        # Create interference patterns
        pattern1 = math.sin(7 * math.pi * (x + y + z) / 3)
        pattern2 = math.cos(9 * math.pi * x * y * z)

        # Fixed to additive composition (removed composition_type categorical)
        # Additive creates smoother transitions
        self.intensity = 0.6 * scale_factor + 0.3 * wave1 + 0.2 * pattern1 + 0.5
        self.contrast = 0.4 * scale_factor2 + 0.5 * wave2 + 0.3 * pattern2 + 0.3

        # Add minimal randomness (to maintain pattern visibility)
        random_factor = random.uniform(0.98, 1.02)
        self.intensity *= random_factor
        self.contrast *= random_factor

        # Keep values in a reasonable range
        self.intensity = max(0.1, min(3.0, self.intensity))
        self.contrast = max(0.1, min(3.0, self.contrast))

        return super().__call__(**kwargs)


def example_3_float_2_cat_in_2_out(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Benchmark demonstrating 3D visual patterns based on 2 categorical settings.

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object
    """
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
        run_cfg.level = 5
    run_cfg.repeats = 1  # Fewer repeats for a quicker benchmark

    hv.opts.defaults(hv.opts.HeatMap(cmap="plasma", width=300, height=300, colorbar=True))

    bench = Pattern3DModel2Cat().to_bench(run_cfg, report)
    bench.plot_sweep(
        title="3D Pattern Visualization (3 Float, 2 Categorical Variables)",
        description="Response patterns with distinctive shapes based on 3D coordinates and 2 categorical settings",
        post_description="""
        Geometry Type: Spherical (radial from center) vs Cylindrical (distance from z-axis)
        Scaling Type: Linear (uniform effects) vs Quadratic (concentrated effects)
        
        This example uses additive composition for pattern generation (fixed parameter).
        2D slices of the 3D space show visually distinctive patterns that vary based on categorical settings.
        The intensity and contrast measures reveal different aspects of the underlying mathematical model.
        """,
    )

    return bench


if __name__ == "__main__":
    example_3_float_2_cat_in_2_out().report.show()
