import bencher as bch
import numpy as np
from enum import auto
from strenum import StrEnum
import random


class ReactionType(StrEnum):
    """Types of chemical reactions to model"""

    zero_order = auto()  # Rate independent of reactant concentration
    first_order = auto()  # Rate proportional to one reactant concentration
    second_order = auto()  # Rate proportional to product of two reactant concentrations


class CatalystType(StrEnum):
    """Types of catalysts that can be used"""

    none = auto()  # No catalyst
    enzyme = auto()  # Enzyme catalyst (follows Michaelis-Menten kinetics)
    metal = auto()  # Metal catalyst (linear enhancement)


class ChemicalReactionSimulation(bch.ParametrizedSweep):
    """A simulation of chemical reaction kinetics with various parameters"""

    # Floating point variables
    initial_concentration = bch.FloatSweep(
        default=1.0, bounds=[0.1, 10.0], doc="Initial concentration of reactant (mol/L)"
    )
    temperature = bch.FloatSweep(default=298.0, bounds=[250.0, 500.0], doc="Temperature (K)")
    activation_energy = bch.FloatSweep(
        default=50.0, bounds=[10.0, 150.0], doc="Activation energy (kJ/mol)"
    )
    pre_exponential_factor = bch.FloatSweep(
        default=1.0e7, bounds=[1.0e3, 1.0e12], doc="Pre-exponential factor in Arrhenius equation"
    )
    catalyst_concentration = bch.FloatSweep(
        default=0.0, bounds=[0.0, 1.0], doc="Catalyst concentration (mol/L)"
    )

    # Categorical variables
    reaction_type = bch.EnumSweep(
        ReactionType, default=ReactionType.first_order, doc=ReactionType.__doc__
    )
    catalyst_type = bch.EnumSweep(CatalystType, default=CatalystType.none, doc=CatalystType.__doc__)
    add_inhibitor = bch.BoolSweep(default=False, doc="Add an inhibitor to the reaction")

    # Result variables
    reaction_rate = bch.ResultVar("mol/(L*s)", doc="Initial reaction rate")
    half_life = bch.ResultVar("s", doc="Time for half of the reactant to be consumed")
    time_to_90_percent = bch.ResultVar("s", doc="Time for 90% of the reactant to be consumed")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        # Constants
        R = 8.314e-3  # Gas constant in kJ/(mol·K)

        # Calculate rate constant using Arrhenius equation
        k_base = self.pre_exponential_factor * np.exp(
            -self.activation_energy / (R * self.temperature)
        )

        # Apply catalyst effect
        k = k_base
        if self.catalyst_type == CatalystType.none:
            pass  # No change to k
        elif self.catalyst_type == CatalystType.metal:
            # Linear enhancement by catalyst
            k = k_base * (1 + 10 * self.catalyst_concentration)
        elif self.catalyst_type == CatalystType.enzyme:
            # Michaelis-Menten type enhancement
            Km = 0.5  # Michaelis constant
            k = k_base * (
                1 + (3 * self.catalyst_concentration) / (Km + self.catalyst_concentration)
            )

        # Apply inhibitor effect if present
        if self.add_inhibitor:
            k *= 0.5  # Reduce rate by half with inhibitor

        # Calculate initial reaction rate based on reaction type
        if self.reaction_type == ReactionType.zero_order:
            self.reaction_rate = k
            self.half_life = (self.initial_concentration / 2) / k
            self.time_to_90_percent = (0.9 * self.initial_concentration) / k

        elif self.reaction_type == ReactionType.first_order:
            self.reaction_rate = k * self.initial_concentration
            self.half_life = np.log(2) / k
            self.time_to_90_percent = np.log(10) / k

        elif self.reaction_type == ReactionType.second_order:
            # Assume equal concentrations of both reactants for simplicity
            self.reaction_rate = k * self.initial_concentration**2
            self.half_life = 1 / (k * self.initial_concentration)
            self.time_to_90_percent = 9 / (k * self.initial_concentration)

        # Add some noise to simulate experimental uncertainty (1% random variation)
        noise_factor = 1.0 + random.uniform(-0.01, 0.01)
        self.reaction_rate *= noise_factor
        self.half_life *= noise_factor
        self.time_to_90_percent *= noise_factor

        return super().__call__()


def example_chemical_kinetics(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Create a benchmark for the chemical reaction simulation"""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
        run_cfg.repeats = 5  # Multiple repeats to show experimental variation
        run_cfg.level = 3

    bench = ChemicalReactionSimulation().to_bench(run_cfg, report)

    bench.plot_sweep(
        title="Chemical Reaction Kinetics",
        description="""## Chemical Reaction Kinetics Simulation
This benchmark explores how different factors affect the rates of chemical reactions, including
temperature, catalyst types, and reaction order.""",
        input_vars=[
            "initial_concentration",
            "temperature",
            "activation_energy",
            "catalyst_type",
            "catalyst_concentration",
            "reaction_type",
        ],
        result_vars=[
            ChemicalReactionSimulation.param.reaction_rate,
            ChemicalReactionSimulation.param.half_life,
            ChemicalReactionSimulation.param.time_to_90_percent,
        ],
    )

    return bench


if __name__ == "__main__":
    example_chemical_kinetics()
