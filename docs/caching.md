# Caching

Bencher caches at two independent levels, and both are off by default. Turning the right
one on is the difference between a sweep that resumes after a crash and one that starts
from zero every time.

## The two caches

| | Per-sample cache | Benchmark-level result cache |
|---|---|---|
| Flag | `cache_samples` | `cache_results` |
| Granularity | one entry per call to the benchmark function | one entry per completed sweep |
| Key | the function's inputs plus the run tag — **nothing else** | `BenchCfg.hash_persistent()` — bench name, input/result/const vars, tag, `over_time`, `repeats` |
| Written | as each sample finishes | when the sweep completes (unconditionally, see below) |
| Read | only when `cache_samples=True` | only when `cache_results=True` |
| Buys you | resume a half-finished sweep; share samples between sweeps | skip re-running an unchanged sweep entirely |
| On disk | `cachedir/sample_cache` | `cachedir/benchmark_inputs` |

Both are [diskcache](https://grantjenks.com/docs/diskcache/) stores under a `cachedir/`
directory in the working directory, so they survive process restarts.

Two more stores live alongside them:

- `cachedir/history` — the `over_time` history, keyed *without* result variables so a
  changed metric set reconciles per column instead of orphaning the whole trend. See
  [Tracking results over time](over_time.md).
- `cachedir/blobs/` — content-addressed payloads for `ResultDataSet`. Reclaim orphans with
  `bn.clean_orphaned_blobs()`.

The important asymmetry: only the sample cache records partial progress. If your benchmark
function can crash, or the sweep is long enough that you might interrupt it, `cache_samples`
is the one you want — it is what makes a resumed run pick up where the crash left off. A
sweep that dies halfway writes nothing to the benchmark-level cache.

## The sample cache key: inputs plus tag

This is worth stating precisely, because getting it wrong costs you correct data. The
per-sample cache key is computed in `bencher/worker_job.py` as:

```python
return hash_sha1((self.fn_inputs_sorted, self.tag))
```

That is the *whole* key: the sorted function inputs (swept values merged with const values)
and the tag. The hash of the enclosing benchmark is deliberately not folded in.

The consequence: **two benchmarks that share a tag share cached samples.** If they define
the same input names and call the same-named function with the same values, one will
silently serve the other's results — even if their benchmark functions compute entirely
different things. There is currently no way to opt out of this. If you need isolation, give
the benchmarks distinct `run_tag` values.

```python
run_cfg.run_tag = "experiment_a"   # isolates this run's samples from other tags
```

`run_tag` is prefixed onto the benchmark's tag, so it is the practical lever for both
isolating and deliberately sharing samples.

> **`only_hash_tag` is a dead flag — do not rely on it.** Its parameter docstring claims
> that by default the sample key "includes the hash of the greater benchmarking context",
> so that "data generated from one benchmark will not affect data from another benchmark".
> No such default exists. Nothing in the codebase reads the flag: `BenchRunner` sets it and
> `BenchCfg` prints it into the sampling summary, and that is all. The tag-only key above is
> unconditional. This is tracked as **W6** in
> `plans/architecture/A4-caching-architecture.md`; `plans/architecture/A5-config-surface-reduction.md`
> schedules the flag's removal, with A4's `SampleKey.scope` restoring the choice properly.

## The flags

These are `BenchRunCfg` parameters. Each row below was checked against the code that reads
it; the "Reader" column names that site.

| Parameter | Default | What it actually does | Reader |
|---|---|---|---|
| `cache_samples` | `False` | Creates the sample cache at all. When `False` no `Cache` object is constructed, so nothing is stored *or* loaded per sample. | `sweep_executor.py` -> `FutureCache.__init__` (`job.py`) |
| `cache_results` | `False` | Gates the **read** of the benchmark-level cache. On a hit the whole sweep is skipped. The write is not gated — every completed sweep is stored regardless. | `bencher.py` (`elif run_cfg.cache_results:`) |
| `clear_cache` | `False` | Deletes this benchmark's entry from the benchmark-level cache before the run, and skips the cache check for it. | `bencher.py` (`if run_cfg.clear_cache:`) |
| `clear_sample_cache` | `False` | Clears the sample cache entries carrying this benchmark's tag, before sampling starts. Other tags are untouched. | `bencher.py` (`if bench_cfg.clear_sample_cache:`) |
| `overwrite_sample_cache` | `False` | Sets `FutureCache.overwrite`, which makes `submit()` skip the cache lookup and recompute, overwriting the stored value. | `sweep_executor.py` -> `FutureCache.submit` |
| `only_plot` | `False` | Turns a benchmark-level cache miss into `FileNotFoundError` instead of running the sweep. | `bencher.py` |
| `cache_size` | `None` | Maximum disk cache size in **megabytes**; applied as the `size_limit` of every store. `None` uses the 100 GB default. | `bencher.py` -> `SweepExecutor` / `ResultCollector` |
| `run_tag` | `""` | Prefixed onto the benchmark tag, which is part of the sample cache key and of `BenchCfg.hash_persistent()`. The isolation mechanism. | `bencher.py` (`tag=run_cfg.run_tag + tag`) |
| `only_hash_tag` | `False` | **Nothing.** No reader; see the box above. | none |

Two naming traps worth knowing:

- `BenchRunCfg.cache_results` (benchmark-level cache) and the `cache_results=` keyword
  accepted by `BenchRunner.run()` / `bn.run()` are **different things**. The keyword is a
  deprecated alias for `cache_samples` and emits a `DeprecationWarning`; the attribute is
  the benchmark-level cache flag. Prefer setting attributes on a `BenchRunCfg` explicitly.
- `bn.run()` and `BenchRunner.run()` auto-enable `cache_samples` for *progressive* runs
  (when `max_repeats` or `max_subsampling_divisions` is set), because reusing lower-density
  samples is the whole point of progression. Pass `cache_samples=False` to override.

### Cache invalidation is your problem

Both cache keys cover the inputs, not the body of your benchmark function. Edit the function
so it computes a different number for the same inputs and neither cache notices. Clear the
relevant cache (`clear_cache` / `clear_sample_cache`) or force recomputation with
`overwrite_sample_cache` whenever the measurement itself changes. The `cache_samples`
docstring says as much: "beware that depending on how you change code in the objective
function, the cache could provide values that are not correct."

## Worked example: surviving a crash

`bencher/example/example_sample_cache.py` benchmarks a function that raises partway
through the sweep. The sweep class is ordinary:

```python
class UnreliableClass(bn.ParametrizedSweep):
    input_val = bn.IntSweep(
        default=0,
        bounds=[0, 3],
        doc="If check limit=True the crashy_fn will crash if this value is >1",
    )
    return_value = bn.ResultFloat(units="ul")
    trigger_crash = bn.ResultFloat(units="True/False")

    def crashy_fn(self, input_val: int = 0, **kwargs) -> float:
        if self.trigger_crash and input_val > 1:
            raise RuntimeError("I crashed for no good reason ;P")

        return {"return_value": input_val, "trigger_crash": self.trigger_crash}
```

The interesting part is the driver:

```python
ex_run_cfg = bn.BenchRunCfg()
ex_run_cfg.repeats = 1
ex_run_cfg.executor = bn.Executors.SCOOP

# this will store the result of of every call to crashy_fn
ex_run_cfg.cache_samples = True
ex_run_cfg.clear_sample_cache = True

try:
    # this will crash after iteration 2 ... We don't want to lose those
    # (potentially expensive to calculate) datapoints so they are stored
    # in the sample_cache
    example_sample_cache(ex_run_cfg, trigger_crash=True)
except RuntimeError as e:
    print(f"caught the exception {e}")

ex_run_cfg.clear_sample_cache = False
example_sample_cache(ex_run_cfg, trigger_crash=False)
```

The first run starts from a clean slate (`clear_sample_cache=True`) and dies at
`input_val > 1`, but the samples it *did* compute are already in
`cachedir/sample_cache`. The second run keeps the cache (`clear_sample_cache=False`), loads
those samples back, and only evaluates the ones that were missed. The resulting report
shows a complete curve with no trace of the crash.

Note that this example deliberately uses the legacy separate-function pattern (passing
`instance.crashy_fn` as the worker) rather than a `benchmark()` method, because the worker
has to be able to raise for the cache system to resume from.

`bencher/example/example_sample_cache_context.py` goes further and asserts exact call
counts (`sample_cache.worker_wrapper_call_count`, `worker_fn_call_count`,
`worker_cache_call_count`), which is the clearest way to see when a call was served from
the cache and when it reached the worker.

## Caching and file-based results

Do not use `cache_results` for results that are file paths (`ResultImage`, `ResultVideo`,
`ResultPath`). A cached path can outlive the file it names. Set
`run_cfg.cache_results = False` and write to a unique path per parameter combination — see
[File-Based Results](how_to_use_bencher.md#file-based-results-images-videos).

## Relation to the collect/render split

Caching decides whether a sweep *runs*. The collect/render split decides where its results
are *turned into a report* — they compose, and neither replaces the other.

`Bench.collect()` (i.e. `plot_sweep(auto_plot=False)`) runs the sweep and computes
regression detection but builds no holoviews/panel/bokeh objects. The `BenchResult` it
returns can be pickled to disk with `bn.save_result()`, reloaded with `bn.load_result()`,
and rendered to HTML with `bn.render_report()` — typically from a separate, clean process,
which is what makes it safe when the collecting process holds foreign C-extension state
(ROS 2 `rclpy`/DDS) that can segfault during garbage collection of plotting objects.

From `bencher/example/example_collect_render.py`:

```python
# Collection phase — no holoviews/bokeh objects are constructed here.
result = bench.collect(
    input_vars=["theta"],
    result_vars=["out_sin"],
    title="Collect/render split",
)

out_dir = Path(tempfile.mkdtemp(prefix="bencher_collect_render_"))
result_path = out_dir / "result.pkl"
bn.save_result(result, result_path)

# Render phase — build + save the HTML report from the persisted result.
# In production run this in a separate process:
#   python -m bencher.render <result_path> <out_dir>
saved = bn.render_report(result_path, out_dir)
```

Points where the two interact:

- The caches are consulted during **collect**, exactly as they are for `plot_sweep()`.
  Rendering never re-executes the sweep — the loaded result already carries its dataset and
  its `regression_report`.
- `save_result` is a *manual* persistence step, unrelated to the caches: it writes wherever
  you point it, not into `cachedir/`. Blobs written for `ResultDataSet` payloads do live in
  the shared `cachedir/blobs/`, which is why a result saved this way still renders in
  another process — and why `bn.clean_orphaned_blobs()` needs `extra_roots=[...]` to know
  about results you saved outside the cache.
- A declared `container=` renderer travels with `BenchCfg` into the result cache *and*
  through the split, so it has to be picklable — a module-level function or callable
  object, not a lambda.

## See also

- [Getting Started](how_to_use_bencher.md) — run configuration overview
- [Tracking results over time](over_time.md) — the history cache and regression detection
- [Examples index](examples_index.md) — `example_sample_cache`, `example_sample_cache_context`,
  `example_collect_render`
