"""
Advanced Pareto Optimization Example with Randomness

This example demonstrates multi-objective optimization using Optuna with the Bencher framework.
It shows how to:
1. Define a problem with multiple competing objectives
2. Use Optuna's multi-objective optimization capabilities
3. Visualize and analyze the Pareto front
4. Compare different optimization approaches
5. Demonstrate the effect of randomness on Pareto optimization
"""

import bencher as bch
import numpy as np

np.random.seed(0)


class EngineeringDesignProblem(bch.ParametrizedSweep):
    """
    A simplified engineering design problem with two competing objectives.

    This example simulates a common engineering trade-off problem:
    - Performance vs Cost

    This is a classic multi-objective optimization scenario.
    The problem includes controlled randomness to simulate real-world variability
    in manufacturing processes and materials.
    """

    # Input design parameters - reduced to just 2
    material_quality = bch.FloatSweep(
        default=0.5, bounds=[0.1, 1.0], doc="Quality of the material (dimensionless)", samples=20
    )
    thickness = bch.FloatSweep(
        default=0.05, bounds=[0.01, 0.2], doc="Component thickness (m)", samples=20
    )

    # Result variables - reduced to just 2 objectives to be optimized
    performance = bch.ResultVar("score", bch.OptDir.maximize, doc="Performance metric (maximize)")
    cost = bch.ResultVar("$", bch.OptDir.minimize, doc="Manufacturing cost (minimize)")

    def __call__(self, **kwargs) -> dict:
        """
        Calculate the multi-objective outcomes based on input parameters.

        This simulates an engineering design problem where various objectives
        compete with each other:
        - Higher quality materials improve performance but increase cost
        - Thicker material improves performance but increases cost

        Includes inherent randomness to simulate:
        - Manufacturing variability
        - Material property variations
        - Measurement uncertainty
        """
        self.update_params_from_kwargs(**kwargs)

        # Base performance calculation
        base_performance = self.material_quality * 80 + self.thickness * 50

        # Add significant randomness (standard deviation = 10% of the base value)
        # This will create noticeably different results on each run
        performance_variability = 0.15 * base_performance
        self.performance = base_performance + np.random.normal(0, performance_variability)

        # Introduce a 30% chance of failure (e.g., due to manufacturing defects)
        if np.random.rand() < 0.3:
            self.performance = np.nan

        # Base cost calculation
        base_cost = self.material_quality * 100 + 10 / (self.thickness + 0.01)

        # Add randomness to cost (standard deviation = 8% of the base value)
        # Manufacturing costs can vary significantly in real-world scenarios
        cost_variability = 0.12 * base_cost
        self.cost = base_cost + np.random.normal(0, cost_variability)

        return self.get_results_values_as_dict()


def example_pareto(run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None) -> bch.Bench:
    """
    Advanced example of multi-objective Pareto optimization using Optuna.

    This function demonstrates:
    1. Grid search approach to visualize the entire parameter space
    2. True multi-objective optimization with Optuna
    3. Analysis of the Pareto front
    4. Effect of randomness on the Pareto front

    Args:
        run_cfg (BenchRunCfg): Configuration for the benchmark run
        report (BenchReport): Report object to store results

    Returns:
        Bench: Benchmark object with results
    """
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
        run_cfg.repeats = 5  # Multiple repeats to demonstrate randomness effects
        run_cfg.level = 4

    # Set up Optuna for multi-objective optimization
    run_cfg.use_optuna = True

    # Important: Set multiple repeats to demonstrate the effect of randomness
    # The framework will automatically calculate and plot both individual runs and averages
    run_cfg.repeats = 5

    # Create problem definition and benchmark
    bench = EngineeringDesignProblem().to_bench(run_cfg, report)

    # Perform grid search on our two input variables
    grid_result = bench.plot_sweep(
        title="Parameter Space Exploration with Variability",
        description="Exploring how material quality and thickness affect performance and cost with inherent randomness",
    )

    # Add Optuna-specific visualizations
    bench.report.append(grid_result.to_optuna_plots())

    return bench


if __name__ == "__main__":
    example_pareto().report.show()
