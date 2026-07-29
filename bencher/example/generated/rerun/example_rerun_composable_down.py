"""Auto-generated example: Rerun Composition — Down."""

import rerun as rr

import bencher as bn


class RerunComposition(bn.ParametrizedSweep):
    """Create two recordings and combine them into one Rerun result."""

    out_rerun = bn.ResultRerun(width=900, height=520)

    def benchmark(self):
        composed = bn.ComposableContainerRerun(
            compose_method=bn.ComposeType.down,
            name="Down composition",
        )
        scenes = [
            ("Reference", [-0.65, 0.0], [230, 80, 80]),
            ("Candidate", [0.65, 0.0], [70, 120, 235]),
        ]
        for index, (label, center, color) in enumerate(scenes):
            recording = rr.RecordingStream(
                f"bencher_composable_down_{index}",
                make_default=False,
            )
            recording.log(
                "scene/box",
                rr.Boxes2D(
                    centers=[center],
                    half_sizes=[[0.5, 0.35]],
                    colors=[color],
                    labels=[label],
                ),
                static=True,
            )
            recording.log(
                "scene/landmarks",
                rr.Points2D(
                    [[center[0] - 0.25, -0.55], [center[0] + 0.25, 0.55]],
                    colors=[color],
                    radii=0.08,
                ),
                static=True,
            )
            composed.append(bn.capture_rerun_rrd(recording), label=label)

        # ResultRerun recognizes the compositor and materializes one combined
        # path-backed .rrd before the result enters Bencher's cache.
        self.out_rerun = composed


def example_rerun_composable_down(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Composition — Down."""
    bench = RerunComposition().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=[],
        result_vars=["out_rerun"],
        description="Two independent ``.rrd`` recordings are assigned directly to a "
        "``ComposableContainerRerun``. Bencher namespaces their entity paths, combines "
        "their chunks into one recording, and creates a native Rerun ``down`` layout.",
        post_description="``right`` and ``down`` create horizontal and vertical views; "
        "``sequence`` creates tabs; ``overlay`` places compatible entities in one shared view.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_composable_down)
