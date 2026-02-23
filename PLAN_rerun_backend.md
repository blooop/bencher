# Plan: Rerun Composable Container Backend for Bencher

## Goal

Create a feature-complete Rerun-based visualization backend as an alternative to the
existing Panel/HoloViews backend. Users should be able to swap between backends at will
with matching data types and plot semantics. Rerun's timeline scrubber maps to bencher's
`over_time` dimension.

---

## 1. Architecture Overview

### Current Backend Stack

```
BenchResult (MRO)
  -> RerunResult            (basic scalar/image/video/text logging, no blueprints)
  -> VolumeResult           (Plotly Volume)
  -> BoxWhiskerResult       (hv.BoxWhisker)
  -> ViolinResult           (hv.Violin)
  -> ScatterJitterResult    (hv.Scatter + jitter)
  -> ScatterResult          (hvplot.scatter)
  -> LineResult             (hvplot.line)
  -> BarResult              (hvplot.bar)
  -> HeatmapResult          (hvplot.heatmap)
  -> CurveResult            (hv.Curve + Spread)
  -> SurfaceResult          (hv.Surface / Plotly)
  -> HoloviewResult         (base HoloViews)
  -> HistogramResult        (hvplot.hist)
  -> VideoSummaryResult     (MoviePy composition)
  -> DataSetResult          (raw xarray display)
  -> OptunaResult           (optuna pareto)
```

### Proposed Rerun Backend Stack

```
ComposableContainerRerun          (new composable container)
  -> uses rerun.blueprint (rrb)   (programmatic layout)
  -> uses rr.log()                (data logging)
  -> maps to RerunResult views    (Spatial2DView, BarChartView, TimeSeriesView for over_time, etc.)

RerunBackendResult                (new result class - mirrors BenchResult methods)
  -> RerunLineResult              (Spatial2DView with LineStrips2D, X=float param, Y=result)
  -> RerunCurveResult             (Spatial2DView with LineStrips2D for mean + upper/lower bounds)
  -> RerunBarResult               (BarChartView)
  -> RerunHeatmapResult           (Spatial2DView with Tensor archetype or custom)
  -> RerunScatterResult           (Spatial2DView with Points2D)
  -> RerunBoxWhiskerResult        (BarChartView with precomputed stats)
  -> RerunViolinResult            (BarChartView with precomputed density)
  -> RerunHistogramResult         (BarChartView with bin counts)
  -> RerunSurfaceResult           (Spatial3DView with Mesh3D)
  -> RerunVolumeResult            (Spatial3DView with Points3D + opacity)
  -> RerunVideoResult             (AssetVideo + VideoFrameReference)
  -> RerunImageResult             (EncodedImage / Image)
  -> RerunTextResult              (TextDocumentView)
  -> RerunDataSetResult           (DataframeView)
```

---

## 2. Key Design Decisions

### 2.1 ComposableContainerRerun

A new `ComposableContainerRerun` class in
`bencher/results/composable_container/composable_container_rerun.py`
that implements the `ComposableContainerBase` interface.

- **`ComposeType.right`** -> `rrb.Horizontal(...)` container
- **`ComposeType.down`** -> `rrb.Vertical(...)` container
- **`ComposeType.sequence`** -> Rerun timeline (data logged at different time steps)
- **`ComposeType.overlay`** -> Multiple entities logged to same view (overlaid in one panel)

The `render()` method returns a `rrb.Blueprint` subtree (container or view) rather than
a Panel widget. The final top-level render produces a complete `rrb.Blueprint` that is
sent via `rr.send_blueprint()`.

### 2.2 Backend Selection

Add a `backend` parameter to `BenchRunCfg`:

```python
class RenderBackend(StrEnum):
    panel = auto()    # existing HoloViews/Panel backend (default)
    rerun = auto()    # new Rerun backend

class BenchRunCfg:
    backend: RenderBackend = RenderBackend.panel
```

`BenchResult.to_auto()` and `BenchResult.plot()` dispatch to the appropriate backend
based on this setting. Users swap with:

```python
bench = MySweep().to_bench(bch.BenchRunCfg(backend="rerun"))
```

### 2.3 Timeline Mapping (over_time ONLY)

The Rerun time slider maps **exclusively** to bencher's `over_time` dimension. No other
dimension should use the time slider.

