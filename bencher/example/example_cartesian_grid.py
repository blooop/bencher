"""Grid of Cartesian product animations across all dimensionality combinations.

Uses bencher's sweep machinery to explore the animation space:
  - spatial_dims (1-4) × use_repeat × use_over_time

Run with: pixi run python bencher/example/example_cartesian_grid.py
"""

from __future__ import annotations

import bencher as bn

from bencher.results.manim_cartesian import CartesianProductCfg, SweepVar, render_animation


class CartesianAnimationSweep(bn.ParametrizedSweep):
    spatial_dims = bn.IntSweep(default=1, bounds=(1, 5), doc="Number of spatial dimensions")
    repeats = bn.IntSweep(default=0, bounds=(0, 100), doc="Number of repeats (0 = no repeat dim)")
    time_steps = bn.IntSweep(
        default=0, bounds=(0, 10), doc="Number of time steps (0 = no over_time dim)"
    )

    # Strobe tunables
    strobe_pad = 12
    strobe_border_radius = 4
    strobe_mark_size = 2
    strobe_mark_gap = 4

    animation = bn.ResultImage()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        all_spatial = [
            SweepVar("dim_1", [0, 1, 2]),
            SweepVar("dim_2", [0, 1, 2]),
            SweepVar("dim_3", [0, 1]),
            SweepVar("dim_4", [0, 1]),
            SweepVar("dim_5", [0, 1]),
        ]
        sweep_vars = list(all_spatial[: self.spatial_dims])

        if self.repeats > 0:
            sweep_vars.append(SweepVar("repeat", list(range(1, self.repeats + 1))))
        if self.time_steps > 0:
            sweep_vars.append(SweepVar("over_time", [f"t{i}" for i in range(self.time_steps)]))

        cfg = CartesianProductCfg(
            all_vars=sweep_vars,
            result_names=["result"],
            strobe_pad=self.strobe_pad,
            strobe_mark_size=self.strobe_mark_size,
            strobe_mark_gap=self.strobe_mark_gap,
            strobe_border_radius=self.strobe_border_radius,
        )

        # With caching, no need for tag-based directories - each unique animation gets its own filename
        gif_path = render_animation(
            cfg,
            width=320,
            height=200,
        )
        self.animation = gif_path
        return super().__call__()


def example_cartesian_grid(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    run_cfg.cache_results = False
    run_cfg.executor = bn.Executors.THREAD_POOL  # Use thread pool to avoid multiprocessing import issues
    bench = bn.Bench("cartesian_animations", CartesianAnimationSweep(), run_cfg=run_cfg)
    bench.result_vars = ["animation"]
    bench.add_plot_callback(bn.BenchResult.to_sweep_summary)
    bench.add_plot_callback(bn.BenchResult.to_panes)

    # -- 2D sweep: spatial_dims × repeats --
    bench.plot_sweep(
        "Tally: spatial_dims x repeats",
        input_vars=["spatial_dims", bn.sweep("repeats", [0, 1, 5, 10, 20, 100])],
        const_vars=[("time_steps", 0)],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_cartesian_grid, level=4, cache_results=False)
