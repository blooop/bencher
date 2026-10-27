"""Scrub a five-objective Pareto front, drawn as parallel coordinates.

Two objectives are a curve on a plane and three are a surface in a cube, but past
three there is no space to put a front in. Every projection down to three hides at
least one direction of the trade. So the front is drawn the way many-objective
optimisation draws it: as *parallel coordinates*, one vertical axis per objective and
each design a line across them. Every axis is turned so its better end is at the
bottom, so two objectives whose lines run parallel agree, and two whose lines cross
trade against each other.

The rest is the same scrub as the two- and three-objective examples:
``bench.plot_pareto_front`` lays the front out as a sweep over ``pareto_rank``, and
under ``backend="rerun"`` the slider walks it. The cursor's design is the thick line
on the plot, and the 3-D model above the plot is that design itself, which the
objective values alone cannot show.

The design is a quadcopter: arm length, propeller size and battery capacity. A bigger
battery flies longer and weighs more. A bigger propeller hovers more cheaply and
quietly, but needs longer arms to clear its neighbours. Longer arms make the craft
heavier and wider. No design wins on all five objectives.
"""

import math

import rerun as rr

import bencher as bn

_AIR_DENSITY = 1.2  # kg/m^3
_GRAVITY = 9.81  # m/s^2
_PACK_VOLTS = 14.8  # a 4S lithium pack
_USABLE_CHARGE = 0.8  # of the rated capacity, before the pack is damaged
_FIGURE_OF_MERIT = 0.6  # how close a real rotor comes to ideal momentum theory
_DRIVE_EFFICIENCY = 0.7  # of the battery power, what the motors and ESCs turn into shaft power


