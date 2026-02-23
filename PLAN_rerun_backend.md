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
  -> maps to RerunResult views    (TimeSeriesView, BarChartView, etc.)

RerunBackendResult                (new result class - mirrors BenchResult methods)
  -> RerunLineResult              (TimeSeriesView with entity paths per category)
  -> RerunCurveResult             (TimeSeriesView with mean + std band entities)
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

### 2.3 Timeline Mapping (over_time)

| Bencher Concept | Rerun Mapping |
|-----------------|---------------|
| `over_time` (datetime) | `rr.set_time("over_time", timestamp=epoch_seconds)` |
| `over_time` (event string) | `rr.set_time("over_time", sequence=index)` |
| Float sweep dims | `rr.set_time(dim_name, sequence=index)` -- each becomes an independent timeline scrubber |
| Categorical dims | Entity path segments: `/{dim_name}/{value}/` |
| Repeat dim | `rr.set_time("repeat", sequence=repeat_idx)` OR aggregated away via ReduceType |

This extends the existing `RerunResult._set_time()` and `_log_to_rerun()` approach.

---

## 3. Plot Type Mapping (Panel -> Rerun)

### 3.1 LineResult -> RerunLineResult

| Panel | Rerun |
|-------|-------|
| `hvplot.line(x=float_var, by=cat_var)` | `rr.log(entity, rr.Scalars(val))` on a `TimeSeriesView` |
| X-axis: float sweep variable | Timeline: float sweep dim (sequence index) |
| Grouping by categorical | Separate entity paths per category value |
| Multiple result vars | Separate entities, all in same TimeSeriesView |

**Blueprint:**
```python
rrb.TimeSeriesView(
    name=f"{result_var.name} vs {float_var.name}",
    origin=f"/{result_var.name}",
)
```

**Data logging:**
```python
for cat_val in cat_values:
    for i, float_val in enumerate(float_values):
        rr.set_time(float_var.name, sequence=i)
        rr.log(f"/{rv.name}/{cat_var.name}/{cat_val}", rr.Scalars(value))
```

### 3.2 CurveResult -> RerunCurveResult

| Panel | Rerun |
|-------|-------|
| `hv.Curve + hv.Spread(mean +/- std)` | `rr.Scalars` for mean + additional entities for upper/lower bounds |
| Mean line + shaded std band | 3 scalar series: mean, mean+std, mean-std in same view |

**Blueprint:** Same as LineResult (`TimeSeriesView`), but with 3 entities per result var.

**Data logging:**
```python
rr.log(f"/{rv.name}/mean", rr.Scalars(mean_val))
rr.log(f"/{rv.name}/upper", rr.Scalars(mean_val + std_val))
rr.log(f"/{rv.name}/lower", rr.Scalars(mean_val - std_val))
```

Use `SeriesLines` archetype to style bounds differently (dashed, alpha).

### 3.3 BarResult -> RerunBarResult

| Panel | Rerun |
|-------|-------|
| `hvplot.bar(x=cat_var)` | `rr.BarChart(values)` in a `BarChartView` |
| Grouped bars (multiple cats) | Multiple BarChart entities or stacked values |
| Error bars (repeats > 1) | Not natively supported -> log as separate annotation or TextDocument |

**Blueprint:**
```python
rrb.BarChartView(
    name=f"{result_var.name}",
    origin=f"/{result_var.name}",
)
```

**Data logging:**
```python
# Collect values across categories into an array
values = [dataset[rv.name].sel({cat: c}).item() for c in cat_values]
rr.log(f"/{rv.name}", rr.BarChart(values))
```

**Limitation:** Rerun's BarChart is simpler than HoloViews bars. For grouped bars with
multiple categoricals, generate multiple BarChart entities or fall back to a single
flattened bar chart with labels logged as `AnnotationContext`.

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
| Grouped scatter | Separate entity paths per category, colored differently |

**Blueprint:**
```python
rrb.Spatial2DView(
    name=f"Scatter: {result_var.name}",
    origin=f"/{result_var.name}/scatter",
)
```

**Data logging:**
```python
for cat_val in cat_values:
    positions = [[i, val] for i, val in enumerate(values_for_cat)]
    rr.log(f"/{rv.name}/scatter/{cat_val}", rr.Points2D(positions, colors=[color]))
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
| P0 | Line (scalar time series) | TimeSeriesView | Low (extends existing) |
| P0 | Bar chart | BarChartView | Low |
| P0 | Image | Spatial2DView | Low (exists) |
| P0 | Video | AssetVideo | Low (exists) |
| P0 | Text | TextDocumentView | Low (exists) |
| P1 | Curve (mean +/- std) | TimeSeriesView | Medium |
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
     - Map extra categorical dims to entity path branches (already done)
     - Map extra float dims to additional timelines (already done)
     - Use `rrb.Tabs` for high-cardinality categorical dims
     - Use `rrb.Grid` for 2-way categorical slicing

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

### 6.1 Multi-Timeline Scrubbing

Rerun's key advantage: each float sweep dimension becomes an independent
timeline. The viewer provides separate scrubbers for each, enabling users to
explore the parameter space interactively. This is superior to Panel's widget
sliders because:
- All timelines are visible simultaneously
- Frame-based navigation
- Keyboard shortcuts for stepping

### 6.2 Entity Hierarchy Browser

Categorical dimensions create a browsable entity tree in the Rerun viewer's
Blueprint panel. Users can toggle visibility of individual categories.

### 6.3 View Linking

Multiple views in the same blueprint share timeline state. Scrubbing one
timeline updates all views simultaneously -- equivalent to Panel's linked
widgets but built into the viewer.

---

## 7. Data Type Compatibility Matrix

| ResultType | Panel Container | Rerun Archetype | Rerun View |
|------------|----------------|-----------------|------------|
| ResultVar | hvplot / hv.* | rr.Scalars | TimeSeriesView |
| ResultBool | hvplot.bar | rr.Scalars (0/1) | TimeSeriesView / BarChartView |
| ResultVec | multi-line | rr.Scalars (per component) | TimeSeriesView |
| ResultImage | pn.pane.PNG | rr.EncodedImage | Spatial2DView |
| ResultVideo | pn.pane.Video | rr.AssetVideo | Spatial2DView |
| ResultString | pn.pane.Markdown | rr.TextDocument | TextDocumentView |
| ResultPath | pn.widgets.FileDownload | rr.TextDocument (path) | TextDocumentView |
| ResultContainer | pn.Column | N/A (skip) | N/A |
| ResultReference | custom callback | N/A (skip) | N/A |
| ResultDataSet | raw display | rr.log columns | DataframeView |
| ResultHmap | hv.HoloMap | timeline animation | TimeSeriesView |

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
