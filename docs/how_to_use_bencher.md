# How to Use Bencher

Bencher is a Python framework for running parameter sweeps and visualizing results.
You define dimensions (input parameters), a benchmark function, and result variables.
Bencher computes the Cartesian product of all dimensions, executes each combination,
and produces interactive reports with auto-detected plot types.

Install: `pip install holobench`

## Quick Start

```python
import bencher as bn

class MyBenchmark(bn.ParametrizedSweep):
    # Inputs — bencher sweeps the Cartesian product of these
    size = bn.IntSweep(default=10, bounds=(10, 1000), doc="Problem size")
    method = bn.StringSweep(["brute", "optimized"], doc="Algorithm")

    # Results — what the benchmark measures
    elapsed = bn.ResultVar(units="s")

    def benchmark(self):
        self.elapsed = run_benchmark(self.size, self.method)

def example_benchmark(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = bn.Bench("my_bench", MyBenchmark(), run_cfg=run_cfg)
    bench.result_vars = ["elapsed"]
    bench.plot_sweep("Benchmark", input_vars=["size", "method"])
    return bench

if __name__ == "__main__":
    bn.run(example_benchmark)
```

This produces an interactive HTML report with the appropriate plot type auto-selected
based on the parameter and result types.

## Core Concept: Dimensions Are Sweep Variables

Every independent parameter that you want to vary must be its own sweep variable.
Bencher computes the Cartesian product automatically. **Never manually loop over
combinations.**

```python
class Good(bn.ParametrizedSweep):
    width = bn.IntSweep(default=64, bounds=(32, 256))
    use_cache = bn.BoolSweep(default=False)
    backend = bn.StringSweep(["cpu", "gpu"])
    # 3 independent dimensions → bencher sweeps all combinations
```

## Sweep Types

Choose the type that matches the parameter's nature:

| Type | Use for | Example |
|---|---|---|
| `bn.IntSweep(bounds=(lo, hi))` | Integer ranges | `n_workers = bn.IntSweep(bounds=(1, 8))` |
| `bn.FloatSweep(bounds=(lo, hi))` | Float ranges | `learning_rate = bn.FloatSweep(bounds=(0.001, 0.1))` |
| `bn.BoolSweep()` | On/off toggles | `use_jit = bn.BoolSweep(default=False)` |
| `bn.StringSweep([...])` | Categorical choices | `optimizer = bn.StringSweep(["adam", "sgd"])` |
| `bn.EnumSweep(MyEnum)` | Python enums | `mode = bn.EnumSweep(CompressionMode)` |

**Critical rule:** If two things vary independently, they must be separate variables.

Wrong — one variable encoding combinations:
```python
config = bn.StringSweep(["no_cache_cpu", "no_cache_gpu", "cache_cpu", "cache_gpu"])
```

Right — two independent dimensions:
```python
use_cache = bn.BoolSweep(default=False)
backend = bn.StringSweep(["cpu", "gpu"])
```

Use `IntSweep(bounds=(0, N))` when 0 means "feature absent" and 1+ controls magnitude
(e.g., number of retries, repeat count, number of threads).

## Result Types

| Type | Use for | Set to |
|---|---|---|
| `bn.ResultVar(units="s")` | Scalar metrics | `self.elapsed = 0.42` |
| `bn.ResultImage()` | Images, GIFs | `self.img = "/path/to/output.png"` |
| `bn.ResultVideo()` | Videos | `self.vid = video_writer.write()` |

For images: use `bn.gen_image_path("name")` to generate unique paths.
For videos: use `bn.VideoWriter()` to collect frames and `.write()` to save.

## Running a Sweep

```python
def example_foo(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = bn.Bench("name", MyBenchmark(), run_cfg=run_cfg)
    bench.result_vars = ["elapsed", "accuracy"]

    # Single sweep over all dimensions — produces a complete grid
    bench.plot_sweep(
        "Full Sweep",
        input_vars=["size", "method", "backend"],
    )

    return bench

if __name__ == "__main__":
    bn.run(example_foo)
```

Prefer **one `plot_sweep` with all input vars** to get a complete grid.

## Controlling Which Values Are Swept

Use `bn.sweep()` inside `input_vars` to control the range without changing the
variable definition:

```python
bench.plot_sweep(
    "Sweep",
    input_vars=[
        "size",                                    # full range from bounds
        bn.sweep("method", ["fast", "accurate"]),  # explicit subset
        bn.sweep("workers", max_level=3),           # auto-pick up to 3 values
    ],
)
```

## Fixing Dimensions with const_vars

To hold some parameters constant while sweeping others:

```python
bench.plot_sweep(
    "CPU only",
    input_vars=["size", "method"],
    const_vars=dict(backend="cpu"),
)
```

## Run Configuration

```python
def example_foo(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    run_cfg.cache_results = False   # disable for file-based / non-deterministic results
    bench = bn.Bench("name", MyBenchmark(), run_cfg=run_cfg)
    ...
    return bench

if __name__ == "__main__":
    bn.run(example_foo, level=4)    # level controls sweep detail depth
```

## The benchmark() Method

Every benchmark class inherits from `bn.ParametrizedSweep` and implements `benchmark()`:

```python
class MyBench(bn.ParametrizedSweep):
    x = bn.FloatSweep(bounds=(0, 1))
    result = bn.ResultVar()

    def benchmark(self):
        self.result = compute(self.x)
```

When `benchmark()` is called, all sweep parameters (`self.x`, etc.) are already set.
Just set result variables directly on `self`. No boilerplate required.

> **Migration from `__call__`:** The old pattern of overriding `__call__()` with
> `self.update_params_from_kwargs(**kwargs)` and `return super().__call__()` is
> deprecated. Simply rename `__call__` to `benchmark`, remove the two boilerplate
> lines, and remove `**kwargs` from the signature.

## File-Based Results (Images, Videos)

When producing files:
1. Write to a **unique path** per combination (use parameter values in the path)
2. Set `run_cfg.cache_results = False`
3. Use `bn.ResultImage()` / `bn.ResultVideo()` and set to the path string

```python
class ImageBench(bn.ParametrizedSweep):
    width = bn.IntSweep(bounds=(100, 500))
    output = bn.ResultImage()

    def benchmark(self):
        path = bn.gen_image_path(f"output_{self.width}")
        render_image(self.width, path)
        self.output = str(path)
```

## Entry Point Convention

- Function name must start with `example_` (used for discovery by tests and docs)
- Accept `run_cfg: bn.BenchRunCfg | None = None`
- Return the `bn.Bench` instance
- Use `bn.run(example_func)` in `__main__`

## Common Mistakes

| Mistake | Fix |
|---|---|
| Manually looping over parameter combinations | Use `plot_sweep(input_vars=[...])` |
| One StringSweep encoding multiple independent toggles | Use separate BoolSweep / IntSweep per toggle |
| Many small plot_sweep calls for different combos | One plot_sweep with all input_vars |
| Building panel/HTML layouts manually | Use bencher's report system |
| Using the old `__call__` pattern with boilerplate | Override `benchmark()` instead |
| Caching file-path results | Set `run_cfg.cache_results = False` |