class Quadcopter(bn.ParametrizedSweep):
    """A quadcopter: endurance, agility, mass, size and noise, all at once."""

    arm_length = bn.FloatSweep(default=150.0, bounds=[80.0, 260.0], units="mm")
    prop_diameter = bn.FloatSweep(default=150.0, bounds=[75.0, 260.0], units="mm")
    battery = bn.FloatSweep(default=3000.0, bounds=[1000.0, 6000.0], units="mAh")

    hover_time = bn.ResultFloat(units="min", direction=bn.OptDir.maximize)
    thrust_to_weight = bn.ResultFloat(units="ul", direction=bn.OptDir.maximize)
    mass = bn.ResultFloat(units="g", direction=bn.OptDir.minimize)
    span = bn.ResultFloat(units="mm", direction=bn.OptDir.minimize)
    noise = bn.ResultFloat(units="dB", direction=bn.OptDir.minimize)
    model = bn.ResultRerun(width=600, height=400)

    def _overlap(self) -> float:
        """How far each propeller reaches into its neighbour's disc, as a fraction.

        On an X frame the neighbouring motors are ``arm * sqrt(2)`` apart. A
        propeller that reaches into the next one's wake loses lift and makes more
        noise. Without that loss, a bigger propeller is free and nothing is
        dominated.
        """
        clearance = self.arm_length * math.sqrt(2.0) - self.prop_diameter
        return min(1.0, max(0.0, -clearance / self.prop_diameter))

    def benchmark(self):
        overlap = self._overlap()
        lift = max(0.2, 1.0 - 4.0 * overlap)
        frame_g = 60.0 + 4 * 0.12 * self.arm_length
        motor_g = 4 * (10.0 + 0.12 * self.prop_diameter)
        battery_g = 0.11 * self.battery
        self.mass = float(frame_g + motor_g + battery_g)

        weight_n = self.mass / 1000.0 * _GRAVITY
        disc_m2 = 4 * math.pi * (self.prop_diameter / 2000.0) ** 2 * lift
        hover_w = weight_n**1.5 / math.sqrt(2.0 * _AIR_DENSITY * disc_m2)
        hover_w /= _FIGURE_OF_MERIT * _DRIVE_EFFICIENCY
        energy_j = self.battery / 1000.0 * _PACK_VOLTS * 3600.0 * _USABLE_CHARGE
        self.hover_time = float(energy_j / hover_w / 60.0)

        max_thrust_g = 4 * 600.0 * (self.prop_diameter / 127.0) ** 1.5 * lift
        self.thrust_to_weight = float(max_thrust_g / self.mass)
        self.span = float(2.0 * self.arm_length + self.prop_diameter)
        # A rotor's noise rises with its tip speed. To make the same thrust, a bigger
        # rotor turns slower, so its tips are slower too.
        tip_speed = math.sqrt(weight_n / 4.0 / lift) / (self.prop_diameter / 1000.0)
        self.noise = float(20.0 * math.log10(tip_speed) + 40.0 + 10.0 * overlap)
        self.model = self._draw(overlap)
        return super().benchmark()

    def _draw(self, overlap: float) -> str:
        """The craft in 3-D, which is the half a line on a plot cannot show."""
        recording = rr.RecordingStream("quadcopter", make_default=False)
        recording.log("/", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)
        arm = self.arm_length / 1000.0
        radius = self.prop_diameter / 2000.0
        battery_m = (0.04 + self.battery / 1.5e5, 0.035, 0.012 + self.battery / 4e5)
        recording.log(
            "craft/body",
            rr.Boxes3D(half_sizes=[[0.035, 0.035, 0.01]], colors=[(60, 70, 90)]),
        )
        recording.log(
            "craft/battery",
            rr.Boxes3D(
                centers=[[0.0, 0.0, 0.01 + battery_m[2] / 2]],
                half_sizes=[[size / 2 for size in battery_m]],
                colors=[(230, 170, 40)],
            ),
        )
        hubs = [
            [arm * math.cos(angle), arm * math.sin(angle), 0.0]
            for angle in (math.pi / 4 + k * math.pi / 2 for k in range(4))
        ]
        recording.log(
            "craft/arms",
            rr.LineStrips3D(
                [[[0.0, 0.0, 0.0], hub] for hub in hubs],
                radii=0.006,
                colors=[(90, 100, 120)],
            ),
        )
        # A propeller that reaches into its neighbour is drawn red, so the reason it
        # lost is visible on the model.
        disc_color = (220, 60, 50) if overlap > 0 else (90, 180, 240)
        circle = [
            [radius * math.cos(t), radius * math.sin(t), 0.02]
            for t in (2 * math.pi * k / 48 for k in range(49))
        ]
        recording.log(
            "craft/props",
            rr.LineStrips3D(
                [[[hub[0] + x, hub[1] + y, z] for x, y, z in circle] for hub in hubs],
                radii=0.003,
                colors=[disc_color],
            ),
        )
        return bn.capture_rerun_rrd(recording)


def example_optimize_pareto_scrub_nd(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Search five objectives, then walk the front with a slider and parallel coordinates."""
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=1)
    bench = Quadcopter().to_bench(run_cfg)

    result = bench.optimize(
        title="Endurance, agility, mass, size and noise",
        input_vars=["arm_length", "prop_diameter", "battery"],
        result_vars=["hover_time", "thrust_to_weight", "mass", "span", "noise"],
        n_trials=80,
        warm_start=False,
        plot=False,
    )
    front = result.pareto_trials()
    bench.report.append_markdown(
        f"### The front\n\n{len(front)} designs of {len(result.study.trials)} trials are "
        "Pareto optimal across all five objectives. Five objectives have no space to "
        "draw them in, so the front is drawn as parallel coordinates: one axis per "
        "objective, one line per design, the better end of every axis at the bottom. "
        "Lines that cross between two axes show two objectives that trade."
    )

    # One viewer: the slider walks the front, the model shows the design at the cursor.
    bench.run_cfg.backend = "rerun"
    bench.plot_pareto_front(
        result,
        description=(
            "Each tick is one design on the front, longest hover time first. The thick "
            "line on the plot is the design at the cursor. The model above it is that "
            "design: arms, propellers, and the battery in amber. A red propeller "
            "reaches into its neighbour's disc: that design gives away lift to be "
            "smaller."
        ),
    )
    return bench


if __name__ == "__main__":
    bn.run(example_optimize_pareto_scrub_nd)
