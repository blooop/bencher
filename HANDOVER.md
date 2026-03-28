# Handover: Cartesian Product Animation for Bencher

## Goal

Create an animated GIF that visualizes bencher's Cartesian product data collection method. The animation is embedded in every sweep report (via `describe_sweep()` in `bench_cfg.py`) to give users a conceptual overview of how their parameter dimensions combine.

## Core Concept: Dimensional Extrusion

The animation shows how each dimension builds on the last:

```
point --dim1--> line --dim2--> grid --dim3--> sets of grids --dim4--> sets of sets ...
```

- Each step is labeled with the dimension name
- A running combination count is shown
- Directions alternate right/down for spatial dims to show nesting
- `over_time` is rendered distinctly as a horizontal timeline with an arrow
- No actual data values are shown — this is a conceptual overview of dimensionality

## What Was Built

### New files under `bencher/results/manim_cartesian/`:

| File | Purpose |
|------|---------|
| `__init__.py` | Exports `CartesianProductCfg`, `SweepVar`, `from_bench_cfg`, `render_animation` |
| `cartesian_product_cfg.py` | Data model: `SweepVar`, `CartesianProductCfg`, `from_bench_cfg()`. Pure Python, no rendering deps. Truncates dimensions to 5 values max (matching LaTeX summary). Uses `all_vars` (includes repeat, over_time — they are full dimensions). |
| `cartesian_product_scene.py` | Frame renderer using PIL + moviepy. Contains `Shape` class (recursive structure), `TimelineShape` (over_time arrow), `render_animation()` function. Outputs GIF. |
| `dimension_layout.py` | Currently unused legacy file from manim approach. Can be deleted. |
| `visual_elements.py` | Currently unused legacy file from manim approach. Can be deleted. |

### Modified files:

| File | Change |
|------|--------|
| `bencher/bench_cfg.py` | Added `to_cartesian_animation()` method and GIF embedding in `describe_sweep()` |
| `pyproject.toml` | Added optional `manim` dependency group (no longer needed — could be removed) |

### Test file:
- `test/test_manim_cartesian.py` — Tests data model classes. Render tests reference old manim-based `CartesianProductScene` class and need updating.

### Example file:
- `bencher/example/example_cartesian_animation.py` — References old manim API, needs updating.

## Current State

### What works:
- GIF renders in ~0.5-1.5s for typical 3-5D sweeps
- Embedded in sweep reports via `describe_sweep()` → `pn.pane.Image`
- Dimensional extrusion animation: point → line → grid → grouped grids
- Alternating right/down directions for spatial dims
- Hierarchical gaps: inner grid is tight, outer groupings have increasing spacing
- `over_time` rendered as horizontal timeline with arrow and t0/t1/t2 labels
- Dimensions capped at 5 values for visual clarity
- Combination count shown persistently (no flickering)
- Uses only PIL (already a bencher dep) — no manim needed for rendering
- Output goes to `cachedir/manim/` (gitignored)

### Known issues / next steps:

1. **Clean up dead files** — `dimension_layout.py` and `visual_elements.py` are leftover from the manim-based approach. They can be deleted or repurposed.

2. **Update tests** — `test/test_manim_cartesian.py` has data model tests (passing) but render tests reference the old manim `CartesianProductScene` class. Need to update to test `render_animation()` instead.

3. **Update example** — `example_cartesian_animation.py` references old manim API.

4. **Remove manim optional dep** — `pyproject.toml` still has `manim = ["manim>=0.18.0,<1.0"]` in optional-dependencies. No longer needed since we use PIL+GIF.

5. **GIF file naming** — Currently all sweeps write to the same `cachedir/manim/cartesian_product.gif`. Should include a hash or sweep name to avoid overwrites when multiple sweeps run.

6. **Visual polish** — The user has been iterating on the visual style. Key feedback so far:
   - Keep it conceptual, not detailed (no data values, no axis labels)
   - Dimensions should alternate x/y directions
   - over_time must always be left-to-right and visually distinct
   - Hierarchical gaps between sets of sets are important
   - Text should not be obscured by video controls (solved by using GIF)
   - Rendering must be fast (solved — <2s)

7. **The directory is still called `manim_cartesian`** — could be renamed since manim is no longer used.

## Architecture Decisions

- **PIL + GIF over manim**: Manim was tried first but was orders of magnitude too slow (~60s+ for simple scenes due to per-frame ffmpeg stitching). PIL renders frames as images and saves directly as GIF in <2s.
- **`all_vars` not `input_vars`**: repeat and over_time are full dimensions of the Cartesian product, not secondary. User explicitly corrected this.
- **Truncation at 5 values**: Matches the LaTeX summary's `format_values_list` approach. Higher counts show first 2, gap marker, last 2.
- **`from_bench_cfg()` bridges BenchCfg → CartesianProductCfg**: Same extraction pattern as `DimsCfg.__init__` in `bench_cfg.py:790-810`.

## Key User Feedback (saved in memory)

- Meta vars (repeat, over_time) are core dimensions — always include them
- User runs examples themselves — don't run them
- Iterate visually before running CI
- Keep deepcopy guards for mutation safety
