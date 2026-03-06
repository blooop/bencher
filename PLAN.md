# Plan: Enrich Auto-Generated Examples with Context & Add Missing Features

## Problem Statement

The **auto-generated examples** are minimal stubs that call `BenchableObject` or helper classes
from `benchable_objects.py` — they show *what bencher can plot* but not **how to build the
benchable objects themselves**. Compare:

| Aspect | Manual (e.g. `example_simple.py`) | Auto-generated (e.g. `ex_1_float_0_cat.py`) |
|---|---|---|
| Defines its own domain class | Yes — `InputCfg`, `OutputCfg`, enums, static bench function | No — imports shared `BenchableObject` |
| Explains *why* parameters exist | Yes — docstrings, comments about noise, optimality | No — bare `plot_sweep()` call |
| Shows multiple sweeps per report | Yes — 4 progressive sweeps building intuition | No — single `plot_sweep()` |
| Demonstrates `description` / `post_description` | Yes — rich narrative text | No |
| Shows advanced API (`const_vars`, `run_cfg`, callbacks) | Yes — organically | No |
| Teaches the reader to write their own benchmark | Yes | No |

The gallery looks impressive visually but a new user copying an auto-generated example has no
idea how to adapt it to their own problem.

---

## Plan Overview

Two workstreams, each broken into concrete tasks:

### Workstream A — Enrich existing auto-generated examples with context

Goal: Each generated example should **define its own small domain class** inline (or clearly
inherit from a shared one with commentary), include a docstring that explains the scenario, and
show at least one `description=` kwarg.

### Workstream B — Add examples for missing features / patterns

Goal: Cover features that only exist in manual examples today but have no gallery representation.

---

## Workstream A: Enrich Auto-Generated Examples

### A1. Create richer benchable domain classes in `benchable_objects.py`

**Current state:** `BenchableObject` is a generic math function with `float1/float2/float3` —
no domain context.

**Action:** Add 2-3 new small domain classes alongside `BenchableObject` that tell a story:

- `BenchableRobotArm` — 2-3 float inputs (joint angles), categorical (gripper type), result
  vars (reach distance, energy). Demonstrates a physical simulation use case.
- `BenchableMLTrainer` — float inputs (learning_rate, dropout), enum (optimizer: adam/sgd/rmsprop),
  result vars (accuracy, training_time). Demonstrates an ML hyperparameter search.

These give users something relatable to copy and adapt.

### A2. Update meta generators to emit richer example bodies

**Files:** `generate_meta.py`, `generate_meta_result_types.py`, etc.

**Action for each generator:**

1. Generated examples should include a **module-level docstring** explaining the scenario
   (not just "Auto-generated example: 1 Float, 0 Categorical")
2. The `plot_sweep()` call should include `title=` and `description=` kwargs
3. For the dimensionality examples (0-3 float), use different domain classes at different
   dimensions to show variety:
   - 0D: `BenchableMLTrainer` with only categoricals
   - 1D: `BenchableRobotArm` sweeping one joint angle
   - 2D: `BenchableRobotArm` sweeping two joint angles (heatmap)
   - 3D: Keep `BenchableObject` for the math function (volume plots are inherently abstract)

### A3. Add inline class definitions to a subset of generated examples

**Action:** For ~3-4 "flagship" examples per section (the ones most likely to be a user's
entry point), have the generator emit the full class definition inline rather than importing.
This teaches users the pattern without requiring them to trace imports.

Candidates:
- `ex_1_float_0_cat.py` — the simplest line plot
- `ex_0_float_1_cat.py` — simplest bar chart
- `ex_2_float_0_cat.py` — simplest heatmap
- One result type example (e.g., `result_image/`)
- One composable container example

### A4. Add `description` and `post_description` to generated `plot_sweep()` calls

