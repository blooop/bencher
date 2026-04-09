"""Auto-generated example: Rerun Sweep — control system response across damping ratios."""

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

    out_overshoot = bn.ResultFloat(units="%", doc="peak overshoot", direction=bn.OptDir.minimize)
    out_settling_time = bn.ResultFloat(
        units="s", doc="2% settling time", direction=bn.OptDir.minimize
    )
    out_rerun = bn.ResultRerun(width=400, height=400, max_time_events=2)

    _degradation = 0.0  # set externally per over-time snapshot

    def benchmark(self):
        n_steps = 200
        dt = 0.02
        setpoint = 1.0
        omega_n = 5.0  # natural frequency  rad/s
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


def example_rerun_sweep(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Sweep — control system response across damping ratios."""
    bench = ControlSystemSweep().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["damping_ratio"],
        result_vars=["out_overshoot", "out_settling_time", "out_rerun"],
        description="Sweep the damping ratio of a second-order control system and "
        "visualise each step response in the rerun viewer.  Low damping causes "
        "overshoot and ringing; high damping is sluggish but stable.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_sweep, level=3)
