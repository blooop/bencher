import bencher as bch
import numpy as np
import math
from enum import auto
from strenum import StrEnum
import random


class FlowRegime(StrEnum):
    """Types of fluid flow regimes"""

    laminar = auto()  # Smooth, orderly flow
    transitional = auto()  # Between laminar and turbulent
    turbulent = auto()  # Chaotic, irregular flow


class BoundaryCondition(StrEnum):
    """Types of boundary conditions for the pipe flow"""

    no_slip = auto()  # Zero velocity at walls
    partial_slip = auto()  # Some slip allowed at walls
    free_slip = auto()  # No friction at walls


class FluidFlowSimulation(bch.ParametrizedSweep):
    """A simulation of fluid flow in a pipe with variable parameters"""

    # Floating point variables
    pipe_diameter = bch.FloatSweep(default=0.1, bounds=[0.01, 1.0], doc="Pipe diameter (m)")
    fluid_velocity = bch.FloatSweep(
        default=1.0, bounds=[0.1, 20.0], doc="Average fluid velocity (m/s)"
    )
    fluid_density = bch.FloatSweep(
        default=1000.0, bounds=[800.0, 1200.0], doc="Fluid density (kg/m³)"
    )
    fluid_viscosity = bch.FloatSweep(
        default=0.001, bounds=[0.0005, 0.1], doc="Fluid dynamic viscosity (Pa·s)"
    )
    pipe_length = bch.FloatSweep(default=10.0, bounds=[1.0, 100.0], doc="Pipe length (m)")

    # Categorical variables
    flow_regime = bch.EnumSweep(FlowRegime, default=FlowRegime.laminar, doc=FlowRegime.__doc__)
    boundary_condition = bch.EnumSweep(
        BoundaryCondition, default=BoundaryCondition.no_slip, doc=BoundaryCondition.__doc__
    )
    include_temperature_effects = bch.BoolSweep(
        default=False, doc="Include temperature effects on fluid properties"
    )

    # Result variables
    reynolds_number = bch.ResultVar("dimensionless", doc="Reynolds number of the flow")
    pressure_drop = bch.ResultVar("Pa", doc="Pressure drop across the pipe length")
    flow_rate = bch.ResultVar("m³/s", doc="Volumetric flow rate")
    wall_shear_stress = bch.ResultVar("Pa", doc="Shear stress at the pipe wall")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        # Calculate cross-sectional area and hydraulic diameter
        area = np.pi * (self.pipe_diameter / 2) ** 2

        # Calculate Reynolds number
        self.reynolds_number = (
            self.fluid_density * self.fluid_velocity * self.pipe_diameter
        ) / self.fluid_viscosity

        # Determine actual flow regime based on Reynolds number
        actual_regime = None
        if self.reynolds_number < 2300:
            actual_regime = FlowRegime.laminar
        elif self.reynolds_number > 4000:
            actual_regime = FlowRegime.turbulent
        else:
            actual_regime = FlowRegime.transitional

        # If user specified a flow regime different from the actual one, adjust viscosity to match
        if self.flow_regime != actual_regime:
            # Recalculate viscosity to match desired Reynolds number
            target_reynolds = (
                1500
                if self.flow_regime == FlowRegime.laminar
                else 3000
                if self.flow_regime == FlowRegime.transitional
                else 6000
            )

            # Calculate new viscosity but ensure it stays within bounds
            new_viscosity = (
                self.fluid_density * self.fluid_velocity * self.pipe_diameter
            ) / target_reynolds
            # Clamp to bounds
            new_viscosity = max(0.0005, min(new_viscosity, 0.1))

            # Only update if within bounds
            if 0.0005 <= new_viscosity <= 0.1:
                self.fluid_viscosity = new_viscosity
                # Recalculate Reynolds number with new viscosity
                self.reynolds_number = (
                    self.fluid_density * self.fluid_velocity * self.pipe_diameter
                ) / self.fluid_viscosity

        # Calculate friction factor based on flow regime and boundary condition
        if self.reynolds_number < 2300:  # Laminar flow
            if self.boundary_condition == BoundaryCondition.no_slip:
                friction_factor = 64 / self.reynolds_number
            elif self.boundary_condition == BoundaryCondition.partial_slip:
                friction_factor = 56 / self.reynolds_number  # Approximation for partial slip
            else:  # Free slip
                friction_factor = 48 / self.reynolds_number  # Approximation for free slip
        else:  # Turbulent or transitional flow - Colebrook equation simplified
            pipe_roughness = 0.0000015  # Default roughness (m)

            # Adjust roughness based on boundary condition
            if self.boundary_condition == BoundaryCondition.partial_slip:
                pipe_roughness *= 0.5
            elif self.boundary_condition == BoundaryCondition.free_slip:
                pipe_roughness *= 0.1

            # Simplified Colebrook equation
            relative_roughness = pipe_roughness / self.pipe_diameter
            friction_factor = (
                0.25
                / (math.log10(relative_roughness / 3.7 + 5.74 / self.reynolds_number**0.9)) ** 2
            )

        # Temperature effects (simplified)
        if self.include_temperature_effects:
            # Add a random temperature effect (±10% variation)
            temperature_factor = 1.0 + random.uniform(-0.1, 0.1)
            friction_factor *= temperature_factor

        # Calculate pressure drop using Darcy-Weisbach equation
        self.pressure_drop = (
            friction_factor
            * (self.pipe_length / self.pipe_diameter)
            * (self.fluid_density * self.fluid_velocity**2)
            / 2
        )

        # Calculate flow rate
        self.flow_rate = area * self.fluid_velocity

        # Calculate wall shear stress
        self.wall_shear_stress = friction_factor * self.fluid_density * self.fluid_velocity**2 / 8

        return super().__call__()


def example_fluid_flow(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Create a benchmark for the fluid flow simulation"""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
        run_cfg.repeats = 3
        run_cfg.level = 3

    bench = FluidFlowSimulation().to_bench(run_cfg, report)

    bench.plot_sweep(
        title="Fluid Flow Simulation",
        description="""## Fluid Dynamics in Pipe Flow
This benchmark explores the behavior of fluid flow in pipes with different parameters
including pipe diameter, fluid properties, and boundary conditions.""",
        input_vars=[
            "pipe_diameter",
            "fluid_velocity",
            "fluid_viscosity",
            "flow_regime",
            "boundary_condition",
            "include_temperature_effects",
        ],
        result_vars=[
            FluidFlowSimulation.param.reynolds_number,
            FluidFlowSimulation.param.pressure_drop,
            FluidFlowSimulation.param.wall_shear_stress,
        ],
    )

    return bench


if __name__ == "__main__":
    example_fluid_flow()
