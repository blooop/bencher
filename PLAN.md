# Plan: Deprecate `__call__()` and Introduce `benchmark()` Method

## Context

Every `ParametrizedSweep` subclass currently requires users to override `__call__` with 2 mandatory boilerplate lines that are easy to forget and add no value:

```python
# CURRENT — verbose, error-prone
class MyBench(bn.ParametrizedSweep):
    x = bn.FloatSweep(bounds=(0, 1))
    result = bn.ResultVar()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)  # boilerplate
        self.result = math.sin(self.x)
        return super().__call__()                  # boilerplate
```

The goal is to replace this with a streamlined `benchmark()` method:

```python
# NEW — clean, no boilerplate
class MyBench(bn.ParametrizedSweep):
    x = bn.FloatSweep(bounds=(0, 1))
    result = bn.ResultVar()

    def benchmark(self):
        self.result = math.sin(self.x)
```

**Scope**: ~193 files use the pattern (~10 hand-written examples, ~150+ auto-generated, ~30 tests).

---

## Phase 1: Framework Core Changes

### 1a. `bencher/variables/parametrised_sweep.py`

Add `benchmark()` method and update `__call__` dispatch logic:

```python
def __call__(self, **kwargs) -> dict:
    if type(self).benchmark is not ParametrizedSweep.benchmark:
        # New-style: subclass overrides benchmark()
        self.update_params_from_kwargs(**kwargs)
        self.benchmark()
        return self.get_results_values_as_dict()
    else:
        # Legacy path: subclass overrides __call__() and handles
        # update_params_from_kwargs + super().__call__() itself.
        # Base just returns results dict (called via super().__call__()).
        return self.get_results_values_as_dict()

def benchmark(self):
    """Override this with your benchmark logic.

    When called, all sweep parameters (self.x, etc.) are already set.
    Set result variables (self.result, etc.) directly on self.
    No need to call update_params_from_kwargs or super().__call__().
    """
    pass
```

**Key insight**: Legacy `__call__` overrides call `super().__call__()` which hits the base — the base method is only ever reached as the *final* step. The detection `type(self).benchmark is not ParametrizedSweep.benchmark` correctly distinguishes new vs legacy code. No double `update_params_from_kwargs` call occurs.

Also update:
- `plot_hmap` (line 210): works unchanged since `self.__call__(**kwargs)` dispatches correctly
- `to_dynamic_map` (line 170): works unchanged for same reason

### 1b. `bencher/worker_manager.py` (line 91-93)

Add deprecation warning when a ParametrizedSweep overrides `__call__` but not `benchmark`:

```python
if isinstance(worker, ParametrizedSweep):
    self.worker_class_instance = worker
    self.worker = self.worker_class_instance.__call__
    if (type(worker).__call__ is not ParametrizedSweep.__call__
            and type(worker).benchmark is ParametrizedSweep.benchmark):
        warnings.warn(
            f"{type(worker).__name__} overrides __call__() which is deprecated. "
            "Override benchmark() instead.",
            DeprecationWarning, stacklevel=2
        )
```

### 1c. No changes needed to:
- `bencher/sweep_executor.py` — calls `worker(**kwargs)` which resolves to `__call__`
- `bencher/bencher.py` — wraps worker in `partial(worker_kwargs_wrapper, ...)`
- `bencher/results/optuna_result.py` — calls `worker(**kwargs)`, same chain
- `bencher/bench_runner.py` — `BenchableV1`/`BenchableV2` protocols are for top-level bench functions, not sweep workers

---

## Phase 2: Migrate Hand-Written Examples

Convert `__call__` → `benchmark()` in each file (remove `update_params_from_kwargs` + `super().__call__()`, rename method):

- `bencher/example/example_simple_float.py`
- `bencher/example/example_workflow.py`
- `bencher/example/example_image.py`
- `bencher/example/example_video.py`
- `bencher/example/example_rerun.py`
- `bencher/example/example_cartesian_animation.py`
- `bencher/example/example_self_benchmark.py`
- `bencher/example/example_tab_bar_sweep.py`
- `bencher/example/example_sample_cache_context.py`
- `bencher/example/benchmark_data.py`
- `bencher/example/yaml_sweep_dict.py`
- `bencher/example/yaml_sweep_list.py`
- `bencher/example/optuna/example_optuna.py`
- `bencher/example/optuna/example_optimize.py`

---

## Phase 3: Migrate Benchable Objects & Meta Generators

### 3a. `bencher/example/meta/benchable_objects.py`
Convert all 8 benchmark classes (`BenchableBoolResult`, `BenchableVecResult`, etc.) from `__call__` to `benchmark()`.

### 3b. `bencher/example/meta/meta_generator_base.py` (line 45-48)
Update code generation to emit `benchmark()` instead of `__call__`:
- Replace the `__call__` type hint rewrite logic
- Update template to generate `def benchmark(self):` instead of `def __call__(self, **kwargs):`
- Remove `self.update_params_from_kwargs(**kwargs)` and `return super().__call__()` from templates

### 3c. Meta generators that emit `__call__` in class code
Search all `bencher/example/meta/generate_meta_*.py` files for `__call__` in string templates and convert them.

### 3d. Regenerate all generated examples
Run `pixi run generate-docs` to regenerate ~150 files in `bencher/example/generated/`.

---

## Phase 4: Migrate Tests

Convert test benchmark classes from `__call__` → `benchmark()` in:
- `test/test_singleton_parametrised_sweep.py`
- `test/test_sweep_timings.py`
- `test/test_time_event_curve.py`
- `test/test_regression.py`
- `test/test_result_bool.py`
- `test/test_sample_order.py`
- `test/test_job.py`
- `test/test_multiprocessing_executor.py`
- `test/test_optimize.py`
- `test/test_optuna_conversions.py`
- `test/test_optuna_result.py`
- `test/test_over_time_repeats.py`
- `test/test_over_time_save_perf.py`
- `test/test_cache.py`
- `test/test_bench_result_base.py`
- `test/test_sweep_vars.py`
- `scripts/benchmark_save.py`

Add new tests:
- Test that `benchmark()` override works correctly (params auto-populated, results auto-collected)
- Test that legacy `__call__` override still works (backward compat)
- Test that deprecation warning is emitted for legacy `__call__` override
- Test that a class with neither override returns empty results

---

## Phase 5: Documentation

- `docs/how_to_use_bencher.md` — Replace `__call__` pattern with `benchmark()`, add migration section
- `docs/intro.md` — Update examples
- `CHANGELOG.md` — Add deprecation notice

---

## Verification

1. After Phase 1: `pixi run ci` — all existing tests pass (backward compat confirmed)
2. After Phase 2-4: `pixi run ci` — everything passes with new interface
3. Spot-check: `pixi run python bencher/example/example_simple_float.py` works
4. Verify deprecation: temporarily revert one example to `__call__` pattern, confirm warning is emitted
