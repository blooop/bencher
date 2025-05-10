"""Simple Central Limit Theorem demonstration using matplotlib.

This example shows how sums of random samples from different distributions
approach a normal distribution as the number of samples increases.
It saves the visualizations as images using ResultImage.
"""

import random
import math
import numpy as np
import matplotlib.pyplot as plt
import bencher as bch
from scipy.stats import norm


class SimpleCLTDemo(bch.ParametrizedSweep):
    """A simplified Central Limit Theorem demonstration."""
    
    # Input parameter: number of random samples to sum
    num_samples = bch.IntSweep(
        default=1, 
        bounds=[1, 10], 
        samples=5, 
        doc="Number of random samples to sum together"
    )
    
    # Parameter to select the source distribution
    distribution_type = bch.StringSweep(
        ["uniform", "exponential", "gamma", "lognormal", "triangular", 
         "binomial", "poisson", "chi2", "beta", "pareto", "weibull"],
        doc="Type of source distribution to sample from"
    )
    
    # # Output statistics as numeric values
    # mean = bch.ResultVar(units="", doc="Sample mean")
    # std_dev = bch.ResultVar(units="", doc="Sample standard deviation")
    # skewness = bch.ResultVar(units="", doc="Sample skewness")
    
    # Output visualization as an image
    distribution_plot = bch.ResultImage(doc="Histogram plot showing the distribution")
    
    def __call__(self, **kwargs) -> dict:
        """Generate sums of random samples and create a visualization.
        
        Returns:
            dict: Results including statistics and plot image path
        """
        self.update_params_from_kwargs(**kwargs)
        
        # Number of trials for the experiment
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
                elif self.distribution_type == "gamma":
                    # Gamma distribution with k=2, theta=1
                    shape, scale = 2.0, 1.0
                    sample = np.random.gamma(shape, scale)
                elif self.distribution_type == "lognormal":
                    # Log-normal distribution with mean=0, sigma=0.5
                    mu, sigma = 0, 0.5
                    sample = np.random.lognormal(mu, sigma)
                elif self.distribution_type == "triangular":
                    # Triangular distribution between 0 and 1, with mode at 0.3
                    sample = np.random.triangular(0, 0.3, 1)
                elif self.distribution_type == "binomial":
                    # Binomial distribution with n=10, p=0.3
                    n, p = 10, 0.3
                    sample = np.random.binomial(n, p)
                elif self.distribution_type == "poisson":
                    # Poisson distribution with lambda=3
                    lam = 3
                    sample = np.random.poisson(lam)
                elif self.distribution_type == "chi2":
                    # Chi-squared distribution with k=3 degrees of freedom
                    df = 3
                    sample = np.random.chisquare(df)
                elif self.distribution_type == "beta":
                    # Beta distribution with alpha=2, beta=5
                    alpha, beta = 2, 5
                    sample = np.random.beta(alpha, beta)
                elif self.distribution_type == "pareto":
                    # Pareto distribution with alpha=3
                    alpha = 3
                    sample = np.random.pareto(alpha) + 1  # adding 1 to match scipy's definition
                elif self.distribution_type == "weibull":
                    # Weibull distribution with a=1, scale=1.5
                    a, scale = 1, 1.5
                    sample = np.random.weibull(a) * scale
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
        
        # Normalize data if we have more than one sample
        # This is to make the comparison with standard normal distribution easier
        if self.num_samples > 1:
            if self.distribution_type == "uniform":
                # Uniform(0,1) has mean 0.5 and variance 1/12 per sample
                normalized_sums = (sums - self.num_samples * 0.5) / math.sqrt(
                    self.num_samples * (1/12)
                )
            elif self.distribution_type == "exponential":
                # Exponential(1) has mean 1 and variance 1 per sample
                normalized_sums = (sums - self.num_samples * 1) / math.sqrt(self.num_samples)
            elif self.distribution_type == "gamma":
                # Gamma(2,1) has mean 2 and variance 2 per sample
                normalized_sums = (sums - self.num_samples * 2) / math.sqrt(self.num_samples * 2)
            elif self.distribution_type == "lognormal":
                # Log-normal(0,0.5) has mean exp(0.5/2) and variance (exp(0.5)-1)*exp(0.5)
                mean_ln = math.exp(0.5/2)
                var_ln = (math.exp(0.5) - 1) * math.exp(0.5)
                normalized_sums = (sums - self.num_samples * mean_ln) / math.sqrt(self.num_samples * var_ln)
            elif self.distribution_type == "triangular":
                # Triangular(0,0.3,1) has mean (0+0.3+1)/3 and variance calculated accordingly
                mean_tri = (0 + 0.3 + 1) / 3
                var_tri = (0**2 + 0.3**2 + 1**2 - 0*0.3 - 0.3*1 - 1*0) / 18
                normalized_sums = (sums - self.num_samples * mean_tri) / math.sqrt(self.num_samples * var_tri)
            elif self.distribution_type == "binomial":
                # Binomial(10,0.3) has mean n*p and variance n*p*(1-p)
                n, p = 10, 0.3
                normalized_sums = (sums - self.num_samples * n * p) / math.sqrt(self.num_samples * n * p * (1-p))
            elif self.distribution_type == "poisson":
                # Poisson(3) has mean and variance both equal to lambda=3
                lam = 3
                normalized_sums = (sums - self.num_samples * lam) / math.sqrt(self.num_samples * lam)
            elif self.distribution_type == "chi2":
                # Chi-squared(k) has mean k and variance 2k
                df = 3
                normalized_sums = (sums - self.num_samples * df) / math.sqrt(self.num_samples * 2 * df)
            elif self.distribution_type == "beta":
                # Beta(alpha,beta) has mean alpha/(alpha+beta) and variance alpha*beta/((alpha+beta)^2 * (alpha+beta+1))
                alpha, beta = 2, 5
                mean_beta = alpha / (alpha + beta)
                var_beta = (alpha * beta) / ((alpha + beta)**2 * (alpha + beta + 1))
                normalized_sums = (sums - self.num_samples * mean_beta) / math.sqrt(self.num_samples * var_beta)
            elif self.distribution_type == "pareto":
                # Pareto(alpha,1) has mean alpha/(alpha-1) for alpha>1 and variance alpha/((alpha-1)^2*(alpha-2)) for alpha>2
                alpha = 3
                mean_pareto = alpha / (alpha - 1)
                var_pareto = alpha / ((alpha - 1)**2 * (alpha - 2))
                normalized_sums = (sums - self.num_samples * mean_pareto) / math.sqrt(self.num_samples * var_pareto)
            elif self.distribution_type == "weibull":
                # Weibull(a,scale) has mean scale*gamma(1+1/a) and variance scale^2*(gamma(1+2/a) - gamma(1+1/a)^2)
                a, scale = 1, 1.5
                from scipy.special import gamma
                mean_weibull = scale * gamma(1 + 1/a)
                var_weibull = scale**2 * (gamma(1 + 2/a) - gamma(1 + 1/a)**2)
                normalized_sums = (sums - self.num_samples * mean_weibull) / math.sqrt(self.num_samples * var_weibull)
        else:
            normalized_sums = sums
            
        # Create and save the plot
        self.distribution_plot = self._create_plot(normalized_sums)
        
        return super().__call__(**kwargs)
    
    def _create_plot(self, data):
        """Create a histogram plot with a normal curve overlay.
        
        Args:
            data: Array of sum values to plot
            
        Returns:
            str: Path to the saved plot image
        """
        plt.figure(figsize=(8, 6))
        
        # Plot histogram
        plt.hist(data, bins=30, density=True, alpha=0.7, label='Observed Sums')
        
        # Add normal distribution curve
        if self.num_samples > 1:
            x = np.linspace(min(data), max(data), 100)
            plt.plot(x, norm.pdf(x), 'r-', linewidth=2, label='Normal Distribution')
            
        # Add labels and title
        plt.xlabel('Value')
        plt.ylabel('Frequency')
        plt.title(f'{self.distribution_type.capitalize()} Distribution - {self.num_samples} Samples')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Information text
        plt.figtext(
            0.02, 0.02, 
            f"Mean: {self.mean:.3f}, Std Dev: {self.std_dev:.3f}, Skewness: {self.skewness:.3f}", 
            ha='left'
        )
        
        # Save the plot to a file and return the path
        filepath = bch.gen_image_path(f"clt_{self.distribution_type}_{self.num_samples}")
        plt.savefig(filepath)
        plt.close()
        
        return filepath


