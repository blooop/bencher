"""Demonstration of benchmarking with 2 float and 3 categorical inputs producing visually distinct patterns.

Each categorical input has 2 conditions that create distinctly different surface shapes.
"""

import random
import math
import bencher as bch

random.seed(0)


class PatternBenchmark(bch.ParametrizedSweep):
    """Benchmark demonstrating patterns with distinctive shapes based on categorical settings."""

    # Float input parameters
    x_value = bch.FloatSweep(default=100, bounds=[1, 100], doc="X value parameter")
    y_value = bch.FloatSweep(default=10, bounds=[1, 100], doc="Y value parameter")

    # Categorical input parameters - each with 2 conditions
    pattern_type = bch.StringSweep(["linear", "exponential"], doc="Pattern relationship")
    symmetry_type = bch.StringSweep(["symmetric", "asymmetric"], doc="Pattern symmetry")
    feature_type = bch.StringSweep(["smooth", "ridged"], doc="Surface features")

    # Output metrics
    response_a = bch.ResultVar(units="units", doc="Response variable A")
    response_b = bch.ResultVar(units="units", doc="Response variable B")

    def __call__(self, **kwargs) -> dict:
        """Generate responses with distinctly different patterns based on categorical inputs."""
        self.update_params_from_kwargs(**kwargs)

        # Normalize inputs to [0,1]
        x = self.x_value / 100
        y = self.y_value / 100

        # Set base patterns based on pattern_type
        if self.pattern_type == "linear":
            base_a = 2 * x + 3 * y
            base_b = 3 * x - y
        else:  # exponential
            base_a = math.exp(2 * x) * math.exp(y) / math.exp(3)
            base_b = math.exp(x) * math.exp(2 * y) / math.exp(3)

        # Apply symmetry effect
        if self.symmetry_type == "symmetric":
            sym_a = (x + y) ** 2
            sym_b = (x + y) * abs(x - y)
        else:  # asymmetric
            sym_a = x**2 * y
            sym_b = x * y**2

        # Apply surface features
        if self.feature_type == "smooth":
            feat_a = math.sin(3 * math.pi * x) * math.sin(3 * math.pi * y)
            feat_b = math.cos(3 * math.pi * x) * math.cos(3 * math.pi * y)
        else:  # ridged
            feat_a = math.sin(8 * math.pi * x) ** 2 * math.sin(8 * math.pi * y) ** 2
            feat_b = abs(math.sin(10 * math.pi * x * y))

        # Combine patterns with weights that vary by condition combination
        # Each combination produces a visually distinct surface shape
        weights = {
            "linear": {
                "symmetric": {
                    "smooth": ([1, 2, 0.5], [1, 1.5, 0.3]),  # Valley pattern
                    "ridged": ([1, 1.5, 1.8], [1, 1, 2]),  # Diagonal ridges
                },
                "asymmetric": {
                    "smooth": ([1, 1.8, 0.7], [1, 1.2, 0.9]),  # Tilted plane with waves
                    "ridged": ([1, 1, 2.2], [1, 0.8, 2.5]),  # Grid pattern
                },
            },
            "exponential": {
                "symmetric": {
                    "smooth": ([1, 1, 0.3], [1, 0.8, 0.4]),  # Corner peak with ripples
                    "ridged": ([1, 0.7, 1.5], [1, 0.5, 1.8]),  # Corner peak with ridges
                },
                "asymmetric": {
                    "smooth": ([1, 1.5, 0.4], [1, 1.8, 0.2]),  # Curved gradient
                    "ridged": ([1, 1.2, 1.2], [1, 1.4, 1.4]),  # Extreme corner peak
                },
            },
        }

        # Get the weights for the current combination
        w_a, w_b = weights[self.pattern_type][self.symmetry_type][self.feature_type]

        # Calculate final responses with weights
        if self.pattern_type == "linear":
            self.response_a = w_a[0] * base_a + w_a[1] * sym_a + w_a[2] * feat_a
            self.response_b = w_b[0] * base_b + w_b[1] * sym_b + w_b[2] * feat_b
        else:  # exponential - multiplicative relationship
            self.response_a = base_a * (1 + w_a[1] * sym_a) * (1 + w_a[2] * feat_a)
            self.response_b = base_b * (1 + w_b[1] * sym_b) * (1 + w_b[2] * feat_b)

        # Add minimal randomness (to maintain pattern visibility)
        random_factor = random.uniform(0.98, 1.02)
        self.response_a *= random_factor
        self.response_b *= random_factor

        return super().__call__(**kwargs)


def example_2_float_3_cat_in_2_out(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Benchmark demonstrating visually distinct patterns based on categorical settings.

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object
    """
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 3  # Fewer repeats for a quicker benchmark

    bench = PatternBenchmark().to_bench(run_cfg, report)
    bench.plot_sweep(
        title="Pattern Visualization (2 Float, 3 Categorical Variables)",
        description="Response patterns with distinctive shapes based on categorical settings",
        post_description="""
        Pattern Type: Linear (diagonal gradients) vs Exponential (corner-concentrated)
        Symmetry Type: Symmetric (x/y similarity) vs Asymmetric (x/y difference)
        Feature Type: Smooth (gradual transitions) vs Ridged (sharp features)
        
        Each combination produces a unique pattern shape that remains visually distinctive
        even with auto-scaling of the color maps.
        """,
    )
    return bench


if __name__ == "__main__":
    example_2_float_3_cat_in_2_out().report.show()
