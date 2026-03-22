# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
