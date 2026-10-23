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

### Subsampling the repeats

`subsampling_divisions` thins the swept variables and never touches `repeat`, because
thinning it would change what the mean and standard deviation are taken over.
`pane_repeat_subsampling_divisions` is its counterpart for the repeats, and it is
display-side only: every repeat is still measured and still counted by the statistics,
but only the resolution you ask for gets a pane.

```python
# Five repeats per cell for the statistics, the first two on screen.
bn.run(example_benchmark, run_cfg=bn.BenchRunCfg(repeats=5, pane_repeat_subsampling_divisions=2))
```

It takes the *leading* repeats rather than spreading the picks across the range, which
is the opposite of what `subsampling_divisions` does to a swept variable. A swept
variable's endpoints mean something, so spanning the extent is the right sample; repeats
are interchangeable draws, so spanning it only ties the report to the last repeat
measured when the leading ones are already cached.

The two resolutions are separate knobs because a report usually wants them to disagree:
a sweep over three planners with five recordings each has fifteen panes, and cutting that
down by dropping a planner asks a different question than the sweep did. Reach for this
whenever the per-sample payload is heavy — recordings, videos, large images — and the page
is slower or larger than the comparison needs.

### Sampling the repeats round-robin

By default every repeat of one point is measured before the next point starts, so each
point's repeats share one stretch of the run. When the benchmark runs long enough for
the machine to drift — thermals, other load, a slow leak — that drift lands on whichever
points ran last and reads as a difference between them.
`sample_order=bn.SampleOrder.ROUND_ROBIN` measures every point once per round, one round
per repeat, so each point's repeats are spread across the whole run:

```python
bench.plot_sweep(input_vars=["theta"], result_vars=["out_sin"],
                 sample_order=bn.SampleOrder.ROUND_ROBIN)
```

Only the order the samples are taken in changes. The dataset, the plots and the cache
keys are the same as `INORDER`.

## Result Types

### Choosing a result type

Start from what your `benchmark()` method actually produces:

| You return... | Use | Example in gallery |
|---|---|---|
| a single number | `ResultFloat` | [Result Var: 1D input](reference/meta/result_types/result_var/example_result_var_1d) |
| success/failure | `ResultBool` | [Result Bool: 1D input](reference/meta/result_types/result_bool/example_result_bool_1d) |
| a fixed-size vector | `ResultVec` | [Result Vec: 1D input](reference/meta/result_types/result_vec/example_result_vec_1d) |
| text | `ResultString` | [Result String: 1D input](reference/meta/result_types/result_string/example_result_string_1d) |
| an image file path | `ResultImage` | [Result Image: 1D input](reference/meta/result_types/result_image/example_result_image_1d) |
| an SVG file path (SMIL animations play) | `ResultSVG` | [Cartesian Animation gallery](reference/meta/cartesian_animation/index) |
| a video file path | `ResultVideo` | [Result Video: 1D input](reference/meta/result_types/result_video/example_result_video_1d) |
| any other file path | `ResultPath` | [Result Path: 1D input](reference/meta/result_types/result_path/example_result_path_1d) |
| a table or array payload | `ResultDataSet` | [Result DataSet: 1D input](reference/meta/result_types/result_dataset/example_result_dataset_1d) |
| a Rerun recording | `ResultRerun` | [Rerun Integration gallery](reference/meta/rerun/index) |
| embeddable panel content | `ResultContainer` / composable containers | [Composable Containers gallery](reference/meta/composable_containers/index) |
| something unpicklable | `ResultReference` | (same-process escape hatch — see below) |

The distinction that matters most in practice is the first two rows: a binary outcome
belongs in `ResultBool`, never in `ResultFloat`. The next distinction is whether the payload
has to survive a process boundary — `ResultDataSet` is pickled into the cache's blob store
and so renders from any process, while `ResultReference` keeps a live object in memory and
is stripped on the way to the cache.

The full table, with what to assign in `benchmark()`:

| Type | Use for | Set to |
|---|---|---|
| `bn.ResultFloat(units="s")` | Continuous scalar metrics (time, distance, score) | `self.elapsed = 0.42` |
| `bn.ResultBool()` | Success/failure, pass/fail, any binary outcome | `self.success = True` |
| `bn.ResultString()` | Text outputs, labels, error messages | `self.error_msg = "timeout"` |
| `bn.ResultImage()` | Images, GIFs | `self.img = "/path/to/output.png"` |
| `bn.ResultSVG()` | SVG drawings and SMIL animations, kept out of the raster-only image paths | `self.drawing = "/path/to/output.svg"` |
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
See the [ResultImage examples](reference/meta/result_types/result_image/example_result_image_1d)
and [ResultVideo examples](reference/meta/result_types/result_video/example_result_video_1d)
for working code.

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

### Choosing a backend: panel or rerun

`BenchRunCfg(backend=...)` picks the *rendering library*, not a different report.
It is a per-chart-type preference applied during plot selection: a chart type the
preferred backend implements renders through it, and every other chart type keeps
its best other implementation. So the same sweep, unchanged, runs under either:

```python
for backend in ("panel", "rerun"):
    bench.run_cfg.backend = backend
    bench.plot_sweep(input_vars=["sides", "color"], result_vars=["polygon", "area"])
```

Today the one chart type both backends implement is `panes`, the renderer for
media results. The panel backend tiles it — one pane per sample, laid out in a
grid. The rerun backend puts the samples on a **timeline** named after the swept
variable, in one embedded viewer: dragging the time cursor sweeps the parameter,
one sample per tick. See
[Rerun Backend Choice](reference/meta/rerun/example_rerun_backend_choice) for the
same polygon sweep rendered both ways in one report.

