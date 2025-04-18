import bencher as bch

from bencher.example.engineering.fluid_flow import (
    FluidFlowSimulation,
    example_fluid_flow,
    FlowRegime,
)


def test_fluid_flow():
    """Test that the fluid flow simulation example runs without errors."""
    # Create a simple run config with minimal repetitions
    run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 1
    run_cfg.level = 2

    # Create the benchmark
    bench = example_fluid_flow(run_cfg)

    # Check that the benchmark has the expected properties
    assert isinstance(bench, bch.Bench)

    # Run a simple sweep to test functionality
    res = bench.plot_sweep(
        "test_sweep",
        input_vars=["pipe_diameter", "fluid_velocity"],
        result_vars=[FluidFlowSimulation.param.reynolds_number],
    )

    # Verify that we got results
    assert res is not None

    # Test specific cases
    # Test laminar flow
    laminar = FluidFlowSimulation(
        pipe_diameter=0.05,
        fluid_velocity=0.5,
        fluid_density=1000.0,
        fluid_viscosity=0.001,
        flow_regime=FlowRegime.laminar,
    )
    laminar()

    # Test turbulent flow
    turbulent = FluidFlowSimulation(
        pipe_diameter=0.05,
        fluid_velocity=5.0,
        fluid_density=1000.0,
        fluid_viscosity=0.001,
        flow_regime=FlowRegime.turbulent,
    )
    turbulent()

    # Verify Reynolds number calculations are correct and consistent with flow regimes
    # For laminar flow, Reynolds number should be < 2300
    assert laminar.reynolds_number < 2300

    # For turbulent flow, Reynolds number should be > 4000
    assert turbulent.reynolds_number > 4000

    # Verify pressure drop increases with fluid velocity
    low_vel = FluidFlowSimulation(fluid_velocity=1.0)
    low_vel()
    high_vel = FluidFlowSimulation(fluid_velocity=2.0)
    high_vel()

    assert high_vel.pressure_drop > low_vel.pressure_drop
