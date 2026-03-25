import bencher as bn

from bencher.example.example_simple_float import example_simple_float
from bencher.example.example_levels import example_levels
from bencher.example.optuna.example_optuna import optuna_rastrigin
from bencher.example.example_sample_cache import example_sample_cache


if __name__ == "__main__":
    run_cfg = bn.BenchRunCfg()
    run_cfg.overwrite_sample_cache = True
    bench_runner = bn.BenchRunner("bencher_examples", run_cfg=run_cfg)

    bench_runner.add(example_simple_float)
    bench_runner.add(example_levels)
    bench_runner.add(optuna_rastrigin)
    bench_runner.add(example_sample_cache)

    bench_runner.run(level=4, show=True, grouped=True, save=False)
