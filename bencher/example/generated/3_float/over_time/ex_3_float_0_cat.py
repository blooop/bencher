"""Auto-generated example: 3 Float, 0 Categorical."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject
from datetime import datetime, timedelta


def example_over_time_3_float_0_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """3 Float, 0 Categorical."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
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
            input_vars=[
                "float1",
                "float2",
                {"name": "float3", "values": None, "max_level": 3, "samples": None},
            ],
            result_vars=["distance", "sample_noise"],
            const_vars=dict(noise_scale=0.1),
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bch.run(example_over_time_3_float_0_cat, level=4)
