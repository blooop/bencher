import bencher as bch

from bencher.example.physics.pendulum_sim import PendulumSimulation, example_pendulum


def test_pendulum_simulation():
    """Test that the pendulum simulation example runs without errors."""
    # Create a simple run config with minimal repetitions
    run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 1
    run_cfg.level = 2

    # Create the benchmark
    bench = example_pendulum(run_cfg)

    # Check that the benchmark has the expected properties
    assert isinstance(bench, bch.Bench)

    # Run a simple sweep to test functionality
    res = bench.plot_sweep(
        "test_sweep",
        input_vars=["length", "use_small_angle"],
        result_vars=[PendulumSimulation.param.period],
    )

    # Verify that we got results
    assert res is not None

    # Test that the period calculation is reasonable
    # Simple test case: for length=1m, g=9.81m/s², small angle approximation
    pendulum = PendulumSimulation(length=1.0, gravity=9.81, use_small_angle=True)
    pendulum()

    # Expected period for simple pendulum with small angle: T = 2π√(L/g)
    expected_period = 2.0 * 3.14159 * (1.0 / 9.81) ** 0.5
    assert abs(pendulum.period - expected_period) < 0.1  # 10% tolerance
