"""Demonstration of the Central Limit Theorem using parameter sweeps.

This example shows how sums of independent random variables tend to approximate
a Gaussian distribution as the number of samples increases.
"""

import random
import math
import numpy as np
import bencher as bch
import holoviews as hv
import pandas as pd


class CentralLimitTheoremDemo(bch.ParametrizedSweep):
    """Demonstrates the Central Limit Theorem by summing various distributions."""

    # Input parameter to control how many random samples to sum together
    num_samples = bch.IntSweep(
        default=1, bounds=[1, 50], samples=10, doc="Number of random samples to sum together"
    )

    # Parameter to select the source distribution
    distribution_type = bch.StringSweep(
        ["uniform", "exponential", "triangular", "discrete"],
        doc="Type of source distribution to sample from",
    )

    # Output results
    mean = bch.ResultVar(units="", doc="Sample mean")
    std_dev = bch.ResultVar(units="", doc="Sample standard deviation")
    skewness = bch.ResultVar(units="", doc="Sample skewness")
    kurtosis = bch.ResultVar(units="", doc="Sample kurtosis (peakedness)")

    # Store raw data separately for each run
    raw_data = bch.ResultReference(doc="Raw sample data for histogram visualization")

    def __call__(self, **kwargs) -> dict:
        """Generate sums of random variables and compute their statistics.

        Returns:
            dict: Results including statistics and raw data
        """
        self.update_params_from_kwargs(**kwargs)

        # Number of trials for each experiment
        num_trials = 1000

        # Initialize array to store sums
        sums = np.zeros(num_trials)

        # Generate the specified number of samples and sum them for each trial
        for i in range(num_trials):
            trial_sum = 0

            # Generate and sum samples based on the selected distribution
            for _ in range(self.num_samples):
                if self.distribution_type == "uniform":
                    # Uniform distribution between 0 and 1
                    sample = random.uniform(0, 1)
                elif self.distribution_type == "exponential":
                    # Exponential distribution with lambda=1
                    sample = random.expovariate(1)
                elif self.distribution_type == "triangular":
                    # Triangular distribution
                    sample = random.triangular(0, 0.5, 1)
                elif self.distribution_type == "discrete":
                    # Discrete distribution (like rolling a die)
                    sample = random.randint(1, 6)
                else:
                    sample = 0

                trial_sum += sample

            # Store the sum for this trial
            sums[i] = trial_sum

        # Compute statistics
        self.mean = float(np.mean(sums))
        self.std_dev = float(np.std(sums))

        # Compute skewness: 3rd standardized moment
        if self.std_dev > 0:
            m3 = np.mean((sums - self.mean) ** 3)
            self.skewness = float(m3 / (self.std_dev**3))
        else:
            self.skewness = 0

        # Compute kurtosis: 4th standardized moment - 3
        # (subtracting 3 makes the normal distribution have kurtosis=0)
        if self.std_dev > 0:
            m4 = np.mean((sums - self.mean) ** 4)
            self.kurtosis = float(m4 / (self.std_dev**4) - 3)
        else:
            self.kurtosis = 0

        # Store raw data for histogram visualization
        # Store data directly in ResultReference
        from bencher.variables.results import ResultReference
        self.raw_data = ResultReference(obj=sums.tolist(), container=None)

        # If we take many samples, normalize the sum to keep the scale consistent
        if self.num_samples > 1:
            # Normalize to have the same scale as a single sample
            if self.distribution_type == "uniform":
                # Uniform(0,1) has mean 0.5 and variance 1/12 per sample
                self.mean = (self.mean - self.num_samples * 0.5) / math.sqrt(
                    self.num_samples * (1 / 12)
                )
                self.std_dev = self.std_dev / math.sqrt(self.num_samples * (1 / 12))
            elif self.distribution_type == "exponential":
                # Exponential(1) has mean 1 and variance 1 per sample
                self.mean = (self.mean - self.num_samples * 1) / math.sqrt(self.num_samples)
                self.std_dev = self.std_dev / math.sqrt(self.num_samples)
            elif self.distribution_type == "triangular":
                # Triangular(0,0.5,1) has mean 0.5 and variance 1/24 per sample
                self.mean = (self.mean - self.num_samples * 0.5) / math.sqrt(
                    self.num_samples * (1 / 24)
                )
                self.std_dev = self.std_dev / math.sqrt(self.num_samples * (1 / 24))
            elif self.distribution_type == "discrete":
                # Discrete uniform 1-6 has mean 3.5 and variance 35/12 per sample
                self.mean = (self.mean - self.num_samples * 3.5) / math.sqrt(
                    self.num_samples * (35 / 12)
                )
                self.std_dev = self.std_dev / math.sqrt(self.num_samples * (35 / 12))

        return super().__call__(**kwargs)