| Bencher Concept | Rerun Mapping |
|-----------------|---------------|
| `over_time` (datetime) | `rr.set_time("over_time", timestamp=epoch_seconds)` -- drives the time slider |
| `over_time` (event string) | `rr.set_time("over_time", sequence=index)` -- drives the time slider |
| Float sweep dims | X-axis of a line chart (`LineStrips2D` in `Spatial2DView`) -- NOT a timeline |
| Categorical dims | Bar chart positions / grouped bars (`BarChartView`) or line groupings -- NOT entity path segments |
| Repeat dim | Aggregated away via ReduceType (mean, std, etc.) before plotting |

**Rationale:** Float sweep parameters are independent variables that define the X-axis of
line charts, not a time dimension to scrub through. Categorical parameters define discrete
groupings within a plot (bars, grouped lines, etc.), just as they do in the holoviews
backend. Only `over_time` represents actual temporal progression and maps to the time slider.

This extends the existing `RerunResult._set_time()` and `_log_to_rerun()` approach, but
restricts timeline usage to `over_time` only.

---

## 3. Plot Type Mapping (Panel -> Rerun)

### 3.1 LineResult -> RerunLineResult

| Panel | Rerun |
|-------|-------|
| `hvplot.line(x=float_var, by=cat_var)` | `rr.LineStrips2D` in a `Spatial2DView` |
| X-axis: float sweep variable | X-coordinates of LineStrips2D points |
| Y-axis: result variable | Y-coordinates of LineStrips2D points |
| Grouping by categorical | Separate `LineStrips2D` entities per category, each with distinct color |
| Multiple result vars | Separate views (one per result var) |

**Key design:** Float sweep line charts use `Spatial2DView` with `LineStrips2D`, NOT
`TimeSeriesView`. The float parameter values are the X-coordinates and result values are
the Y-coordinates. This produces a standard X-Y line chart without involving the time slider.

**Blueprint:**
```python
rrb.Spatial2DView(
    name=f"{result_var.name} vs {float_var.name}",
    origin=f"/{result_var.name}/line",
)
```

**Data logging:**
```python
for cat_val in cat_values:
    # Build XY points: [(float_val_0, result_0), (float_val_1, result_1), ...]
    points = [[float_val, result_val] for float_val, result_val in zip(float_values, results)]
    color = color_for_category(cat_val)
    rr.log(
        f"/{rv.name}/line/{cat_var.name}/{cat_val}",
        rr.LineStrips2D([points], colors=[color], labels=[str(cat_val)]),
    )

# If no categorical variable, single line:
points = [[float_val, result_val] for float_val, result_val in zip(float_values, results)]
rr.log(f"/{rv.name}/line", rr.LineStrips2D([points]))
```

**Axis labels:** Use `rr.TextDocument` entities at axis endpoints or a companion
`TextDocumentView` to label axes, since Spatial2DView doesn't have built-in axis labels.

### 3.2 CurveResult -> RerunCurveResult

| Panel | Rerun |
|-------|-------|
| `hv.Curve + hv.Spread(mean +/- std)` | `rr.LineStrips2D` for mean + upper/lower bounds in `Spatial2DView` |
| Mean line + shaded std band | 3 line strips: mean, mean+std, mean-std (bounds with lower alpha) |

**Blueprint:** Same as LineResult (`Spatial2DView`), but with 3 line strip entities per
result var.

**Data logging:**
```python
# Build XY points for mean line and error bounds
mean_points = [[fv, mean] for fv, mean in zip(float_values, mean_values)]
upper_points = [[fv, mean + std] for fv, mean, std in zip(float_values, mean_values, std_values)]
lower_points = [[fv, mean - std] for fv, mean, std in zip(float_values, mean_values, std_values)]

rr.log(f"/{rv.name}/curve/mean", rr.LineStrips2D([mean_points], colors=[[0, 0, 255, 255]]))
rr.log(f"/{rv.name}/curve/upper", rr.LineStrips2D([upper_points], colors=[[0, 0, 255, 80]]))
rr.log(f"/{rv.name}/curve/lower", rr.LineStrips2D([lower_points], colors=[[0, 0, 255, 80]]))
```

Style bounds with lower alpha to visually distinguish from the mean line.

### 3.3 BarResult -> RerunBarResult

