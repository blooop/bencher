import bencher as bch
import numpy as np

from bencher.example.chemistry.reaction_kinetics import (
    ChemicalReactionSimulation,
    example_chemical_kinetics,
    ReactionType,
)


def test_chemical_kinetics():
    """Test that the chemical kinetics example runs without errors."""
    # Create a simple run config with minimal repetitions
    run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 1
    run_cfg.level = 2

    # Create the benchmark
    bench = example_chemical_kinetics(run_cfg)

    # Check that the benchmark has the expected properties
    assert isinstance(bench, bch.Bench)

    # Run a simple sweep to test functionality
    res = bench.plot_sweep(
        "test_sweep",
        input_vars=["temperature", "reaction_type"],
        result_vars=[ChemicalReactionSimulation.param.reaction_rate],
    )

    # Verify that we got results
    assert res is not None

    # Test that the reaction rate calculation follows Arrhenius equation
    # Simple test case: first order reaction
    sim = ChemicalReactionSimulation(
        temperature=300.0,
        activation_energy=50.0,
        pre_exponential_factor=1.0e7,
        initial_concentration=1.0,
        reaction_type=ReactionType.first_order,
    )
    sim()

    # Calculate expected rate: k = A * exp(-Ea/RT) * [A]
    R = 8.314e-3  # Gas constant in kJ/(mol·K)
    expected_k = 1.0e7 * np.exp(-50.0 / (R * 300.0))
    expected_rate = expected_k * 1.0

    # Allow for some variation due to the random noise
    assert abs(sim.reaction_rate - expected_rate) < expected_rate * 0.02  # 2% tolerance