Any result type goes on the timeline, not just recordings. Images become
`rr.EncodedImage`, numbers `rr.Scalars`, strings `rr.TextDocument`, and a
`ResultRerun`'s cached `.rrd` is re-indexed onto the sweep timeline (keeping any
timeline the benchmark recorded inside a sample — `log_tick` included, which is what
an over-time recording uses — so that can still be scrubbed within the tick it sits
on; only the wall-clock `log_time` is dropped). Each result variable gets its own
view, so an image swept beside a metric reads as a picture and a time series *of the
sweep*, moving together under one cursor.

With `repeats > 1`, a number becomes `rr.Measurements` instead: the mean across the
repeats with its variance, which rerun draws as a line in a ±1σ band. See
[Rerun Repeats Band](reference/meta/rerun/example_rerun_repeats_band).

The axis is a tick counter, not a clock. Rerun labels a sequence index `#3` with
no unit, which is the honest reading for a sweep — a polygon with three sides is
`#3`, where `+3s` would claim a unit the parameter does not have. Where the
coordinates are whole numbers the ticks *are* those numbers; where they are not the
ticks count the samples and the parameter's real value gets a small read-out view of
its own so the cursor position is still legible — a time series for fractional
floats, a text document for categories, which have no position to plot.

`index=` overrides the choice:

| `bn.TimelineIndex` | Axis |
|---|---|
| `tick` (default) | `#3`, `#4`, … — the coordinate where it is a whole number, else the sample's position |
| `position` | `#0`, `#1`, … — always the sample's position |
| `duration` | `+3s`, `+4s`, … — one second per unit; the only encoding that shows a non-uniform sweep as non-uniform |

By default the timeline is the **longest numeric** dimension: a time axis reads as
a continuum, so a three-value colour axis makes a poor one however the sweep was
declared. Pass `timeline_dim=` to choose:

```python
from functools import partial

plot_callbacks=[partial(bn.BenchResult.to_rerun_timeline, timeline_dim="sides")]
```

Only one dimension can be time. Rerun timelines are independent axes rather than a
joint index — a latest-at query resolves on the timeline being viewed and ignores
every other one — so a 2-D sweep cannot become two scrubbers. The other dimensions
are peeled onto the entity tree instead, one branch and one view each, all driven
by the single shared cursor. That is how the mapping scales: one dimension
animates, the rest tile. The timeline stays one sample per tick at any
dimensionality; what grows is the view count, the product of the peeled
dimensions' sizes.

With two remaining dimensions, the first defines columns and the second rows, in
their sampled coordinate order. For example, `pose` then `scenario` gives one column
per pose and one row per scenario. The column count is fixed when the recording
is composed, so resizing the viewer preserves the axis mapping. Missing recordings
leave empty cells. A single remaining dimension forms one row; with more than two,
the first defines columns and combinations of the remaining dimensions define rows.

For an *all*-rerun report — scalars included, mapped onto rerun's entity tree as
bar charts, line graphs and tensors and laid out by a generated Blueprint, with
every `ResultRerun` alongside them merged the way `rerun_grid` merges them — ask
for it by callback rather than by backend:

```python
bench.plot_sweep(..., plot_callbacks=[bn.BenchResult.to_rerun_plots])
```

That is a different report shape, not a backend swap, which is why it is not what
`backend="rerun"` selects.

A `ResultRerun` that recorded nothing logs a warning naming it instead of leaving a
gap in the report.

Two things to know if you pick the merged viewer by hand instead:

* `rerun_summary` and `rerun_grid` are named-only plot types, so `plot_callbacks=`
  is the only route to them. The sweep timeline is not named-only: it is `panes`
  on the rerun backend, so `backend="rerun"` selects it.
* Define the callback at module scope. The callback list is pickled into the result
  cache, so a closure fails with `AttributeError: Can't pickle local object`.

## The svg Backend: Plots for a GitHub PR

`backend="svg"` draws charts with matplotlib as self-contained SVGs. A GitHub `<img>`
shows them: they hold no script, no font file and no external link. Chart types without
an svg twin keep the panel pipeline.

The backend is a run config setting, so any example or benchmark draws with it unchanged.
To run an existing example with the svg backend, pass it the run config:

```python
example_sweep_1_float_2_cat_no_repeats(bn.BenchRunCfg(backend="svg"))
```

To write the charts as files:

```python
run_cfg = bn.BenchRunCfg(backend="svg")
res = bench.plot_sweep("wave", input_vars=["x", "wave", "envelope"])
res.to_svg_files("docs/my_plots")  # one <chart>_<result var>.svg per auto-selected chart
res.to_svg_files("docs/my_plots", charts=["violin", "table"])  # named-only charts
```

A chart shows two or three dimensions: the x axis, the y axis of a heatmap, and a colour
per level of a categorical input. Every other swept dimension, `over_time` included,
becomes a grid of small panels: one panel per combination of values, all visible at
once, titled with those values. The panels share their axes, their colour scale, the
title and the legend. A soft highlight walks the panels in sweep order and loops: the
current panel gets a border and the others dim a little. No mark moves, so every instant
is the whole chart, and a reader who asks for reduced motion
(`prefers-reduced-motion`) sees the grid with no animation. A chart with nothing left
over is a static SVG, as before.

Past `bn.MAX_SVG_PANELS` (12) panels the panels get too small, so the chart steps
through the combinations as frames instead: one chart, one frame per combination, played
in a loop with a label naming the current values and a progress bar, on fixed axes. Past
`bn.MAX_SVG_FRAMES` (60) the rest are dropped, with a log warning and a note on the
image. To choose the layout, set `svg_layout`:

