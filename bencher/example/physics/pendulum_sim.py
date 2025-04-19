import bencher as bch
import numpy as np
from enum import auto
from strenum import StrEnum
import random


class IntegrationMethod(StrEnum):
    """Integration methods for the pendulum simulation"""

    euler = auto()  # Simple Euler integration
    rk4 = auto()  # 4th order Runge-Kutta
    verlet = auto()  # Verlet integration


class PendulumSimulation(bch.ParametrizedSweep):
    """A simulation of a pendulum with variable parameters"""

    # Floating point variables
    length = bch.FloatSweep(default=1.0, bounds=[0.1, 5.0], doc="Length of the pendulum (m)")
    initial_angle = bch.FloatSweep(
        default=0.1, bounds=[0.001, np.pi / 2], doc="Initial angle (rad)"
    )
    gravity = bch.FloatSweep(
        default=9.81, bounds=[1.0, 20.0], doc="Gravitational acceleration (m/s²)"
    )
    damping = bch.FloatSweep(default=0.1, bounds=[0.0, 1.0], doc="Damping coefficient")

    # Categorical variables
    use_small_angle = bch.BoolSweep(default=True, doc="Use small angle approximation")
    integration_method = bch.EnumSweep(
        IntegrationMethod, default=IntegrationMethod.euler, doc=IntegrationMethod.__doc__
    )
    add_noise = bch.BoolSweep(default=False, doc="Add random noise to the simulation")

    # Result variables
    period = bch.ResultVar("s", doc="Period of the pendulum")
    max_velocity = bch.ResultVar("m/s", doc="Maximum velocity reached")
    energy_loss = bch.ResultVar("%", doc="Percentage of energy lost due to damping")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        # Calculate the period of the pendulum
        if self.use_small_angle:
            # Small angle approximation: T = 2π√(L/g)
            self.period = 2 * np.pi * np.sqrt(self.length / self.gravity)
        else:
            # Full solution using elliptic integral (approximated)
            k = np.sin(self.initial_angle / 2)
            # Approximation of the complete elliptic integral
            elliptic_term = 1 + (1 / 4) * k**2 + (9 / 64) * k**4 + (25 / 256) * k**6
            self.period = 2 * np.pi * np.sqrt(self.length / self.gravity) * elliptic_term

        # Simulate the pendulum motion to find max velocity and energy loss
        dt = 0.01  # Time step
        total_time = max(5 * self.period, 20)  # Simulate for at least 5 periods
        steps = int(total_time / dt)

        # Initial conditions
        angle = self.initial_angle
        angular_velocity = 0.0

        # For tracking
        max_vel = 0.0
        initial_energy = 0.5 * self.length**2 * 0**2 + self.gravity * self.length * (
            1 - np.cos(angle)
        )

        # Simple simulation
        for _ in range(steps):
            # Add noise if requested
            noise = 0.0
            if self.add_noise:
                noise = random.uniform(-0.01, 0.01) * self.gravity

            # Calculate acceleration
            angular_acceleration = (
                -(self.gravity + noise) / self.length * np.sin(angle)
                - self.damping * angular_velocity
            )

            # Update based on integration method
            if self.integration_method == IntegrationMethod.euler:
                angular_velocity += angular_acceleration * dt
                angle += angular_velocity * dt
            elif self.integration_method == IntegrationMethod.rk4:
                # RK4 for angular velocity
                k1v = angular_acceleration
                k1x = angular_velocity

                k2v = -(self.gravity + noise) / self.length * np.sin(
                    angle + 0.5 * dt * k1x
                ) - self.damping * (angular_velocity + 0.5 * dt * k1v)
                k2x = angular_velocity + 0.5 * dt * k1v

                k3v = -(self.gravity + noise) / self.length * np.sin(
                    angle + 0.5 * dt * k2x
                ) - self.damping * (angular_velocity + 0.5 * dt * k2v)
                k3x = angular_velocity + 0.5 * dt * k2v

                k4v = -(self.gravity + noise) / self.length * np.sin(
                    angle + dt * k3x
                ) - self.damping * (angular_velocity + dt * k3v)
                k4x = angular_velocity + dt * k3v

                angular_velocity += dt * (k1v + 2 * k2v + 2 * k3v + k4v) / 6
                angle += dt * (k1x + 2 * k2x + 2 * k3x + k4x) / 6
            else:  # Verlet
                half_v = angular_velocity + 0.5 * angular_acceleration * dt
                angle += half_v * dt

                # Recalculate acceleration
                new_angular_acceleration = (
                    -(self.gravity + noise) / self.length * np.sin(angle) - self.damping * half_v
                )

                angular_velocity = half_v + 0.5 * new_angular_acceleration * dt

            # Track maximum velocity (convert to linear velocity at the pendulum tip)
            current_velocity = abs(angular_velocity * self.length)
            max_vel = max(max_vel, current_velocity)

        self.max_velocity = max_vel

        # Calculate final energy and loss
        final_energy = 0.5 * self.length**2 * angular_velocity**2 + self.gravity * self.length * (
            1 - np.cos(angle)
        )
        self.energy_loss = 100 * (1 - final_energy / initial_energy) if initial_energy > 0 else 0

        return super().__call__()


def example_pendulum(run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None) -> bch.Bench:
    """Create a benchmark for the pendulum simulation"""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
        run_cfg.repeats = 3
        run_cfg.level = 3

    bench = PendulumSimulation().to_bench(run_cfg, report)

    bench.plot_sweep(
        title="Pendulum Simulation",
        description="""## Pendulum Physics Simulation
This benchmark explores the behavior of a pendulum with various parameters including length, 
initial angle, damping, and different integration methods.""",
        input_vars=[
            "length",
            "initial_angle",
            "damping",
            "use_small_angle",
            "integration_method",
        ],
        result_vars=[
            PendulumSimulation.param.period,
            PendulumSimulation.param.max_velocity,
            PendulumSimulation.param.energy_loss,
        ],
    )

    return bench


if __name__ == "__main__":
    example_pendulum()
