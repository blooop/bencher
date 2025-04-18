import bencher as bch

from bencher.example.finance.portfolio_optimization import (
    PortfolioOptimization,
    example_portfolio_optimization,
    RiskModel,
)


def test_portfolio_optimization():
    """Test that the portfolio optimization example runs without errors."""
    # Create a simple run config with minimal repetitions
    run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 1
    run_cfg.level = 2

    # Create the benchmark
    bench = example_portfolio_optimization(run_cfg)

    # Check that the benchmark has the expected properties
    assert isinstance(bench, bch.Bench)

    # Run a simple sweep to test functionality
    res = bench.plot_sweep(
        "test_sweep",
        input_vars=["risk_model", "target_return"],
        result_vars=[PortfolioOptimization.param.sharpe_ratio],
    )

    # Verify that we got results
    assert res is not None

    # Test different risk models
    variance = PortfolioOptimization(
        risk_model=RiskModel.variance, target_return=0.08, risk_aversion=2.0
    )
    variance()

    cvar = PortfolioOptimization(risk_model=RiskModel.cvar, target_return=0.08, risk_aversion=2.0)
    cvar()

    # Test risk aversion effect
    low_aversion = PortfolioOptimization(risk_aversion=1.0)
    low_aversion()
    high_aversion = PortfolioOptimization(risk_aversion=5.0)
    high_aversion()

    # Higher risk aversion should lead to lower volatility
    assert high_aversion.portfolio_volatility < low_aversion.portfolio_volatility

    # Test short selling effect
    no_short = PortfolioOptimization(allow_short_selling=False, target_return=0.12)
    no_short()
    with_short = PortfolioOptimization(allow_short_selling=True, target_return=0.12)
    with_short()

    # With short selling, we have more flexibility and should achieve higher Sharpe ratio
    # for challenging target returns
    assert with_short.sharpe_ratio >= no_short.sharpe_ratio * 0.95  # Allow for random variations