```python
run_cfg = bn.BenchRunCfg(backend="svg", svg_layout="frames")  # "auto" (default), "grid"
res.to_svg_files("docs/my_plots", svg_layout="grid")  # overrides the run config
```

The value charts reduce repeats by the mean; the curve draws one standard deviation as a
band. The distribution charts draw every repeat as a dot, with a thick median line.

Each svg chart declares the sweep shapes it draws, the same as its holoviews twin.
Named-only twins stay named-only: request them with `plot_list=[...]` or
`to_svgs([...])`.

| Chart | Auto | Shape | Shown | One panel (or frame) per |
|---|---|---|---|---|
| `line` | yes | 1 float, any cats, no repeats | x, first cat as colour | other cats, `over_time` |
| `curve` | yes | 1 float, any cats, repeats | x, first cat as colour, ±1 std | other cats, `over_time` |
| `heatmap` | yes | 2+ floats | first two floats | other inputs, `over_time` |
| `bar` | yes | 0 floats, 1+ cats, no repeats | first cat, second cat as colour | other cats, `over_time` |
| `box_whisker` | yes | 0 floats, any cats, repeats | box, dots, median per first cat; second cat as colour | other cats, `over_time` |
| `histogram` | yes | no inputs | bins, dots, median of the repeats | `over_time` |
| `violin` | no | as `box_whisker` | density, dots, median | other cats, `over_time` |
| `scatter_jitter` | no | 0 floats, 0-1 cats, repeats | dots, median | `over_time` |
| `scatter` | no | 0 floats, any cats, no repeats | one dot per first cat; second cat as colour | other cats, `over_time` |
| `band` | no | any | 10-90% and 25-75% bands, median, every sample, over `over_time` or the first input | nothing: other dims are pooled |
| `table` | no | any | one row per sample (first `bn.MAX_TABLE_ROWS`) | nothing |
| `xy_scatter`, `xy_curve`, `xy_histogram`, `xy_hexbin` | no | a `ResultDataSet` | one sample's table | sample |
| `volume` | yes | 3 floats, no cats | filled contour bands of the first two floats | value of the third float (not `over_time`) |
| `surface` | no | 2 floats, any cats | a 3D surface of the mean from a fixed camera, every repeat as a dot | cat, `over_time` |

The `xy_*` charts take their twin's options (`x=`, `y=`, `color=`, `column=`, `bins=`,
`gridsize=`...) as keywords to `to_svgs` or `to_auto`, or from a `container=bn.xy_scatter(...)`
spec declared on the result var.

A sweep outside those shapes (a 0-D `over_time` line, a bool bar with repeats, a violin
over a float) falls back to the holoviews (or, for `surface` and `volume`, plotly) chart,
and so does a result var the svg chart cannot draw. `res.to_svgs()` returns the SVG strings instead of files.

To link the files from a PR, commit them and use a URL pinned to the commit. This repo
keeps `*.svg` in Git LFS, so use
`https://media.githubusercontent.com/media/<owner>/<repo>/<sha>/<path>`;
`raw.githubusercontent.com` serves the LFS pointer, not the image.

[The svg backend gallery](reference/meta/svg_backend/index) runs existing examples with
`backend="svg"` when the docs build. Each page names the example and the run config it
uses.

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
| `pane_repeat_subsampling_divisions` | None | Resolution the repeats are shown at in sample panes (display only) |
| `cache_samples` | False | Cache individual results across runs (resume interrupted sweeps) |
| `cache_results` | False | Cache the entire sweep result (skip re-runs with same inputs) |
| `over_time` | False | Track results across multiple runs for time-series analysis |
| `headless` | False | Skip opening a browser to display results |
| `dry_run` | False | Log the sweep grid summary without executing the benchmark |

All other parameters have sensible defaults. See `BenchRunCfg`'s docstring for the
full reference, [Caching](caching.md) for the cache flags in detail, and
[Tracking results over time](over_time.md) for `over_time` and regression detection.

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
    agg_fn="mean",           # aggregation function: see bencher.utils.AggFn
)
```

- `agg_fn` — one of the values of `bencher.utils.AggFn`, the single definition of
  this vocabulary: `"mean"`, `"sum"`, `"max"`, `"min"`, `"median"`. The strings are
  **lowercase and case-sensitive**, and an unrecognised value raises `ValueError`
  rather than quietly falling back to `"mean"`.

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

A metric that only one side declares has nothing to compare against. It is named in
`unpaired` (`{"candidate_only": [...], "baseline_only": [...]}`), and `bencher compare` and
`bencher ab` print a warning on stderr for each one.
The top-level `claims` list judges every claim the candidate declares, also on a metric
that the change adds (see [Declaring a claim](#declaring-a-claim)).

The same artifacts are available from the CLI on a saved result (see the collect/render split):

```bash
# render HTML and also emit result.json
python -m bencher.render result.pkl out_dir --json result.json

# diff two saved results
python -m bencher.render compare baseline.pkl candidate.pkl --json comparison.json
```

### Evidence for a pull request

`bencher compare` also writes what a reviewer reads. `--markdown PATH` writes a block to
paste as a PR's `## Evidence` section. It is text only: every chart is text that GitHub
draws in the PR body, with no image and no external resource, so it works without pushing
any file. Per metric it has a chart, then a caption with the verdict, the mean before →
after with the change in percent, the claim outcome on each side (see below), the change
with its 95% CI and statistical verdict, and each side's revision and sample count, then a
collapsed `<details>` block with a CSV of the points the chart shows. Above the charts, a
**Claims** list gives each claim the candidate declares with its outcome on the candidate
and on the baseline, or "no baseline" for a metric the baseline does not measure, and a
**Not compared** list names each metric that only one side declares. `--png DIR` (or
`--png-dir DIR`) also writes one PNG per metric, for local viewing, with the claim
threshold drawn in and a ±1 std band; the Markdown does not link it. The PNG plots against
the first swept input; the mean and std pool the repeats and every other swept input, so
with two or more swept inputs the band also holds the spread across the other inputs. Any
of `--json`, `--markdown` and `--png` may be given; at least one is required.

