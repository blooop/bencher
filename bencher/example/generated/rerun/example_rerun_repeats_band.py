"""Auto-generated example: Rerun Repeats Band — the mean and a ±1σ band from repeats."""

import math
import random

import bencher as bn


class NoisySine(bn.ParametrizedSweep):
    """A sine wave with noise that grows away from the peak.

    Every repeat of a sample gives a different value, so the sweep has a mean and a
    standard deviation at each ``x``.
    """

    x = bn.FloatSweep(default=0.0, bounds=[0.0, math.pi], samples=20, units="rad")

    out = bn.ResultFloat(units="V", doc="sin(x) plus noise")

    def benchmark(self):
        noise_scale = 0.05 + 0.3 * abs(math.cos(self.x))
        self.out = math.sin(self.x) + random.gauss(0.0, noise_scale)
        return super().benchmark()


def example_rerun_repeats_band(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Repeats Band — the mean and a ±1σ band from repeats."""
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=8)
    run_cfg.backend = "rerun"

    bench = NoisySine().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["x"],
        result_vars=["out"],
        description="With ``repeats > 1`` the rerun backend reduces each numeric result "
        "to its mean and standard deviation.  It logs them as one ``rr.Measurements`` "
        "series, which the rerun viewer draws as the mean line inside a shaded "
        "\u00b11\u03c3 band.  The noise is largest at the two ends of the sweep, so the "
        "band is widest there.",
        post_description="The viewer opens on the ``log_tick`` timeline, one tick per "
        "``x`` sample.  The units of the result var (``V``) show in the legend and the "
        "tooltips.  With one repeat the same sweep logs plain ``rr.Scalars`` and no band.",
        plot_callbacks=[bn.BenchResult.to_rerun_plots],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_repeats_band)
