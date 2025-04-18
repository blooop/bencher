import bencher as bch
import numpy as np
from enum import auto
from strenum import StrEnum
import random


class EcosystemType(StrEnum):
    """Types of ecosystem models"""

    predator_prey = auto()  # Classic Lotka-Volterra predator-prey model
    competition = auto()  # Competition between two species
    mutualism = auto()  # Mutualistic relationship between species


class PopulationDynamicsModel(bch.ParametrizedSweep):
    """A model of population dynamics in an ecosystem"""

    # Floating point variables
    initial_population_a = bch.FloatSweep(
        default=100.0, bounds=[10.0, 1000.0], doc="Initial population of species A"
    )
    initial_population_b = bch.FloatSweep(
        default=50.0, bounds=[5.0, 500.0], doc="Initial population of species B"
    )
    growth_rate_a = bch.FloatSweep(
        default=0.1, bounds=[0.01, 1.0], doc="Intrinsic growth rate of species A"
    )
    growth_rate_b = bch.FloatSweep(
        default=0.2, bounds=[0.01, 1.0], doc="Intrinsic growth rate of species B"
    )
    carrying_capacity = bch.FloatSweep(
        default=1000.0, bounds=[100.0, 10000.0], doc="Environment carrying capacity"
    )

    # Categorical variables
    ecosystem_type = bch.EnumSweep(
        EcosystemType, default=EcosystemType.predator_prey, doc=EcosystemType.__doc__
    )
    include_seasonality = bch.BoolSweep(
        default=False, doc="Include seasonal variations in growth rates"
    )
    random_events = bch.BoolSweep(default=False, doc="Include random environmental events")

    # Result variables
    final_population_a = bch.ResultVar("individuals", doc="Final population of species A")
    final_population_b = bch.ResultVar("individuals", doc="Final population of species B")
    extinction_time = bch.ResultVar("time units", doc="Time to first extinction, if any")
    stability_index = bch.ResultVar("dimensionless", doc="Index of ecosystem stability")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        # Simulation parameters
        dt = 0.1  # Time step
        total_time = 100  # Total simulation time
        steps = int(total_time / dt)

        # Initial conditions
        pop_a = self.initial_population_a
        pop_b = self.initial_population_b

        # Track values for stability calculation
        pop_a_values = []
        pop_b_values = []
        extinction_occurred = False
        extinction_time = total_time

        # Interaction parameters based on ecosystem type
        if self.ecosystem_type == EcosystemType.predator_prey:
            # Lotka-Volterra parameters
            # How much each predator-prey interaction benefits/harms each species
            interaction_ab = -0.01  # Effect of B on A (negative: B eats A)
            interaction_ba = 0.02  # Effect of A on B (positive: B benefits from eating A)
        elif self.ecosystem_type == EcosystemType.competition:
            # Competition parameters (both negative)
            interaction_ab = -0.005  # A is harmed by B
            interaction_ba = -0.005  # B is harmed by A
        else:  # Mutualism
            # Mutualism parameters (both positive)
            interaction_ab = 0.005  # A benefits from B
            interaction_ba = 0.005  # B benefits from A

        # Run simulation
        for t in range(steps):
            # Calculate time of year for seasonality (0 to 1)
            season = (t * dt % 20) / 20  # 20 time units = 1 year

            # Adjust growth rates for seasonality if enabled
            growth_a = self.growth_rate_a
            growth_b = self.growth_rate_b

            if self.include_seasonality:
                # Sinusoidal variation throughout the year
                growth_a *= 1 + 0.5 * np.sin(2 * np.pi * season)
                growth_b *= 1 + 0.5 * np.cos(2 * np.pi * season)  # Offset peak from species A

            # Check for random environmental events
            event_factor_a = 1.0
            event_factor_b = 1.0

            if self.random_events and random.random() < 0.01:  # 1% chance per time step
                # Random event affects one or both species
                event_severity = random.uniform(0.5, 1.5)  # Could be good or bad
                if random.random() < 0.5:
                    event_factor_a = event_severity
                else:
                    event_factor_b = event_severity

            # Prevent numerical issues by capping populations
            pop_a = min(pop_a, 1e6)
            pop_b = min(pop_b, 1e6)

            # Calculate derivatives based on ecosystem type
            # Here we use logistic growth with interactions
            dA_dt = growth_a * pop_a * (1 - pop_a / self.carrying_capacity)
            if abs(pop_a * pop_b) < 1e6:  # Prevent overflow
                dA_dt += interaction_ab * pop_a * pop_b

            dB_dt = growth_b * pop_b * (1 - pop_b / self.carrying_capacity)
            if abs(pop_a * pop_b) < 1e6:  # Prevent overflow
                dB_dt += interaction_ba * pop_a * pop_b

            # Apply event factors
            dA_dt *= event_factor_a
            dB_dt *= event_factor_b

            # Update populations using Euler method with bounds checking
            pop_a += dA_dt * dt
            pop_b += dB_dt * dt

            # Ensure populations don't go negative or too large
            pop_a = max(0, min(pop_a, 1e6))
            pop_b = max(0, min(pop_b, 1e6))

            # Check for extinction
            if not extinction_occurred and (pop_a < 1 or pop_b < 1):
                extinction_occurred = True
                extinction_time = t * dt

            # Record populations for stability calculation
            if t >= steps // 2:  # Only consider second half for stability
                pop_a_values.append(pop_a)
                pop_b_values.append(pop_b)

        # Set final populations
        self.final_population_a = pop_a
        self.final_population_b = pop_b

        # Set extinction time if extinction occurred
        self.extinction_time = extinction_time if extinction_occurred else total_time

        # Calculate stability index (coefficient of variation, lower is more stable)
        if len(pop_a_values) > 0 and len(pop_b_values) > 0:
            # Calculate means and standard deviations safely
            mean_a = np.mean(pop_a_values) if pop_a_values else 1
            mean_b = np.mean(pop_b_values) if pop_b_values else 1

            # Prevent division by zero
            if mean_a > 0 and mean_b > 0:
                cv_a = np.std(pop_a_values) / mean_a
                cv_b = np.std(pop_b_values) / mean_b
                self.stability_index = 1 / (
                    1 + cv_a + cv_b
                )  # Transform to make higher values more stable
            else:
                self.stability_index = 0
        else:
            self.stability_index = 0  # If extinction occurs early, stability is zero

        return super().__call__()


def example_population_dynamics(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Create a benchmark for the population dynamics model"""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
        run_cfg.repeats = 3
        run_cfg.level = 3

    bench = PopulationDynamicsModel().to_bench(run_cfg, report)

    bench.plot_sweep(
        title="Ecosystem Population Dynamics",
        description="""## Ecosystem Population Dynamics Model
This benchmark explores how different species interact in various ecosystem types, 
including predator-prey relationships, competition, and mutualism.""",
        input_vars=[
            "ecosystem_type",
            "initial_population_a",
            "initial_population_b",
            "growth_rate_a",
            "include_seasonality",
            "random_events",
        ],
        result_vars=[
            PopulationDynamicsModel.param.final_population_a,
            PopulationDynamicsModel.param.final_population_b,
            PopulationDynamicsModel.param.stability_index,
            PopulationDynamicsModel.param.extinction_time,
        ],
    )

    return bench


if __name__ == "__main__":
    example_population_dynamics()