```bash
bencher compare base.pkl candidate.pkl --markdown evidence.md --png evidence/
```

The chart is the form that shows the metric honestly:

| What was swept | Chart |
| --- | --- |
| No input | Mermaid `xychart-beta`, one bar per side |
| No input, a negative value | `diff` fence of text bars grown from a zero column (an xychart bar grows from the bottom of the axis, not from 0) |
| No input, a repeat-to-repeat spread as large as the change | `diff` fence of text bars, each with its ± std |
| One numeric input, same values on both sides | Mermaid `xychart-beta`, a grey "before" line and a blue "after" line with a legend; binned to at most 30 points |
| ... with a spread as large as the change | The same two lines and a pale line at ±1 std of each (the series colors at 40% opacity) |
| ... with values that do not print as distinct labels | `diff` fence of text bars, with `#2`, `#3` added to repeated labels |
| One categorical input (string, enum or bool) | A table: before, after, the change and its 95% CI from that category's repeats, one row per category, however many |
| Two or more inputs | An emoji heatmap: the percent change at each point of the first two inputs |
| Points or inputs that only one side has | A table over the shared points, and a "Left out:" line naming the rest |

In the heatmap, the color says better or worse for the metric's `direction`, not the sign
of the change: 🟦 better by at least twice the margin, 🟩 better by at least the margin,
⬜ within the margin, 🟧 and 🟥 the same for worse (the margin is the metric's
`regression_percentage`, 10 by default). With no direction, 🟪 is down and 🟨 is up. A line
under the table gives the legend. A third swept input with at most 6 values gets one table
per value; past that, or with four or more inputs, each cell is the mean over the inputs
after the first two, and a line says so. A numeric axis past 30 rows or 12 columns is
binned. When the two sides swept different inputs, the table uses the first input both
swept and averages over the others; with no shared input it compares the overall means.

`--png-url-base` is still accepted but deprecated and ignored: there is no image to link,
and `bencher compare` and `bencher ab` print a warning saying so.

With three or more compared metrics, a Mermaid `radar-beta` chart above the per-metric
charts shows them all at once: each axis is one metric's mean divided by its baseline mean,
so the "before" curve is 1 on every axis and "after" shows the relative change. A metric
whose baseline mean is 0, negative or not finite, or whose mean changes sign, cannot be scaled that
way; it is left off and named under the chart.

**The change and its CI.** Each metric in `comparison.json` carries a `change` record
with `mean_diff` (candidate − baseline), its 95% CI `ci_low`/`ci_high`, `method`, the
counts and `stat_verdict`: over the input points both sides swept, the per-point
differences of the repeat means are bootstrapped (`paired_bootstrap`), and with no swept
input or one shared point the two sides' repeats are resampled on their own (`bootstrap`).
The CI is the 2.5th–97.5th percentile of 10,000 resamples with a fixed seed, so the same
results give the same evidence byte for byte. `stat_verdict` is "equivalent within ±X%"
when the whole CI lies inside ±X% of the baseline mean (X is `regression_percentage`, 10
by default, or the metric's own percentage override), else "improved"/"regressed" (or
"increased"/"decreased" with no `direction`) when the CI excludes 0, else "no significant
change"; too few samples give "too few samples" and no CI, and sides with no shared input
point give "not comparable" (with `method` null, `mean_diff` and the CI null, and a
`reason` key that says why; only this record has `reason`). The threshold `verdict` does
not change, and the caption shows both when they disagree.

