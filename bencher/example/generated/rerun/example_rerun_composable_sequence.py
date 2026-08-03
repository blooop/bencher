"""Auto-generated example: Rerun Composition — Sequence."""

import rerun as rr

import bencher as bn


class RerunComposition(bn.ParametrizedSweep):
    """Record two step responses over time and combine them into one result.

    Each recording animates a second-order system tracking a unit step: the
    plant marker sweeps left to right as it settles, the trace grows behind it,
    and the output is logged as a scalar.  Both recordings span the same
    ``time_s`` range, which is what makes the composition modes differ — see
    the description below.
    """

    out_rerun = bn.ResultRerun(width=900, height=520)

    def benchmark(self):
        composed = bn.ComposableContainerRerun(
            compose_method=bn.ComposeType.sequence,
            name="Sequence composition",
        )
        # (label, damping ratio, colour) — the reference settles cleanly, the
        # candidate is under-damped and rings.
        scenes = [
            ("Reference", 0.9, [230, 80, 80]),
            ("Candidate", 0.35, [70, 120, 235]),
        ]
        n_steps, dt, omega_n = 80, 0.025, 8.0

        for index, (label, zeta, color) in enumerate(scenes):
            recording = rr.RecordingStream(
                f"bencher_composable_sequence_{index}",
                make_default=False,
            )
            y, dy, trace = 0.0, 0.0, []
            for step in range(n_steps):
                # Euler integration of  y'' + 2*zeta*wn*y' + wn^2*y = wn^2
                ddy = omega_n**2 * (1.0 - y) - 2 * zeta * omega_n * dy
                dy += ddy * dt
                y += dy * dt
                trace.append([step * dt, y])

                recording.set_time("time_s", duration=step * dt)
                recording.log(
                    "scene/plant",
                    rr.Boxes2D(
                        centers=[[step * dt, y]],
                        half_sizes=[[0.03, 0.05]],
                        colors=[color],
                        labels=[label],
                    ),
                )
                recording.log("scene/trace", rr.LineStrips2D([trace], colors=[color]))
                recording.log("metrics/output", rr.Scalars(y))

            composed.append(bn.capture_rerun_rrd(recording), label=label)

        # ResultRerun recognizes the compositor and materializes one combined
        # path-backed .rrd before the result enters Bencher's cache.
        self.out_rerun = composed


def example_rerun_composable_sequence(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Composition — Sequence."""
    bench = RerunComposition().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=[],
        result_vars=["out_rerun"],
        description="Two independent ``.rrd`` recordings, each animating a step response "
        "over a ``time_s`` timeline, are assigned directly to a ``ComposableContainerRerun``. "
        "Bencher namespaces their entity paths, combines their chunks into one recording, "
        "and generates a native Rerun Blueprint. ``sequence`` splices the recordings end to end: the second recording's ``time_s`` values are offset to start where the first one ends, and each recording is cleared as the next begins.  Scrubbing or playing the single shared view therefore runs the reference response first, then the candidate.",
        post_description="``right`` and ``down`` place each recording in its own view on a "
        "shared timeline; ``overlay`` draws them in one view at the same times; ``sequence`` "
        "offsets the timelines so the recordings play back to back.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_composable_sequence)
