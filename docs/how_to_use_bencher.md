# Getting Started

A practical quick-start reference — install bencher, write your first benchmark, and
learn the core patterns. For a tour of all features (repeats, over-time tracking,
optimization), see the [Feature Guide](intro.md).

Install: `pip install holobench`

## Quick Start

```python
import bencher as bn

class MyBenchmark(bn.ParametrizedSweep):
    # Inputs — bencher sweeps the Cartesian product of these
    size = bn.IntSweep(default=10, bounds=(10, 1000), doc="Problem size")
    method = bn.StringSweep(["brute", "optimized"], doc="Algorithm")

    # Results — what the benchmark measures
    elapsed = bn.ResultFloat(units="s")

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

Notice the three stages in the code above:

1. **Problem Definition** — the `MyBenchmark` class declares inputs, results, and the
   `benchmark()` method
2. **Sweep Definition** — `plot_sweep()` selects which parameters to vary and which
   results to collect
3. **Run Definition** — `bn.run()` sets sampling density (`subsampling_divisions`), `repeats`, and
   output options

Every bencher example follows this pattern. See
[Architecture Overview](concepts.md#architecture-overview) for a diagram and deeper
explanation.

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
(e.g., number of retries, repeat count, number of threads). See the
[Sampling Strategies gallery](reference/meta/sampling/index) for examples of how different
sweep types produce different sample distributions.

## The Subsampling Divisions System

Instead of specifying `samples` on each sweep variable, you can use the `subsampling_divisions`
parameter to control sampling density globally with a single knob:

| Subsampling Divisions | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| Samples per dimension | 1 | 2 | 3 | 5 | 9 | 17 | 33 |

Higher subsampling_divisions values reuse all lower samples (binary subdivision), so cached results
carry over automatically. Start low for quick iteration, increase for publication
quality:

```python
# Quick check — 2 samples per dimension
bn.run(example_benchmark, subsampling_divisions=2)

# Publication quality — 9 samples per dimension
bn.run(example_benchmark, subsampling_divisions=5)
```

See [Concepts: The Subsampling Divisions System](concepts.md#the-subsampling-divisions-system) for the full formula
and theory, and the [Subsampling Divisions System gallery](reference/meta/levels/index) for an interactive
demo.

## Result Types

| Type | Use for | Set to |
|---|---|---|
| `bn.ResultFloat(units="s")` | Continuous scalar metrics (time, distance, score) | `self.elapsed = 0.42` |
| `bn.ResultBool()` | Success/failure, pass/fail, any binary outcome | `self.success = True` |
| `bn.ResultString()` | Text outputs, labels, error messages | `self.error_msg = "timeout"` |
| `bn.ResultImage()` | Images, GIFs | `self.img = "/path/to/output.png"` |
| `bn.ResultVideo()` | Videos | `self.vid = video_writer.write()` |
| `bn.ResultPath()` | Downloadable file outputs | `self.artifact = "/path/to/file"` |
| `bn.ResultContainer()` | Embeddable HTML/panel content | `self.widget = pane` |
| `bn.ResultRerun()` | Rerun recording or composition | `self.scene = path_or_compositor` |
| `bn.ResultVec(size=3)` | Fixed-size vector results (x, y, z) | `self.position = [1.0, 2.0, 3.0]` |
| `bn.ResultDataSet()` | Any picklable data payload per sample | `self.data = bn.ResultDataSet(payload)` |

**Choosing between ResultFloat and ResultBool:** If a result is binary (success/failure,
reachable/unreachable, pass/fail), always use `ResultBool` — it locks bounds to [0, 1]
and produces correct boolean-style plots. Only use `ResultFloat` for continuous metrics.
See the [Result Types gallery](reference/meta/result_types/index) for examples of each type.

**Deprecated:** `bn.ResultHmap` is deprecated (it stores its data outside the result
dataset) — use `bn.ResultContainer` or `bn.ResultReference` with a declared
`container=` instead.

**Rendering stored data:** `ResultDataSet` stores the payload without interpreting
its type. Without a renderer, Panel displays the raw object. Pass `container=` a
callable taking the stored object and returning anything Panel can display, and every
sample renders through it, in `result_vars` order alongside the other results:

```python
def render_measurement(payload):       # -> a HoloViews / Panel object
    return build_view(payload)

class MySweep(bn.ParametrizedSweep):
    measurement = bn.ResultDataSet(container=render_measurement)

    def benchmark(self):
        self.measurement = bn.ResultDataSet(measure())
