"""This file demonstrates benchmarking with categorical inputs and multiple outputs with repeats.

It simulates comparing programming languages and development environments, measuring
performance and developer productivity metrics.
"""

import random
import bencher as bch

random.seed(42)  # Fixed seed for reproducibility


class ProgrammingBenchmark(bch.ParametrizedSweep):
    """Benchmark class comparing programming languages and development environments."""

    language = bch.StringSweep(
        ["Python", "JavaScript", "Rust", "Go"], doc="Programming language being benchmarked"
    )
    environment = bch.StringSweep(
        ["Development", "Testing", "Production"], doc="Environment configuration"
    )

    is_successful = bch.ResultBool(doc="Whether the benchmark run was successful")
    score = bch.ResultVar(units="score", doc="A floating point score for the run")

    def __call__(self, **kwargs) -> dict:
        """Execute the parameter sweep for the given inputs.

        Args:
            **kwargs: Additional parameters to update before executing

        Returns:
            dict: Dictionary containing the outputs of the parameter sweep
        """
        self.update_params_from_kwargs(**kwargs)

        # Assign a float score based on language and environment
        base_score = 0.0
        if self.language == "Python":
            base_score = 70.0
        elif self.language == "JavaScript":
            base_score = 60.0
        elif self.language == "Rust":
            base_score = 95.0
        elif self.language == "Go":
            base_score = 85.0

        # Environment affects score
        if self.environment == "Development":
            env_modifier = 0.9
        elif self.environment == "Testing":
            env_modifier = 0.95
        else:  # Production
            env_modifier = 1.0

        # Calculate final score with some randomness
        self.score = base_score * env_modifier * random.uniform(0.95, 1.05)

        # Boolean result: success if score above a threshold
        self.is_successful = self.score > 65.0

        return super().__call__(**kwargs)


def example_2_cat_in_4_out_repeats(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """This example compares a boolean and a float result across programming languages and environments.

    It demonstrates how to sample categorical variables with multiple repeats
    and plot the results of a boolean and a float output variable.

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object
    """

    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 15  # Run multiple times to get statistical significance
    bench = ProgrammingBenchmark().to_bench(run_cfg, report)
    bench.plot_sweep(
        title="Programming Language and Environment: Boolean and Float Results",
        description="Comparing a boolean (success) and a float (score) result across different programming languages and environments",
    )

    return bench


if __name__ == "__main__":
    example_2_cat_in_4_out_repeats().report.show()
