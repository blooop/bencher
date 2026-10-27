"""Decide whether a test is flaky with the SPRT, swept over the test's true failure rate.

Each sample simulates a test that fails at ``fail_rate`` and runs ``bn.sprt`` on it many
times. The plots show how many runs the SPRT needs to decide, and how often it says
FLAKY. Below ``p0`` (0.1 %) it almost always says PASS; above ``p1`` (1 %) it almost
always says FLAKY; between the two it needs the most runs.
"""

import random

import bencher as bn

SPRT_CFG = bn.SprtCfg(p0=0.001, p1=0.01, alpha=0.05, beta=0.10)


class FlakyTest(bn.ParametrizedSweep):
    fail_rate = bn.FloatSweep(
        default=0.001,
        sample_values=[0.0005, 0.001, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.02],
        doc="True failure rate of the simulated test",
    )
    trials = bn.IntSweep(default=1000, bounds=(1, 100_000), doc="SPRTs to run per sample")

    mean_runs = bn.ResultFloat(units="runs", doc="Mean runs the SPRT needs to decide")
    flaky_rate = bn.ResultFloat(units="ratio", doc="Fraction of SPRTs that say FLAKY")

    def benchmark(self):
        # Seed from the inputs so the benchmark stays pure and the cache stays valid.
        rng = random.Random(f"{self.fail_rate}-{self.trials}")
        results = [
            bn.sprt(lambda: rng.random() >= self.fail_rate, SPRT_CFG) for _ in range(self.trials)
        ]
        self.mean_runs = sum(r.runs for r in results) / self.trials
        self.flaky_rate = sum(r.verdict is bn.SprtVerdict.FLAKY for r in results) / self.trials


def example_sprt(run_cfg: bn.BenchRunCfg | None = None, trials: int = 1000) -> bn.Bench:
    """Sweep the true failure rate and plot the SPRT's run count and FLAKY rate."""
    bench = FlakyTest().to_bench(run_cfg)
    bench.plot_sweep(
        title="SPRT verdicts by true failure rate",
        input_vars=["fail_rate"],
        result_vars=["mean_runs", "flaky_rate"],
        const_vars={"trials": trials},
        description=(
            f"bn.sprt with p0={SPRT_CFG.p0}, p1={SPRT_CFG.p1}, alpha={SPRT_CFG.alpha}, "
            f"beta={SPRT_CFG.beta}. A fixed-sample plan with the same error rates needs "
            "531 runs at every failure rate."
        ),
    )
    return bench


if __name__ == "__main__":
    bn.run(example_sprt)
