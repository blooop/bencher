"""Auto-generated example: 1 Float, 2 Categorical."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject
from datetime import datetime, timedelta


def example_over_time_1_float_2_cat(run_cfg=None):
    """1 Float, 2 Categorical."""
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.over_time = True
    benchable = BenchableObject()
    bench = benchable.to_bench(run_cfg)
    time_offsets = [0.0, 0.5, 1.0]
    _base_time = datetime(2000, 1, 1)
    for i, offset in enumerate(time_offsets):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "over_time",
            input_vars=["float1", "wave", "variant"],
            result_vars=["distance", "sample_noise"],
            const_vars=dict(noise_scale=0.1),
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bch.run(example_over_time_1_float_2_cat, level=4)