In Python: `bn.evidence_markdown(base, cand)`, `bn.write_evidence_pngs(base, cand, out_dir)`
and `bn.write_evidence(base, cand, json_path=..., markdown_path=..., png_dir=...)`. Their
`png_url_base` argument is deprecated and ignored, with a `DeprecationWarning`. See
[`example_evidence.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_evidence.py).

### Before and after a change: `bencher ab`

`bencher ab` runs one bench command on the base revision and on the working tree, then
writes the comparison and the evidence:

```bash
bencher ab -- python my_bench.py
bencher ab --base origin/main --out evidence/ -- pixi run python my_bench.py
```

- The base is `--base REF` when given, else the merge-base of `HEAD` with `origin/HEAD`
  (then `origin/main`, then `main`). It runs in a temporary detached `git worktree`,
  removed afterwards even on failure. The candidate runs in the working tree as it is, so
  uncommitted changes count.
- The base run puts the worktree's `src` directory (when it has one) and its root first
  on `PYTHONPATH`. That shadows an editable install or an absolute `PYTHONPATH` entry
  that points into the working tree, so the base imports its own package. If the base
  run still loads a module from the working tree (a package outside `src` or the root,
  for example), it saves no result and fails, and `base.log` names each such module.
- A relative path in the command that the base worktree cannot have, because it is outside
  the repository or ignored by git (a `.venv/bin/python`, a data directory), is made
  absolute for the base run. A tracked path such as the bench file stays relative, so each
  side runs its own copy.
- Each side runs with `BENCHER_NO_CACHE=1` (see [Caching](caching.md)): the caches are
  keyed by inputs, not code, so without it the candidate could read the base's samples.
- Each side is told where to save its result with `BENCHER_RESULT_PATH`. Any process that
  sets it gets every collected sweep saved there with `bn.save_result`; a command that runs
  several sweeps leaves the last one. `BENCHER_SOURCE_REVISION` is the side's commit (with
  `+dirty` for a modified working tree) and `BENCHER_DISPLAY_LABEL` is `base <rev>` or
  `candidate <rev>`.
- `--out` (default `./bencher-ab/`) receives `base.pkl`, `candidate.pkl`,
  `comparison.json`, the text-only `evidence.md`, and `base.log`/`candidate.log` with each
  side's output. `--png-dir DIR` also writes one PNG per metric there, for local viewing.
  `--images` adds images to `evidence.md` (see below); its PNGs share those file names, so
  `--png-dir` must not be `<out>/images/`. The paths are printed on stdout.
- The exit status is 0 when both sides ran, whatever the verdict and whatever the claims
  say (a failed claim, on a metric the base has or not, is reported, not enforced); 1 when
  a side failed or saved no result (stderr names the side and the tail of its log, which is
  kept), or when the two sides share no metric (no claim is judged then, and stderr names
  the metrics on each side); 2 for a usage or git problem.

#### Images in the PR body: `bencher ab --images`

`--images` is opt-in; without it `evidence.md` stays text only. With it, `bencher ab`
draws a PNG of each metric whose image shows more than its text chart, pushes the PNGs to
GitHub on a ref that no branch reaches, and links each one above its text chart:

```bash
bencher ab --base origin/main --images -- python my_bench.py
```

- **What is drawn.** A metric with more than one sample at a point gets every repeat as a
  dot, a box of the quartiles per swept point (or per side with no swept input) and the
  mean ± 1 std, before (grey, hollow) and after (blue, filled), with the claim threshold.
  Two or more swept inputs get a heatmap of the percent change at each point, blue for
  better and red for worse by the metric's `direction` (violet down and yellow up with no
  direction), one panel per value of a third input as in the text heatmap. A metric with
  one sample per point and one or no swept input gets no image: its text chart already
  shows everything. Points or inputs that only one side has get no image either.
- **Where it goes.** The PNGs and a `<metric>.csv` of every sample (side, each input,
  repeat, value) are written to `images/` under `--out`, then pushed as one commit to
  `refs/bencher/evidence` on `origin`, under a directory unique to the run (UTC time,
  candidate revision, random suffix). The commit's parent is the ref's previous tip, so
  every older run stays reachable and git never deletes it. No branch reaches the ref, so
  `git clone` and `git fetch` do not download the images; `git ls-remote origin
  refs/bencher/evidence` shows the ref. Only git plumbing builds the commit: the work tree,
  the index and `HEAD` do not change, and `--no-filters` stores the real PNG even when
  `.gitattributes` sends `*.png` to Git LFS. When another run pushes first, the commit is
  made again on the new tip and pushed again, up to 5 times; the push is never forced.
  A throwaway repository makes and pushes the commit and fetches only the previous tip,
  so the local repository keeps no ref, no image and no unpushed commit.
- **The links.** Each image is linked as
  `https://github.com/<owner>/<repo>/blob/<commit-sha>/<path>?raw=true`, with the owner and
  repository read from `origin` (ssh or https). A PR page draws that link for anyone who
  can read the repository, public or private. A `<sub>` link under the image opens the
  CSV. The text chart, the caption and the `<details>` CSV block stay under each image, so
  the PR reads correctly when an image does not load.
- **When it cannot push.** With no GitHub `origin`, or no push access, the images stay in
  `images/`, `evidence.md` stays text only, and one line on stderr says why. The exit
  status does not change.

Each side also runs with `BENCHER_NO_SHOW=1`, which makes `bn.run` and `BenchRunner` show
nothing: the default `show=True` starts a live report server, and that server keeps a
non-interactive process alive after the bench finishes. The bench file must
exist on the base revision: for a bench added by the change itself, commit it on its own
first and pass that commit as `--base`.

`BenchReport.save(..., emit_json=True)` writes `result.json` next to the HTML for every
contained result (opt-in; default off). All JSON output is strict — non-finite values (e.g. a
zero-baseline percent change) are emitted as `null`.

### Declaring a claim

A result variable can declare what a change is meant to make true:

```python
class Braking(bn.ParametrizedSweep):
    speed = bn.FloatSweep(bounds=(0.5, 3.0))
    stop_distance = bn.ResultFloat(units="m", claim="< 0.7")
```

The forms are `< x`, `<= x`, `> x`, `>= x` and the inclusive range `low..high`. The string
is parsed when the class is defined, so a typo fails there and not after the sweep. A claim
is judged against every sample, repeats included: it holds only if the *worst* sample
satisfies it (the largest for `<`/`<=`, the smallest for `>`/`>=`, the one nearest or
furthest past an edge for a range). A mean inside the bound with one point outside it fails.

`result_to_dict` adds a `claim` entry to that metric — `holds` (`null` when nothing was
recorded), `worst_value`, `worst_inputs` (sweep inputs and `repeat`) and `samples`.
`compare_results` judges the candidate's claim on both sides, so "the baseline fails the
claim and the candidate holds it" reads straight off the comparison. Its top-level `claims`
list has one entry per claim the candidate declares, in declaration order:

```json
{"variable": "peak_decel", "claim": "< 3",
 "candidate": {"holds": false, "worst_value": 5.336, "worst_inputs": {"speed": 2.5, "repeat": 4}, "samples": 36},
 "baseline": null}
```

`baseline` is `null` when the baseline does not measure the metric, which is the usual case
for a metric that the change adds; otherwise it is the baseline's outcome, and the entry
repeats the `claim` on that metric's `metrics` entry. The claim is not part
of the variable's cache identity: changing it keeps cached samples and over-time history.

### A light install for the evidence tools

A CI job that only gates a change does not need the plotting stack. Install the package
without its dependencies, then the light ones by hand:

```bash
pip install --no-deps holobench
pip install numpy param diskcache xarray pandas strenum matplotlib jinja2 pyyaml
```

The second list is holobench's own dependencies without the heavy ones, plus pyyaml, which
bencher imports and a full install gets through panel. pip then warns that holobench's other requirements (holoviews, panel, hvplot, optuna,
plotly, scikit-learn, moviepy) are missing; that is expected. It can also warn that a light
package is newer than holobench's upper pin; add the pin to the second command (for example
`"numpy<=2.5.1"`) if you want to stay inside it.

