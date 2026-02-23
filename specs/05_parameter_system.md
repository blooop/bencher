# 05 - Parameter System

## Overview

The parameter system is built on the `param` library and defines how input variables (sweep parameters) and output variables (result types) are declared, sampled, and hashed. All classes live in `bencher/variables/`.

## SweepBase (`bencher/variables/sweep_base.py:50-165`)

Abstract base class for all sweep types. Inherits from `param.Parameter`.

### Shared Slots (`sweep_base.py:14`)
All sweep types share: `["units", "samples"]`

### Key Methods

| Method | Line | Purpose |
|--------|------|---------|
| `values()` | 57-65 | Abstract: generate sample values based on bounds and sample count |
| `hash_persistent()` | 67-69 | SHA1 hash avoiding PYTHONHASHSEED randomization |
| `sampling_str()` | 71-76 | Human-readable sampling description |
| `as_slider()` | 78-87 | Creates Panel slider widget from sweep values |
| `as_dim()` | 89-117 | Converts to HoloViews `Dimension` for plotting |
| `with_samples(n)` | 129-136 | Deep copy with new sample count |
| `with_sample_values(vals)` | 138-146 | Deep copy with explicit value list |
| `with_const(val)` | 148-157 | Create single-value constant sweep |
| `with_level(lvl)` | 159-164 | Level-based adaptive sampling (0,1,2,3,5,9,17,33...) |

### Helper Functions

- `hash_sha1(var)` (`bencher/utils.py:91-104`): Core hashing function using SHA1, supports `__bencher_hash__` protocol
- `describe_variable(var)` (`sweep_base.py`): Human-readable variable description

## Sweep Types

### Numeric Sweeps

#### IntSweep (`bencher/variables/inputs.py:431-506`)
- **Inherits**: `Integer, SweepBase`
- **Slots**: `shared_slots + ["sample_values"]`
- **Constructor**: `units="ul"`, `samples` (auto from bounds), `sample_values` (optional list)
- **`values()`** (472-487): Returns integers from bounds or `sample_values` list, respecting `samples` count
- **Validation**: `_validate_value()` (490-500) and `_validate_step()` (503-505) allow numpy int types

#### FloatSweep (`bencher/variables/inputs.py:508-562`)
- **Inherits**: `Number, SweepBase`
- **Slots**: `shared_slots + ["sample_values"]`
- **Constructor**: `units="ul"`, `samples=10`, `sample_values` (optional), `step` (optional)
- **`values()`** (546-561): Returns `np.linspace` (if no step) or `np.arange` values

#### `box()` factory (`bencher/variables/inputs.py:564-580`)
Creates centered `FloatSweep`: `box(name, center, width)` → bounds = `(center-width, center+width)`

### Selector-Based Sweeps

#### SweepSelector (`bencher/variables/inputs.py:27-151`)
- **Inherits**: `Selector, SweepBase`
- **Purpose**: Base for all categorical sweeps
- **`values()`** (50-56): Returns sampled subset of objects list
- **Dynamic loading**: Supports `LoadValuesDynamically` sentinel (`inputs.py:16-24`) for runtime value updates
- **Dynamic update methods** (61-150): `load_values_dynamically()`, `_ensure_nonempty()`, `_choose_default()`, `_update_instance_objects()`, `_sync_class_defaults()`, `_apply_owner_value()`

#### BoolSweep (`bencher/variables/inputs.py:153-174`)
- **Inherits**: `SweepSelector`
- **Constructor**: `units="ul"`, `samples=None`, `default=True`
- **Objects**: `[True, False]` or `[False, True]` (default first)

#### StringSweep (`bencher/variables/inputs.py:177-239`)
- **Inherits**: `SweepSelector`
- **Constructor**: accepts `string_list` parameter
- **Factory**: `StringSweep.dynamic()` (210-238) creates placeholder for dynamic population

#### EnumSweep (`bencher/variables/inputs.py:241-269`)
- **Inherits**: `SweepSelector`
- **Constructor**: accepts Enum type or list of enum values
- **Doc propagation**: Copies docstring from enum type definition

#### YamlSweep (`bencher/variables/inputs.py:332-429`)
- **Inherits**: `SweepSelector`
- **Slots**: `shared_slots + ["yaml_path", "_entries", "default_key"]`
- **Purpose**: Loads YAML mapping file, exposes top-level keys as sweep choices
- **Wrapper**: `YamlSelection` (`inputs.py:286-330`) wraps key-value pairs
- **Caching**: `_load_yaml()` (391-396) uses LRU cache; `_read_yaml()` (398-403) is static cached reader
- **Methods**: `keys()` (405), `items()` (409), `values()` (413), `key_for_value()` (417)

## ParametrizedSweep (`bencher/variables/parametrised_sweep.py:13-221`)

The core framework class that users subclass to define benchmark configurations.

### Inherits: `param.Parameterized`

### Parameter Discovery

| Method | Line | Purpose |
|--------|------|---------|
| `get_input_and_results()` | 57-81 | Class method returning namedtuple of `(input_params, result_params)` by inspecting class attributes |
| `get_inputs_only()` | 97-104 | Returns list of input `Parameter` objects (sweep types only) |
| `get_results_only()` | 137-144 | Returns list of result `Parameter` objects (result types only) |
| `get_input_defaults()` | 110-123 | Returns `[(param, default)]` with override support |
| `get_input_defaults_override()` | 125-135 | Returns dict of defaults merged with kwargs overrides |

### Sweep Building

