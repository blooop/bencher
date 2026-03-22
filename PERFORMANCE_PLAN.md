# Performance Improvement Plan for Bencher

This document identifies performance improvement opportunities across benchmark generation,
caching, and viewing. Each item includes a correctness assessment and regression testing strategy.

> **Critical invariant**: The existing codebase uses `deepcopy` extensively to ensure callers can
> freely mutate returned objects without corrupting cached data or shared state. Any optimization
> that removes or reduces copying **must** prove that no caller depends on mutation freedom, or
> must substitute an equivalent safety mechanism (e.g., copy-on-write, frozen objects).

---

## Table of Contents

1. [Benchmark Generation & Execution](#1-benchmark-generation--execution)
2. [Caching](#2-caching)
3. [Viewing & Visualization](#3-viewing--visualization)
4. [Cross-Cutting Concerns](#4-cross-cutting-concerns)
5. [Regression Testing Strategy](#5-regression-testing-strategy)
6. [Implementation Priority](#6-implementation-priority)

---

## 1. Benchmark Generation & Execution

### 1.1 Eliminate redundant deep copies in `plot_sweep()`

**File**: `bencher/bencher.py:303-331`

**Problem**: Variables are deep-copied at function entry (lines 303-305), then conditionally
deep-copied *again* when defaults are used (lines 315, 325, 331). This means up to 6 deep copies
per `plot_sweep()` call when all three variable lists use defaults.

**Proposed fix**: Check for `None` *before* copying. Copy once from the chosen source.

```python
# Before (current)
input_vars_in = deepcopy(input_vars)        # always copies
...
if input_vars_in is None:
    input_vars_in = deepcopy(self.input_vars)  # copies again

# After (proposed)
input_vars_in = deepcopy(input_vars if input_vars is not None else self.input_vars)
```

**Correctness risk**: LOW. The second copy was always redundant — the first copy's result is
discarded when `None`. The single copy still provides mutation isolation.

**Regression test**: Existing `test_bencher.py` and `test_bench_runner.py` cover `plot_sweep()`.
Add an assertion that modifying the returned variables does not affect `self.input_vars`.

---

### 1.2 Eliminate double deep copy in `BenchRunner.run()`

**File**: `bencher/bench_runner.py:317,332`

**Problem**: `run_cfg` is deep-copied at method entry (line 317), then copied *again* for each
level/repeat iteration (line 332). For N levels × M repeats, this creates N×M unnecessary copies.

**Proposed fix**: Copy once per iteration from the original, not from the already-copied value.
Or, if per-iteration mutations are limited to specific fields, copy once and reset those fields
instead of full deep copy.

**Correctness risk**: MEDIUM. The per-iteration copy exists because the benchmark function may
mutate `run_cfg`. Must audit all code paths that receive `run_lvl` to verify which fields are
actually modified during a run. If mutations are limited to a known set of fields, a shallow copy
+ field reset is sufficient.

**Regression test**: `test_bench_runner.py` — verify multi-level runs produce identical results
before and after the change by comparing output datasets element-by-element.

---

### 1.3 Avoid materializing full Cartesian product into a list

**File**: `bencher/result_collector.py:113-116`

**Problem**: `list(zip(product(...), product(...)))` eagerly materializes the entire Cartesian
product. For 5 dimensions × 10 values each = 100,000 tuples allocated upfront.

**Proposed fix**: Use a lazy generator instead of `list()`. The downstream loop (bencher.py:754)
already iterates sequentially.

```python
# Before
function_inputs = list(zip(product(*dim_ranges_index), product(*dim_ranges)))

# After
function_inputs = zip(product(*dim_ranges_index), product(*dim_ranges))
```

**Correctness risk**: LOW-MEDIUM. Must verify no downstream code indexes into `function_inputs`
by position or calls `len()` on it. The reversed sample order path (bencher.py:726-746) rebuilds
the product anyway, so it would not be affected.

**Regression test**: `test_sample_order.py`, `test_result_collector.py` — verify identical results
for both forward and reversed orderings with a multi-dimensional sweep.

---

### 1.4 Deduplicate Cartesian product calls for reversed sample order

**File**: `bencher/bencher.py:726-746`

**Problem**: For `SampleOrder.REVERSED`, the entire Cartesian product is regenerated from scratch
by re-extracting coordinates from the dataset (3 separate `product()` calls). This is wasteful.

**Proposed fix**: Generate the product once, store as a list, and reverse it in-place or via
`reversed()`. Map indices back to original order using a permutation array.

**Correctness risk**: LOW. Output order should be verified to match the current reversed behavior
exactly.

**Regression test**: `test_sample_order.py` — compare results for `SampleOrder.REVERSED` with a
known multi-dimensional sweep. Assert element-by-element dataset equality.

---

### 1.5 Deep copy kwargs only when necessary in `worker_kwargs_wrapper()`

**File**: `bencher/sweep_executor.py:39`

**Problem**: `deepcopy(kwargs)` is called for *every* job submission, even when the worker function
does not mutate its inputs. For thousands of jobs, this is O(n × sizeof(kwargs)).

**Proposed fix**: Two options:
1. **Filter first, copy second**: Remove metadata keys (`repeat`, `over_time`, `time_event`)
   *before* deep-copying, reducing the copy size.
2. **Opt-in copy**: Add a `BenchRunCfg.copy_worker_kwargs` flag (default `True` for safety).
   Users with pure functions can set it to `False` to skip the copy entirely.

**Correctness risk**: HIGH for option 2. The deep copy exists because user-provided benchmark
functions may mutate their keyword arguments. Removing it could cause silent data corruption if a
worker function stores references to its inputs. Option 1 is safe and always beneficial.

**Regression test**: `test_sweep_executor.py` — test with a worker function that deliberately
mutates its kwargs; verify results are unaffected. `test_sample_cache.py` — verify cache hit/miss
counts are unchanged.

---

### 1.6 Parallel result streaming for non-serial executors

**File**: `bencher/bencher.py:782-784`

**Problem**: For `MULTIPROCESSING` executor, all jobs are submitted first, then results are
collected in a second pass. The worker pool is idle during result storage.

**Proposed fix**: Use `concurrent.futures.as_completed()` to process results as they finish,
overlapping result storage with computation.

**Correctness risk**: MEDIUM. Result storage order would change (non-deterministic). Must verify
that `set_xarray_multidim()` is safe for out-of-order writes (it indexes by tuple, so it should
be). The progress bar may need adjustment.

**Regression test**: Run a multi-dimensional sweep with `MULTIPROCESSING` and compare the final
xarray dataset to the `SERIAL` result. They must be element-wise identical.

---

## 2. Caching

### 2.1 Avoid redundant cache opens

**File**: `bencher/result_collector.py:254-281`, `bencher/bencher.py:554-582`

**Problem**: `diskcache.Cache()` is opened (potentially creating/reading the SQLite index) each
time a benchmark is run. For repeated runs in the same process, this is wasted I/O.

**Proposed fix**: Cache the `diskcache.Cache` instance on the `Bench` object and reuse it across
calls. Close it on `__del__` or via a context manager.

**Correctness risk**: LOW. `diskcache.Cache` is designed for reuse. Must ensure thread safety if
parallel executors are used.

**Regression test**: `test_cache.py`, `test_sample_cache.py` — verify identical cache behavior
across multiple sequential `plot_sweep()` calls.

---

### 2.2 Use `diskcache.FanoutCache` for parallel workloads

**File**: `bencher/job.py:210`

**Problem**: The sample cache uses a single `diskcache.Cache`, which serializes all writes through
one SQLite connection. With `MULTIPROCESSING` executor, this becomes a bottleneck.

**Proposed fix**: Switch to `diskcache.FanoutCache` (sharded cache) when using parallel executors.
This distributes writes across multiple shards, reducing lock contention.

**Correctness risk**: LOW. `FanoutCache` has the same API as `Cache`. Tag-based operations
(used in `clear_tag_from_sample_cache`) work identically.

**Regression test**: `test_sample_cache.py` — verify all cache hit/miss counts are identical.
Run with both `SERIAL` and `MULTIPROCESSING` executors.

---

### 2.3 Batch cache lookups

**File**: `bencher/job.py:239-246`

**Problem**: Each job does an individual `key in self.cache` lookup followed by `self.cache[key]`.
For thousands of jobs, this is thousands of individual SQLite queries.

**Proposed fix**: Before the main execution loop, batch-check which keys exist in the cache using
a single query (e.g., `SELECT key FROM Cache WHERE key IN (...)`). Pre-populate a hit set. On
cache hit, retrieve values in batches.

**Correctness risk**: MEDIUM. Must handle the race condition where cache entries are evicted
between the batch check and the individual retrieval. Fallback to computation on miss.

**Regression test**: `test_sample_cache.py` — verify all cache hit/miss/call counts are identical.
Test with cache clearing mid-run to verify race condition handling.

---

### 2.4 Reduce hash computation overhead

**File**: `bencher/utils.py:94-107`, `bencher/worker_job.py:48-69`

**Problem**: Each job computes two SHA1 hashes: `function_input_signature_pure` and
`function_input_signature_benchmark_context`. The pure hash is always computed even when not needed
(only used when `only_hash_tag` is False).

**Proposed fix**: Lazily compute hashes — only compute `function_input_signature_benchmark_context`
when needed (i.e., when `only_hash_tag` is True, skip the context hash). Use `@property` with
caching (`functools.cached_property`).

**Correctness risk**: LOW. Hash values are read-only after construction. Lazy evaluation produces
identical results.

**Regression test**: `test_hash_persistent.py` — all existing determinism tests must pass.
`test_sample_cache.py` — verify cache key collisions don't change.

---

### 2.5 Remove non-pickleable objects before caching more efficiently

**File**: `bencher/result_collector.py:272-278`

**Problem**: Before caching a `BenchResult`, certain non-pickleable attributes are temporarily
removed and restored. This pattern is fragile and adds overhead.

**Proposed fix**: Implement `__getstate__`/`__setstate__` on `BenchResult` to automatically
exclude non-pickleable fields during serialization. This moves the logic into pickle's protocol
where it belongs.

**Correctness risk**: MEDIUM. Must verify all non-pickleable fields are correctly excluded and
that deserialized objects are functional. The restore-after-cache pattern currently guarantees the
in-memory object remains complete.

**Regression test**: `test_cache.py` — round-trip a `BenchResult` through cache and verify all
fields are present/correct after retrieval.

---

## 3. Viewing & Visualization

### 3.1 Avoid unnecessary dataset copies in `to_dataset()`

**File**: `bencher/results/bench_result_base.py:223`

**Problem**: `ds_out = self.ds.copy()` creates a full copy of the xarray dataset before every
reduction. For `ReduceType.REDUCE`, the mean/std operations already create new arrays, making
the initial copy wasteful.

**Proposed fix**: Operate directly on `self.ds` for read-only reductions (mean, std, min, max).
These xarray operations return new datasets and do not modify the source.

**Correctness risk**: HIGH. Must verify that *no* code path between the copy (line 223) and the
reduction (line 244) mutates `ds_out` in place. If any filtering or renaming modifies the dataset
before reduction, the copy is necessary. Audit all `ReduceType` branches carefully.

**Regression test**: Create a benchmark result with known values. Call `to_dataset()` with each
`ReduceType`. Verify the source `self.ds` is unmodified after each call. Compare reduced outputs
to expected values.

---

### 3.2 Lazy HoloMap construction for over_time plots

**File**: `bencher/results/holoview_results/line_result.py:145-150`,
`bencher/results/holoview_results/heatmap_result.py:154-158`

**Problem**: For over_time benchmarks, the code eagerly creates a separate plot for *every*
time point and assembles them into a `HoloMap`. For many time points, this is slow and
memory-intensive.

**Proposed fix**: Use `hv.DynamicMap` instead of `hv.HoloMap`. DynamicMap generates plots on
demand (when the user selects a time point in the widget).

**Correctness risk**: LOW-MEDIUM. DynamicMap requires a callable that returns a plot for a given
key. The current loop body can be extracted into such a callable. However, DynamicMap behavior
in static exports (HTML, notebook) differs from HoloMap — DynamicMap requires a live server for
interactivity.

**Regression test**: Visual regression test — generate plots with both HoloMap and DynamicMap for
a known dataset. Verify data values are identical. Test both interactive (Panel serve) and static
(HTML export) contexts.

---

### 3.3 Avoid redundant `to_dataframe()` conversions

**File**: `bencher/results/holoview_results/distribution_result/distribution_result.py:120`,
`bencher/results/volume_result.py:85`

**Problem**: Several plot types convert xarray datasets to pandas DataFrames using
`.to_dataframe().reset_index()`. This creates a full copy of the data in a different format.
Some plots then subset the DataFrame, wasting most of the conversion work.

**Proposed fix**: Where possible, select/filter the xarray data *before* converting to DataFrame.
For plots that accept xarray directly (via hvplot.xarray), skip the DataFrame conversion entirely.

**Correctness risk**: LOW. The data content is identical; only the container format changes.

**Regression test**: Compare plot data values before and after the change using `hv.render()` to
extract the underlying data from the generated plot objects.

---

### 3.4 Reduce xr.merge() overhead in reduction pipeline

**File**: `bencher/results/bench_result_base.py:244-253`

**Problem**: `ReduceType.REDUCE` computes mean and std as separate datasets, then merges them.
`ReduceType.MINMAX` similarly merges mean, min, and max. Each `xr.merge()` copies all arrays.

**Proposed fix**: Build the output dataset in a single pass by computing mean and std together
and assigning them directly to a new dataset's data variables, avoiding the merge.

```python
ds_mean = ds_out.mean(dim="repeat", keep_attrs=True)
for rv in self.bench_cfg.result_vars:
    ds_mean[f"{rv.name}_std"] = ds_out[rv.name].std(dim="repeat")
ds_out = ds_mean
```

**Correctness risk**: MEDIUM. Must preserve the exact naming convention for `_std` and `_range`
variables. Must handle `ResultBool`'s special binomial standard error (not regular std).

**Regression test**: Compare `to_dataset(ReduceType.REDUCE)` output variable-by-variable against
a reference dataset with known statistical values. Verify `_std` variable names and values.

---

### 3.5 Cache reduced datasets

**File**: `bencher/results/bench_result_base.py:204-326`

**Problem**: `to_dataset()` is called multiple times for the same result (once per plot type that
matches the filter). The reduction is recomputed each time.

**Proposed fix**: Memoize `to_dataset()` results keyed by `(reduce_type, result_var, level,
agg_over_dims, agg_fn)`. Use `functools.lru_cache` or a simple dict cache on the result object.

**Correctness risk**: LOW-MEDIUM. Safe as long as the underlying `self.ds` is not modified between
calls. Since `self.ds` is populated during benchmark execution and then only read during plotting,
this should be safe. Add a flag to invalidate the cache if `self.ds` changes.

**Regression test**: Verify that calling `to_dataset()` twice with the same arguments returns
equal datasets. Verify that modifying `self.ds` and re-calling produces updated results.

---

## 4. Cross-Cutting Concerns

### 4.1 Profile before optimizing

Before implementing any of the above changes, establish a performance baseline:

1. **Create a benchmark suite** with representative workloads:
   - Small sweep: 2 dims × 5 values = 25 jobs
   - Medium sweep: 4 dims × 10 values = 10,000 jobs
   - Large sweep: 5 dims × 20 values = 3,200,000 jobs (cache-only, skip execution)
2. **Measure**: wall time, peak memory, cache hit rate, plot render time
3. **Profile**: Use `cProfile` or `py-spy` to identify actual hotspots
4. **Track**: Store baseline metrics to compare against after each optimization

### 4.2 Add performance regression tests

Add a `test_performance.py` that runs representative sweeps and asserts:
- Execution time stays within 2× of baseline (to catch algorithmic regressions)
- Memory usage stays within 1.5× of baseline
- Cache hit rates remain identical for identical inputs

### 4.3 Document the deep-copy contract

Add a section to `CLAUDE.md` or a `CONTRIBUTING.md` explaining:
- Why deep copies exist (mutation safety for cached data)
- When it's safe to remove them (pure functions, read-only access)
- How to test for correctness (mutation tests, cache integrity checks)

---

## 5. Regression Testing Strategy

Every change in this plan must pass:

1. **Existing test suite**: `pixi run test` — all tests green
2. **Hash stability**: `test_hash_persistent.py` — all hash determinism tests pass
3. **Cache integrity**: `test_sample_cache.py` — all cache hit/miss counts unchanged
4. **Data correctness**: For each modified code path, add a test that:
   - Runs a sweep with known inputs and expected outputs
   - Compares the output dataset element-by-element to a reference
   - Verifies the source data is not mutated after operations
5. **Cross-process stability**: `test_hash_persistent.py::TestCrossProcessDeterminism` — hashes
   identical across processes
6. **Mutation safety test** (new): After each operation that was previously guarded by deep copy,
   mutate the returned object and verify the source is unaffected

---

## 6. Implementation Priority

| Priority | Item | Effort | Risk | Impact |
|----------|------|--------|------|--------|
| **P0** | 4.1 Profile baseline | Low | None | Enables all other work |
| **P1** | 1.1 Deduplicate `plot_sweep()` copies | Low | Low | Moderate |
| **P1** | 1.5 Filter-then-copy kwargs | Low | Low | High for large sweeps |
| **P1** | 3.1 Avoid dataset copy in `to_dataset()` | Medium | High | High |
| **P2** | 1.2 Single copy in `BenchRunner.run()` | Medium | Medium | Moderate |
| **P2** | 1.3 Lazy Cartesian product | Low | Low-Med | High for large sweeps |
| **P2** | 2.1 Reuse cache instances | Low | Low | Moderate |
| **P2** | 2.4 Lazy hash computation | Low | Low | Low-Moderate |
| **P2** | 3.4 Single-pass reduction | Medium | Medium | Moderate |
| **P2** | 3.5 Memoize `to_dataset()` | Medium | Low-Med | High for many plots |
| **P3** | 1.4 Deduplicate reversed product | Low | Low | Low |
| **P3** | 1.6 Streaming parallel results | Medium | Medium | High for parallel |
| **P3** | 2.2 FanoutCache for parallel | Low | Low | Moderate for parallel |
| **P3** | 2.3 Batch cache lookups | High | Medium | High for large sweeps |
| **P3** | 2.5 `__getstate__` for results | Medium | Medium | Low |
| **P3** | 3.2 DynamicMap for over_time | Medium | Low-Med | Moderate |
| **P3** | 3.3 Pre-filter before to_dataframe | Low | Low | Low |