What works: `import bencher`, sweeps, claims, `bn.compare_results`, `bencher compare` (JSON,
Markdown and PNG evidence) and `bencher ab`. A sweep that would plot warns once and collects
without plots. Plots, HTML reports, the report server, `bencher <result.pkl> <dir>`,
optimisation and video raise an `ImportError` that says to run `pip install holobench`, which
adds them.

## Complete execution reports

`BenchReport.save_report(root)` freezes a complete execution under
`root/<execution-uuid>/index.html`. It includes tabs, collision-free per-result
summaries, referenced local media, and a versioned `report.json` inventory of
relative paths, byte sizes and SHA-256 digests. Use `bn.verify_report(directory)`
before transferring the directory. Serve it over HTTP; CDN libraries still need
network access. Moving the directory does not require its original cache.

For multiple collected sweeps, establish one identity before measurement starts:

```python
# Resolve revision in your launcher, before starting ROS or other foreign threads.
with bn.execution_context(source_revision=revision, workflow_run=run_id, lane=machine):
    results = [bench.collect(...), bench.collect(...)]
bn.save_results(results, "execution.pkl")
```

When the launcher is a *different process* — a CI job, or a wrapper script that
starts the benchmark — export the same provenance instead:

```bash
export BENCHER_SOURCE_REVISION=$(git rev-parse HEAD)
export BENCHER_WORKFLOW=nightly BENCHER_WORKFLOW_RUN=$CI_RUN_ID
export BENCHER_LANE=$RUNNER_NAME
export BENCHER_ATTEMPT=$GITHUB_RUN_ATTEMPT   # 1 on the first run, not 0
```

Every execution started in that environment carries those fields, so the frozen
`report.json` and the publication receipt say which revision they describe. An
argument to `execution_context` wins over the environment — a field the caller
supplied is not read from it at all — and an empty variable is the same as an
unset one.

`BENCHER_ATTEMPT` counts attempts from 1, the same as `Execution.attempt`, and a
value that is not a positive integer fails the run instead of misattributing the
retry. A retry counter that starts at 0, such as Buildkite's
`BUILDKITE_RETRY_COUNT`, therefore needs converting rather than exporting
directly:

```bash
export BENCHER_ATTEMPT=$((BUILDKITE_RETRY_COUNT + 1))
```

Bencher reports all of these and never checks them: export them per job, not from
a long-lived shell, where they would outlive the checkout they name.

Render that bundle in one clean process:

```bash
bencher execution.pkl reports/my-benchmark --report --cachedir cachedir
```

Only load pickles from trusted producers. Serialization includes collected
results, not a live `Bench` or its worker. Missing execution provenance and
mixed-execution bundles are errors; old results are never stamped with the
renderer machine's time or checkout revision. Use the existing single-result
renderer for legacy pickles without execution metadata.

`bn.run(..., report_directory="reports/my-benchmark", show=False)` enables the
same complete export in the shared runner, including every requested refinement
and grouped result. `BENCHER_REPORT_DIR` is the equivalent environment opt-in.
Each runner invocation gets a new execution unless the launcher has explicitly
grouped it in `execution_context`. Plain `run(save=True)`, `save()`, positional
rendering, `compare`, and `--cachedir` keep their existing behavior.

Retries verify and reuse the frozen files without saving HTML again. A missing
asset or failed render does not finalize the UUID directory. Changes to frozen
bytes or result summaries fail verification; start a new execution for new
measurements. Keep collected pickle bundles and regression diagnostics until
rendering and publication have succeeded. A manifest proves local completeness,
not successful remote publication.

Summaries are snapshots of the history available during collection. They do not
claim to describe later merges of concurrent history writers. Each manifest
result records the actual history namespace, series and collection configuration
key, even if the runner subsequently changes the displayed report name.

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
| A benchmark function that reads or mutates global state | Make it pure — see below |
| Assuming an unrecorded result reads as `0` | It is `NaN` since v1.105 — pass `default=0` to opt out |
| Running `python` / `pytest` / `ruff` directly when developing bencher | Prefix every command with `pixi run` |

### Encode combinations as dimensions, not as one variable

