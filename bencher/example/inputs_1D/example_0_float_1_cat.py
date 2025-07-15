"""This file demonstrates benchmarking with both categorical and float variables."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject

run_cfg = bch.BenchRunCfg()
run_cfg.repeats = 2  # only shows distance
run_cfg.level = 4
bench = BenchableObject().to_bench(run_cfg)
# bench.worker_class_instance.float2=0.2
run_cfg.repeats = 1
# WORKS
# shows both distance and simple noise
res = bench.plot_sweep(input_vars=["float1"], result_vars=["distance", "sample_noise"])

# WORKS
# shows both distance and simple noise
res = bench.plot_sweep(input_vars=["noisy"], result_vars=["distance", "sample_noise"])


run_cfg.repeats = 10  # If i set repeats>1 then floating point variables still work but categorical variables do not
# WORKS
# shows both distance and simple noise
res = bench.plot_sweep(input_vars=["float1"], result_vars=["distance", "sample_noise"])

# BUG
# only shows distance result var, ignores sample_noise
res = bench.plot_sweep(input_vars=["noisy"], result_vars=["distance", "sample_noise"])


bench.report.append(res.to_tabulator())
# bench.report.append(res.to_scatter_jitter_single(BenchableObject.param.sample_noise))
bench.report.show()
