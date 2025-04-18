import bencher as bch

from bencher.example.biology.population_dynamics import (
    PopulationDynamicsModel,
    example_population_dynamics,
    EcosystemType,
)


def test_population_dynamics():
    """Test that the population dynamics example runs without errors."""
    # Create a simple run config with minimal repetitions
    run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 1
    run_cfg.level = 2

    # Create the benchmark
    bench = example_population_dynamics(run_cfg)

    # Check that the benchmark has the expected properties
    assert isinstance(bench, bch.Bench)

    # Run a simple sweep to test functionality
    res = bench.plot_sweep(
        "test_sweep",
        input_vars=["ecosystem_type", "initial_population_a"],
        result_vars=[PopulationDynamicsModel.param.stability_index],
    )

    # Verify that we got results
    assert res is not None

    # Test specific ecosystem types
    # Test predator-prey relationship
    pred_prey = PopulationDynamicsModel(
        ecosystem_type=EcosystemType.predator_prey,
        initial_population_a=100,
        initial_population_b=50,
    )
    pred_prey()

    # Test competition relationship
    competition = PopulationDynamicsModel(
        ecosystem_type=EcosystemType.competition, initial_population_a=100, initial_population_b=100
    )
    competition()

    # Verify that both simulations produce different results due to different dynamics
    assert pred_prey.stability_index != competition.stability_index
