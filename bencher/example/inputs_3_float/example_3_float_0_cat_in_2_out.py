"""Demonstration of benchmarking with 3 float inputs and no categorical inputs.

This example shows a 3D parameter space with consistent mathematical pattern generation.
"""

import random
import math
import bencher as bch
import holoviews as hv

random.seed(0)


class Pattern3DModel0Cat(bch.ParametrizedSweep):
    """Benchmark demonstrating 3D patterns without categorical settings."""

    # Float input parameters
    x_value = bch.FloatSweep(default=50, bounds=[0, 100], doc="X value parameter")
    y_value = bch.FloatSweep(default=50, bounds=[0, 100], doc="Y value parameter")
    z_value = bch.FloatSweep(default=50, bounds=[0, 100], doc="Z value parameter")

    # No categorical inputs - all parameters are fixed

    # Output metrics
    contrast = bch.ResultVar(units="ratio", doc="Secondary contrast measure")
    intensity = bch.ResultVar(units="units", doc="Primary response intensity")

    def __call__(self, **kwargs) -> dict:
        """Generate 3D responses with consistent pattern generation."""
        self.update_params_from_kwargs(**kwargs)

        # Normalize inputs to [0,1]
        x = self.x_value / 100
        y = self.y_value / 100
        z = self.z_value / 100

        # Fixed to spherical geometry
        # Spherical geometry creates radial patterns from center
        r = math.sqrt(x**2 + y**2 + z**2) / math.sqrt(3)
        theta = math.atan2(y, x) / (2 * math.pi) + 0.5  # normalized [0,1]
        phi = math.acos(z / max(0.001, math.sqrt(x**2 + y**2 + z**2))) / math.pi

        # Fixed to linear scaling
        # Linear scaling creates more uniform patterns
        scale_factor = 1.5 * r + 0.8 * phi + 0.5 * theta
        scale_factor2 = 0.7 * r + 1.2 * phi + 0.9 * theta

        # Create wave patterns
        wave1 = math.sin(5 * math.pi * r) * math.cos(4 * math.pi * theta)
        wave2 = math.sin(3 * math.pi * phi) * math.sin(6 * math.pi * r * theta)

        # Create interference patterns
        pattern1 = math.sin(7 * math.pi * (x + y + z) / 3)
        pattern2 = math.cos(9 * math.pi * x * y * z)

        # Fixed to additive composition
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


def example_3_float_0_cat_in_2_out(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Benchmark demonstrating 3D visual patterns with no categorical settings.

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

    bench = Pattern3DModel0Cat().to_bench(run_cfg, report)
    bench.plot_sweep(
        title="3D Pattern Visualization (3 Float Variables, No Categorical Variables)",
        description="Response patterns based purely on 3D coordinates with no categorical settings",
        post_description="""
        This example uses fixed parameters for all categorical settings:
        - Spherical geometry (radial patterns from center)
        - Linear scaling (uniform effects)
        - Additive composition (smooth transitions)
        
        2D slices of the 3D space show how the input coordinates affect the pattern generation.
        The intensity and contrast measures reveal different aspects of the underlying mathematical model.
        """,
    )

    return bench


if __name__ == "__main__":
    example_3_float_0_cat_in_2_out().report.show()