| Method | Line | Purpose |
|--------|------|---------|
| `get_inputs_as_dict()` | 83-87 | Returns `{name: value}` for all input variables |
| `get_results_values_as_dict()` | 89-95 | Returns `{name: value}` for all result variables |
| `get_inputs_as_dims()` | 146-158 | Returns list of HoloViews Dimensions for interactive plots |
| `to_dynamic_map()` | 160-183 | Creates HoloViews DynamicMap for interactive exploration |
| `to_gui()` | 185-189 | Shows interactive Panel GUI |
| `to_holomap()` | 191-197 | Creates HoloViews HoloMap |

### Hash-Based Caching

| Method | Line | Purpose |
|--------|------|---------|
| `param_hash()` | 16-41 | Static method: SHA1 hash of parameter name + value + metadata |
| `hash_persistent()` | 43-45 | Instance method using `param_hash()` on all parameters |
| `update_params_from_kwargs()` | 47-55 | Updates instance parameters from dict |

### Convenience Methods

| Method | Line | Purpose |
|--------|------|---------|
| `__call__()` | 199-205 | Callable interface returning results dict |
| `to_bench()` | 210-212 | Creates `Bench` instance (via `factories.create_bench`) |
| `to_bench_runner()` | 214-220 | Creates `BenchRunner` instance (via `factories.create_bench_runner`) |

## ParametrizedSweepSingleton (`bencher/variables/singleton_parametrized_sweep.py:21-51`)

Singleton variant ensuring one instance per subclass.

- **Class variables**: `_instances` (dict), `_seen` (set)
- **`__new__()`** (32-35): Per-subclass singleton
- **`init_singleton()`** (44-50): Returns `True` on first construction only

## Time Variables (`bencher/variables/time.py:1-93`)

### TimeBase (`time.py:9-39`)
- **Inherits**: `SweepBase, Selector`
- **`values()`** (36-39): Returns objects list directly

### TimeSnapshot (`time.py:42-68`)
- **Inherits**: `TimeBase`
- **Constructor**: `datetime_src: datetime | str`, `units="time"`, `samples=None`
- **Purpose**: Continuous time value (e.g., timestamp), classified as float for plotting

### TimeEvent (`time.py:70-93`)
- **Inherits**: `TimeBase`
- **Constructor**: `time_event: str`, `units="event"`, `samples=None`
- **Purpose**: Discrete time event (e.g., git commit tag), classified as categorical

## Result Types (`bencher/variables/results.py:1-276`)

### OptDir Enum (`results.py:14-17`)
Optimization direction: `minimize`, `maximize`, `none`

### Result Type Table

| Type | Line | Parent | Slots | Purpose |
|------|------|--------|-------|---------|
| `ResultVar` | 20 | `Number` | `["units", "direction"]` | Numeric scalar |
| `ResultBool` | 40 | `Number` | `["units", "direction"]` | Boolean (0-1 bounds) |
| `ResultVec` | 61 | `param.List` | `["units", "direction", "size"]` | Fixed-size vector |
| `ResultHmap` | 103 | `param.Parameter` | - | HoloViews HoloMap |
| `ResultPath` | 123 | `param.Filename` | `["units"]` | File path |
| `ResultVideo` | 139 | `param.Filename` | `["units"]` | Video file path |
| `ResultImage` | 151 | `param.Filename` | `["units"]` | Image file path |
| `ResultString` | 163 | `param.String` | `["units"]` | String value |
| `ResultContainer` | 175 | `param.Parameter` | `["units"]` | Generic container |
| `ResultReference` | 187 | `param.Parameter` | `["units", "obj", "container"]` | Non-picklable object ref |
| `ResultDataSet` | 210 | `param.Parameter` | `["units", "obj"]` | Dataset/reference |
| `ResultVolume` | 229 | `param.Parameter` | `["units", "obj"]` | 3D volume data |

### Type Collections (`results.py:242-276`)

| Collection | Types | Purpose |
|------------|-------|---------|
| `PANEL_TYPES` | ResultPath, ResultImage, ResultVideo, ResultContainer, ResultString, ResultReference, ResultDataSet | Direct Panel rendering |
| `XARRAY_MULTIDIM_RESULT_TYPES` | ResultVar, ResultBool, ResultVideo, ResultImage, ResultString, ResultContainer, ResultPath | Support N-D xarray storage |
| `ALL_RESULT_TYPES` | All 12 types | Complete union for parameter discovery |

## Parameter Type → Plot Type Mapping

| Input Type(s) | Result Type | Default Plot | PlotFilter |
|---------------|-------------|-------------|------------|
| 0 float, 0+ cat | `ResultVar`/`ResultBool` | Scatter | float:0-0, cat:0+, repeats:1 |
| 1 float, 0+ cat | `ResultVar`/`ResultBool` | Line | float:1-1, cat:0+, repeats:1 |
| 2+ inputs (any mix) | `ResultVar`/`ResultBool` | Heatmap | float:0+, cat:0+, inputs:2+ |
| 3 float, 0 cat | `ResultVar` | Volume (3D) | float:3-3, cat:0 |
| 2+ float, 0+ cat | `ResultVar` | Surface (3D) | float:2+, cat:0+ |
| Any, repeats > 1 | `ResultVar`/`ResultBool` | BoxWhisker/Violin/ScatterJitter | repeats:2+ |
| Any | `ResultImage`/`ResultVideo` | VideoSummary | panel_range:1+ |
| Any | `ResultDataSet` | DataSet viewer | (always available) |
| Any | Any (with Optuna) | Optuna plots | (when use_optuna=True) |

> **NOTE:** Plot type selection is not exclusive - multiple plot types can match the same data configuration. The `to_auto()` method tries all callbacks in order and includes all matches.
