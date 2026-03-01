"""This file demonstrates benchmarking with both float and categorical variables with repeats."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject

# Configure and run a benchmark with multiple input types and repeats
run_cfg = bch.BenchRunCfg()
run_cfg.repeats = 20
run_cfg.level = 4
benchable = BenchableObject()
benchable.active_dims = 1
benchable.noise_scale = 0.15
bench = benchable.to_bench(run_cfg)
res = bench.plot_sweep(
    input_vars=["float1", "wave", "variant"], result_vars=["distance", "sample_noise"]
)

bench.report.show()
