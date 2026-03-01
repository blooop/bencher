"""This file demonstrates benchmarking with both categorical and float variables."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject

run_cfg = bch.BenchRunCfg()
run_cfg.repeats = 2  # only shows distance
run_cfg.level = 4
benchable = BenchableObject()
bench = benchable.to_bench(run_cfg)
run_cfg.repeats = 1
# shows both distance and sample_noise
res = bench.plot_sweep(input_vars=["float1"], result_vars=["distance", "sample_noise"])

# shows both distance and sample_noise
res = bench.plot_sweep(input_vars=["wave"], result_vars=["distance", "sample_noise"])


run_cfg.repeats = 10
# shows both distance and sample_noise
res = bench.plot_sweep(input_vars=["float1"], result_vars=["distance", "sample_noise"])

# shows distance result var with categorical input
res = bench.plot_sweep(input_vars=["wave"], result_vars=["distance", "sample_noise"])


bench.report.append(res.to_tabulator())
bench.report.show()
