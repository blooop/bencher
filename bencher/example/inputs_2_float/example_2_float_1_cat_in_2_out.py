"""Demonstration of benchmarking with 2 float and 1 categorical input producing visually distinct patterns.

The categorical input has 2 conditions that create distinctly different surface shapes.
"""

import random
import math
import bencher as bch

random.seed(0)


class Pattern1CatBenchmark(bch.ParametrizedSweep):
    """Benchmark demonstrating patterns with distinctive shapes based on pattern type."""

    # Float input parameters
    x_value = bch.FloatSweep(default=100, bounds=[1, 100], doc="X value parameter")
    y_value = bch.FloatSweep(default=10, bounds=[1, 100], doc="Y value parameter")

    # Categorical input parameter - with 2 conditions
    pattern_type = bch.StringSweep(["linear", "exponential"], doc="Pattern relationship")
    # symmetry_type and feature_type removed

    # Output metrics
    response_a = bch.ResultVar(units="units", doc="Response variable A")
    response_b = bch.ResultVar(units="units", doc="Response variable B")

    def __call__(self, **kwargs) -> dict:
        """Generate responses with distinctly different patterns based on pattern type."""
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

        # Using fixed "symmetric" symmetry type
        sym_a = (x + y) ** 2
        sym_b = (x + y) * abs(x - y)

        # Using fixed "smooth" feature type
        feat_a = math.sin(3 * math.pi * x) * math.sin(3 * math.pi * y)
        feat_b = math.cos(3 * math.pi * x) * math.cos(3 * math.pi * y)

        # Simplified weights dictionary for 1 categorical variable
        weights = {
            "linear": ([1, 2, 0.5], [1, 1.5, 0.3]),  # Valley pattern
            "exponential": ([1, 1, 0.3], [1, 0.8, 0.4]),  # Corner peak with ripples
        }

        # Get the weights for the current pattern type
        w_a, w_b = weights[self.pattern_type]

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


def example_2_float_1_cat_in_2_out(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Benchmark demonstrating visually distinct patterns based on pattern type.

    This example is simplified from the 2-category version by fixing the symmetry_type
    to "symmetric" and feature_type to "smooth".

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object
    """
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 3  # Fewer repeats for a quicker benchmark

    bench = Pattern1CatBenchmark().to_bench(run_cfg, report)
    bench.plot_sweep(
        title="Pattern Visualization (2 Float, 1 Categorical Variable)",
        description="Response patterns with distinctive shapes based on pattern type",
        post_description="""
        Pattern Type: Linear (diagonal gradients) vs Exponential (corner-concentrated)
        
        Each pattern type produces a unique surface shape that remains visually distinctive
        even with auto-scaling of the color maps. This example uses fixed "symmetric" symmetry
        and "smooth" feature settings.
        """,
    )
    return bench


if __name__ == "__main__":
    example_2_float_1_cat_in_2_out().report.show()
