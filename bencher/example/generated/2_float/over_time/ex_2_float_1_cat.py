"""Auto-generated example: 2 Float, 1 Categorical."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_over_time_2_float_1_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """2 Float, 1 Categorical."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    from datetime import datetime, timedelta

    run_cfg.repeats = 1
    run_cfg.level = 4
    run_cfg.over_time = True
    benchable = BenchableObject()
    benchable.noise_scale = 0.1
    bench = benchable.to_bench(run_cfg)
    time_offsets = [0.0, 0.5, 1.0]
    _base_time = datetime(2000, 1, 1)
    for i, offset in enumerate(time_offsets):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "over_time",
            input_vars=["float1", "float2", "wave"],
            result_vars=["distance", "sample_noise"],
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bch.run(example_over_time_2_float_1_cat)
