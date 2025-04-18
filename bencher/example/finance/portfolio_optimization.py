import bencher as bch
import numpy as np
from enum import auto
from strenum import StrEnum
import random


class RiskModel(StrEnum):
    """Types of risk models for portfolio optimization"""

    variance = auto()  # Simple variance as risk measure
    semi_variance = auto()  # Only downside variance
    var = auto()  # Value at Risk
    cvar = auto()  # Conditional Value at Risk


class RebalancingFrequency(StrEnum):
    """How often the portfolio is rebalanced"""

    monthly = auto()
    quarterly = auto()
    annually = auto()


class PortfolioOptimization(bch.ParametrizedSweep):
    """A portfolio optimization simulation with different strategies and parameters"""

    # Floating point variables
    risk_free_rate = bch.FloatSweep(default=0.02, bounds=[0.0, 0.10], doc="Annual risk-free rate")
    target_return = bch.FloatSweep(default=0.08, bounds=[0.02, 0.20], doc="Target annual return")
    risk_aversion = bch.FloatSweep(default=2.0, bounds=[0.5, 10.0], doc="Risk aversion coefficient")
    max_single_allocation = bch.FloatSweep(
        default=0.3, bounds=[0.05, 0.5], doc="Maximum allocation to a single asset"
    )
    market_volatility = bch.FloatSweep(
        default=0.15, bounds=[0.05, 0.40], doc="Market volatility (standard deviation)"
    )

    # Categorical variables
    risk_model = bch.EnumSweep(RiskModel, default=RiskModel.variance, doc=RiskModel.__doc__)
    rebalancing_frequency = bch.EnumSweep(
        RebalancingFrequency,
        default=RebalancingFrequency.quarterly,
        doc=RebalancingFrequency.__doc__,
    )
    allow_short_selling = bch.BoolSweep(default=False, doc="Allow short positions in assets")

    # Result variables
    sharpe_ratio = bch.ResultVar("ratio", doc="Sharpe ratio of the portfolio")
    portfolio_volatility = bch.ResultVar("%", doc="Annual portfolio volatility")
    max_drawdown = bch.ResultVar("%", doc="Maximum drawdown")
    total_return = bch.ResultVar("%", doc="Annualized total return")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        # Set the random seed based on the parameters to ensure reproducibility
        # but still allow for different results with different parameters
        seed_value = int(
            hash(f"{self.risk_aversion}{self.target_return}{self.market_volatility}") % 2**32
        )
        random.seed(seed_value)
        np.random.seed(seed_value)

        # Asset characteristics - simplified model
        # We'll simulate 4 asset classes with different return/risk profiles
        asset_returns = np.array([0.05, 0.08, 0.12, 0.15])  # Expected returns
        asset_vols = np.array([0.08, 0.12, 0.20, 0.25])  # Volatilities

        # Scale based on market volatility
        vol_scale = self.market_volatility / 0.15  # 0.15 is the baseline
        asset_vols = asset_vols * vol_scale

        # Correlation matrix - roughly based on common asset classes
        corr_matrix = np.array(
            [[1.0, 0.5, 0.3, 0.2], [0.5, 1.0, 0.6, 0.4], [0.3, 0.6, 1.0, 0.7], [0.2, 0.4, 0.7, 1.0]]
        )

        # Construct covariance matrix
        cov_matrix = np.outer(asset_vols, asset_vols) * corr_matrix

        # Perform portfolio optimization (simplified mean-variance approach)
        # We'll use a numerical approach to find the optimal weights

        # Constraints based on parameters
        min_weight = -0.5 if self.allow_short_selling else 0.0
        max_weight = self.max_single_allocation

        # Simplified optimization using numerical sampling
        num_samples = 5000
        best_sharpe = -np.inf
        best_weights = None
        best_vol = None
        best_ret = None

        for _ in range(num_samples):
            # Generate random weights
            if self.allow_short_selling:
                weights = np.random.uniform(min_weight, max_weight, size=4)
                # Rescale to sum to 1
                weights = weights / np.sum(np.abs(weights))
            else:
                weights = np.random.uniform(0, max_weight, size=4)
                # Rescale to sum to 1
                if np.sum(weights) > 0:
                    weights = weights / np.sum(weights)

            # Calculate portfolio return and risk
            portfolio_return = np.sum(weights * asset_returns)

            # Different risk models
            if self.risk_model == RiskModel.variance:
                portfolio_risk = np.sqrt(weights.T @ cov_matrix @ weights)
            elif self.risk_model == RiskModel.semi_variance:
                # Simplified semi-variance (only captures downside)
                portfolio_risk = np.sqrt(weights.T @ cov_matrix @ weights) * 0.7
            elif self.risk_model == RiskModel.var:
                # Simplified Value at Risk (95% confidence)
                portfolio_risk = np.sqrt(weights.T @ cov_matrix @ weights) * 1.645
            else:  # CVaR
                # Simplified Conditional Value at Risk (95% confidence)
                portfolio_risk = np.sqrt(weights.T @ cov_matrix @ weights) * 2.06

            # Apply risk aversion directly to the objective function
            # Higher risk aversion puts more penalty on risk
            adjusted_risk = portfolio_risk * (0.5 + 0.5 * self.risk_aversion / 5.0)

            # Calculate Sharpe ratio with risk-adjusted volatility
            sharpe = (
                (portfolio_return - self.risk_free_rate) / adjusted_risk if adjusted_risk > 0 else 0
            )

            # Check if this portfolio is better than current best
            if sharpe > best_sharpe and portfolio_return >= self.target_return:
                best_sharpe = sharpe
                best_weights = weights
                best_vol = portfolio_risk
                best_ret = portfolio_return

        # If we couldn't find a solution meeting the target return, take the highest return
        if best_weights is None:
            # Sort by return
            best_idx = np.argmax(asset_returns)
            best_weights = np.zeros(4)
            best_weights[best_idx] = 1.0
            best_ret = asset_returns[best_idx]
            best_vol = asset_vols[best_idx]
            best_sharpe = (best_ret - self.risk_free_rate) / best_vol

        # Apply rebalancing effect
        rebalancing_factor = {
            RebalancingFrequency.monthly: 1.01,  # Slight improvement with frequent rebalancing
            RebalancingFrequency.quarterly: 1.0,  # Base case
            RebalancingFrequency.annually: 0.98,  # Slight penalty for infrequent rebalancing
        }[self.rebalancing_frequency]

        best_sharpe *= rebalancing_factor

        # Apply risk aversion factor to final volatility
        # Higher risk aversion means we select lower volatility portfolios
        risk_adjustment = 1.0 / (0.5 + 0.5 * self.risk_aversion / 5.0)
        best_vol *= risk_adjustment

        # Calculate maximum drawdown - roughly estimated based on volatility and return
        # This is a simplified model of worst-case drawdown
        self.max_drawdown = best_vol * 2.5 - best_ret * 1.5
        self.max_drawdown = max(self.max_drawdown, 0.05)  # At least 5% drawdown
        self.max_drawdown = min(self.max_drawdown, 0.9)  # Cap at 90% drawdown

        # Convert to percentage
        self.max_drawdown *= 100

        # Set result variables
        self.sharpe_ratio = best_sharpe
        self.portfolio_volatility = best_vol * 100  # Convert to percentage
        self.total_return = best_ret * 100  # Convert to percentage

        # Add some random noise to simulate real-world variations
        # Use a much smaller amount of noise to maintain the risk aversion relationship
        noise_factor = 1.0 + random.uniform(-0.02, 0.02)
        self.sharpe_ratio *= noise_factor
        self.portfolio_volatility *= 1.0 + random.uniform(-0.01, 0.01)
        self.total_return *= 1.0 + random.uniform(-0.01, 0.01)
        self.max_drawdown *= 1.0 + random.uniform(-0.02, 0.02)

        return super().__call__()


def example_portfolio_optimization(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Create a benchmark for the portfolio optimization simulation"""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
        run_cfg.repeats = 4  # Multiple repeats to show statistical variations
        run_cfg.level = 3

    bench = PortfolioOptimization().to_bench(run_cfg, report)

    bench.plot_sweep(
        title="Portfolio Optimization",
        description="""## Financial Portfolio Optimization
This benchmark explores different portfolio optimization strategies with various risk models,
constraints, and market conditions.""",
        input_vars=[
            "risk_model",
            "target_return",
            "risk_aversion",
            "market_volatility",
            "rebalancing_frequency",
            "allow_short_selling",
        ],
        result_vars=[
            PortfolioOptimization.param.sharpe_ratio,
            PortfolioOptimization.param.portfolio_volatility,
            PortfolioOptimization.param.max_drawdown,
            PortfolioOptimization.param.total_return,
        ],
    )

    return bench


if __name__ == "__main__":
    example_portfolio_optimization()