| Panel | Rerun |
|-------|-------|
| `hvplot.bar(x=cat_var)` | `rr.BarChart(values)` in a `BarChartView` |
| X-axis: categorical variable | Bar positions indexed by category |
| Grouped bars (by=secondary cat) | Multiple `BarChart` entities (one per group value) in same view |
| Error bars (repeats > 1) | TextDocument companion with statistics |

**Key design:** Categorical dimensions map to bar positions within the chart, just like
in holoviews. Categories are NOT entity path segments -- they are data values that define
where bars appear. Secondary categorical grouping produces multiple BarChart entities in
the same view.

**Blueprint:**
```python
rrb.BarChartView(
    name=f"{result_var.name} by {cat_var.name}",
    origin=f"/{result_var.name}/bar",
)
```

**Data logging (single categorical):**
```python
# Bars indexed by primary categorical variable
values = [dataset[rv.name].sel({cat_var.name: c}).item() for c in cat_values]
rr.log(f"/{rv.name}/bar", rr.BarChart(values))
# Log category labels as companion text
labels = ", ".join([f"{i}: {c}" for i, c in enumerate(cat_values)])
rr.log(f"/{rv.name}/bar/labels", rr.TextDocument(f"Categories: {labels}"))
```

**Data logging (grouped -- multiple categoricals):**
```python
# One BarChart entity per secondary category value
for group_val in secondary_cat_values:
    values = [
        dataset[rv.name].sel({primary_cat: c, secondary_cat: group_val}).item()
        for c in primary_cat_values
    ]
    rr.log(f"/{rv.name}/bar/{group_val}", rr.BarChart(values))
```

**Limitation:** Rerun's BarChart is simpler than HoloViews bars. For complex multi-level
grouping, we flatten to a single bar chart with composite labels, or use multiple
BarChart entities within the same BarChartView.

### 3.4 HeatmapResult -> RerunHeatmapResult

| Panel | Rerun |
|-------|-------|
| `hvplot.heatmap(x, y, C)` | `rr.Tensor` or `rr.Image` in a `TensorView` or `Spatial2DView` |
| 2D color grid | Log 2D numpy array as `rr.Tensor` with colormap |
| Hover values | DataframeView companion panel with raw values |

**Blueprint:**
```python
rrb.Horizontal(
    rrb.TensorView(
        name=f"Heatmap: {result_var.name}",
        origin=f"/{result_var.name}/heatmap",
        scalar_mapping=rrb.TensorScalarMapping(colormap="turbo"),
    ),
    rrb.DataframeView(
        name="Values",
        origin=f"/{result_var.name}/data",
    ),
)
```

**Data logging:**
```python
# Pivot dataset into 2D array
arr = dataset[rv.name].values  # shape: (x_size, y_size)
rr.log(f"/{rv.name}/heatmap", rr.Tensor(arr))
```

### 3.5 ScatterResult -> RerunScatterResult

| Panel | Rerun |
|-------|-------|
| `hvplot.scatter(by=cat_var)` | `rr.Points2D` in a `Spatial2DView` |
| X-axis: category index or value | X-coordinates of Points2D |
| Y-axis: result value | Y-coordinates of Points2D |
| Grouped scatter (by=cat_var) | Multiple `Points2D` entities with distinct colors per group |

**Key design:** Categories define the X-axis positions of scatter points (like holoviews),
not entity path segments. Grouping by a secondary categorical produces color-coded point
groups within the same view.

**Blueprint:**
```python
rrb.Spatial2DView(
    name=f"Scatter: {result_var.name}",
    origin=f"/{result_var.name}/scatter",
)
```

**Data logging:**
```python
# Map category values to X positions
cat_to_x = {cat: i for i, cat in enumerate(cat_values)}
for cat_val in cat_values:
    positions = [[cat_to_x[cat_val], val] for val in values_for_cat]
    color = color_for_category(cat_val)
    rr.log(
        f"/{rv.name}/scatter/{cat_val}",
        rr.Points2D(positions, colors=[color], labels=[str(cat_val)]),
    )
```

### 3.6 BoxWhiskerResult -> RerunBoxWhiskerResult

| Panel | Rerun |
|-------|-------|
| `hv.BoxWhisker` | Precomputed stats -> `rr.BarChart` + `rr.TextDocument` for stats |
| Median, Q1, Q3, whiskers, outliers | Log summary statistics as text + bar chart of medians |

