"""Auto-generated example: 0 Float, 1 Categorical (over time repeats)."""

from typing import Any

import random
import bencher as bn
from datetime import datetime, timedelta


class CacheBackend(bn.ParametrizedSweep):
    """Compares latency across different cache backends."""

    backend = bn.StringSweep(["redis", "memcached", "local"], doc="Cache backend")

    latency = bn.ResultVar(units="ms", doc="Cache lookup latency")

    _time_offset = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        base = {"redis": 1.2, "memcached": 1.5, "local": 0.3}[self.backend]
        self.latency = base + random.gauss(0, 0.15 * base)
        self.latency += self._time_offset * 10
        return super().__call__()


def example_sweep_0_float_1_cat_over_time_repeats(
    run_cfg: bn.BenchRunCfg | None = None,
) -> bn.Bench:
    """0 Float, 1 Categorical (over time repeats)."""
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=3)
    run_cfg.over_time = True
    benchable = CacheBackend()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)
    for i, offset in enumerate([0.0, 0.5, 1.0]):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "over_time",
            input_vars=["backend"],
            result_vars=["latency"],
            description="A 0 float + 1 categorical parameter sweep with both repeats and over_time tracking. This combination is the most informative: repeats reveal per-measurement noise at each time point, while over_time captures long-term drift. If your nightly benchmark shows increasing variance, repeats help distinguish whether the algorithm became noisier or the environment became less stable. Categorical-only sweeps produce bar/swarm plots comparing discrete settings.",
            post_description="Compare the per-snapshot distributions (via the slider) with the aggregated view. Growing spread over time suggests a real change, not just noise.",
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_0_float_1_cat_over_time_repeats, level=4)