def example_simple_clt(
    run_cfg: bch.BenchRunCfg = None, 
    report: bch.BenchReport = None
) -> bch.Bench:
    """Demonstrate the Central Limit Theorem with a simple visualization.
    
    Shows how sums of random variables approach a normal distribution
    as the number of summed variables increases.
    
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
    
    # Create the benchmark
    bench = SimpleCLTDemo().to_bench(run_cfg, report)
    
    # Set up the benchmark visualization
    result = bench.plot_sweep(
        title="Simple Central Limit Theorem Demonstration",
        description="""
        This example demonstrates the Central Limit Theorem, which states that the sum of a 
        sufficiently large number of independent random variables will approach a normal 
        distribution, regardless of the original distribution.
        
        The plots show histograms of sums from different distributions. As the number of 
        random samples increases, the resulting distribution becomes more normal-shaped.
        
        This example includes several different distribution types to show that the 
        Central Limit Theorem applies regardless of the shape of the original distribution.
        """,
        post_description="""
        As you can see in the images, when we sum just a few samples, the distribution 
        shape resembles the original distribution. As we increase the number of samples,
        the sum distribution increasingly resembles a normal distribution (bell curve), 
        as predicted by the Central Limit Theorem.
        
        Notice how even highly skewed distributions like exponential, lognormal, and Pareto,
        or discrete distributions like binomial and Poisson, all approach the normal 
        distribution as more samples are summed. The Central Limit Theorem is one of the most
        important results in probability theory and statistics.
        """
    )
    
    # We don't need to append anything else, as the plot_sweep already adds the
    # images to the report through the ResultImage variable
    
    return bench


if __name__ == "__main__":
    example_simple_clt().report.show()
