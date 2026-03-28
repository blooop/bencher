# Plan: Manim Backend for Bencher

## Context

Bencher implements a **grammar of Cartesian products** — a declarative system where users
define typed parameter sweeps, and the framework automatically computes the full Cartesian
product, executes the benchmark function at each point, stores results in N-D xarray
tensors, and selects appropriate visualizations based on the type signature
`(float_count, cat_count, repeats)`.

The **grammar of graphics** mapping in bencher:

| Grammar of Graphics | Bencher Equivalent |
|---|---|
| Data | xarray Dataset (N-D tensor from Cartesian product) |
| Aesthetics | Input variable types (float→axis, categorical→color/facet) |
| Geometry | Plot result classes (CurveResult, BarResult, HeatmapResult…) |
| Statistics | Repeats + ReduceType (mean/std/min/max) |
| Facets | Recursive panel slicing via ComposableContainer |
| Scales | SweepBase + level system |

### Current Backend Architecture

Bencher uses a **mixin-based** architecture where `BenchResult` inherits from ~15 result
classes via multiple inheritance. Each result class provides a `to_plot()` method that
calls `self.filter()` with dimension constraints, then delegates to a dataset→visualization
callback.

**Existing backends:**

1. **HoloViews + Bokeh** (default) — Interactive 2D plots (Curve, Line, Bar, Scatter,
   Heatmap, Band, BoxWhisker, Violin, Histogram)
2. **Plotly** — 3D visualizations (Surface, Volume)
3. **Panel panes** — Media results (PNG images, Video playback, file downloads, Markdown)
4. **MoviePy** — Video composition via `ComposableContainerVideo`

**Composition system:** `ComposableContainerBase` defines 4 compose types (right, down,
sequence, overlay). Concrete implementations exist for Panel (interactive dashboards),
Video (MoviePy clips), and Dataset (xarray concatenation).

---

## What Manim Brings