def plot_histograms(bench_result):
    """Create histogram plots from raw data in the benchmark results."""
    plots = []
    
    # Get the dataset from the bench_result
    ds = bench_result.to_dataset()
    
    # Extract unique values for distribution_type and num_samples
    dist_types = list(ds.coords["distribution_type"].values)
    num_samples_vals = sorted(list(ds.coords["num_samples"].values))
    
    # Show subset of histograms for cleaner visualization
    samples_to_show = [1, 5, 10, 30] if len(num_samples_vals) > 3 else num_samples_vals
    samples_to_show = [s for s in samples_to_show if s in num_samples_vals]
    
    for dist_type in dist_types:
        for n_samples in samples_to_show:
            # Extract the raw data for this combination of distribution_type and num_samples
            raw_data_ref = ds["raw_data"].sel(
                distribution_type=dist_type, 
                num_samples=n_samples
            ).item()
            
            # Get the actual data list from the ResultReference
            raw_data = np.array(raw_data_ref)
            
            # Normalize data for consistent comparison
            if n_samples > 1:
                if dist_type == "uniform":
                    raw_data = (raw_data - n_samples * 0.5) / math.sqrt(n_samples * (1 / 12))
                elif dist_type == "exponential":
                    raw_data = (raw_data - n_samples * 1) / math.sqrt(n_samples)
                elif dist_type == "triangular":
                    raw_data = (raw_data - n_samples * 0.5) / math.sqrt(n_samples * (1 / 24))
                elif dist_type == "discrete":
                    raw_data = (raw_data - n_samples * 3.5) / math.sqrt(n_samples * (35 / 12))
            
            # Create histogram using HoloViews
            hist = hv.Histogram(np.histogram(raw_data, bins=30))
            hist = hist.opts(
                title=f"{dist_type.capitalize()}, n={n_samples}",
                xlabel="Normalized Sum Value",
                ylabel="Frequency",
                height=250,
                width=300,
            )
            
            # Add a standard normal PDF for comparison
            if n_samples > 1:
                x = np.linspace(min(raw_data), max(raw_data), 100)
                y = norm_pdf(x, 0, 1)  # Standard normal
                normal_curve = hv.Curve((x, y)).opts(color="red", line_width=2)
                hist = hist * normal_curve
            
            plots.append(hist)
    
    # Arrange plots in a grid
    layout = hv.Layout(plots).cols(4)
    return layout


def norm_pdf(x, mu, sigma):
    """Compute the normal probability density function."""
    return (1 / (sigma * math.sqrt(2 * math.pi))) * np.exp(-((x - mu) ** 2) / (2 * sigma**2))


def example_central_limit_theorem(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Demonstrate the Central Limit Theorem with various source distributions.

    Shows how sums of random variables from different distributions approach
    a normal distribution as the number of summed variables increases.

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object
    """
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()

    # Only need one trial since we're generating many samples internally
    run_cfg.repeats = 1

    # Set up holoviews options
    hv.opts.defaults(hv.opts.Curve(width=400, height=300, padding=0.1))

    # Create the benchmark
    bench = CentralLimitTheoremDemo().to_bench(run_cfg, report)

    # Plot standard metrics
    result = bench.plot_sweep(
        title="Central Limit Theorem Demonstration",
        description="""
        This example demonstrates the Central Limit Theorem, which states that the sum of a 
        sufficiently large number of independent random variables will approach a normal 
        distribution, regardless of the original distribution of the variables.
        
        The example shows how various statistics (mean, standard deviation, skewness, and kurtosis)
        change as we increase the number of random variables being summed together.
        
        Note that all distributions are normalized to have comparable scales.
        """,
        post_description="""
        As the number of summed samples increases:
        
        1. The skewness approaches 0 (symmetry of the normal distribution)
        2. The kurtosis approaches 0 (peakedness of the normal distribution)
        3. The histogram shape increasingly resembles a normal distribution (bell curve)
        
        This demonstrates that regardless of the original distribution shape (uniform, exponential, etc.),
        the sum tends toward a normal distribution as predicted by the Central Limit Theorem.
        """,
    )

    # Add histogram visualizations
    bench.report.append(plot_histograms(bench.get_result()))

    return bench


if __name__ == "__main__":
    example_central_limit_theorem().report.show()
