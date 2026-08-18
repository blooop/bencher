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

The goal is long-term simplicity and correctness, not migration ease. Treat
this as a clean-slate rewrite: no backward-compat shims for the Python API.
bencher ships on PyPI as `holobench`, so downstream users get **zero runtime
warnings** when the flat names disappear — signal the break loudly instead:
a major version bump and release notes carrying the full rename table.

Parameter inventories and call-site counts below were regenerated against
`main` on 2026-08-18. **Regenerate them again immediately before executing** —
this file goes stale every time a parameter is added or renamed. It has
already gone stale twice: once when `level` became `subsampling_divisions`,
and once when ~230 commits landed between 2026-07-23 and 2026-08-18 (adding
`catch`/`fail_on_sample_error` to the execution group, the `series_id`/
`bencher/identity.py` identity subsystem, and the collect/render split's
pickle-based save files — all folded in below).

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
  server_cfg.py          # ServerCfg        (replaces BenchPlotSrvCfg; also
                         #   home of ShowMode, normalize_show, _SHOW_ALIASES)
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
- `ShowMode`, `normalize_show`, and `_SHOW_ALIASES` move to `server_cfg.py`
  with it.

### `ExecutionCfg` -- how the function is run
`repeats`, `subsampling_divisions`, `samples_per_var`, `executor`, `nightly`,
`headless`, `dry_run`, `only_plot`, `catch`, `fail_on_sample_error`
- `catch` and `fail_on_sample_error` are the sample fault-tolerance pair added
  after the original inventory. They keep their names: `catch` is documented as
  "spelled exactly as on `Bench.optimize(catch=...)`", and both are error-mode
  gates on how the sweep executes, so they belong here, unrenamed.
- `subsampling_divisions_to_samples()` moves here from `BenchRunCfg`.
- `only_plot` moves in from the cache group -- it's an execution-mode gate,
  not a cache-layer setting.
- The deprecated `level` kwarg alias (in `__init__` and `with_defaults`) and
  the deprecated `level_to_samples()` wrapper are **deleted** as part of the
  break -- no deprecation shims survive it.

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
| `on_history_reset`         | `on_history_reset`      |
| `max_time_events`          | `max_events`            |
| `max_slider_points`        | `max_slider_points`     |
| `show_aggregated_time_tab` | `show_aggregated_tab`   |
| `show_aggregate_plots`     | `show_aggregate_plots`  |
| `time_event`               | `event`                 |

### `RegressionCfg` -- regression detection (names drop the `regression_` prefix)
| Old                       | New           |
|---------------------------|---------------|
| `regression_detection`    | `enabled`     |
| `regression_method`       | `method`      |
| `regression_min_history`  | `min_history` |
| `regression_mad`          | `mad`         |
| `regression_percentage`   | `percentage`  |
| `regression_delta`        | `delta`       |
| `regression_absolute`     | `absolute`    |
| `regression_overrides`    | `overrides`   |
| `regression_fail`         | `fail`        |

### `raise_duplicate_exception` -- delete it entirely
It is declared on **both** `BenchRunCfg` and `BenchCfg`, documented in both
docstrings, and set once in `test/test_bencher.py` -- but **nothing anywhere
in the library reads it**. It is dead code. Delete both declarations, both
docstring entries, and the test line. (An earlier draft of this plan claimed
it was "consumed during filename generation" -- it is not; no consumer
exists.)

### `BenchRunCfg` top-level (the run itself, not a sub-domain)
`run_tag`, `run_date`, plus the sub-config slots listed above.
Methods: `__init__`, `from_cmd_line`, `with_defaults`, `deep`.

### `BenchCfg` (unchanged semantics, just moves file)
All sweep metadata, result metadata, hashing, LaTeX, and description methods.
This now includes the parameters added since the original inventory --
`series_id` (names the over_time trend; **deliberately excluded** from
`hash_persistent`, see below), `agg_over_dims`, and `agg_fn` -- which stay on
`BenchCfg` exactly as they are. They are sweep/result metadata, not run
configuration, so the split does not touch them.

---

## `BenchRunCfg` composition sketch

`param.ClassSelector` defaults to `instantiate=True`, so declaring an instance
as the parameter default already gives every `BenchRunCfg` its own fresh copy
-- no `__init__` boilerplate needed, and the param-level default stays
non-`None` (which keeps `.param` introspection and default-comparison logic
honest):