```

The payload can be a DataFrame, xarray object, mapping, sequence, custom dataclass,
or another picklable Python object. Use `ResultReference` for data that cannot be
pickled. A per-sample `container=` also works. An explicit renderer passed through
`bench.add(bn.DataSetResult, container=...)` overrides the declared renderer and
appends that view to the report.

A declared container is part of the benchmark config, which the result cache and the
collect/render split both pickle, so it must be picklable: a module-level function (as
above) or a callable object, not a lambda or a local function. Because a renderer is not
data, declaring one leaves every cache key and `over_time` history series untouched.

**Which result types accept one:** `ResultDataSet`, `ResultReference`, `ResultString`,
`ResultPath`, `ResultContainer` and `ResultRerun`. The callback always receives the
stored value alone, so one renderer works across all of them, and it beats whatever the
type would render by default:

```python
def path_contents(path):               # a CSV as a chart, not a download button
    return plot(pd.read_csv(path))

class MySweep(bn.ParametrizedSweep):
    report = bn.ResultPath(container=path_contents)
    summary = bn.ResultString(container=pn.pane.Markdown)     # markdown, not plain text
```

When both a class-level and a per-sample container are present, the sample's wins.

**Built-in intra-sample charts:** tabular interpretation belongs to these renderers, not
to `ResultDataSet`. For the common cases of that container bencher builds one for you, so
no plotting code is needed. Each accepts a DataFrame, xarray Dataset/DataArray, or
HoloViews Dataset, and plots *inside* one sample — the axes are columns the benchmark
measured, and the sweep dimensions separate one plot from the next.

| Builder | Draws | Use for |
|---|---|---|
| `bn.xy_scatter(x=, y=)` | an unordered cloud of points | landing points, hit locations, a phase-space cloud |
| `bn.xy_curve(x=, y=)` | a connected series | a signal collected over time, a convergence trace |
| `bn.xy_histogram(column=)` | a binned distribution | every request timed, not just the mean |
| `bn.xy_hexbin(x=, y=)` | hex-binned density | the same cloud when there are too many points to read as markers |

```python
cloud = bn.ResultDataSet(
    container=bn.xy_scatter(x="dx_mm", y="dy_mm", color="touch", data_aspect=1)
)
trace = bn.ResultDataSet(
    container=bn.xy_curve(x="time_s", y=["measured_mm", "commanded_mm"])
)
latencies = bn.ResultDataSet(container=bn.xy_histogram("latency_ms", bins=40))
```

Do not reach for `scatter`, `curve`, `line` or `histogram` for this: those plot *across*
the sweep, with one value per sample, so an input variable is their x axis and what a
`histogram` shows is the spread of the repeats. These take their axes from within a
single sample.

Pick between `xy_scatter` and `xy_hexbin` by point count: markers show individual
outliers and stop working once they saturate, which is the point at which where the mass
actually sits becomes the thing you cannot see. A few hundred points scatter fine; tens
of thousands want hexbin.

What each builder returns is a picklable spec object, so it satisfies the constraint
above. Columns are validated — a typo triggers a message listing the available columns
instead of rendering nothing — and x/y are inferred from the numeric columns when the
frame holds only the pair being plotted. A frame built with `Dataset.to_pandas()`
keeps its dimension coordinate in the *index* rather than a column; a named index is
promoted, so `x="time"` works on one.

Notable options:

- `xy_scatter(data_aspect=1)` and `xy_hexbin(data_aspect=1)` force equal x/y scaling,
  which a cloud of positions wants — an auto-scaled aspect makes an elongated cloud look
  round.
- `xy_curve(y=[...])` overlays several series with a legend, `markers=True` adds a marker
  per row so a sparse series is visible, and `sort=False` keeps the frame's row order for
  a trajectory that doubles back in x rather than sorting it into a function of x.
- `xy_histogram(column=[...])` overlays several distributions, binned over a shared range
  so they are comparable; `density=True` normalises instead of counting.
- `xy_hexbin(gridsize=)` sets how many hexagons span the x axis, and `min_count=1` drops
  empty tiles rather than drawing them at zero.

Anything else holoviews accepts (`alpha`, `line_width`, `color`, ...) passes straight
through.

A declared container is the preferred route: the chart takes the raw table's place in the
normal result position, so the report shows the plot and not the rows behind it. Each is
*also* available as a chart type for a report-level plot, which is *appended* to whatever
`plot_sweep` already rendered (so declare the container as well if the table below it is
not wanted) — `bench.add(bn.XYScatterResult, x="dx_mm", y="dy_mm")`,
`bench.add(bn.XYCurveResult, x="time_s", y="measured_mm")`,
`bench.add(bn.XYHistogramResult, column="latency_ms")`,
`bench.add(bn.XYHexbinResult, x="dx_mm", y="dy_mm")` — or by name via
`to_auto(plot_list=["xy_scatter"], x=..., y=...)`. None of them are ever selected
automatically, so no existing report gains a plot it did not ask for.

Under `over_time`, a `ResultDataSet` renders its full history: each cell stores a
blob-store path, so every time point's payload stays loadable and the report shows a
labelled per-time grid — one pane per snapshot under its timestamp. Cells cached before
the blob store existed (legacy index cells) render where their payload list is still
available and as a labelled placeholder where it is not. See the
[ResultDataSet over time example](reference/meta/result_types/result_dataset/example_result_dataset_1d_over_time)
for a working sweep.

Those payloads accumulate in `cachedir/blobs/`, one file per distinct payload, and aging an
event out with `max_time_events` leaves its file behind. `bn.clean_orphaned_blobs()` reports
the blobs no stored result or history event references any more (`dry_run=False` reclaims
them; `pixi run cache-blob-orphans` / `cache-blob-gc` from a checkout). Results written with
`bn.save_result` live at paths bencher does not record, so pass them as
`extra_roots=[...]` to keep their payloads protected.

For images: use `bn.gen_image_path("name")` to generate unique paths.
For videos: use `bn.VideoWriter()` to collect frames and `.write()` to save.
See the [ResultImage gallery](reference/meta/result_types/result_image/index) and
[ResultVideo gallery](reference/meta/result_types/result_video/index) for working examples.

For Rerun recordings, assign the path returned by `bn.capture_rerun_rrd()` to a
`bn.ResultRerun`. To combine complete recordings, assign a
`bn.ComposableContainerRerun` directly; Bencher materializes it into one namespaced
recording and native Rerun Blueprint before caching:

```python
combined = bn.ComposableContainerRerun(compose_method=bn.ComposeType.right)
combined.append(reference_rrd, label="Reference")
combined.append(candidate_rrd, label="Candidate")
self.scene = combined
```

The four composition methods map to horizontal views (`right`), vertical views
(`down`), one shared view showing every recording at its original times
(`overlay`), and one shared view whose timelines are spliced end to end so the
recordings play one after the other (`sequence`). `sequence` needs recordings with
data on a timeline — it offsets each recording's index values to start where the
previous one ended, and clears each recording as the next begins.
View types are inferred from recorded archetypes; pass `view_kinds=` to `append()`
to override inference. See the
[Rerun Integration gallery](reference/meta/rerun/index) for complete examples.

That composition happens *inside* `benchmark()`, so it can only combine recordings
made by a single sample. To combine the recordings of a whole **sweep**, use the
`rerun_summary` or `rerun_grid` plot callbacks instead. Each sample still caches its
own `.rrd`, but the renderer merges them all into one recording, so a sweep shows a
single viewer rather than one embedded viewer per sample:

```python
bench.plot_sweep(
    input_vars=["damping", "omega_n"],
    result_vars=["out_rerun"],
    plot_callbacks=[bn.BenchResult.to_rerun_summary],
)
```

`to_rerun_summary()` puts every dimension on one timeline so the samples can be
scrubbed together; `to_rerun_grid()` lays the dimensions out in space instead and
takes `compose_method_list=` for explicit per-dimension control. Both are named-only
plot types — like `video_summary`, they are opt-in because merging every recording is
expensive. This is the `ResultRerun` counterpart to `video_summary` for
`ResultImage`/`ResultVideo`.

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
        bn.sweep("workers", max_subsampling_divisions=3),           # auto-pick up to 3 values
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

See the [Constant Variables gallery](reference/meta/const_vars/index) for examples of
slicing, comparing, and pinning parameters.

## Declare Each Variable Once

Variable lists are **sets keyed by name**. Order matters only for `input_vars`, where it
sets the dimension order of the dataset; reordering `result_vars` or `const_vars` is a
presentation change that does not affect the cache key.

Declaring the same variable twice in one sweep is always a mistake, and bencher now says
so rather than guessing:

| List | A repeated variable |
|---|---|
| `input_vars` | **raises `ValueError`** — each input is one dataset dimension, so a repeat has no valid meaning |
| `result_vars` | dropped, first occurrence kept, with a `UserWarning` |
| `const_vars` | dropped when the values agree; **raises** when they disagree |

This matters most when result variables are assembled by concatenation — a shared group of
core metrics, plus a group from a base class, plus a few specific to one environment. One
overlapping entry is invisible in review, and before this check it silently changed the
benchmark's cache and history key without changing the data, so the run appended to a
different trend line than the one it appeared to belong to. If you see the warning, remove
the duplicate; the key then matches what a correct declaration would have produced.

## Run Configuration

`BenchRunCfg` has many options, but you rarely need more than a few:

| Parameter | Default | What it does |
|---|---|---|
| `subsampling_divisions` | 0 | Sampling density per dimension (see Subsampling Divisions System above) |
| `repeats` | 1 | How many times to evaluate each combination |
| `cache_samples` | False | Cache individual results across runs (resume interrupted sweeps) |
| `cache_results` | False | Cache the entire sweep result (skip re-runs with same inputs) |
| `over_time` | False | Track results across multiple runs for time-series analysis |
| `headless` | False | Skip opening a browser to display results |
| `dry_run` | False | Log the sweep grid summary without executing the benchmark |

All other parameters have sensible defaults. See `BenchRunCfg`'s docstring for the
full reference.

```python
def example_foo(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    run_cfg.cache_results = False   # disable for file-based / non-deterministic results
    bench = bn.Bench("name", MyBenchmark(), run_cfg=run_cfg)
    ...
    return bench

if __name__ == "__main__":
    bn.run(example_foo, subsampling_divisions=4)    # subsampling_divisions controls sweep detail depth
```

## The benchmark() Method

Every benchmark class inherits from `bn.ParametrizedSweep` and implements `benchmark()`:

```python
class MyBench(bn.ParametrizedSweep):
    x = bn.FloatSweep(bounds=(0, 1))
    result = bn.ResultFloat()

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

See the [Workflows gallery](reference/meta/workflows/index) for complete examples showing
this convention in action, including multi-sweep and BenchRunner patterns.

## Aggregating Dimensions

When sweeping many dimensions, the visualizations can become unwieldy. Use the
`aggregate` parameter on `plot_sweep()` to collapse dimensions into summary
statistics (mean, std, etc.):

```python
bench.plot_sweep(
    "Aggregated view",
    input_vars=["x", "y", "method"],
    result_vars=["elapsed"],
    aggregate=True,          # collapse all dimensions except the first
    # aggregate=2,           # collapse the last 2 dimensions
    # aggregate=["method"],  # collapse only the "method" dimension
    agg_fn="mean",           # aggregation function: mean, sum, max, min, median
)
```

- `aggregate=True` — collapse all dimensions except the first into a single
  aggregated statistic
- `aggregate=N` (int) — collapse the last N dimensions
- `aggregate=["var1", "var2"]` — collapse only the named dimensions

See the [Aggregation gallery](reference/meta/aggregation/index) for examples of each mode.

## Machine-Readable Results (Agents & CI)

Bencher already computes per-metric verdicts, optimal values, and regression deltas during
collection. To consume them programmatically — from an agent, a CI gate, or another script —
export them as JSON instead of scraping the HTML report or logs.

```python
import bencher as bn

res = bench.collect(input_vars=[...], result_vars=[...], run_cfg=run_cfg)

# A single run -> result.json
bn.result_to_dict(res)             # dict: schema_version, metrics, regressions, provenance
bn.result_to_json(res, "result.json")

# A/B between two independently collected results -> comparison.json
cmp = bn.compare_results(baseline_res, candidate_res)   # per-metric verdict + summary counts
bn.comparison_to_json(baseline_res, candidate_res, "comparison.json")
```

`compare_results` runs the same regression detector used by the over-time path (a percentage
comparison by default), so each metric's `verdict` is one of `improved` / `regressed` /
`unchanged` using identical direction/threshold semantics. Pass `run_cfg=` to choose a
different `regression_method`.

The same artifacts are available from the CLI on a saved result (see the collect/render split):

```bash
# render HTML and also emit result.json
python -m bencher.render result.pkl out_dir --json result.json

# diff two saved results
python -m bencher.render compare baseline.pkl candidate.pkl --json comparison.json
```

`BenchReport.save(..., emit_json=True)` writes `result.json` next to the HTML for every
contained result (opt-in; default off). All JSON output is strict — non-finite values (e.g. a
zero-baseline percent change) are emitted as `null`.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Manually looping over parameter combinations | Use `plot_sweep(input_vars=[...])` |
| One StringSweep encoding multiple independent toggles | Use separate BoolSweep / IntSweep per toggle |
| Many small plot_sweep calls for different combos | One plot_sweep with all input_vars |
| Building panel/HTML layouts manually | Use bencher's report system |
| Using the old `__call__` pattern with boilerplate | Override `benchmark()` instead |
| Caching file-path results | Set `run_cfg.cache_results = False` |
| Using `ResultFloat` for success/failure booleans | Use `ResultBool()` — bounds are [0, 1], plots render correctly |