**Strategy:** Rerun has no native box-whisker. Two approaches:
1. **Primary:** Log a `BarChart` of median values per category + a `TextDocument` with
   full statistics (Q1, Q3, whiskers, outliers).
2. **Alternative:** Use `Spatial2DView` with `Points2D` for outliers + `Boxes2D` for IQR
   boxes + `LineStrips2D` for whiskers (custom box plot rendering).

**Blueprint:**
```python
rrb.Vertical(
    rrb.Spatial2DView(
        name=f"BoxPlot: {result_var.name}",
        origin=f"/{result_var.name}/boxplot",
    ),
    rrb.TextDocumentView(
        name="Statistics",
        origin=f"/{result_var.name}/stats",
    ),
)
```

### 3.7 ViolinResult -> RerunViolinResult

| Panel | Rerun |
|-------|-------|
| `hv.Violin` | Precomputed KDE -> `Spatial2DView` with `LineStrips2D` for density contours |

**Strategy:** Compute kernel density estimate, render as mirrored line strips in Spatial2D.

### 3.8 HistogramResult -> RerunHistogramResult

| Panel | Rerun |
|-------|-------|
| `hvplot.hist(y=result_var)` | Precompute bins -> `rr.BarChart(bin_counts)` |

**Blueprint:**
```python
rrb.BarChartView(
    name=f"Histogram: {result_var.name}",
    origin=f"/{result_var.name}/histogram",
)
```

**Data logging:**
```python
counts, bin_edges = np.histogram(values, bins='auto')
rr.log(f"/{rv.name}/histogram", rr.BarChart(counts.tolist()))
```

### 3.9 SurfaceResult -> RerunSurfaceResult

| Panel | Rerun |
|-------|-------|
| `hv.Surface` (Plotly 3D) | `rr.Mesh3D` in `Spatial3DView` |
| 3D surface with color | Triangulated mesh with per-vertex colors |

**Blueprint:**
```python
rrb.Spatial3DView(
    name=f"Surface: {result_var.name}",
    origin=f"/{result_var.name}/surface",
)
```

**Data logging:**
```python
# Convert 2D grid to triangulated mesh
vertices, indices, colors = grid_to_mesh(x_vals, y_vals, z_vals, colormap)
rr.log(f"/{rv.name}/surface", rr.Mesh3D(
    vertex_positions=vertices,
    triangle_indices=indices,
    vertex_colors=colors,
))
```

### 3.10 VolumeResult -> RerunVolumeResult

| Panel | Rerun |
|-------|-------|
| `go.Volume` (Plotly isosurface) | `rr.Points3D` in `Spatial3DView` with opacity-mapped colors |

**Strategy:** Rerun lacks native volume rendering. Use `Points3D` with RGBA colors where
alpha encodes the scalar value, providing a point-cloud volume visualization.

**Blueprint:**
```python
rrb.Spatial3DView(
    name=f"Volume: {result_var.name}",
    origin=f"/{result_var.name}/volume",
)
```

### 3.11 VideoResult -> RerunVideoResult (existing, enhanced)

| Panel | Rerun |
|-------|-------|
| `pn.pane.Video` (autoplay) | `rr.AssetVideo` + `rr.VideoFrameReference` |
| Video file path | Log video asset, reference frames on timeline |

Already partially implemented in `RerunResult._log_result_var()`. Enhancement:
- Use `VideoFrameReference` to enable frame-level timeline scrubbing
- Map `over_time` to video frame indices

### 3.12 ImageResult -> RerunImageResult (existing, enhanced)

| Panel | Rerun |
|-------|-------|
| `pn.pane.PNG` | `rr.EncodedImage(path=...)` in `Spatial2DView` |

Already implemented. Enhancement:
- Add blueprint to create proper `Spatial2DView` per image entity
- Support image grids via `rrb.Grid` of `Spatial2DView`s

### 3.13 TextResult -> RerunTextResult (existing, enhanced)

| Panel | Rerun |
|-------|-------|
| `pn.pane.Markdown` | `rr.TextDocument(text)` in `TextDocumentView` |

Already implemented. Enhancement:
- Blueprint creates `TextDocumentView` for each text entity

### 3.14 DataSetResult -> RerunDataSetResult