This is the single most common structural mistake, and it is worth repeating here because
it is invisible once the data is collected. A `StringSweep(["no_cache_cpu", "no_cache_gpu",
"cache_cpu", "cache_gpu"])` produces a bar chart of four unrelated labels. The same
information as two variables — `use_cache = bn.BoolSweep()` and
`backend = bn.StringSweep(["cpu", "gpu"])` — produces a 2D grid in which bencher can show
you the effect of caching *independently* of the backend, and the interaction between them.
The Cartesian product is the point of the tool; collapsing it into labels throws away every
comparison you were trying to make. See
[Core Concept: Dimensions Are Sweep Variables](#core-concept-dimensions-are-sweep-variables).

### Keep the benchmark function pure

Bencher assumes a stochastic pure function: given the same inputs it returns the same output
plus random noise, and each call is uninfluenced by any other. Two mechanisms depend on that
assumption:

- **Repeats.** The distribution shown as mean ± std is only meaningful if the repeats are
  independent samples of the same quantity. A counter that increments across calls, or a
  warm cache inside your own code, turns "noise" into a trend that the plot presents as
  spread.
- **Caching.** A cache key is computed from the inputs. If the output also depends on a
  global — a module-level accumulator, the contents of a directory a previous sample wrote
  to, an env var flipped halfway through — then a cached value is a value computed under
  conditions that no longer hold, and it will be silently reused. Nothing detects this.

Where state genuinely is part of the measurement, make it an input variable so it is part
of the key, or turn the caches off for that benchmark.

### Missing results are NaN, not zero

Since **v1.105.0**, the default value for `ResultFloat`, `ResultVec`, and `ResultBool` is
`NaN` rather than `0`. An *unrecorded* sample — a run that aborts before measuring, or a
result variable the worker never sets — is treated as missing and dropped by the NaN-aware
regression and aggregation reductions, instead of masquerading as a real `0`/`False`
measurement and dragging means toward zero. This matches the storage layer, which already
initialises result arrays with `NaN`.

For `ResultBool` this means **missing is not failure**: an unrecorded repeat is dropped from
the success proportion rather than counted as `False`. A worker that wants a crash or abort
to count as a failure must explicitly record `False` on its failure path.

If downstream code expects `0`, opt out per variable:

```python
count = bn.ResultFloat(units="ul", default=0)
```

`CACHE_VERSION` was not bumped for this change, because a result variable's `default` is not
part of `BenchCfg.hash_persistent()`. Existing benchmark and `over_time` history caches are
preserved, and the new `NaN` default only applies to cache *misses*, so a benchmark with
missing samples may transiently hold a mix of `0` (old cells) and `NaN` (new ones) until
those cells are recomputed.

### Use `pixi run` when developing bencher itself

Every command in this repository goes through Pixi — `pixi run test`, `pixi run ci`,
`pixi run python bencher/example/example_simple_float.py`. A bare `python`, `pytest`, or
`ruff` picks up whatever happens to be on `PATH` rather than the pinned environment, which
is how "works on my machine" bugs and spurious lint failures get in. This applies only to
developing bencher; users who installed `holobench` from PyPI run their own benchmarks
normally.

## Publishing frozen reports

Publish a complete execution directory without rendering it again:

```bash
bencher publish reports/my-benchmark/EXECUTION_UUID \
  --store gs://my-reports-bucket --prefix reports/my-benchmark \
  --http-base https://reports.example/benchmarks/my-benchmark \
  --receipt published.json --pointer latest/my-benchmark/index.html
```

The storage prefix and HTTP base are independent: both get the execution UUID,
but the serving route need not match the bucket path. `--store /tmp/report-store`
uses a local SQLite object database for testing; it is **not** a static HTTP
directory. The CLI prints a JSON publication receipt and optionally persists it
atomically. It preserves that receipt if the separate pointer update fails.
Expected storage failures exit nonzero. Adapters decide whether that failure
should gate a benchmark job; measurements and diagnostics remain on disk.
The legacy render positional command, `--cachedir`, and `compare` are unchanged.

### Publishing from the run itself

A launcher that only wants a URL does not have to find the frozen directory and
run a second command. Configure the same target in the environment and the run
publishes what it froze:

```bash
export BENCHER_PUBLISH_STORE=gs://my-reports-bucket
export BENCHER_PUBLISH_PREFIX=reports/my-benchmark
export BENCHER_PUBLISH_HTTP_BASE=https://reports.example/benchmarks/my-benchmark
export BENCHER_PUBLISH_RECEIPT=published.json   # optional
python my_benchmark.py                          # calls bn.run(...)
```

`BENCHER_PUBLISH_EXPIRY_DAYS` and `BENCHER_PUBLISH_MINIMUM_REMAINING_DAYS` are
the remaining CLI options. `bn.run(..., publication=bn.PublicationTarget(...))`
is the in-process equivalent, and `BenchRunner.publication` holds the receipt
afterwards. Read the URL from the receipt file rather than from stdout, which a
benchmark shares with everything else it prints.

Configuring publication enables the complete export on its own: without
`BENCHER_REPORT_DIR` the report is frozen into a temporary directory that is
removed once it is committed — and **kept** when publication fails, with its path
in the raised `PublicationFailed`, so `bencher publish` can be pointed at it
rather than the sweep being run again. A partially configured environment (a
store with no serving root) is an error, not a silent skip. This is unrelated to
`bn.run(publish=True, publisher=...)`, which calls the in-process `Publisher`
protocol during the run.

The publisher creates assets and `report.json` before the entry page, which is
the commit object. It reads back and verifies all inventory bytes before
returning a URL. An interrupted upload can resume from the frozen directory;
matching objects are reused, while different bytes under the same UUID fail.
A matching committed retry performs **no writes**, including no age renewal.
A missing dependency in a committed report is an explicit failure, not implicit
repair. A manifest alone does not establish a committed report.

For Python integrations, import `CompleteReportPublisher` from `bencher.publishing`
and stores from `bencher.object_store` (`LocalStore`) or `bencher.gcloud_store`
(`GcloudStore`). It is not the `Publisher` protocol in `bencher.bench_report` that
`bn.run(publisher=...)` calls during a run — this one publishes a directory that
`save_report` already froze.
`publish(directory)` returns `Published(url, receipt)` or `PublishFailed`.
Restore a JSON handoff with `PublicationReceipt.from_dict(json.loads(...))`;
`publisher.verify(receipt)` checks its manifest, storage location and every
dependency before downstream consumers trust it.
`publisher.point(receipt, key)` re-verifies the report before updating a pointer.
Default ordering uses measurement time and UUID, not upload time. Deployment
callers may supply a `PointerCandidate` from `bencher.publication_pointers` with
a named ordering policy and comparable integer/string rank components, for
example `(source_revision_rank, attempt, execution_time, uuid)`. Rank source
revisions **before** rerun time so an old checkout cannot displace a newer one.
The caller owns positive write eligibility, revision ordering and lane mapping;
bencher knows nothing about GitHub workflows, branch names or machines.

Pointers embed their target and ordering state in the same redirect HTML object.
CAS conflicts cause reread, reordering and bounded retries. An unknown existing
HTML format fails closed: migrate old aliases explicitly rather than overwriting
their contents. The lower-level `update_pointer` accepts a `verify_target` callback
for non-report dependencies; use `CompleteReportPublisher.point` for report targets.

### Remote storage and renewal contract

`read(key)` returns `Present(data, version, metadata, created_at, expires_at)`,
`Absent`, or `ReadFailed`. `write(key, data, CreateOnly() | Match(version))` returns
`Written`, `Conflict`, or `WriteFailed(reason, outcome_unknown)`. Never infer
absence from a failed read, or success from a timeout. Versions are opaque and
only valid for the object/store that issued them. A successful write is not a
directory-wide transaction. GcloudStore obtains credentials through gcloud and
uses the JSON API for structured HTTP errors, generation-pinned downloads and
generation/metageneration preconditions; its environment, timeout and transport
are injectable. The byte-oriented interface holds one object in memory.

`list(prefix, token=..., limit=...)` returns `Listed(items, next_token)` or
`ListFailed`; `complete` is true only without a continuation token. Continue even
after an empty page with a token. Listings are not snapshots: concurrently added
objects before a cursor may require another pass. A partial listing cannot prove
that an object is unreferenced or that a benchmark never ran.

`renew(key, expected_version)` conditionally rewrites the observed bytes and
serving metadata, returning `Renewed(version, created_at, expires_at)`, `Conflict`,
`Absent`, `Unsupported`, or `WriteFailed`. Reread and reevaluate conflicts instead
of replaying stale mutable content. GCS renewal uploads the same bytes, then
checks the new version and creation time; a metadata-only touch or equal bytes
after a timeout do not prove renewal. The host UTC clock must be accurate: a
creation time preceding the attempt fails verification conservatively.

Renewal requires explicit `expiry_seconds` describing the verified backend
age-based policy. GCS expiry is **eligibility**, not confirmation of deletion;
bucket rules and lifecycle lag remain external. No policy is inferred or changed.
For LocalStore this is an explicit fake expiry model: expired rows become absent
to reads/listings, but the filesystem does not independently delete them.
No configured policy means unsupported renewal.

Set `CompleteReportPublisher(..., minimum_remaining_seconds=...)` (CLI
`--minimum-remaining-days` with `--expiry-days`) to require verified dependency
lifetime before new references. Publication never extends that lifetime itself;
run explicit maintenance first. A zero minimum promises no retention window.
Scheduling, graph traversal, retention roots and renewal receipts are separate
maintenance integration, not implemented by ordinary publication.

The opt-in GCS contract test creates a fresh UUID prefix and small objects:

```bash
BENCHER_GCS_CONTRACT_ROOT=gs://YOUR_BUCKET/DISPOSABLE_PREFIX \
  pixi run pytest test/test_gcloud_store.py::test_gcloud_live_disposable_contract -s
```

It exercises create conflicts, stale generations, competing writers, pagination,
and byte/metadata-preserving renewal with verified creation-time reset. Use a
disposable prefix with a verified seven-day Age Delete policy; the test leaves
its objects for that lifecycle rule. The test does not establish rule coverage.
GCS contracts follow the official [preconditions](https://docs.cloud.google.com/storage/docs/request-preconditions),
[uploads](https://docs.cloud.google.com/storage/docs/json_api/v1/objects/insert),
[listing](https://docs.cloud.google.com/storage/docs/json_api/v1/objects/list), and
[lifecycle](https://docs.cloud.google.com/storage/docs/lifecycle) documentation.

## Transferring history

Set `BenchRunCfg(history_namespace="machine-name")` to isolate a machine's
baselines without changing its benchmark or configuration keys. The empty
namespace keeps existing cache keys. Moving old history into a named namespace
is an explicit migration: export the empty namespace, assign the intended
`snapshot.namespace`, then restore it. Only do this when that machine's origin
is known; an ambiguous shared history should remain in its original namespace.

`bencher.history_transfer.HistorySnapshot.export(cachedir, namespace=...)`
reads the native records used by collection. Its optional `keys` selects existing
configuration keys. `to_bytes()` and `from_bytes()` transfer these records as a
pickle between trusted writers. Associated media and blob files remain references
and must travel separately with their cache-relative layout intact.

`snapshot.merge(other, max_time_events=20)` returns a new snapshot containing
both writers' distinct executions. `snapshot.restore(cachedir)` merges into the
local cache in one transaction. A duplicate execution with conflicting values,
different input coordinates, incompatible column identities, or a different
namespace raises instead of overwriting data. Keep a failed transfer for retry
or inspection. Remote writers should read a generation, merge, and conditionally
replace that generation, retrying the merge after a competing update.

For categorical execution IDs such as UUIDs, supply
`BenchRunCfg(time_event=id, time_event_metadata={"executed_at": utc_iso_time,
"label": display_label})`. Transfer merges order them by execution time;
legacy coordinates without metadata sort by their string representation.
Timestamps must include a timezone. Merge follows the depth limit recorded by
collection, or an explicit `max_time_events` override. A record without a limit
keeps all executions; merging never deletes configurations absent from a newer snapshot.
Trends can be projected directly from `snapshot.records[key]["dataset"]`, so
the dashboard and the next comparison use the same history.
