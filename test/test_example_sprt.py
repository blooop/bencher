"""The SPRT gallery example sweeps the true failure rate and reports what the SPRT decides."""

import bencher as bn
from bencher.example.example_sprt import example_sprt


def test_example_sprt_sweeps_the_failure_rate():
    run_cfg = bn.BenchRunCfg(clear_cache=True, auto_plot=False)
    bench = example_sprt(run_cfg, trials=200)
    ds = bench.results[-1].ds
    flaky = ds["flaky_rate"].values.ravel()
    runs = ds["mean_runs"].values.ravel()
    # The sweep runs from far below p0 to far above p1.
    assert flaky[0] < 0.05
    assert flaky[-1] > 0.95
    # Every point decides in fewer runs than the 531-run fixed-sample plan.
    assert (runs < 531).all()