| Panel | Rerun |
|-------|-------|
| Raw xarray display | `DataframeView` showing tabular data |

**Blueprint:**
```python
rrb.DataframeView(
    name="Dataset",
    origin="/dataset",
)
```

### 3.15 ScatterJitterResult -> RerunScatterJitterResult

Same as ScatterResult but add random jitter to x-positions of Points2D.

---

## 4. Implementation Plan

### Phase 1: Core Infrastructure

**Files to create/modify:**

1. **`bencher/results/composable_container/composable_container_rerun.py`** (NEW)
   - `ComposableContainerRerun(ComposableContainerBase)` dataclass
   - `render()` returns `rrb.Blueprint` subtree
   - Maps `ComposeType` to `rrb.Horizontal/Vertical/Tabs` containers
   - `append()` collects `rrb` views/containers
   - Labels become `TextDocumentView` annotations in the layout

2. **`bencher/results/rerun_result.py`** (MODIFY)
   - Add `to_rerun_blueprint()` method that creates a programmatic blueprint
   - Add per-plot-type `_log_*` methods (line, bar, heatmap, etc.)
   - Refactor `_log_to_rerun()` to support blueprint-aware logging
   - Add `_build_blueprint()` that constructs the `rrb.Blueprint` from the data shape

3. **`bencher/bench_run_cfg.py`** or equivalent config (MODIFY)
   - Add `RenderBackend` enum
   - Add `backend` field to `BenchRunCfg`

4. **`bencher/results/bench_result.py`** (MODIFY)
   - Add `to_auto_rerun()` method mirroring `to_auto()` for Rerun backend
   - Add `rerun_plot_callbacks()` static method listing Rerun-compatible plotters
   - Dispatch from `to_auto()` based on `backend` setting

### Phase 2: Plot Type Implementations

Each plot type gets a dedicated method in `RerunResult` (or a new `RerunPlotResult`
mixin class). Implementation order by priority:

| Priority | Plot Type | Rerun View | Complexity |
|----------|-----------|------------|------------|
| P0 | Line (XY float sweep) | Spatial2DView + LineStrips2D | Medium |
| P0 | Bar chart | BarChartView | Low |
| P0 | Image | Spatial2DView | Low (exists) |
| P0 | Video | AssetVideo | Low (exists) |
| P0 | Text | TextDocumentView | Low (exists) |
| P0 | Over-time series | TimeSeriesView (rr.Scalar + over_time timeline) | Low |
| P1 | Curve (mean +/- std) | Spatial2DView + LineStrips2D | Medium |
| P1 | Heatmap | TensorView | Medium |
| P1 | Histogram | BarChartView | Low |
| P1 | Scatter | Spatial2DView + Points2D | Medium |
| P1 | Dataset table | DataframeView | Low |
| P2 | BoxWhisker | Spatial2DView (custom) | High |
| P2 | Violin | Spatial2DView (custom) | High |
| P2 | Surface | Spatial3DView + Mesh3D | High |
| P2 | Volume | Spatial3DView + Points3D | High |
| P2 | ScatterJitter | Spatial2DView + Points2D | Medium |

### Phase 3: Blueprint Layout Engine

5. **`bencher/results/rerun_blueprint_builder.py`** (NEW)
   - `RerunBlueprintBuilder` class
   - Takes list of views generated by Phase 2 plot methods
   - Organizes into a `rrb.Blueprint` with:
     - `rrb.Grid` or `rrb.Vertical(rrb.Horizontal(...), ...)` layout
     - One view per result variable per applicable plot type
     - `rrb.TimePanel(state="expanded")` for timeline scrubbing
   - `build(views: List[rrb.SpaceView]) -> rrb.Blueprint`

### Phase 4: Dimension Reduction and Composition

6. **Extend `_to_panes_da()` analogue for Rerun**
   - The Panel backend recursively slices N-D data and creates nested
     `ComposableContainerPanel` with labels.
   - The Rerun backend should:
     - Map the first float dim to the X-axis of line charts
     - Map the first categorical dim to bar positions or line groupings (color)
     - Use `rrb.Tabs` for extra dimensions beyond what a single plot can show
     - Use `rrb.Grid` for 2-way categorical slicing (one plot per combination)
     - Map `over_time` exclusively to `rr.set_time()` for the time slider
     - Aggregate repeats via ReduceType before plotting