**Action:** Each meta generator should populate `description=` with 1-2 sentences explaining
what the sweep demonstrates and what to look for in the output. The `post_description=` can
note what pattern the user should observe (e.g., "Notice how the heatmap shows the interaction
between joint angles").

---

## Workstream B: Add Missing Feature Examples

### B1. BenchRunner example (gallery: "Workflows" section)

**Current state:** `example_benchrunner.py` exists as a manual example but is not in the
gallery.

**Action:** Create a generated example demonstrating `BenchRunner` with progressive sweeps
(`sweep_sequential`, `group_size`). Add a new gallery section "Workflows".

### B2. Multiple sweeps per report (gallery: "Workflows" section)

**Current state:** `example_simple.py` shows 4 progressive sweeps building a report with
tabs, but no generated equivalent exists.

**Action:** Create a generated example that:
1. Defines a domain class
2. Calls `plot_sweep()` 3 times with different `input_vars` subsets
3. Shows how `bench.report` accumulates tabs

### B3. Cache and context patterns (gallery: "Advanced Patterns" section)

**Current state:** `example_sample_cache.py` and `example_sample_cache_context.py` show
caching, tags, and context passing — no generated equivalent.

**Action:** Create examples showing:
- `run_tag` usage for cache partitioning
- `clear_cache` / `cache_results` flags
- Context object mutation between runs

### B4. Custom sweep values (gallery: "Sampling Strategies" section)

**Current state:** `example_custom_sweep.py` shows `sample_values=[2, 3, 4, 7, 8, 9]` —
the generated `sampling_custom_values.py` exists but may lack the inline class pattern.

**Action:** Verify `sampling_custom_values.py` defines its own class inline with
`sample_values=` and has explanatory docstrings. If not, enrich it.

### B5. YamlSweep / external config (gallery: new "Configuration" section)

**Current state:** `example_yaml_sweep_dict.py` and `example_yaml_sweep_list.py` show loading
sweep configs from YAML files — no generated equivalent.

**Action:** Create a generated example that:
1. Writes a small YAML file inline (or references one)
2. Uses `YamlSweep` to load it
3. Runs a benchmark with the loaded config

### B6. Optuna optimization with `use_optuna=True` (enrich existing)

**Current state:** `optimization/` has 4 examples but they're minimal stubs.

**Action:** Enrich the optimization examples to:
- Show `OptDir.maximize` / `OptDir.minimize` on result vars
- Include `post_description` explaining the Pareto front
- Show `bench.sweep_sequential()` for iterative optimization refinement

### B7. Time events (gallery: new "Time Tracking" section or enrich "Over Time")

**Current state:** `example_time_event.py` shows `TimeEvent` usage — no generated equivalent.
The over-time examples exist but don't cover `TimeEvent` (only `TimeSnapshot` style).

**Action:** Create a generated example using `TimeEvent` to track discrete events (e.g.,
simulated pull request benchmarks).

### B8. Report customization and publication

**Current state:** `example_publish.py` shows `bench.report.save()` and publishing, and
`example_docs.py` shows documentation features — no generated equivalents.

**Action:** Create a small example showing:
- Custom `add_plot_callback()` usage
- `bench.report.append()` for manual result insertion
- `bench.report.save()` with custom directory

### B9. InputCfg / OutputCfg separation pattern

**Current state:** `example_simple.py` shows the `InputCfg` + `OutputCfg` + static
`bench_function` pattern, which is an alternative to the `ParametrizedSweep.__call__` pattern.
No generated example covers this.

**Action:** Create at least one generated example demonstrating the separated input/output
class pattern with `bch.Bench("name", InputCfg.bench_function, InputCfg)` constructor style.

---

## New Gallery Sections to Add

Update `SECTIONS` in `generate_examples.py`:

```python
SECTIONS = {
    # ... existing sections ...
    "Workflows": "workflows",
    "Advanced Patterns": "advanced",
    "Configuration": "configuration",
}
```

---

## Implementation Order

1. **A1** — Create domain classes (foundation for everything else)
2. **A2 + A4** — Update meta generators (enriches all generated examples at once)
3. **A3** — Inline class definitions for flagship examples
4. **B2** — Multiple sweeps (highest user value)
5. **B1** — BenchRunner
6. **B9** — InputCfg/OutputCfg pattern
7. **B6** — Enrich optimization examples
8. **B3** — Cache/context patterns
9. **B5** — YamlSweep
10. **B7** — TimeEvent
11. **B8** — Report customization
12. **B4** — Verify/enrich custom sweep values

---

## Success Criteria

- A new user reading any gallery example can understand how to define their own
  `ParametrizedSweep` class without reading other files
- Every generated example has a meaningful docstring and `description=` in `plot_sweep()`
- The gallery covers all major bencher features (no feature is only in manual examples)
- `pixi run ci` passes after all changes
- `pixi run generate-docs` produces the updated gallery successfully
