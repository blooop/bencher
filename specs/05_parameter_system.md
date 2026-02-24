# 05 - Parameter System

Built on the `param` library. All classes live in `bencher/variables/`.

## SweepBase (`variables/sweep_base.py:50`)

Abstract base class for all sweep types. Inherits from `param.Parameter`.

Key methods:
- `values()` — abstract: generate sample values from bounds and sample count
- `hash_persistent()` — SHA1 hash avoiding PYTHONHASHSEED randomization
- `with_samples(n)` / `with_sample_values(vals)` / `with_const(val)` — deep-copy variants
- `with_level(lvl)` — level-based adaptive sampling (0→1, 1→2, 2→3, 3→5, 4→9, 5→17, 6→33...)
- `as_dim()` — converts to HoloViews `Dimension` for plotting

## Sweep Types

### Numeric
| Type | File:Line | Parent(s) | `values()` behavior |
|------|-----------|-----------|---------------------|
| `IntSweep` | `inputs.py:431` | `param.Integer, SweepBase` | Integers from bounds or explicit `sample_values` list |
| `FloatSweep` | `inputs.py:508` | `param.Number, SweepBase` | `np.linspace` (default) or `np.arange` (if step set) |

Factory: `box(name, center, width)` → `FloatSweep` with bounds `(center-width, center+width)`

### Categorical (via `SweepSelector` base, `inputs.py:27`)
| Type | File:Line | Notes |
|------|-----------|-------|
| `BoolSweep` | `inputs.py:153` | Objects: `[True, False]` or `[False, True]` (default first) |
| `StringSweep` | `inputs.py:177` | Accepts `string_list`; has `StringSweep.dynamic()` factory |
| `EnumSweep` | `inputs.py:241` | Accepts Enum type or list of enum values |
| `YamlSweep` | `inputs.py:332` | Loads YAML file, exposes top-level keys as sweep choices |

### Time (`variables/time.py`)
- `TimeSnapshot` — continuous datetime, classified as **float** for plotting
- `TimeEvent` — discrete event label (e.g., git commit tag), classified as **categorical**

## ParametrizedSweep (`variables/parametrised_sweep.py:13`)

Base class users subclass to define benchmark configurations. Inherits `param.Parameterized`.

**Parameter discovery**: `get_input_and_results()` (class method) inspects class attributes to separate sweep types from result types.

**Callable**: Implements `__call__()` returning a dict of result values. `update_params_from_kwargs()` sets instance params from dict.

**Hashing**: `param_hash()` (static) computes SHA1 of parameter name + value + metadata. `hash_persistent()` hashes all parameters.

**Convenience**: `to_bench()` and `to_bench_runner()` create framework instances (via `factories.py` lazy imports).

## Result Types (`variables/results.py`)

| Type | Parent | Purpose |
|------|--------|---------|
| `ResultVar` | `param.Number` | Scalar numeric result with `OptDir` (minimize/maximize/none) |
| `ResultBool` | `param.Number` | Boolean result in [0,1] |
| `ResultVec` | `param.List` | Fixed-size vector result |
| `ResultHmap` | `param.Parameter` | HoloViews HoloMap return |
| `ResultPath` | `param.Filename` | File path |
| `ResultVideo` | `param.Filename` | Video file path |
| `ResultImage` | `param.Filename` | Image file path |
| `ResultString` | `param.String` | String value |
| `ResultContainer` | `param.Parameter` | Generic Panel container |
| `ResultReference` | `param.Parameter` | Non-picklable object reference |
| `ResultDataSet` | `param.Parameter` | Dataset/reference |
| `ResultVolume` | `param.Parameter` | 3D volume data |

**Type collections** (`results.py:242-276`): `PANEL_TYPES` (direct Panel rendering), `XARRAY_MULTIDIM_RESULT_TYPES` (N-D xarray storage), `ALL_RESULT_TYPES` (complete union for discovery).

## Parameter Type → Plot Type Mapping

| Input Type(s) | Result Type | Default Plot |
|---------------|-------------|-------------|
| 0 float, 0+ cat | ResultVar/ResultBool | Scatter |
| 1 float, 0+ cat | ResultVar/ResultBool | Line |
| 2+ inputs (any mix) | ResultVar/ResultBool | Heatmap |
| 3 float, 0 cat | ResultVar | Volume (3D) |
| 2+ float, 0+ cat | ResultVar | Surface (3D) |
| Any, repeats > 1 | ResultVar/ResultBool | BoxWhisker/Violin/ScatterJitter |
| Any | ResultImage/ResultVideo | VideoSummary |
| Any | ResultDataSet | DataSet viewer |

> Plot selection is additive — multiple plot types can match the same configuration.
