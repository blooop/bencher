"""Auto-generated example: Rerun Summary — merge a whole sweep into one viewer."""

import rerun as rr

import bencher as bn


class RerunSummarySweep(bn.ParametrizedSweep):
    """Record a step response per sample, then merge the whole sweep into one viewer.

    Sweeping a ``ResultRerun`` normally embeds one rerun web viewer *per sample*,
    so this 3x2 sweep would spawn six independent wasm viewers with no way to
    compare across them.  ``rerun_summary`` merges every recording into a single
    recording plus blueprint instead.
    """

    damping = bn.FloatSweep(default=0.5, bounds=[0.2, 0.9], samples=3)
    omega_n = bn.FloatSweep(default=6.0, bounds=[4.0, 8.0], samples=2)

    out_rerun = bn.ResultRerun(width=900, height=520)

    def benchmark(self):
        recording = rr.RecordingStream("rerun_summary_sample", make_default=False)
        n_steps, dt = 80, 0.025
        y, dy, trace = 0.0, 0.0, []
        for step in range(n_steps):
            # Euler integration of  y'' + 2*zeta*wn*y' + wn^2*y = wn^2
            ddy = self.omega_n**2 * (1.0 - y) - 2 * self.damping * self.omega_n * dy
            dy += ddy * dt
            y += dy * dt
            trace.append([step * dt, y])

            recording.set_time("time_s", duration=step * dt)
            recording.log("scene/trace", rr.LineStrips2D([trace]))
            recording.log("metrics/output", rr.Scalars(y))

        self.out_rerun = bn.capture_rerun_rrd(recording)
        return super().benchmark()


def example_rerun_summary(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Summary — merge a whole sweep into one viewer."""
    bench = RerunSummarySweep().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["damping", "omega_n"],
        result_vars=["out_rerun"],
        description="Each of the six samples records its own step response to a separate "
        "``.rrd``, which is what diskcache keys on.  ``rerun_summary`` walks the result "
        "dataset afterwards and merges all six into ONE recording, re-homing each sample "
        "under its own entity-path branch and generating a Blueprint to lay them out.  "
        "The result is a single embedded viewer instead of six, and because everything "
        "shares one recording the samples can be scrubbed on a common timeline.",
        post_description="``rerun_summary`` sequences every dimension onto one timeline; "
        "``rerun_grid`` lays the dimensions out in space instead.  Both are named-only "
        "plot types because merging every recording is expensive.",
        plot_callbacks=[bn.BenchResult.to_rerun_summary],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_summary)
