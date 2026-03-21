import bencher as bn

from bencher.example.example_categorical import example_categorical
from bencher.example.example_floats import example_floats
from bencher.example.example_floats2D import example_floats2D
from bencher.example.example_pareto import example_pareto
from bencher.example.example_simple_cat import example_1D_cat
from bencher.example.example_simple_float import example_simple_float
from bencher.example.example_float_cat import example_float_cat
from bencher.example.example_time_event import example_time_event
from bencher.example.example_float3D import example_floats3D

from bencher.example.example_custom_sweep import example_custom_sweep
from bencher.example.example_holosweep import example_holosweep
from bencher.example.example_holosweep_tap import example_holosweep_tap

from bencher.example.optuna.example_optuna import optuna_rastrigin
from bencher.example.example_sample_cache import example_sample_cache

# from bencher.example.example_workflow import example_floats2D_workflow, example_floats3D_workflow


if __name__ == "__main__":
    run_cfg = bn.BenchRunCfg()
    run_cfg.overwrite_sample_cache = True
    bench_runner = bn.BenchRunner("bencher_examples", run_cfg=run_cfg)

    bench_runner.add(example_categorical)
    bench_runner.add(example_floats)
    bench_runner.add(example_floats2D)
    bench_runner.add(example_floats3D)
    bench_runner.add(example_1D_cat)
    bench_runner.add(example_simple_float)
    bench_runner.add(example_pareto)
    bench_runner.add(example_float_cat)
    bench_runner.add(example_time_event)
    bench_runner.add(example_custom_sweep)
    bench_runner.add(example_holosweep)
    bench_runner.add(example_holosweep_tap)
    bench_runner.add(optuna_rastrigin)
    bench_runner.add(example_sample_cache)

    # bench_runner.run(level=2, show=True, grouped=True)

    bench_runner.run(level=4, show=True, grouped=True, save=False)
