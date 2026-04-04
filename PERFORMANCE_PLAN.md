# Performance Improvement Plan for Bencher

This document identifies performance improvement opportunities across benchmark generation,
caching, and viewing. Each item includes a correctness assessment and regression testing strategy.

> **Critical invariant**: The existing codebase uses `deepcopy` extensively to ensure callers can
> freely mutate returned objects without corrupting cached data or shared state. Any optimization
> that removes or reduces copying **must** prove that no caller depends on mutation freedom, or
> must substitute an equivalent safety mechanism (e.g., copy-on-write, frozen objects).

---

## Table of Contents

1. [Report Saving & over_time Rendering (Critical Path)](#1-report-saving--over_time-rendering-critical-path)
2. [Benchmark Generation & Execution](#2-benchmark-generation--execution)
3. [Caching](#3-caching)
4. [Viewing & Visualization](#4-viewing--visualization)
5. [Cross-Cutting Concerns](#5-cross-cutting-concerns)
6. [Regression Testing Strategy](#6-regression-testing-strategy)
7. [Implementation Priority](#7-implementation-priority)

---

## 1. Report Saving & over_time Rendering (Critical Path)

> **Context**: Real-world CI benchmarks with `over_time=True` exposed a major performance
> regression introduced in v1.71.0. The v1.72.0 release (PR #814) partially addressed it
> by optimising DataFrame conversions and adding `max_slider_points` /
> `show_aggregated_time_tab` config knobs. However, **report.save() with embed=True remains
> the dominant bottleneck** — not plot construction (`post_setup_ms` < 10ms) but Panel's
> static HTML serialization of HoloMap slider patches.
>
> **Scaling model**: `cost ~ sum(num_result_vars * (1 + has_aggregate_tab) * f(num_time_events))`
> where `f(N)` is Panel's superlinear embed cost per HoloMap slider.
>
> Benchmarks with many result variables (e.g. 7) and `over_time=True` see `report.save()`
> become the largest non-execution cost, dwarfing all other phases combined.

### 1.1 Default `show_aggregated_time_tab` to `False`

**File**: `bencher/bench_cfg.py:246-251`

**Problem**: `show_aggregated_time_tab` defaults to `True`, meaning every `over_time` report
generates **two** Panel tabs per result variable: a "Per Time Point" slider tab and an
"All Time Points (aggregated)" tab. When saved with `embed=True`, Panel must pre-compute
JSON patches for every slider position in *both* tabs. This doubles the embed cost compared
to pre-v1.71.0 behaviour (which had only one tab).

The aggregated tab is useful for analysis but is the entire source of the 2x regression
relative to v1.70.4. Most CI pipelines care about the per-time-point slider — they can
opt into aggregation when they need it.

**Proposed fix**: Change the default to `False`:

```python
show_aggregated_time_tab: bool = param.Boolean(
    False,
    doc="When over_time is active, show an 'All Time Points (aggregated)' tab "
    "alongside the per-time-point slider. Set True to enable aggregation "
    "view (adds rendering cost during report.save).",
)
```

**Correctness risk**: NONE. This is a default change, not a behavioural change. All existing
code that explicitly sets `show_aggregated_time_tab=True` is unaffected.

**Regression test**: Existing `test_over_time_repeats.py` covers over_time rendering. Verify
both `True` and `False` produce valid HTML. Add a test asserting the default is `False`.

---

### 1.2 Add `report_save_ms` to SweepTimings

**File**: `bencher/sweep_timings.py`, `bencher/bencher.py` (where `report.save()` is called)

**Problem**: `SweepTimings` tracks compute phases (`cache_check`, `dataset_setup`,
`job_execution`, `history_merge`, `post_setup`, `render`) but NOT `report.save()`. In
production benchmarks with `over_time=True`, `report.save()` is the second-largest cost
after `job_execution`, yet there's no timing data for it.

**Proposed fix**: Add `report_save_ms` to `SweepTimings`. Wrap the `report.save()` call
site with `phase_timer()` and record the result.

Additionally, consider breaking down the report save into sub-phases:
- Number of tabs/panes serialized
- Per-tab embed time
- Total HTML write time

This could be a separate `ReportTimings` dataclass or additional fields on `SweepTimings`.

**Correctness risk**: NONE. This is pure instrumentation — no behavioural change.

**Regression test**: Verify `SweepTimings.summary()` includes the new field. Verify
`compute_total()` sums it correctly.

---

### 1.3 Cap embedded slider positions in report.save()

**File**: `bencher/results/holoview_results/holoview_result.py:279-318`

**Problem**: `max_slider_points` (added in v1.72.0) already subsamples which time points
are included in the HoloMap, reducing the number of JSON patches Panel must compute.
However, the default is `None` (no subsampling), so users who don't know about this option
still pay the full O(N) embed cost for all time events.

**Proposed fix**: Set a sensible default for `max_slider_points` — e.g., `20` — so that
users with long histories don't accidentally generate multi-minute `report.save()` calls.
The aggregated tab already uses all data regardless of this setting.

```python
max_slider_points: int | None = param.Integer(
    20,
    bounds=[2, None],
    allow_None=True,
    doc="Maximum number of time points shown in the over_time slider. "
    "Evenly subsampled (first and last always included). "
    "The aggregated tab still uses all data. None means no subsampling.",
)
```

Users who want all slider positions can set `max_slider_points=None`.

**Correctness risk**: LOW. The subsample logic (`subsample_indices`) already exists and
is tested. This just changes the default. First and last time points are always included.

**Regression test**: Verify that with 50 time events and `max_slider_points=20`, the
HoloMap has exactly 20 entries. Verify first and last time points are present.

---

### 1.4 Use `embed_json` to offload slider patches to separate files

**File**: `bencher/bench_report.py:119,136`

**Problem**: `report.save(embed=True)` inlines all HoloMap JSON patches directly into the
HTML file. For reports with many slider positions and result variables, this produces
multi-megabyte HTML files and the serialization itself is slow (Panel must compute diffs
and encode them inline).

**Proposed fix**: Use Panel's `embed_json=True` with `embed_json_prefix` to write JSON
patches as separate files alongside the HTML:

```python
content.save(
    filename=index_path,
    progress=True,
    embed=True,
    embed_json=True,
    embed_json_prefix=str(base_path / "_json"),
    **kwargs,
)
```

This splits the serialization cost: HTML is written quickly, JSON patches are written to
separate files. The browser loads patches on demand when the user interacts with sliders.

**Correctness risk**: MEDIUM. Must verify:
1. Panel correctly resolves the JSON prefix path in the saved HTML
2. The `_tabs/` iframe approach still works with external JSON files
3. GitHub Pages / static hosting can serve the JSON files with correct MIME types
4. Existing tests that check `report.save()` output pass with the new structure

**Regression test**: Save a report with `embed_json=True`, open in browser, verify all
slider positions are accessible. Compare rendering output to the inline-embed approach.

---

### 1.5 Profile and optimize Panel embed serialization hotspots

**File**: `bencher/bench_report.py:80-142`

**Problem**: `pn.Column(tab).save(embed=True)` is called per tab, and each call triggers
Panel's full embed pipeline: state enumeration, plot rendering for each widget state, JSON
diff computation, and HTML assembly. The cost scales as
`O(num_widget_states × rendering_cost_per_state)`.

Evidence from production benchmarks:
- `render_ms` (plot object construction) < 10ms
- `report.save()` for 7 result vars × 1 time event = **16.8s**
- `report.save()` with `over_time=False` for same benchmark = **0.3s** (56× faster)

The bottleneck is Panel's embed pipeline, not HoloViews plot construction.

**Proposed fix**: Profile `report.save()` with `cProfile` or `py-spy` to identify exactly
where time is spent:
1. Is it in Bokeh rendering (converting HoloViews → Bokeh models)?
2. Is it in JSON diff computation (comparing base state to each slider state)?
3. Is it in HTML string assembly / writing?

Based on profiling results, potential fixes:
- **Pre-render Bokeh models once** and reuse across slider positions where possible
- **Parallelise per-tab saves** — each tab's `pn.Column(tab).save()` is independent
- **Use Panel's `save(embed=False)` for over_time reports** and provide a Panel serve
  fallback for interactive use

**Correctness risk**: Varies by approach. Profiling itself has zero risk.

**Regression test**: Benchmark `report.save()` duration with a fixed dataset and assert it
stays within acceptable bounds.

---

### 1.6 Skip Spread bands on per-time-point curve renders

**File**: `bencher/results/holoview_results/holoview_result.py:196-245`

**Problem**: `_build_curve_overlay()` renders `hv.Spread` bands whenever a `_std` variable
exists in the dataset. For the aggregated tab, Spread bands are meaningful (they show
cross-time-point variance). But for per-time-point renders (each slider position), the `_std`
comes from within-repeat variance and the Spread adds rendering overhead without much value
since each time point has its own exact data.

**Proposed fix**: Have `_build_time_holomap()` pass a flag to `make_plot_fn` indicating
whether the render is for a per-time-point slice or the aggregated view. Skip Spread bands
on per-time-point slices. Alternatively, strip the `_std` variable from the dataset before
passing to `make_plot_fn` for per-time-point renders.

**Correctness risk**: LOW. The per-time-point plots are still correct without Spread bands.
The aggregated tab retains them.

**Regression test**: Visual regression test — verify per-time-point plots render correctly
without Spread. Verify aggregated tab still has Spread bands.

---

## 2. Benchmark Generation & Execution

### 2.1 Eliminate redundant deep copies in `plot_sweep()`

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

### 2.2 Eliminate double deep copy in `BenchRunner.run()`

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

### 2.3 Avoid materializing full Cartesian product into a list

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

### 2.4 Deduplicate Cartesian product calls for reversed sample order

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

### 2.5 Deep copy kwargs only when necessary in `worker_kwargs_wrapper()`

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

### 2.6 Use direct numpy indexing in `set_xarray_multidim()`

**File**: `bencher/result_collector.py:45-62`

**Problem**: `data_array[index_tuple] = value` uses xarray's full fancy-indexing pipeline
(Variable.isel, _broadcast_indexes, etc.) for every single scalar write. Profiling a 500-job
sweep (all cache hits) shows `set_xarray_multidim` accounts for **346ms out of 601ms total**
(58% of runtime). Each write costs ~0.19ms due to xarray overhead.

Scaling is linear: 2000 jobs → ~115ms xarray overhead; 5000 jobs → ~301ms.

**Proposed fix**: Access the underlying numpy array directly:

```python
def set_xarray_multidim(
    data_array: xr.DataArray, index_tuple: tuple[int, ...], value: Any
) -> xr.DataArray:
    data_array.values[index_tuple] = value
    return data_array
```

`data_array.values` returns the backing numpy ndarray. Integer-tuple indexing into it is a
direct memory write with no xarray overhead. Benchmarked at **0.001ms/write** — a **159× speedup**
over the xarray path.

**Correctness risk**: LOW. The index tuples are always plain integer tuples generated by the
Cartesian product iterator. `data_array.values[idx]` and `data_array[idx]` produce identical
results for integer index tuples. All result types stored via this path (ResultFloat, ResultBool,
ResultString, ResultImage, ResultVideo, ResultContainer, ResultPath, ResultRerun) are compatible
since xarray stores non-numeric types in object-dtype numpy arrays.

**Regression test**: Existing `test_bencher.py`, `test_bench_runner.py`, and all result-type tests.
Add a targeted test comparing `data_array[idx] = v` vs `data_array.values[idx] = v` for each
result type.

---

### 2.7 Cache `get_input_and_results()` per class

**File**: `bencher/variables/parametrised_sweep.py:59-83`, `bencher/utils.py:34-43`

**Problem**: `get_input_and_results()` is a classmethod called from `get_results_values_as_dict()`
which is invoked **once per job**. Each call:
1. Iterates `cls.param.objects()` to classify params as inputs vs results
2. Creates a **new namedtuple class** via `collections.namedtuple()` (0.058ms each — class
   creation involves `exec()`)
3. Instantiates and returns the namedtuple

For 500 jobs, this costs **~62ms total** (35ms for `get_input_and_results` + 27ms for
`param.values()` overhead in `get_results_values_as_dict`).

**Proposed fix**: Two changes:

1. **Pre-define the `inputresult` namedtuple class** as a module-level constant:
   ```python
   _InputResult = namedtuple("inputresult", ["inputs", "results"])
   ```

2. **Cache `get_input_and_results()` per class** using `functools.lru_cache` or a class-level
   dict cache. Param definitions are fixed after class creation, so the result never changes.

Combined savings: ~62ms per 500-job sweep.

**Correctness risk**: LOW. Param objects are defined at class creation time and do not change.
The cache must be keyed by class identity (not instance) to handle different ParametrizedSweep
subclasses correctly.

**Regression test**: Existing `test_bencher.py`. Add a test verifying that `get_input_and_results()`
returns identical results on repeated calls and across different instances of the same class.

---

### 2.8 Parallel result streaming for non-serial executors

> *Previously numbered 2.6.*

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

## 3. Caching

### 3.1 Avoid redundant cache opens

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

### 3.2 Use `diskcache.FanoutCache` for parallel workloads

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

### 3.3 Batch cache lookups

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

### 3.4 Reduce hash computation overhead

**File**: `bencher/utils.py:94-107`, `bencher/worker_job.py:48-69`

**Problem**: Each job computes two SHA1 hashes: `function_input_signature_pure` and
`function_input_signature_benchmark_context`. The context hash was never read anywhere in the
codebase (dead code). The pure hash is always computed even when not needed (only used when
`only_hash_tag` is False).

**Status**: `function_input_signature_benchmark_context` removed in PR #816 (dead code). Remaining
opportunity: lazily compute `function_input_signature_pure` only when `only_hash_tag` is False,
using `@property` with caching (`functools.cached_property`).

**Correctness risk**: LOW. Hash values are read-only after construction. Lazy evaluation produces
identical results.

**Regression test**: `test_hash_persistent.py` — all existing determinism tests must pass.
`test_sample_cache.py` — verify cache key collisions don't change.

---

### 3.5 Remove non-pickleable objects before caching more efficiently

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

## 4. Viewing & Visualization

### 4.1 Avoid unnecessary dataset copies in `to_dataset()`

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

### 4.2 Lazy HoloMap construction for over_time plots

**File**: `bencher/results/holoview_results/holoview_result.py:279-318`

**Problem**: For over_time benchmarks, `_build_time_holomap()` eagerly creates a separate plot
for *every* time point and assembles them into a `HoloMap`. For many time points, this is slow
and memory-intensive. More importantly, Panel's `embed=True` mode must then pre-compute JSON
patches for every slider position.

**Proposed fix**: Use `hv.DynamicMap` instead of `hv.HoloMap`. DynamicMap generates plots on
demand (when the user selects a time point in the widget).

**Correctness risk**: LOW-MEDIUM. DynamicMap requires a callable that returns a plot for a given
key. The current loop body can be extracted into such a callable. However, **DynamicMap does not
work with Panel's `embed=True` mode** — it requires a live Panel server for interactivity. This
means it cannot be used for `report.save()` static HTML output.

This fix is therefore only applicable when reports are served live via `report.show()` /
`pn.serve()`. For static HTML, the `max_slider_points` subsampling (item 1.3) is the
correct approach.

**Regression test**: Visual regression test — generate plots with both HoloMap and DynamicMap for
a known dataset. Verify data values are identical. Test both interactive (Panel serve) and static
(HTML export) contexts.

---

### 4.3 Avoid redundant `to_dataframe()` conversions

**File**: `bencher/results/holoview_results/distribution_result/distribution_result.py:120`,
`bencher/results/volume_result.py:85`,
`bencher/results/holoview_results/holoview_result.py:234` (groupby path in `_build_curve_overlay`)

**Problem**: Several plot types convert xarray datasets to pandas DataFrames using
`.to_dataframe().reset_index()`. This creates a full copy of the data in a different format.
Some plots then subset the DataFrame, wasting most of the conversion work.  The curve overlay
groupby path was the worst offender: it ran `to_dataframe()` + `df.groupby()` for **every
slider position** when categorical dimensions were present.

**Proposed fix**: Where possible, select/filter the xarray data *before* converting to DataFrame.
For plots that accept xarray directly (via hvplot.xarray), skip the DataFrame conversion entirely.
For the curve overlay groupby path, replace `to_dataframe().groupby()` with `xarray.sel()` +
`itertools.product` — `dataset.sel()` returns an xarray view (no copy, no format conversion).

**Correctness risk**: LOW. The data content is identical; only the container format changes.

**Regression test**: Compare plot data values before and after the change using `hv.render()` to
extract the underlying data from the generated plot objects.  Unit tests in
`test_curve_overlay_groupby.py` validate that the xarray sel path produces identical Curve labels,
Spread elements, and data point counts as the original DataFrame path.

---

### 4.4 Reduce xr.merge() overhead in reduction pipeline

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

### 4.5 Cache reduced datasets

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

## 5. Cross-Cutting Concerns

### 5.1 Profile before optimizing

Before implementing any of the above changes, establish a performance baseline:

1. **Create a benchmark suite** with representative workloads:
   - Small sweep: 2 dims × 5 values = 25 jobs
   - Medium sweep: 4 dims × 10 values = 10,000 jobs
   - Large sweep with over_time: 2 dims × 10 values × 15 time events × 7 result vars
   - Large sweep: 5 dims × 20 values = 3,200,000 jobs (cache-only, skip execution)
2. **Measure**: wall time, peak memory, cache hit rate, plot render time, **report.save() time**
3. **Profile**: Use `cProfile` or `py-spy` to identify actual hotspots — especially in
   `report.save()` → Panel embed pipeline
4. **Track**: Store baseline metrics to compare against after each optimization

**Status**: **DONE** — profiling completed 2026-04-03 (execution path) and 2026-03-23
(`report.save()` path in SAVE_PERFORMANCE_REPORT.md).

#### Current baseline (2026-04-03, post-optimization)

All measurements taken on Linux, Python 3.13, `auto_plot=False`.

| Workload | Total | Top phase | Notes |
|----------|-------|-----------|-------|
| Small (5×5 = 25 jobs, cold) | 47ms | job_execution 10ms | cache_check 18ms (first open) |
| Medium (10×10×5 = 500 jobs, cold) | 246ms | job_execution 224ms | dataset_setup 2ms |
| Medium (500 jobs, cache hits) | 244ms | job_execution 222ms | Execution still dominates even on cache hits |
| Repeat (5×3 = 15 jobs) | 17ms | job_execution 5ms | |
| Large reversed (20×20×5 = 2000) | 1085ms | job_execution ~1000ms | dataset_setup 7.3ms (vs 2.8ms sequential) |

**cProfile hotspots (500 jobs, all cache hits, pre-2.6/2.7)**:

| Function | Calls | cumtime | tottime | % of total |
|----------|-------|---------|---------|------------|
| `store_results` (→ `set_xarray_multidim`) | 500 | 386ms | 1ms | 64% |
| xarray `DataArray.__setitem__` | 500 | 346ms | 3ms | 58% |
| xarray `Variable.isel` | 2500 | 200ms | 11ms | 33% |
| `job.submit` (→ `worker_kwargs_wrapper`) | 500 | 168ms | 3ms | 28% |
| `get_results_values_as_dict` | 500 | 142ms | 2ms | 24% |
| `make_namedtuple` (class creation) | 501 | 58ms | 3ms | 10% |

**Key insight**: After all previous optimizations, the dominant bottleneck on the execution
path is **xarray's fancy-indexing overhead** in `set_xarray_multidim` (58% of runtime).
Bypassing xarray with `data_array.values[idx] = value` is 159× faster per write (see item 2.6).

#### Updated baseline (2026-04-03, post items 2.6, 2.7, 2.9, 2.10)

| Workload | Total | Top phase | Notes |
|----------|-------|-----------|-------|
| Medium (500 jobs, cache hits) | ~103ms | cache_check 35ms | 36% faster vs 159ms pre-2.9/2.10; 58% faster vs 244ms pre-2.6/2.7 |

**cProfile hotspots (500 jobs, all cache hits, post-2.9/2.10)**:

| Function | Calls | cumtime | tottime | % of total |
|----------|-------|---------|---------|------------|
| `prefetch` (→ diskcache `get`) | 500 | 30ms | 1ms | 29% |
| SQLite `execute` | 666 | 19ms | 19ms | 19% |
| `store_results` | 500 | 16ms | 9ms | 16% |
| `setup_hashes` (→ `hash_sha1`) | 500 | 14ms | 3ms | 14% |
| `pickle.load` (cache deser.) | 500 | 8ms | 8ms | 8% |

**Key insight**: After hoisting shared allocations (2.9) and pre-caching numpy arrays (2.10),
`store_results` dropped from 57ms to 16ms (72% reduction) and `job_submission` from 26ms
to 19ms. The remaining dominant cost is SQLite I/O in `prefetch` (29% of runtime) and
`pickle.load` deserialization (8%), which are inherent to the cache layer.

**`to_dataset()` micro-benchmarks**:

| Mode | uncached (ms/call) | cached deep=True (ms/call) | cached deep=False (ms/call) |
|------|-------------------|---------------------------|----------------------------|
| REDUCE | 0.78 | 0.065 | 0.002 |
| SQUEEZE | 0.19 | — | — |
| NONE | 0.14 | — | — |

### 5.2 Add performance regression tests

Add a `test_performance.py` that runs representative sweeps and asserts:
- Execution time stays within 2× of baseline (to catch algorithmic regressions)
- Memory usage stays within 1.5× of baseline
- Cache hit rates remain identical for identical inputs
- **report.save() time with over_time stays within 2× of baseline** (to catch embed regressions)

### 5.3 Document the deep-copy contract

Add a section to `CLAUDE.md` or a `CONTRIBUTING.md` explaining:
- Why deep copies exist (mutation safety for cached data)
- When it's safe to remove them (pure functions, read-only access)
- How to test for correctness (mutation tests, cache integrity checks)

---

## 6. Regression Testing Strategy

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
7. **over_time report.save() timing** (new): For a benchmark with N result vars and M time events,
   assert `report.save()` completes within a time budget. Track this in CI via `SweepTimings`.

---

## 7. Implementation Priority

| Priority | Item | Effort | Risk | Impact | Status |
|----------|------|--------|------|--------|--------|
| **P0** | 1.1 Default `show_aggregated_time_tab` to `False` | Trivial | None | **High** — eliminates 2× regression vs v1.70.4 for all `over_time` users | **DONE** (v1.72.1) |
| **P0** | 1.2 Add `report_save_ms` to SweepTimings | Low | None | **High** — enables visibility into the dominant bottleneck | **DONE** (PR #787, v1.72.1) |
| **P0** | 1.3 Default `max_slider_points` to 20 | Trivial | Low | **High** — prevents superlinear embed cost for long histories | **DONE** (v1.72.1, default=10) |
| **P1** | 2.6 Direct numpy indexing in `set_xarray_multidim()` | Trivial | Low | **High** — measured 159× speedup per write; saves ~346ms/500 jobs (58% of runtime on cache-hit sweeps) | **DONE** (PR #885) |
| **P1** | 2.7 Cache `get_input_and_results()` per class | Low | Low | **Moderate** — measured 130× speedup for namedtuple reuse; saves ~62ms/500 jobs | **DONE** (PR #885) |
| **P1** | 1.7 Disable HoloViews pipeline tracking during save | Trivial | Low | Predicted **High** — profiling showed 3.3s cumtime for 4998 `pipelined_fn` calls | **REJECTED** — benchmarked; `pipelined_fn` tottime is only 28ms (overhead is in child calls, not the wrapper). `disable_pipeline()` measured same-or-slower than baseline. |
| **P1** | 1.8 Pre-compute and freeze plot ranges | Low | Medium | Predicted **Moderate** — profiling showed 3.4s cumtime for 162 `compute_ranges` calls | **REJECTED** — `compute_ranges` tottime is only 2.5ms; the 3.4s cumtime is dominated by child data operations, not range computation itself. |
| **P1** | 1.5 Profile Panel embed hotspots | Medium | None | **Critical** — informs all other report.save() optimizations | **DONE** — profiled in SAVE_PERFORMANCE_REPORT.md. Key finding: the bottleneck is Panel's per-state re-rendering (`plot.update`: 60 calls, 6.6s cumtime), not any single wrapping layer. `pipelined_fn` and `compute_ranges` have low tottime (~30ms combined); their high cumtimes reflect the underlying render cost, not addressable overhead. |
| **P1** | 1.4 Use `embed_json` for external patch files | Medium | Medium | **High** — reduces HTML size and may improve serialization speed | **REJECTED** — benchmarked at 1.6x slower than baseline (6.68s vs 4.15s); computation not skipped, adds I/O |
| **P1** | 1.6 Skip Spread on per-time-point renders | Low | Low | **Moderate** — reduces per-slider-position render cost | **Won't do** — Spread bands on per-time-point renders provide useful information |
| **P1** | 2.1 Deduplicate `plot_sweep()` copies | Low | Low | Moderate | **DONE** (single-copy pattern in place) |
| **P1** | 2.5 Filter-then-copy kwargs | Low | Low | High for large sweeps | **DONE** (PR #816) |
| **P1** | 4.1 Avoid dataset copy in `to_dataset()` | Medium | High | High | **DONE** — skip copy for REDUCE/MINMAX (reductions create new arrays); deep copy only for SQUEEZE/NONE |
| **P2** | 2.2 Single copy in `BenchRunner.run()` | Medium | Medium | Moderate | **DONE** — eliminated redundant entry-level deepcopy; per-iteration copy retained (needed for isolation) |
| **P2** | 2.3 Lazy Cartesian product | Low | Low-Med | High for large sweeps | **DONE** (PR #811) |
| **P2** | 3.1 Reuse cache instances | Low | Low | Moderate | **DONE** (PR #813) |
| **P2** | 3.4 Lazy hash computation | Low | Low | Low-Moderate | **DONE** (PR #816 — removed dead `function_input_signature_benchmark_context` hash; remaining `@cached_property` refactor has no impact since hash is always accessed) |
| **P2** | 4.4 Single-pass reduction | Medium | Medium | Moderate | **DONE** |
| **P2** | 4.5 Memoize `to_dataset()` | Medium | Low-Med | High for many plots | **DONE** |
| **P2** | 2.9 Hoist shared allocations out of per-job loop | Trivial | None | **Moderate** — saves ~7ms/500 jobs (hoists `partial()`, pre-computes title/tag) | **DONE** |
| **P2** | 2.10 Pre-cache numpy arrays for `store_results()` | Trivial | None | **High** — saves ~41ms/500 jobs (bypasses 500× xarray `Dataset.__getitem__`) | **DONE** |
| **P3** | 2.4 Deduplicate reversed product | Low | Low | Low — measured only 4.5ms overhead at 2000 jobs | |
| **P3** | 2.8 Streaming parallel results | Medium | Medium | High for parallel | Deprioritized — parallel execution rarely used |
| **P3** | 3.2 FanoutCache for parallel | Low | Low | Moderate for parallel | Deprioritized — parallel execution rarely used |
| **P3** | 3.3 Batch cache lookups | High | Medium | High for large sweeps | **DONE** — replaced double-query (`key in cache` + `cache[key]`) with single `cache.get()`, added `prefetch()` batch phase before submission loop |
| **P3** | 3.5 `__getstate__` for results | Medium | Medium | Low | |
| **P3** | 4.2 DynamicMap for over_time (live serve only) | Medium | Low-Med | Moderate (only for live server, not static HTML) | **REJECTED** — requires a live Panel server; not viable for static HTML reports (the only supported output mode) |
| **P3** | 4.3 Pre-filter before to_dataframe | Low | Low | Low | DONE (PR #814 — fast path; PR #822 — curve groupby path uses xarray sel) |
