"""Auto-generated example: Line Plot — Inline Class Definition."""

import math
import bencher as bch


class WaveFunction(bch.ParametrizedSweep):
    """A simple wave function that maps an angle to its sine value.

    This is the simplest possible bencher example: one float input swept
    across its bounds, producing one scalar result plotted as a line.
    """

    theta = bch.FloatSweep(default=0, bounds=[0, 2 * math.pi], doc="Input angle", units="rad")

    amplitude = bch.ResultVar(units="V", doc="Sine of the input angle")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.amplitude = math.sin(self.theta)
        return super().__call__()


def example_flagship_line_plot(run_cfg=None):
    """Line Plot — Inline Class Definition."""
    bench = WaveFunction().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["theta"],
        result_vars=["amplitude"],
        description="Sweep a single float variable to produce a 1D line plot. "
        "This is the most basic bencher pattern: define a ParametrizedSweep class, "
        "implement __call__, and pass it to bench.plot_sweep().",
        post_description="The plot shows a clean sine curve. Try adding noise_scale "
        "or repeats to see how bencher handles uncertainty.",
    )

    return bench


if __name__ == "__main__":
    bch.run(example_flagship_line_plot, level=4)