```python
class BenchRunCfg(param.Parameterized):
    server        = param.ClassSelector(class_=ServerCfg,        default=ServerCfg())
    execution     = param.ClassSelector(class_=ExecutionCfg,     default=ExecutionCfg())
    cache         = param.ClassSelector(class_=CacheCfg,         default=CacheCfg())
    display       = param.ClassSelector(class_=DisplayCfg,       default=DisplayCfg())
    visualization = param.ClassSelector(class_=VisualizationCfg, default=VisualizationCfg())
    time          = param.ClassSelector(class_=TimeCfg,          default=TimeCfg())
    regression    = param.ClassSelector(class_=RegressionCfg,    default=RegressionCfg())

    run_tag  = param.String(default="", doc=...)
    run_date = param.Date(default=None, doc=...)

    def __init__(self, **kwargs):
        kwargs.setdefault("run_date", datetime.now())
        super().__init__(**kwargs)
```

Add a test pinning the fresh-copy behaviour (two `BenchRunCfg()` instances
must not share sub-config objects) so a param behaviour change can't silently
reintroduce shared mutable state.

Usage:

```python
# Ad-hoc construction -- assemble groups you care about.
run_cfg = bn.BenchRunCfg(
    execution=bn.ExecutionCfg(subsampling_divisions=4, repeats=3),
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
Current parser exposes 6 flags (`--use-cache`, `--only-plot`, `--port`,
`--nightly`, `--time_event`, `--repeats`). Note the current implementation is
`pragma: no cover` and appears broken on main today: `--use-cache` parses to a
`use_cache` dest that matches no param name, and the whole namespace is
splatted into `BenchRunCfg(**vars(args))`.

New design: each sub-config owns two classmethods -- `add_cli_args(parser)`
to register its flags, and `apply_cli_args(namespace)` to consume the parsed
values back into an instance. `BenchRunCfg.from_cmd_line` invokes both sets.
This keeps CLI discovery focused and colocated with the parameters, and fixes
the flat-namespace-to-nested-slots mapping explicitly. (The revert PR's
"better CLI discovery" worry is answered here -- the CLI is explicit and
scoped, not a dump of every `param`.) Add the first-ever tests for this path.

### `with_defaults`
Current version walks a flat namespace (and carries `level` deprecation
handling, which dies with the break). The replacement walks sub-configs
recursively: only overwrite a value if it still equals its param-level
default. Signature becomes:

```python
BenchRunCfg.with_defaults(
    run_cfg,
    execution=dict(repeats=5, subsampling_divisions=4),
    cache=dict(results=True),
)
```

Accepting dicts (rather than nested `ExecutionCfg` instances) keeps the ergonomic
"merge-if-unset" semantics without requiring callers to construct sub-configs
just to pass defaults. Unknown group names and unknown keys within a group
raise `ValueError`, matching current behaviour.

### `deep`
Already `deepcopy(self)` -- still works, but verify the `ClassSelector` slots
deep-copy cleanly (param does this by default; add a test anyway).

### `hash_persistent` -- keep it, bump `CACHE_VERSION`
Two corrections to earlier thinking here:

1. **The hash is not broken, and its semantics are deliberate.** The current
   (v5) hash encodes documented invariants: `title` is excluded so renames
   don't invalidate caches; `input_vars` are folded in order (they define
   dimension layout); `result_vars`/`const_vars` contribute as unordered sets;
   `series_id` is **deliberately excluded** (its own docstring explains why:
   folding it in would re-key every existing cache and history on upgrade);
   and `include_result_vars=False` produces the over_time history key that
   per-column history reconciliation depends on (see `bencher/history.py`).
   **Do not "simplify" the hash as part of this PR** -- preserve these
   invariants exactly. The only change is accessor paths
   (`self.over_time` -> `self.time.over_time`,
   `self.repeats` -> `self.execution.repeats`).
   Note that `bencher/identity.py` documents itself as mirroring
   `hash_persistent`'s key rules ("anything that changes the keys changes them
   here too") -- its field-inventory comments and `identity_of()` must be
   updated in lockstep with the split.
2. **The split doesn't change hash values -- but the cache still can't
   survive it.** `hash_persistent` consumes *values*, not attribute names, so
   the refactor preserves every hash by construction. The reason to bump
   `CACHE_VERSION` anyway: the benchmark-level cache stores whole pickled
   `BenchResult` objects, which embed a `BenchCfg` -- and pickles of the old
   flat param layout will not load into the new class shape. Bump
   `CACHE_VERSION` in `bencher/cache_management.py` so stale entries are
   discarded cleanly on first run rather than failing at unpickle time.
   This wipes users' over_time history baselines -- say so in the release
   notes.
3. **The cache is no longer the only pickle surface.** The collect/render
   split (`bencher/render.py`, added after the original inventory) pickles
   whole `BenchResult` objects -- embedding a `BenchCfg` -- to user-chosen
   files via `save_result()`/`load_result()`, with **no version guard**.
   Files saved before the break will fail to unpickle after it, and unlike
   the cache there is no `CACHE_VERSION` mechanism to discard them cleanly:
   `load_result()` will raise. Say so explicitly in the release notes
   (re-run `collect` to regenerate saved bench data). Consider having
   `load_result()` catch the unpickle failure and re-raise with a message
   naming the version break, so users get a diagnosis instead of a raw
   `AttributeError` from pickle.

Extend `test/test_hash_persistent.py` with invariant tests (title exclusion,
result-var reorder invariance, `include_result_vars=False` stability) so the
semantics survive future refactors too.

### `sweep_identity` / `identity.py` (new since the original inventory)
`bn.sweep_identity()` is a public API that takes `repeats=` and `over_time=`
as flat convenience kwargs and writes them onto a `BenchRunCfg` (along with
forcing `dry_run=True` and `auto_plot=False` internally). Decision: **keep
the flat kwargs** -- they are function arguments, not attribute paths, and
`sweep_identity(repeats=5)` reads better than
`sweep_identity(execution=dict(repeats=5))` for a two-knob convenience
signature. Only the internals change
(`cfg.repeats = repeats` -> `cfg.execution.repeats = repeats`, etc.).
`SweepIdentity`'s display strings (`repeats: ...`, `over_time: ...`) stay
as-is -- they name hash inputs, not attributes.

### `describe_benchmark`
Same: update field accesses to go through the sub-config groups. Output
string stays identical.

---

## Call-site migration

Regenerated from `rg` against main (2026-08-18), matching moved/renamed
attribute names regardless of receiver (`run_cfg.`, `bench_cfg.`, `self.`,
...). Counts exclude names too generic to grep (`repeats`, `executor`,
`port`, `show`, `nightly`, `headless`, `dry_run`, `catch`, `backend`), so
true totals are higher. **~132 files** reference the flat attributes.
The pattern is still purely mechanical:

| Where                                   | Scale                                          |
|-----------------------------------------|------------------------------------------------|
| `bencher/bencher.py`                    | ~46 refs (largest single site)                 |
| `bencher/results/**`                    | ~33 refs across ~9 files                       |
| `bencher/bench_runner.py`               | ~12 refs                                       |
| `bencher/result_collector.py`           | ~6 refs                                        |
| `bencher/sweep_executor.py`             | ~5 refs                                        |
| `bencher/identity.py`                   | ~5 refs -- **must move in lockstep with the hash**, see `hash_persistent` and `sweep_identity` sections |
| `bencher/history.py`                    | ~1 ref                                         |
| `bencher/regression.py`, `variables/results.py`, `plotting/plt_cnt_cfg.py`, `bench_report.py`, `bench_plot_server.py` | ~16 refs combined |
| `bencher/example/meta/**` (generators)  | ~66 refs across ~14 files                      |
| `bencher/example/generated/**`          | ~106 refs across ~45 files -- **do not hand-edit**; fix the `example/meta/generate_*.py` generators and regenerate |
| `bencher/example/*.py` (hand-written)   | ~14 refs across ~5 files                       |
| `test/**`                               | ~346 refs across ~43 files (`test_bench_cfg.py` 46, `test_regression.py` 43, `test_bench_runner.py` 33, `test_sample_fault_tolerance.py` 20, ...) |
| `scripts/benchmark_save.py`             | ~5 refs                                        |
| `docs/how_to_use_bencher.md`            | documentation examples                         |
| `CHANGELOG.md`                          | add a BREAKING entry                           |

Approach: do the split and the renames in a **single PR**, mechanically. No
feature flags, no shims, no deprecation aliases -- the whole point of the clean
break is that there is nothing to maintain in parallel.

Recommended sequence inside the PR:
1. Regenerate the parameter inventory and call-site counts above from current
   `main`; fix any drift in this document first.
2. Create the `bench_cfg/` package with the seven sub-configs + `BenchRunCfg`
   + `BenchCfg` + `DimsCfg`. Keep the old `bencher/bench_cfg.py` temporarily so
   imports still resolve while the rest of the tree is updated.
3. Update `bencher/__init__.py` to re-export the new sub-config classes
   (`CacheCfg`, `ExecutionCfg`, `DisplayCfg`, `VisualizationCfg`, `TimeCfg`,
   `RegressionCfg`, `ServerCfg`) alongside `BenchCfg`/`BenchRunCfg`.
4. Delete `raise_duplicate_exception` (both declarations, both docstring
   entries, `test/test_bencher.py` usage).
5. Migrate `bencher/**` call sites (library code first -- `bencher.py`,
   `results/**`, `bench_runner.py`, `sweep_executor.py`, `regression.py`,
   `result_collector.py`, `identity.py`, `history.py`, then the small
   single-ref files).
6. Migrate the `bencher/example/meta/generate_*.py` generators, regenerate
   `bencher/example/generated/**`, then migrate the hand-written examples.
7. Migrate `test/**` and `scripts/**`.
8. Migrate docs (`docs/how_to_use_bencher.md`, any gallery text).
9. Delete the old `bencher/bench_cfg.py`.
10. Bump `CACHE_VERSION` in `bencher/cache_management.py` (see
    `hash_persistent` above for why -- pickled layout, not hash values).
11. Add focused unit tests in `test/test_bench_cfg.py`:
    - sub-config defaults,
    - `BenchRunCfg` composition (fresh sub-configs per instance, not shared),
    - `with_defaults` recursion + unknown-key errors,
    - `deep` copies sub-configs independently,
    - `from_cmd_line` flag registration and nested application,
    - `hash_persistent` determinism and invariants (title exclusion,
      result-var reorder invariance) -- no cross-version stability required.
12. Run `pixi run ci` **and** `pixi run test-split`; iterate until both are
    green. The split-render job (`BENCHER_FORCE_SPLIT_RENDER=1`) reroutes
    every report build through the pickle save/load path, so it exercises
    exactly the serialization surface this refactor reshapes.

---

## What is explicitly NOT in scope

- No `__getattr__` / `__setattr__` delegation.
- No deprecation aliases (`run_cfg.cache_results` does **not** work
  post-break, and the existing `level`/`level_to_samples` deprecation shims
  are removed rather than ported).
- No property shims on `BenchRunCfg` that forward to sub-configs.
- No hash redesign -- `hash_persistent` keeps its v5 semantics; only accessor
  paths change.
- No dataclasses-replacing-param rewrite -- `param` is already well-suited to
  nested `Parameterized` holders, and keeping the library means `BenchCfg`
  keeps its `.param` metadata, docs, bounds, and serialization machinery.
- No CLI overhaul beyond moving flag registration/application into each
  sub-config.

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
  seven cache parameters -- not all ~50 run parameters. The revert PR framed
  this as a regression; in practice, grouped autocomplete is better for
  discovery once the groups exist.
- **Extensible.** New concerns (e.g. a future `TelemetryCfg`) slot in as a
  new sub-config without touching existing ones.

---

## Acceptance criteria

- `pixi run ci` **and** `pixi run test-split` pass with no backward-compat
  shims in the source tree (`test-split` covers the pickle save → load →
  render pipeline the new class shape must round-trip through).
- Receiver-agnostic grep for retired names returns nothing outside
  `CHANGELOG.md` and this plan:

  ```
  rg -n "\.(cache_results|cache_samples|clear_cache|clear_sample_cache|overwrite_sample_cache|cache_size|only_plot|max_time_events|time_event|show_aggregated_time_tab|regression_(detection|method|min_history|mad|percentage|delta|absolute|overrides|fail)|level_to_samples|raise_duplicate_exception)\b"
  ```

  (An earlier draft grepped only the `run_cfg.` receiver -- most real call
  sites read `self.bench_cfg.<attr>` and would have slipped through. Names
  that keep their spelling, like `over_time`, can't be grepped this way --
  `over_time` is also an xarray coord name -- so they're covered by the
  mechanical migration + CI instead.)
- `CACHE_VERSION` is bumped so stale caches from prior versions are discarded.
- `CHANGELOG.md` has a **Breaking changes** entry with the full rename table,
  a note that the cache format is reset, a warning that over_time history
  baselines are wiped, and a warning that bench-data files saved with
  `save_result()` (the collect/render split) will no longer load and must be
  regenerated by re-running collect.
- `bencher/identity.py`'s hash-mirror documentation still matches
  `hash_persistent` after the accessor-path migration.
- The package version bump signals the break (major bump recommended --
  `holobench` is on PyPI and users get no runtime deprecation warnings).
- Public API exports the seven sub-config classes from `bencher/__init__.py`.