### Phase 5: Integration and Testing

7. **`bencher/example/example_rerun_panel_comparison.py`** (NEW)
   - Side-by-side example showing identical data rendered by both backends
   - Demonstrates `backend="panel"` vs `backend="rerun"`

8. **`test/test_rerun_backend.py`** (NEW)
   - Unit tests for each plot type mapping
   - Tests for blueprint generation
   - Tests for timeline mapping
   - Tests for composable container Rerun

9. **Update existing examples:**
   - Modify `example_rerun_backend.py` to use blueprint-based approach
   - Add `backend="rerun"` option to key examples

---

## 5. ComposableContainerRerun Detail

```python
@dataclass(kw_only=True)
class ComposableContainerRerun(ComposableContainerBase):
    """Rerun blueprint-based composable container.

    Maps bencher's composition model to Rerun's blueprint layout system:
    - right  -> rrb.Horizontal
    - down   -> rrb.Vertical
    - sequence -> timeline (logged at different time steps)
    - overlay  -> multiple entities in same view
    """
    name: str | None = None
    var_name: str | None = None
    var_value: str | None = None
    recording: rr.RecordingStream | None = None

    def render(self) -> rrb container:
        label_view = None
        label = self.label_formatter(self.var_name, self.var_value)
        if label is not None:
            # Add a small text label view
            label_entity = f"/labels/{self.var_name}/{self.var_value}"
            self.recording.log(label_entity, rr.TextDocument(label))
            label_view = rrb.TextDocumentView(
                name=label, origin=label_entity
            )

        views = []
        if label_view:
            views.append(label_view)
        for item in self.container:
            if isinstance(item, ComposableContainerRerun):
                views.append(item.render())
            else:
                views.append(item)  # already an rrb view/container

        match self.compose_method:
            case ComposeType.right:
                return rrb.Horizontal(*views)
            case ComposeType.down:
                return rrb.Vertical(*views)
            case ComposeType.sequence:
                # For sequence, items are logged at different time steps
                # Return a Tabs view since they share the same spatial view
                return rrb.Tabs(*views)
            case ComposeType.overlay:
                # Overlay: all entities shown in a single view
                # Merge contents from all child views
                if len(views) == 1:
                    return views[0]
                return rrb.Grid(*views)
```

---

## 6. Rerun-Specific Enhancements

### 6.1 Over-Time Timeline Scrubbing

The Rerun time slider maps exclusively to bencher's `over_time` dimension. When
`over_time=True`, historical benchmark runs are logged at different time steps,
and the user can scrub through them with the time slider to see how results
evolved across runs. This is the ONLY use of Rerun's timeline system.

Float sweep dimensions are NOT timelines -- they are X-axis values in line
charts rendered via `Spatial2DView` + `LineStrips2D`.

### 6.2 Plot Type Parity with HoloViews

The Rerun backend reproduces the same plot semantics as the HoloViews backend:
- **Float sweeps** -> X-Y line charts (X = parameter, Y = result)
- **Categorical sweeps** -> bar charts, grouped bars, scatter plots
- **Mixed float + categorical** -> multiple colored lines (one per category)
- **Repeats** -> aggregated (mean/std) before plotting, shown as curve with bounds

Categories appear as visual groupings within plots (different bar colors,
different line colors) rather than as entity path segments.

### 6.3 View Linking via Over-Time

When `over_time=True`, multiple views in the same blueprint share the `over_time`
timeline state. Scrubbing the time slider updates all views simultaneously --
showing how all metrics evolved together across benchmark runs.

### 6.4 Blueprint Entity Browser

The Rerun viewer's Blueprint panel allows users to toggle visibility of
individual plot elements (lines, bars, etc.) within each view. This provides
interactive filtering without needing Panel widget callbacks.

---

## 7. Data Type Compatibility Matrix

