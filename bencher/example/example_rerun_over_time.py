"""Support module: second-order control system step response for rerun examples.

Simulates a damped oscillator responding to a unit step input.  Each
``benchmark()`` call logs the response trajectory, setpoint, and tracking
error into a rerun recording over 200 time steps, then extracts two scalar
metrics — peak overshoot and 2 % settling time.

Used by the generated rerun examples (regression monitoring and parameter
sweep) via ``from bencher.example.example_rerun_over_time import ControlSystemSweep``.
Run this file directly to see the recordings' history laid out in tabs.
"""

from datetime import datetime, timedelta

import rerun as rr

import bencher as bn


class ControlSystemSweep(bn.ParametrizedSweep):
    """Second-order control system step response.

    ``damping_ratio`` controls the oscillatory behaviour.  A value of 1.0 is
    critically damped; below 1.0 the system overshoots, above 1.0 it is
    sluggish.  ``_degradation`` is set externally between over-time snapshots
    to simulate controller tuning drift — it reduces the effective damping,
    making the response progressively worse.
    """

    damping_ratio = bn.FloatSweep(
        default=0.7, bounds=[0.1, 2.0], doc="Damping ratio (zeta)", samples=5
    )
    omega_n = bn.FloatSweep(
        default=5.0, bounds=[2.0, 10.0], doc="Natural frequency (rad/s)", samples=3
    )

    out_overshoot = bn.ResultFloat(units="%", doc="peak overshoot", direction=bn.OptDir.minimize)
    out_settling_time = bn.ResultFloat(
        units="s", doc="2% settling time", direction=bn.OptDir.minimize
    )
    out_rerun = bn.ResultRerun(width=400, height=400, max_time_events=3)

    _degradation = 0.0  # set externally per over-time snapshot

    def benchmark(self):
        n_steps = 200
        dt = 0.02
        setpoint = 1.0
        omega_n = self.omega_n
        zeta = max(0.05, self.damping_ratio - self._degradation)

        y, dy = 0.0, 0.0
        peak_overshoot = 0.0
        last_unsettled = 0

        for step in range(n_steps):
            # Simple Euler integration of  y'' + 2*zeta*wn*y' + wn^2*y = wn^2*setpoint
            ddy = omega_n**2 * (setpoint - y) - 2 * zeta * omega_n * dy
            dy += ddy * dt
            y += dy * dt

            rr.set_time("time_s", duration=step * dt)
            rr.log("response/output", rr.Scalars(y))
            rr.log("response/setpoint", rr.Scalars(setpoint))
            rr.log("response/error", rr.Scalars(abs(y - setpoint)))

            overshoot = (y - setpoint) / setpoint * 100
            peak_overshoot = max(peak_overshoot, overshoot)

            if abs(y - setpoint) > 0.02 * setpoint:
                last_unsettled = step

        self.out_overshoot = max(0.0, peak_overshoot)
        self.out_settling_time = last_unsettled * dt
        self.out_rerun = bn.capture_rerun_window()


def example_rerun_over_time(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Track the controller over time, with each run's recording in its own tab.

    ``out_rerun`` keeps only the last ``max_time_events`` recordings, so the history
    shows the latest two runs while the scalar metrics keep all of them.
    """
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, over_time=True, pane_layout=bn.PaneLayout.tabs)
    benchable = ControlSystemSweep()
    bench = benchable.to_bench(run_cfg)
    base_time = datetime(2024, 1, 1)

    for i, degradation in enumerate([0.0, 0.1, 0.25, 0.4]):
        benchable._degradation = degradation  # pylint: disable=protected-access
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        bench.plot_sweep(
            "controller_over_time",
            input_vars=[],
            result_vars=["out_overshoot", "out_settling_time", "out_rerun"],
            run_cfg=run_cfg,
            time_src=base_time + timedelta(days=i),
        )

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_over_time, over_time=True)
