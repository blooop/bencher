"""Auto-generated example: Getting Started — progressive bencher tutorial."""

import math
import random

from enum import auto
from strenum import StrEnum

import bencher as bn


class AlgoSetting(StrEnum):
    """Categorical input describing algorithm behaviour.

    Use enums to describe categorical inputs. In a real benchmark these would
    be settings whose influence on the metric you want to understand.
    """

    noisy = auto()  # adds random noise -- noisy output often means something is wrong
    optimum = auto()  # best performance -- characterising this is the goal
    poor = auto()  # worst performance


class GettingStartedBenchmark(bn.ParametrizedSweep):
    """A tutorial benchmark demonstrating core bencher features step by step.

    This class defines both inputs (sweep variables) and outputs (result
    variables) in a single ParametrizedSweep. The benchmark() method is the
    benchmark function -- it must be pure (no side effects) so that repeated
    calls produce statistically valid results.

    Bencher is a tool to explore how input parameters affect output metrics.
    The power of bencher is that when you have a system with many moving
    parts that all interact, teasing apart those influences becomes much
    harder because parameter spaces combine quickly. Bencher makes it easy
    to experiment with different input combinations to gain intuition about
    system performance.
    """

    algo_setting = bn.EnumSweep(AlgoSetting, default=AlgoSetting.poor)
    intensity = bn.FloatSweep(
        default=0.0,
        bounds=[0.0, 6.0],
        doc="Continuous input that affects the output",
        units="ul",
        samples=10,
    )

    accuracy = bn.ResultVar(
        units="%",
        direction=bn.OptDir.maximize,
        doc="Algorithm accuracy - the metric we want to optimise",
    )

    def benchmark(self):
        self.accuracy = 50 + math.sin(self.intensity) * 5

        match self.algo_setting:
            case AlgoSetting.noisy:
                self.accuracy += random.uniform(-10, 10)
            case AlgoSetting.optimum:
                self.accuracy += 30
            case AlgoSetting.poor:
                self.accuracy -= 20


def example_workflow_getting_started(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Getting Started — progressive bencher tutorial."""
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=10)

    bench = GettingStartedBenchmark().to_bench(run_cfg)

    # -- Step 1: 1D categorical sweep ------------------------------------
    # Sweep a single enum input while the float stays at its default.
    bench.plot_sweep(
        input_vars=["algo_setting"],
        result_vars=["accuracy"],
        title="Step 1 - 1D Enum Sweep",
        description="Sample all values in the enum setting and record accuracy. "
        "The float input (intensity) is not mentioned so it takes its default "
        "value. With repeats=10 the benchmark function is called 10 times per "
        "setting so you can see the distribution. The function must be pure - "
        "if past calls affect future calls through side effects, the "
        "statistics will be invalid.",
        post_description="The optimum setting clearly dominates. The noisy "
        "setting shows wide variance, indicating something unreliable.",
    )

    # -- Step 2: 1D float sweep ------------------------------------------
    # Now sweep the continuous variable while the enum stays at its default.
    bench.plot_sweep(
        input_vars=["intensity"],
        result_vars=["accuracy"],
        title="Step 2 - 1D Float Sweep",
        description="Sweep the continuous variable intensity while the enum "
        "takes its default value. The bounds and number of samples come from "
        "the class definition.",
        post_description="The output is affected by the float input in a "
        "continuous way with a peak around 1.5.",
    )

    # -- Step 3: 2D sweep with optimisation ------------------------------
    # Combine both inputs to see how they interact.
    run_cfg.use_optuna = True
    bench.plot_sweep(
        input_vars=["intensity", "algo_setting"],
        result_vars=["accuracy"],
        title="Step 3 - 2D Sweep with Optimisation",
        description="Perform a 2D sweep over both inputs to see how they act "
        "together. Setting use_optuna=True adds plots showing how much each "
        "input parameter affects the metric and prints the best parameter "
        "values found during the sweep.",
        post_description="The two inputs combine predictably: the best "
        "combination is algo_setting=optimum and intensity~1.5. If the "
        "'repeat' parameter shows high influence, it indicates undesired "
        "side effects in your benchmark function.",
        run_cfg=run_cfg,
    )

    return bench


if __name__ == "__main__":
    bn.run(example_workflow_getting_started, level=3, repeats=10)