| ResultType | Panel Container | Rerun Archetype | Rerun View |
|------------|----------------|-----------------|------------|
| ResultVar | hvplot / hv.* | rr.LineStrips2D / rr.BarChart | Spatial2DView / BarChartView |
| ResultBool | hvplot.bar | rr.BarChart (0/1 values) | BarChartView |
| ResultVec | multi-line | rr.LineStrips2D (per component) | Spatial2DView |
| ResultImage | pn.pane.PNG | rr.EncodedImage | Spatial2DView |
| ResultVideo | pn.pane.Video | rr.AssetVideo | Spatial2DView |
| ResultString | pn.pane.Markdown | rr.TextDocument | TextDocumentView |
| ResultPath | pn.widgets.FileDownload | rr.TextDocument (path) | TextDocumentView |
| ResultContainer | pn.Column | N/A (skip) | N/A |
| ResultReference | custom callback | N/A (skip) | N/A |
| ResultDataSet | raw display | rr.log columns | DataframeView |
| ResultHmap | hv.HoloMap | `rrb.Tabs` or `rrb.Grid` with multiple views | Spatial2DView / BarChartView |

---

## 8. API Surface

### User-facing API

```python
import bencher as bch

# Existing Panel backend (unchanged)
bench = MySweep().to_bench(bch.BenchRunCfg(level=3))
result = bench.get_result()
panel_view = result.to_auto()  # Panel/HoloViews (default)

# New Rerun backend
rerun_view = result.to_rerun()              # existing basic view (enhanced)
rerun_view = result.to_auto_rerun()         # full auto-plot via Rerun
rerun_view = result.to_rerun_blueprint()    # returns blueprint + viewer pane

# Backend selection at config level
bench = MySweep().to_bench(bch.BenchRunCfg(level=3, backend="rerun"))
result = bench.get_result()
view = result.to_auto()  # automatically uses Rerun
```

### Individual plot methods

```python
result.to_rerun_line(result_var=rv)
result.to_rerun_bar(result_var=rv)
result.to_rerun_heatmap(result_var=rv)
result.to_rerun_scatter(result_var=rv)
result.to_rerun_curve(result_var=rv)
result.to_rerun_histogram(result_var=rv)
result.to_rerun_surface(result_var=rv)
result.to_rerun_volume(result_var=rv)
result.to_rerun_boxwhisker(result_var=rv)
result.to_rerun_violin(result_var=rv)
```

---

## 9. File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `bencher/results/composable_container/composable_container_rerun.py` | CREATE | Rerun composable container |
| `bencher/results/rerun_result.py` | MODIFY | Add blueprint-aware plot methods |
| `bencher/results/rerun_blueprint_builder.py` | CREATE | Blueprint layout engine |
| `bencher/results/bench_result.py` | MODIFY | Add rerun dispatch + callbacks |
| `bencher/bench_run_cfg.py` (or `bench_cfg.py`) | MODIFY | Add RenderBackend enum |
| `bencher/utils_rerun.py` | MODIFY | Add blueprint send/embed helpers |
| `bencher/example/example_rerun_panel_comparison.py` | CREATE | Comparison example |
| `test/test_rerun_backend.py` | CREATE | Unit tests |
| `bencher/__init__.py` | MODIFY | Export new symbols |

---

## 10. Limitations and Workarounds

| Feature | Panel Support | Rerun Support | Workaround |
|---------|---------------|---------------|------------|
| Violin plot | Native | No native | KDE -> LineStrips2D in Spatial2DView |
| Box-whisker | Native | No native | Boxes2D + LineStrips2D + Points2D |
| Error bars | Native | No native | 3 scalar series (mean, upper, lower) |
| Interactive hover/tap | PointerXY streams | Click selection | Rerun selection panel shows details |
| Grouped bars | by= parameter | Single array | Multiple BarChart entities or flattened |
| Colorbar | Native | TensorView built-in | Works for heatmap; manual for others |
| 3D surface | Plotly interactive | Mesh3D (less interactive) | Acceptable trade-off |
| Volume rendering | Plotly isosurface | Points3D cloud | Lower fidelity but functional |
| ResultContainer | Custom Panel panes | Not renderable | Skip with warning |
| ResultReference | Custom callbacks | Not renderable | Skip with warning |

---

## 11. Migration Path

1. All existing Panel functionality remains untouched and is the default
2. Rerun backend is opt-in via `backend="rerun"` or explicit `to_rerun_*()` calls
3. `to_rerun()` (existing) continues to work as before but gains blueprint support
4. New `to_auto_rerun()` provides feature-complete auto-plotting for Rerun
5. The `ComposableContainerRerun` enables video-summary-like composition via blueprints

No breaking changes to the existing API.
