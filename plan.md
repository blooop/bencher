# Plan: Fix HTML Embed Efficiency for Window Size Slider

## Problem

The 2D HoloMap (`over_time` x `window_size`) causes Panel's `embed=True` HTML saving
to pre-render **every state** into the HTML. With N time points and max_time_window=15,
that's N*K embedded Bokeh plot states vs. the previous N — a ~15x increase in HTML file
size. Each Bokeh state is a full JSON spec (50-100KB+), so files that were 1-2MB can
balloon to 15-30MB.

For `_build_time_holomap_raw` (distribution plots) it's worse — each state embeds
concatenated raw samples, not just aggregated stats.

The save path at `bench_report.py:119` calls:
```python
content.save(filename=index_path, progress=True, embed=True)
```

## Strengths of Current PR

- Clean refactoring: reusable `_build_time_holomap` / `_build_time_holomap_raw` helpers
- Correct use of law of total variance for pooling std values
- Generic `make_plot_fn` callback pattern works across bar/line/heatmap/curve/distribution

## Possible Mitigations

### Option 1: Client-side JS computation (ideal long-term)
Keep the HoloMap 1D (over_time only), embed all raw time-point data once, and have a
JS-side slider that computes the rolling average in the browser. HTML size stays O(N)
instead of O(N*K). More work, but optimal for static HTML.

### Option 2: DynamicMap for window_size dimension
A `DynamicMap` generates plots on-demand instead of pre-materializing. Works great in a
live Panel server but **does not embed into static HTML**, so only helps for
`bch.run(show=True)`, not `save=True`.

### Option 3: Reduce default max_time_window
Currently 15. Dropping to 5 reduces embed cost from 15x to 5x. Consider
`min(n_time, 5)` by default, or auto-scaling.

### Option 4: Fall back to 1D HoloMap for static HTML (lowest effort)
When saving to HTML, use the old 1D HoloMap behavior (window_size=1). Only add the
window_size dimension when serving interactively. This preserves the feature for live
use while keeping HTML files small.

## Additional Issues to Address

### Computational inefficiency in `_apply_rolling_window`
Called once per window size K, each time copies the entire dataset and Python-loops over
all time points. xarray's built-in `.rolling()` does this in one line and is vectorized:
```python
dataset[mean_var].rolling(over_time=k, min_periods=1).mean()
```
This would replace ~20 lines and be significantly faster.

### `_build_time_holomap_raw` nested loop
For each (k, t) pair it calls `da.isel(over_time=slice(...))` then `make_plot_fn` which
converts to a DataFrame. With large raw datasets this is a lot of repeated slicing +
conversion.

### Non-reproducible example
`example_git_time_event.py` uses `random.gauss` without seeding. Consider
`random.seed(42)` for reproducible results and non-flaky tests.

### Class attribute mutation
`ServerLatency.drift = 0.0` is a class attribute mutated per-instance. Consider making
it a `param.Number` or an `__init__` parameter.

## Recommendation

Option 4 (fall back to 1D for static HTML, keep 2D for live serving) is the lowest-effort
fix. Option 1 (JS-side computation) is the ideal long-term solution.
