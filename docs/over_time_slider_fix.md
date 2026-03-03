# Fix: over_time slider conflict across report tabs

## Problem

When multiple `over_time` results (0D, 1D, 2D, 3D) are rendered in the same
HTML report, the slider widgets interfere with each other. Only one tab's
slider actually updates its plot; the others appear frozen.

## Root cause

Panel's `save(embed=True)` pre-computes all widget states and bakes them into
the HTML as static JSON. When the document contains multiple `hv.HoloMap`
objects:

- **Same `kdims` label** (e.g. all use `kdims=["over_time"]`): Panel merges
  them into a **single shared slider**. The slider only drives whichever
  HoloMap was last encountered during embedding; the other plots don't update.

- **Different `kdims` labels** (e.g. `"over_time_1D"`, `"over_time_2D"`):
  Panel creates separate sliders but computes the **Cartesian cross-product**
  of all widget values. With *k* sliders of *n* options each this produces
  *n^k* embedded states (exponential blowup). Worse, changing any one slider
  forces a global state switch that can break the others.

In short, Panel's embed mechanism cannot host multiple independent HoloMap
sliders in a single HTML document.

## Approaches tried

| Approach | Result |
|----------|--------|
| Make 1D line use explicit `hv.HoloMap` (same `kdims`) | Still one shared slider; last plot wins |
| Unique `kdims` names with same label | Panel ignores the name, uses the label — no change |
| Unique `kdims` labels | Cross-product explosion; only last slider works |
| Replace `hv.HoloMap` with `pn.bind` + `DiscreteSlider` | `pn.bind` doesn't embed states correctly for static HTML |
| `pn.pane.HoloViews(linked_axes=False)` | Embed skips the HoloViews pane entirely |

## Solution

Save each report tab to its own embedded HTML file, then generate a
lightweight index page with tab buttons and an `<iframe>`. Each tab's
HTML is a fully independent document with its own widget namespace, so
sliders never collide.

```
index.html          ← tab buttons + iframe
_tabs/
  over_time_0D.html ← self-contained embedded page
  over_time_1D.html
  over_time_2D.html
  over_time_3D.html
```

This approach:
- Requires **no changes** to HoloViews or Panel internals
- Scales to any number of tabs without cross-product blowup
- Preserves the existing slider UX within each tab

### Additional changes (may be optional)

The line and curve result classes were also updated to use explicit
`hv.HoloMap` construction for `over_time` (matching the pattern already
used by heatmap and bar). This prevents hvplot's implicit `groupby` widget
from being used, which could conflict with explicit HoloMap sliders within
the same tab. With the iframe isolation these changes may not be strictly
necessary, but they make the rendering more consistent across plot types.
