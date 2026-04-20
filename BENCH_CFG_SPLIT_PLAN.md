# Plan: Re-split `bench_cfg.py` with a Clean API Break

Re-enables the intent of [PR #688](https://github.com/blooop/bencher/pull/688)
(reverted by [PR #704](https://github.com/blooop/bencher/pull/704)) without the
backward-compatibility scaffolding that made the first attempt too complex.

The revert PR was right about one thing: the dual flat-plus-nested access
pattern, built on `__getattr__`/`__setattr__` delegation magic, was the source
of nearly all of PR #688's complexity. It also listed drawbacks ("better CLI
discovery", "natural param integration", "no isolation benefit") that only hold
*if* you keep both access patterns alive. Drop the flat layer entirely and
the design becomes much cleaner.

The goal is long-term simplicity and correctness, not migration ease.

---

## The guiding principle

One canonical way to reach every parameter. Attribute paths express grouping.
No duplication, no delegation, no parallel access modes.

```python
run_cfg.cache.results = True          # not run_cfg.cache_results
run_cfg.execution.repeats = 5         # not run_cfg.repeats
run_cfg.time.over_time = True         # not run_cfg.over_time
run_cfg.regression.enabled = True     # not run_cfg.regression_detection
```

Grouped names also let us drop redundant prefixes baked into the flat names
(`cache_results` -> `cache.results`, `regression_method` -> `regression.method`,
`max_time_events` -> `time.max_events`).

---

## Target module layout

```
bencher/bench_cfg/
  __init__.py            # re-exports the public API
  cache_cfg.py           # CacheCfg
  execution_cfg.py       # ExecutionCfg
  display_cfg.py         # DisplayCfg       (console + pandas/xarray serving)
  visualization_cfg.py   # VisualizationCfg (plot, backend, panes)
  time_cfg.py            # TimeCfg          (over_time + history)
  regression_cfg.py      # RegressionCfg
  server_cfg.py          # ServerCfg        (replaces BenchPlotSrvCfg)
  run_cfg.py             # BenchRunCfg      (composes the above)
  bench_cfg_class.py     # BenchCfg         (BenchRunCfg + sweep metadata)
  dims_cfg.py            # DimsCfg          (unchanged)
```

Each sub-config is a plain `param.Parameterized` -- no mixins, no delegation,
no inheritance chain across groups. `BenchRunCfg` holds each one in a
`param.ClassSelector` slot.

`BenchCfg` inherits from `BenchRunCfg` (sweep metadata composes naturally with
run metadata; splitting them further would just add friction for no gain).

---

## Parameter-to-group mapping

### `ServerCfg` -- panel server
`port`, `allow_ws_origin`, `show`

### `ExecutionCfg` -- how the function is run
`repeats`, `level`, `samples_per_var`, `executor`, `nightly`, `headless`,
`dry_run`, `only_plot`
- `level_to_samples()` moves here from `BenchRunCfg`.
- `only_plot` moves in from the cache group -- it's an execution-mode gate,
  not a cache-layer setting.

### `CacheCfg` -- cache behaviour (names drop the `cache_` / `_cache` prefix)
| Old                      | New                  |
|--------------------------|----------------------|
| `cache_results`          | `results`            |
| `cache_samples`          | `samples`            |
| `clear_cache`            | `clear`              |
| `clear_sample_cache`     | `clear_samples`      |
| `overwrite_sample_cache` | `overwrite_samples`  |
| `only_hash_tag`          | `only_hash_tag`      |
| `cache_size`             | `size_mb`            |

### `DisplayCfg` -- console + served tables
`print_bench_inputs`, `print_bench_results`, `summarise_constant_inputs`,
`print_pandas`, `print_xarray`, `serve_pandas`, `serve_pandas_flat`,
`serve_xarray`

### `VisualizationCfg` -- plotting
`auto_plot`, `use_holoview`, `use_optuna`, `plot_size`, `plot_width`,
`plot_height`, `pane_layout`, `backend`

### `TimeCfg` -- over-time & history
| Old                        | New                     |
|----------------------------|-------------------------|
| `over_time`                | `over_time`             |
| `clear_history`            | `clear_history`         |
| `max_time_events`          | `max_events`            |
| `max_slider_points`        | `max_slider_points`     |
| `show_aggregated_time_tab` | `show_aggregated_tab`   |
| `show_aggregate_plots`     | `show_aggregate_plots`  |
| `time_event`               | `event`                 |

### `RegressionCfg` -- regression detection
| Old                     | New           |
|-------------------------|---------------|
| `regression_detection`  | `enabled`     |
| `regression_method`     | `method`      |
| `regression_mad`        | `mad`         |
| `regression_percentage` | `percentage`  |
| `regression_fail`       | `fail`        |

### `BenchRunCfg` top-level (the run itself, not a sub-domain)
`run_tag`, `run_date`, plus the sub-config slots listed above.
Methods: `__init__`, `from_cmd_line`, `with_defaults`, `deep`.
- `raise_duplicate_exception` is currently defined on **both**
  `BenchRunCfg` and `BenchCfg`. Delete the `BenchRunCfg` copy -- it is only
  consumed during filename generation, which is `BenchCfg` territory.

### `BenchCfg` (unchanged semantics, just moves file)
All sweep metadata, result metadata, hashing, LaTeX, and description methods.

---

## `BenchRunCfg` composition sketch

```python
class BenchRunCfg(param.Parameterized):
    server        = param.ClassSelector(class_=ServerCfg)
    execution     = param.ClassSelector(class_=ExecutionCfg)
    cache         = param.ClassSelector(class_=CacheCfg)
    display       = param.ClassSelector(class_=DisplayCfg)
    visualization = param.ClassSelector(class_=VisualizationCfg)
    time          = param.ClassSelector(class_=TimeCfg)
    regression    = param.ClassSelector(class_=RegressionCfg)

    run_tag  = param.String(default="", doc=...)
    run_date = param.Date(default=None, doc=...)

    def __init__(self, **kwargs):
        # Fresh instances per BenchRunCfg -- never share mutable defaults.
        kwargs.setdefault("server",        ServerCfg())
        kwargs.setdefault("execution",     ExecutionCfg())
        kwargs.setdefault("cache",         CacheCfg())
        kwargs.setdefault("display",       DisplayCfg())
        kwargs.setdefault("visualization", VisualizationCfg())
        kwargs.setdefault("time",          TimeCfg())
        kwargs.setdefault("regression",    RegressionCfg())
        kwargs.setdefault("run_date",      datetime.now())
        super().__init__(**kwargs)
```

Usage:

```python
# Ad-hoc construction -- assemble groups you care about.
run_cfg = bn.BenchRunCfg(
    execution=bn.ExecutionCfg(level=4, repeats=3),
    cache=bn.CacheCfg(results=True, samples=True),
    time=bn.TimeCfg(over_time=True),
)

# Or mutate in place -- cheap, parameters are live.
run_cfg = bn.BenchRunCfg()
run_cfg.cache.results = True
run_cfg.time.over_time = True
```

---

## Methods that need rethinking

### `from_cmd_line`
Current parser exposes only 5 flags (`--use-cache`, `--only-plot`, `--port`,
`--nightly`, `--time_event`). Each sub-config owns a classmethod
`add_cli_args(parser)` that adds its own flags; `BenchRunCfg.from_cmd_line`
invokes all of them. This keeps CLI discovery focused and colocated with
the parameters. (The revert PR's "better CLI discovery" worry is answered
here -- the CLI is explicit and scoped, not a dump of every `param`.)

### `with_defaults`
Current version walks a flat namespace. The replacement walks sub-configs
recursively: only overwrite a value if it still equals its param-level
default. Signature becomes:

```python
BenchRunCfg.with_defaults(
    run_cfg,
    execution=dict(repeats=5, level=4),
    cache=dict(results=True),
)
```

Accepting dicts (rather than nested `ExecutionCfg` instances) keeps the ergonomic
"merge-if-unset" semantics without requiring callers to construct sub-configs
just to pass defaults.

### `deep`
Already `deepcopy(self)` -- still works, but verify the `ClassSelector` slots
deep-copy cleanly (param does this by default; add a test anyway).

### `hash_persistent`
Uses `bench_name`, `over_time`, `repeats`, `tag`, input/result/const vars.
Update attribute access (`self.over_time` -> `self.time.over_time`,
`self.repeats` -> `self.execution.repeats`). **Semantics are identical**, so
existing caches remain valid across the upgrade -- important, since
invalidating user caches silently would be a real regression.

### `describe_benchmark`
Same: update field accesses to go through the sub-config groups. Output
string stays identical.

---

## Call-site migration

~20 files reference the flat attributes. The pattern is purely mechanical:

| Where                         | Changes                              |
|-------------------------------|--------------------------------------|
| `bencher/bencher.py`          | ~32 renames (largest site)           |
| `bencher/bench_runner.py`     | ~8 renames                           |
| `bencher/sweep_executor.py`   | 4 renames                            |
| `bencher/regression.py`       | 1 rename                             |
| `bencher/result_collector.py` | 1 rename                             |
| `bencher/example/**`          | ~30 renames across example files     |
| `test/**`                     | ~40 renames across test files        |
| `scripts/benchmark_save.py`   | ~6 renames                           |
| `docs/how_to_use_bencher.md`  | documentation examples               |
| `CHANGELOG.md`                | add a BREAKING entry                 |

Approach: do the split and the renames in a **single PR**, mechanically. No
feature flags, no shims, no deprecation aliases -- the whole point of the clean
break is that there is nothing to maintain in parallel.

Recommended sequence inside the PR:
1. Create the `bench_cfg/` package with the seven sub-configs + `BenchRunCfg`
   + `BenchCfg` + `DimsCfg`. Keep the old `bencher/bench_cfg.py` temporarily so
   imports still resolve while the rest of the tree is updated.
2. Update `bencher/__init__.py` to re-export the new sub-config classes
   (`CacheCfg`, `ExecutionCfg`, `DisplayCfg`, `VisualizationCfg`, `TimeCfg`,
   `RegressionCfg`, `ServerCfg`) alongside `BenchCfg`/`BenchRunCfg`.
3. Migrate `bencher/**` call sites (library code first -- `bencher.py`,
   `bench_runner.py`, `sweep_executor.py`, `regression.py`,
   `result_collector.py`).
4. Migrate `bencher/example/**`.
5. Migrate `test/**` and `scripts/**`.
6. Migrate docs (`docs/how_to_use_bencher.md`, any gallery text).
7. Delete the old `bencher/bench_cfg.py`.
8. Add focused unit tests in `test/test_bench_cfg.py`:
    - sub-config defaults,
    - `BenchRunCfg` composition (fresh sub-configs per instance, not shared),
    - `with_defaults` recursion,
    - `deep` copies sub-configs independently,
    - hash stability: a `BenchCfg` constructed through the new API produces
      the same `hash_persistent` as one constructed before the split (lock
      this down with a known-good hash string).
9. Run `pixi run ci`; iterate until green.

The hash-stability test is the key safety net -- it verifies users' on-disk
caches survive the upgrade.

---

## What is explicitly NOT in scope

- No `__getattr__` / `__setattr__` delegation.
- No deprecation aliases (`run_cfg.cache_results` does **not** work post-break).
- No property shims on `BenchRunCfg` that forward to sub-configs.
- No dataclasses-replacing-param rewrite -- `param` is already well-suited to
  nested `Parameterized` holders, and keeping the library means `BenchCfg`
  keeps its `.param` metadata, docs, bounds, and serialization machinery.
- No CLI overhaul beyond moving flag registration into each sub-config.

---

## Why this design holds up long term

- **One source of truth per parameter.** Rename, re-document, or add bounds in
  one file; nothing else needs to know.
- **Composable.** Pre-built groups (e.g. a "fast-CI" `ExecutionCfg`, a
  "always-refresh" `CacheCfg`) can live as module-level constants and be
  mixed into any run.
- **Testable in isolation.** `CacheCfg` can be instantiated and asserted on
  without standing up an entire `BenchRunCfg`.
- **Discoverable.** Typing `run_cfg.cache.` in an editor shows exactly the
  seven cache parameters -- not all 45 run parameters. The revert PR framed
  this as a regression; in practice, grouped autocomplete is better for
  discovery once the groups exist.
- **Extensible.** New concerns (e.g. a future `TelemetryCfg`) slot in as a
  new sub-config without touching existing ones.

---

## Acceptance criteria

- `pixi run ci` passes with no backward-compat shims in the source tree.
- `rg -n "run_cfg\.(cache_results|cache_samples|clear_cache|over_time|regression_|time_event|max_time_events)"` returns nothing outside `CHANGELOG.md`.
- A `BenchCfg.hash_persistent` snapshot test proves existing caches stay valid.
- `CHANGELOG.md` has a **Breaking changes** entry with the full rename table.
- Public API exports the seven sub-config classes from `bencher/__init__.py`.
