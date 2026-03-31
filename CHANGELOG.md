# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Deprecated `__call__()` in favor of `benchmark()`**: `ParametrizedSweep` subclasses should now override `benchmark()` instead of `__call__()`. The new method removes the need for `self.update_params_from_kwargs(**kwargs)` and `return super().__call__()` boilerplate. The old `__call__()` pattern still works but emits a `DeprecationWarning`.

## [1.75.2] - 2026-03-31

### Fixed
- `.rrd` iframe URLs no longer hardcode `localhost:8051` — CDN viewer uses relative URLs, local/hosted viewer resolves `window.location.origin` at render time via JavaScript, so reports work behind container port mappings and on any Panel server port (#866)
- Panel server uses `port=0` (OS-assigned) when no explicit port is given, preventing `OSError: Address already in use` when other services occupy the default port (#866)
- `_cdn_viewer_versions` cache collision between `_cdn_viewer_url` (filenames) and `_get_cdn_viewer_html` (HTML strings) — split into separate caches (#866)

### Changed
- `show=True` in `BenchRunner.run()` now auto-saves a static HTML report to `reports/` alongside the live server, with the path logged for offline viewing (#866)

### Removed
- `PANEL_PORT` constant from `utils_rrd` — no longer needed since iframe URLs are resolved dynamically (#866)

## [1.74.0] - 2026-03-28

### Added
- **Cartesian Product Animations**: New PIL-based animation system that visualizes how parameter sweep dimensions build upon each other (point → line → grid → stack → film strip) (#feature/manim_summary)
- `BenchCfg.to_cartesian_animation()` method for rendering dimensional progression animations
- Automatic animation embedding in sweep descriptions via `BenchCfg.describe_sweep()`
- `CartesianProductCfg` and `CartesianProductScene` classes for animation configuration and rendering
- `bencher.results.manim_cartesian` module with Shape, StrobeShape, and TimelineShape classes
- **Complete Usage Guide**: New comprehensive `docs/how_to_use_bencher.md` documentation covering sweep types, result types, and best practices
- Tab bar sweep example (`example_tab_bar_sweep.py`) demonstrating UI layout testing with PIL rendering
- Meta example generation system for creating animation galleries
- 10-color pastel palette for dimensional visualization with proper contrast on white backgrounds
- Film strip metaphor for `over_time` dimension with sprocket holes and frame labels
- Strobe/flash animation for `repeat` dimension with tally mark counters

### Changed 
- **Dark Theme Tab Bar**: Report tabs now use dark background with improved contrast and sticky positioning
- Tab bar styling updated with rounded corners, better spacing, and proper hover states
- Meta example generation now includes animation examples in advanced gallery
- Animation rendering uses unique filenames to prevent file path collisions
- Improved tally mark visuals with thicker strikethrough, larger fonts, and centered labels

### Fixed
- Animation filepath collisions resolved with unique filename generation based on animation parameters
- ListProxy pickle serialization issues for multiprocessing compatibility
- Animation size optimization for better performance and smaller file sizes

## [1.73.1] - 2026-03-27

### Fixed
- Generate optimisation reports for all benchmarks, not just the last (#852)
- Include time event in over_time panel labels and default to last (#849)
- Wrap long description strings in generated examples to fit 100-char line limit (#851)
- Override RTD theme CSS to wrap long lines in docs code blocks (#851)

## [1.73.0] - 2026-03-26

### Added
- `bn.sweep()` API with `bounds=(low, high)` support as the unified replacement for `bn.p()` — `bn.p()` still works but emits a `DeprecationWarning` (#838)
- `SweepBase.__call__()` for concise, type-safe sweep configuration: `Cfg.param.theta([0, 0.5, 1.0])` or `Cfg.param.theta(samples=5)` (#838)
- `SweepBase.with_bounds()` for overriding sweep ranges immutably (#838)
- Dict and inline-dict shorthand for `input_vars` in `plot_sweep`: `{"theta": [0, 0.5, 1.0]}`, `{"theta": 5}`, `{"theta": None}` (#842)
- `atexit` handler to stop Panel servers on exit, preventing process hangs after `bn.run(show=True)` (#841)
- Interactive prompt in terminal mode — press Enter to stop servers after viewing results (#841)
- SIGTERM handler chaining — lazily installed only when servers are created, chains to previous handler instead of calling `sys.exit()` (#841)
- `over_time` parameter on `bn.run()` and `BenchRunner.run()` — enables time-series benchmarking without manually creating a `BenchRunCfg` (#848)
- 2-float 2-categorical aggregation example (`agg_list_2_cat`) demonstrating `aggregate=["direction", "scale"]` on a `GradientSurface` class (#845)

### Changed
- `FloatSweep`/`IntSweep` now store user-supplied bounds as param `softbounds` instead of hard bounds, so values outside the defined sweep range are no longer rejected by `update_params_from_kwargs` (#838)
- `BenchRunCfg.with_defaults()` returns a deep copy and merges defaults into caller-provided configs instead of ignoring them (#840)
- `BenchRunCfg.with_defaults()` raises `ValueError` for unknown parameter names to catch typos early (#840)
- Rename `test/test_bn_p.py` to `test/test_sweep_helper.py` to match new `bn.sweep()` API
- Generated over_time examples now pass `over_time=True` via `bn.run()` kwargs instead of setting `run_cfg.over_time` inside the function body (#848)

### Fixed
- `bn.p()` now raises `ValueError` when `max_level` is used with `SweepBase` objects, which require `run_cfg.level` at execution time (#838)
- `bn.sweep()` / `__call__()` reject combining explicit `values` with `bounds`/`samples` to prevent ambiguous configurations (#838)
- Server shutdown is exception-safe — a failing shutdown on one runner no longer prevents cleanup of remaining runners (#841)
- Shutdown errors are logged to stderr instead of silently swallowed (#841)
- Interactive prompt delayed to appear after async server startup logs (#841)
- Optuna plot failures now show diagnostic `Markdown` panels instead of silently swallowing exceptions (#847)
- `to_optuna_plots()` in `bn.run()` shows a diagnostic when `optimize()` returns `None` (#847)
- `logging.warning` when `dropna` removes all rows from optuna trial data (#847)

## [1.72.3] - 2026-03-24

### Fixed
- `aggregate` parameter in `plot_sweep` now produces the correct plot type for remaining dimensions (e.g. heatmap for 2 remaining floats) instead of always forcing a 1D band plot, collapsing all non-x dimensions

## [1.72.2] - 2026-03-23

### Changed
- `git_time_event()` now uses wall-clock time (`datetime.now()`) instead of commit date, producing labels like `"2024-06-15 14:59 abc1234"` so multiple runs on the same commit get distinct over_time labels
- `git_time_event()` uses `git rev-parse --short HEAD` for the canonical abbreviated SHA instead of hardcoded `[:8]` slicing
- `git_time_event()` falls back to `"<timestamp> unknown"` instead of just the timestamp when git is unavailable, keeping the label format consistent
- Removed the second subprocess call (`git log`) from `git_time_event()`, making it lighter for fork-sensitive environments
- Increased `wrap_long_time_labels` wrap width from 20 to 30 characters to accommodate the longer time-event label format
- Docstring documents the recommended import-time caching pattern for fork-safety in threaded environments (ROS 2, DDS, etc.)

### Performance
- Skip redundant dataset copy in `to_dataset()` for REDUCE/MINMAX paths (#826)
- Single-pass reduction avoids `xr.merge()` in `to_dataset()` (#824)
- Replace DataFrame groupby with xarray sel in curve overlay (#822)
- Batch cross-process hash tests into 2 subprocess invocations (#820)
- Add comprehensive `.save()` performance benchmark and report (#825)

## [1.72.1] - 2026-03-22

### Changed
- **Breaking:** `show_aggregated_time_tab` now defaults to `False`. The aggregated "All Time Points" tab doubled `report.save()` embed cost because Panel must pre-compute JSON patches for every slider position in both tabs. Users who need the aggregated view can set `show_aggregated_time_tab=True`. (#818)

### Added
- `report_save_ms` field on `SweepTimings` so downstream users can instrument `report.save()` cost

## [1.71.0] - 2026-03-21

### Added
- Bencher self-introspection: `SweepTimings` instruments `Bench.run_sweep()` to measure phase-level overhead (dataset setup, job submission, execution, cache checks, etc.) (#793)
- `example_self_benchmark` and `example_self_benchmark_over_time` examples for profiling bencher's own overhead (#793)

### Changed
- Rename import alias convention from `import bencher as bch` to `import bencher as bn` across all examples and tests
- Rename `test/test_bch_p.py` to `test/test_bn_p.py`
- Update AST check in `generate_examples.py` to match new `bn` alias

### Fixed
- Fix `ValueError` crash in `to_optuna_plots()` when `over_time=True` — `TimeSnapshot` param conversion only handled `np.datetime64` but pandas returns `pd.Timestamp` (#792)
- Fix `summarise_optuna_study` for single-objective studies — no longer calls `plot_pareto_front` which requires ≥2 objectives (#795)
- Fix `summarise_optuna_study` for multi-objective studies — passes explicit `target` callbacks to `plot_optimization_history` (#795)
- Fix `sweep_var_to_suggest` fall-through for TimeSnapshot/TimeEvent — now explicitly returns `None` instead of raising `ValueError` (#796)
- Auto-compute `total_ms` in `SweepTimings` and add `inspect` fallback (#796)

## [1.70.4] - 2026-03-20

### Fixed
- Fix curve plots using string-typed over_time (TimeEvent) as x-axis instead of the float input variable — explicitly set kdims in `to_curve_ds` to match `to_line_ds` behavior
- Classify TimeEvent as continuous in plot config so it is treated like TimeSnapshot for plotting
- Add TimeEvent support in optuna conversions and trial building

### Removed
- Remove vestigial `iv_time_event` field from BenchCfg (was never populated)

## [1.70.2] - 2026-03-20

### Fixed
- Fix band plots sharing axes across different metrics
- Fix plot server not working with container port forwarding

## [1.70.1] - 2026-03-19

### Fixed
- Fix over_time slider starting at first position instead of last in embedded HTML — Panel's `DiscreteSlider` sets the Bokeh `Slider.title` to `''`, so the JS that matched by `title === "over_time"` never found the slider; now uses Panel State model's widgets map to reliably locate the slider

## [1.66.3] - 2026-03-14

### Fixed
- Force `DiscreteSlider` widget for the `over_time` dimension so string-based `TimeEvent` coordinates get a slider instead of a dropdown

## [1.66.2] - 2026-03-13

### Fixed
- Fix over_time bar chart broken by unconditional image slider routing — numeric `ResultVar` types were incorrectly routed to `_pane_over_time_slider`, causing `FileNotFoundError` and `ValueError`

## [1.66.1] - 2026-03-13

### Fixed
- Fix `DTypePromotionError` crash when `over_time` coordinate type changes between runs (e.g., `time_event=None` → `time_event="v1.0"`)
- Check `over_time` dtype compatibility before concat, discarding incompatible history with a warning instead of crashing
- Include old/new dtypes in the warning message for easier debugging

## [1.66.0] - 2026-03-12

### Added
- Over-time slider support for BarResult: bar charts now show a time slider when `over_time=True` with multiple time points
- Over-time slider support for DistributionResult (BoxWhisker, Violin): distribution plots now show a time slider when `over_time=True` with multiple time points
- New meta-generated examples combining `over_time=True` with `repeats>1` for 0-1 float input configurations
- Tests for over_time + repeats across bar, distribution, and curve plot types

## [1.65.0] - 2026-03-11

### Fixed
- Fix non-deterministic `hash_persistent()` in 9 result variable classes that broke `over_time` history cache lookups across process invocations
- Fix `ResultVec.hash_persistent()` not including `size` in hash, causing cache key collisions for vectors of different sizes
- Add `_hash_slots()` helper that hashes all `__slots__` by default, with explicit `_hash_exclude` for non-deterministic runtime attributes (`obj`, `container`)
- Add comprehensive auto-discovery tests that will catch any future Result class missing deterministic hashing

## [1.64.0] - 2026-03-11

### Added
- `init_singleton()` now returns a context manager that auto-resets singleton state when first-time init raises, eliminating manual `_seen`/`_instances` cleanup boilerplate
- `reset_singleton()` public classmethod for explicitly clearing singleton state
- Thread-safe singleton operations via internal `threading.Lock`
- Full backward compatibility preserved — `if self.init_singleton():` works identically

## [1.63.0] - 2026-03-09

### Fixed
- Over-time slider now correctly defaults to the most recent time point instead of the first (#756)
- Fixed `DiscreteSlider` dict options handling — `list(w.options)` returned string keys instead of actual values, causing the slider to silently fall back to the first time point
- Added guard against empty widget options to prevent `IndexError`
- Narrowed slider default logic to only target the `over_time` widget, avoiding unintended side effects on other widgets

## [1.62.0] - 2026-03-06

### Added
- Over-time slider for visualizing benchmark results across time steps (#729, #730)
- Single-page scrollable gallery overview with CSS grid cards (#731)
- Feature-specific meta generators for result types, plot types, optimization, sampling, const vars, and statistics (#732)
- `bch.run()` API for simplified benchmark execution (#732)
- Inline rerun viewer support with `rerun_to_pane()` (#717)
- Prebuilt devcontainer image support via GHCR (#136)
- 3D visualization example
- Image, video, and volume plot type examples (#747)
- Full `ComposeType` support across all composable container backends (#746)
- Composable container gallery examples (#746)

### Changed
- Replaced notebook pipeline with Python examples + HTML reports (#734)
- Consolidated generated examples from `meta/generated/` to `example/generated/` and tracked in Git (#735)
- Updated rerun-sdk from 0.29.x to 0.30.1 (#725)
- Replaced `rerun.legacy_notebook` with `rerun_notebook.Viewer`
- Gallery now uses real iframe thumbnails with auto-crop via ResizeObserver
- Skip Tabs sidebar for single-tab reports
- Notebook generation is now fully deterministic across runs
- Updated meta generator `__main__` blocks to use `bch.run()`
- Switched gallery thumbnails from selenium+Firefox to playwright+Chromium (#741)
- Consolidated result types into a single gallery section with sub-headings (#748)
- Improved const vars documentation examples (#749)
- Improved statistics examples to showcase distinct bencher features (#751)

### Fixed
- Panel server dying on `bch.run(show=True)` (#732)
- Widget location fixed by wrapping HoloMaps in `pn.pane.HoloViews` (#730)
- Parameterized sweep benchmark naming when param counter exceeds 5 digits
- Over-time rendering for heatmap/line plots
- `const_vars` hash not chaining accumulated `hash_val` (#723)
- RTD build configuration for Playwright dependencies
- Over-time scrubber not appearing in static HTML
- Surface plot 3D rendering using xarray DataArray directly instead of pivot_table (#747)
- Gallery thumbnails broken on ReadTheDocs (#741)
- Overlay duration bug in composable containers (#746)
- apt package name `libasound2` → `libasound2t64` for Ubuntu 24.04

### Dependencies
- Bumped `rerun-sdk` and `rerun-notebook` to >= 0.30.1
- Updated `actions/checkout` from 4 to 6
- Updated `prefix-dev/setup-pixi` from 0.9.3 to 0.9.4
- Various dependency updates via Dependabot

## [1.60.0] - 2026-01-24

### Changed
- Updated numpy version constraint from `<=2.2.6` to `<=2.4.1` to support latest numpy releases
- Updated all dependencies to latest compatible versions through pixi update

### Fixed
- Resolved historical hvplot compatibility issues with numpy 2.x that were preventing updates

### Technical Details
- The numpy version limitation was due to binary compatibility issues between numpy 2.0 and hvplot that occurred when numpy 2.0 was released in June 2024
- These issues have been fully resolved in the ecosystem, with hvplot 0.12.2 now fully compatible with numpy 2.4.x
- All tests pass successfully with the updated dependencies

## [0.3.10]

Before changelogs
