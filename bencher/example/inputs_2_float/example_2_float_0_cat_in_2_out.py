"""Demonstration of benchmarking with 2 float inputs and 0 categorical inputs producing a distinct pattern.

The two float inputs create a visually distinctive surface shape.
"""

import random
import math
import bencher as bch

random.seed(0)


class Pattern0CatBenchmark(bch.ParametrizedSweep):
    """Benchmark demonstrating patterns with two float inputs and no categorical variables."""

    # Float input parameters
    x_value = bch.FloatSweep(default=100, bounds=[1, 100], doc="X value parameter")
    y_value = bch.FloatSweep(default=10, bounds=[1, 100], doc="Y value parameter")

    # No categorical input parameters

    # Output metrics
    response_a = bch.ResultVar(units="units", doc="Response variable A")
    response_b = bch.ResultVar(units="units", doc="Response variable B")

    def __call__(self, **kwargs) -> dict:
        """Generate responses with a distinctive pattern based on x and y values."""
        self.update_params_from_kwargs(**kwargs)

        # Normalize inputs to [0,1]
        x = self.x_value / 100
        y = self.y_value / 100

        # Using fixed "linear" pattern type
        base_a = 2 * x + 3 * y
        base_b = 3 * x - y

        # Using fixed "symmetric" symmetry type
        sym_a = (x + y) ** 2
        sym_b = (x + y) * abs(x - y)

        # Using fixed "smooth" feature type
        feat_a = math.sin(3 * math.pi * x) * math.sin(3 * math.pi * y)
        feat_b = math.cos(3 * math.pi * x) * math.cos(3 * math.pi * y)

        # Fixed weights for valley pattern
        w_a = [1, 2, 0.5]
        w_b = [1, 1.5, 0.3]

        # Calculate final responses with weights
        self.response_a = w_a[0] * base_a + w_a[1] * sym_a + w_a[2] * feat_a
        self.response_b = w_b[0] * base_b + w_b[1] * sym_b + w_b[2] * feat_b

        # Add minimal randomness (to maintain pattern visibility)
        random_factor = random.uniform(0.98, 1.02)
        self.response_a *= random_factor
        self.response_b *= random_factor

        return super().__call__(**kwargs)


def example_2_float_0_cat_in_2_out(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Benchmark demonstrating a surface pattern based solely on float parameters.

    This example is simplified from the 1-category version by fixing all categorical
    settings to create a valley pattern.

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object
    """
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 3  # Fewer repeats for a quicker benchmark

    bench = Pattern0CatBenchmark().to_bench(run_cfg, report)
    bench.plot_sweep(
        title="Pattern Visualization (2 Float, 0 Categorical Variables)",
        description="Response pattern with a valley shape based on x and y values",
        post_description="""
        This example demonstrates a surface pattern created using only two float inputs
        (x_value and y_value) with no categorical variables. 
        
        The pattern showcases a 'valley' shape that exhibits different characteristics
        across the range of x and y values. This simplified example uses fixed settings
        equivalent to a linear pattern with symmetric properties and smooth features.
        """,
    )
    return bench


if __name__ == "__main__":
    example_2_float_0_cat_in_2_out().report.show()