[Manim](https://www.manim.community/) (Community Edition) is a Python library for
creating mathematical animations. It provides:

- Programmatic scene construction with `Scene`, `Mobject`, `Animation`
- Built-in mathematical objects: axes, graphs, number planes, 3D surfaces
- Smooth interpolated animations between states (transforms, fades, movements)
- LaTeX rendering natively integrated
- High-quality video output (MP4/WebM) and image export (PNG/SVG)
- Camera controls for 3D scenes (`ThreeDScene`)

**Why it fits bencher:** Manim can produce animated visualizations of how benchmark
results change across parameter sweeps — something static plots and basic video
composition cannot do well. It excels at:

- Animated parameter sweep walkthroughs (morphing curves as parameters change)
- 3D surface animations with camera rotation
- Annotated mathematical explanations of benchmark results
- Publication-quality renders with consistent styling

---

## Implementation Plan

### Phase 1: ComposableContainerManim

**Goal:** A new composable container that builds Manim scenes from images/clips, parallel
to `ComposableContainerVideo` (MoviePy) and `ComposableContainerPanel`.

**Files to create/modify:**

1. **`bencher/results/composable_container/composable_container_manim.py`** (new)

   ```python
   @dataclass
   class ManimRenderCfg:
       compose_method: ComposeType = ComposeType.sequence
       quality: str = "medium_quality"  # low/medium/high/fourk
       fps: int = 30
       background_color: str = "#FFFFFF"
       duration: float = 10.0

   @dataclass
   class ComposableContainerManim(ComposableContainerBase):
       def append(self, obj):
           # Accept: file paths (png/mp4), numpy arrays, Manim Mobjects
           ...

       def render(self, render_cfg: ManimRenderCfg = None) -> str:
           # Build a Manim Scene programmatically
           # Compose items based on compose_method:
           #   right/down → Group/VGroup arrangement
           #   sequence → successive animations (FadeIn/FadeOut or Transform)
           #   overlay → Group with opacity
           # Render to video file, return path
           ...

       def to_video(self, render_cfg=None) -> str:
           # Render and return video file path (same interface as Video container)
           ...
   ```

2. **`bencher/results/composable_container/__init__.py`** — Add import for new container

3. **`bencher/__init__.py`** — Export `ComposableContainerManim`, `ManimRenderCfg`

**Key design decisions:**
- Manim is an **optional dependency** — import guarded with try/except, graceful
  fallback error message if not installed
- Same `append()` / `render()` / `to_video()` interface as `ComposableContainerVideo`
- Users can drop it in wherever they currently use `ComposableContainerVideo`

---

### Phase 2: Manim Plot Result Classes

**Goal:** Result classes that render xarray benchmark data as Manim animations instead of
HoloViews plots.

**Files to create:**

4. **`bencher/results/manim_results/manim_result_base.py`** (new)

   Base class providing shared Manim rendering infrastructure:

   ```python
   class ManimResultBase(BenchResultBase):
       """Base class for Manim-rendered benchmark results."""

       def _build_manim_axes(self, dataset, x_var, y_var):
           """Create Manim Axes from dataset bounds."""
           ...

       def _dataset_to_manim_graph(self, dataset, result_var, axes):
           """Plot dataset values onto Manim axes."""
           ...

       def _render_scene(self, scene_builder_fn, quality="medium_quality"):
           """Execute a scene builder function, render to file, return path."""
           ...

       def _wrap_as_panel(self, video_path):
           """Wrap rendered video in pn.pane.Video for Panel integration."""
           return pn.pane.Video(video_path)
   ```

5. **`bencher/results/manim_results/manim_curve_result.py`** (new)

   Animated curve plots — the Manim equivalent of `CurveResult`:

   ```python
   class ManimCurveResult(ManimResultBase):
       def to_plot(self, result_var=None, override=True, **kwargs):
           return self.filter(
               self.to_manim_curve_ds,
               float_range=VarRange(1, 1),
               cat_range=VarRange(0, None),
               repeats_range=VarRange(1, None),
               reduce=ReduceType.REDUCE,
               target_dimension=2,
               result_var=result_var,
               result_types=(ResultVar,),
               override=override,
               **kwargs,
           )

       def to_manim_curve_ds(self, dataset, result_var, **kwargs):
           # Build Manim Scene with Axes + animated curve
           # If categorical vars: animate transform between curves (one per category)
           # If over_time: animate temporal progression
           # Return pn.pane.Video wrapping rendered mp4
           ...
   ```

6. **`bencher/results/manim_results/manim_bar_result.py`** (new)

   Animated bar charts with bars growing/morphing:

   ```python
   class ManimBarResult(ManimResultBase):
       # filter: float_range=(0,0), cat_range=(0,None)
       # Bars animate in with GrowFromEdge
       # Category changes animate with Transform
       ...
   ```

7. **`bencher/results/manim_results/manim_surface_result.py`** (new)

   3D surface visualization with camera animation (replaces Plotly for animated 3D):

   ```python
   class ManimSurfaceResult(ManimResultBase):
       # Uses ThreeDScene, Surface mobject
       # filter: float_range=(2, 2)
       # Camera orbits the surface
       ...
   ```

8. **`bencher/results/manim_results/__init__.py`** (new)

**Integration with BenchResult:** These are NOT added to the default `BenchResult` MRO.
Instead, users opt in via the `to()` method:

```python
result.to(ManimCurveResult)     # Explicit Manim rendering
result.to(ManimBarResult)
result.to(ManimSurfaceResult)
```

This avoids breaking existing behavior and keeps Manim as an optional backend.

---

### Phase 3: ResultManim Variable Type

**Goal:** A new result variable type for storing Manim Scene objects directly from
benchmark functions.

**Files to modify:**

9. **`bencher/variables/results.py`** — Add `ResultManim`

   ```python
   class ResultManim(param.Parameter):
       """Stores a rendered Manim animation file path."""
       __slots__ = ["units", "quality"]

       def __init__(self, units="animation", quality="medium_quality", **params):
           super().__init__(**params)
           self.units = units
           self.quality = quality

       def hash_persistent(self):
           return _hash_slots(self)
   ```

   Add to `PANEL_TYPES` so it renders via `pn.pane.Video`.

This allows benchmark functions to return Manim animations as results:

```python
class MyBenchmark(bn.ParametrizedSweep):
    x = bn.FloatSweep(default=1.0, bounds=(0, 10))
    animation = bn.ResultManim(doc="Animated visualization")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        # Build and render a Manim scene
        self.animation = build_manim_animation(self.x)
        return super().__call__()
```

---

### Phase 4: Examples and Documentation

**Files to create:**

10. **`bencher/example/example_manim_curve.py`** — Basic animated curve sweep
11. **`bencher/example/example_manim_surface.py`** — 3D animated surface
12. **`bencher/example/example_manim_composable.py`** — ComposableContainerManim demo

**Generated examples** (via `generate_examples.py`):

13. Register in `bencher/example/meta/generate_examples.py` with section prefix `manim_`
14. Output directory: `bencher/example/generated/manim/`
15. Examples:
    - `manim_curve_1float.py` — Single float sweep animated curve
    - `manim_bar_categorical.py` — Categorical bar chart animation
    - `manim_surface_2float.py` — 3D surface with camera orbit
    - `manim_composable_sequence.py` — Composable container sequence
    - `manim_composable_right.py` — Side-by-side Manim composition

**Documentation:**

16. Update `docs/intro.md` — Mention Manim backend in backends section
17. Add `docs/backends/manim.md` — Dedicated Manim backend guide
18. Update `docs/conf.py` — Include new doc pages

---

### Phase 5: Testing

**Files to create:**

19. **`test/test_manim_backend.py`** — Unit tests for:
    - `ComposableContainerManim` append/render/to_video
    - `ManimCurveResult` / `ManimBarResult` / `ManimSurfaceResult` filter + render
    - `ResultManim` hash_persistent
    - Graceful failure when manim not installed

20. **`test/test_manim_integration.py`** — Integration tests running example files

---

### Phase 6: Dependency Management

**Files to modify:**

21. **`pyproject.toml`** — Add optional dependency group:

    ```toml
    [project.optional-dependencies]
    manim = ["manim>=0.18.0"]
    ```

    Add pixi feature/environment for manim:

    ```toml
    [feature.manim.dependencies]
    manim = ">=0.18.0"
    ```

---

## File Summary

| # | File | Action | Phase |
|---|---|---|---|
| 1 | `bencher/results/composable_container/composable_container_manim.py` | Create | 1 |
| 2 | `bencher/results/composable_container/__init__.py` | Modify | 1 |
| 3 | `bencher/__init__.py` | Modify | 1 |
| 4 | `bencher/results/manim_results/manim_result_base.py` | Create | 2 |
| 5 | `bencher/results/manim_results/manim_curve_result.py` | Create | 2 |
| 6 | `bencher/results/manim_results/manim_bar_result.py` | Create | 2 |
| 7 | `bencher/results/manim_results/manim_surface_result.py` | Create | 2 |
| 8 | `bencher/results/manim_results/__init__.py` | Create | 2 |
| 9 | `bencher/variables/results.py` | Modify | 3 |
| 10-12 | `bencher/example/example_manim_*.py` | Create | 4 |
| 13-15 | `bencher/example/generated/manim/` | Create (generated) | 4 |
| 16-18 | `docs/` | Create/Modify | 4 |
| 19-20 | `test/test_manim_*.py` | Create | 5 |
| 21 | `pyproject.toml` | Modify | 6 |

## Architecture Diagram

```
User Benchmark Function
        │
        ▼
   ParametrizedSweep (defines inputs + ResultManim / ResultVar / ...)
        │
        ▼
   Bench.run_sweep() → Cartesian product → xarray.Dataset
        │
        ├──── Existing path: BenchResult.to_auto() → HoloViews/Plotly/Panel
        │
        └──── New Manim path:
              │
              ├── result.to(ManimCurveResult)  ─┐
              ├── result.to(ManimBarResult)     ─┤ Opt-in via to()
              └── result.to(ManimSurfaceResult) ─┘
                       │
                       ▼
                  ManimResultBase
                       │
                  ┌────┴────┐
                  │ filter() │ ← dimension constraints (same as HoloViews results)
                  └────┬────┘
                       │
                  Build Manim Scene programmatically from xarray data
                       │
                  Render → MP4/WebM file
                       │
                  Wrap in pn.pane.Video → Panel integration
```

```
ComposableContainerManim (user-facing, in benchmark __call__):

  vid = bn.ComposableContainerManim()
  vid.append(image_or_mobject)    # per-frame or per-item
  vid.append(...)
  self.animation = vid.to_video(ManimRenderCfg(
      compose_method=bn.ComposeType.sequence,
      quality="medium_quality",
  ))
```

## Key Design Principles

1. **Optional dependency** — Manim is heavy; guard all imports, fail gracefully
2. **Same interfaces** — Follow existing `filter()` + `ComposableContainer` patterns exactly
3. **Opt-in, not default** — Manim results accessed via `result.to(ManimCurveResult)`,
   not added to `to_auto()` by default (too slow for default rendering)
4. **Panel-compatible output** — All Manim results ultimately produce `pn.pane.Video`,
   so they integrate with existing Panel dashboards
5. **Leverage the grammar** — Manim results respect the same type-driven dimension
   constraints as HoloViews results; no special-casing needed
6. **Composable** — `ComposableContainerManim` supports all 4 compose types
   (right/down/sequence/overlay) using Manim's `Group`/`VGroup`/animation primitives
