# Plan 11 — Worker Lifecycle & Resource Injection

**Goal:** Give `ParametrizedSweep` workers a sanctioned lifecycle: (a) a way to inject
expensive shared resources (a GPU simulator, a hardware rig, a database server, a
subprocess pool) without module-level globals, (b) per-sample and per-run
setup/teardown hooks, and (c) a library *guarantee* that result variables are reset
to their declared defaults before each sample, so a sample that returns early can
never silently record the previous sample's values.

**Branch name:** `feat/worker-lifecycle`

**Rules:**
- Always use the pixi environment (`pixi run ...`). Never run tools directly.
- Work on a feature branch, never `main` (merging to `main` with a version bump
  auto-publishes to PyPI — see plans/01).
- None of these features may change any cache key. Injected resources and lifecycle
  hooks must be invisible to `BenchCfg.hash_persistent` and to the sample-cache job
  key. Add tests that assert this.
- If a step fails in a way this plan does not cover, stop and report rather than
  improvising.

---

## 1. Background — how a worker is constructed and invoked today

Verify each step against source before changing anything:

1. **Construction.** A `ParametrizedSweep` *instance* passed to `Bench` is stored and
   its bound `__call__` becomes the worker (`bencher/worker_manager.py:92-94`). But
   two entry points construct instances themselves, always **with no constructor
   arguments**: `bn.run(MyClass)` does `target = target()` (`bencher/run.py:157-158`),
   and the function-plus-config path builds a **fresh instance per sample** via
   `input_cfg = worker_input_cfg()` (`bencher/worker_manager.py:29`, wrapped at
   `worker_manager.py:34-49` and bound at `:112`).
2. **Invocation.** `calculate_benchmark_results` wraps the worker once
   (`bencher/bencher.py:943`), builds one `Job` per grid point (`bencher.py:959-967`),
   and submits through `FutureCache.submit` (`bencher/job.py:253-309`). Serial
   execution calls `run_job(job)` in-process (`job.py:307`); parallel executors pickle
   `(run_job, job)` — including the bound-method worker and therefore the whole
   instance — per submission (`job.py:301`).
3. **Per-sample dispatch.** `worker_kwargs_wrapper` strips meta keys and deep-copies
   only the *kwargs*, never the instance (`bencher/sweep_executor.py:61-66`). The
   new-style `__call__` path then runs `update_params_from_kwargs(**kwargs)` →
   `benchmark()` → `get_results_values_as_dict()`
   (`bencher/variables/parametrised_sweep.py:220-224`).
4. **No reset.** `update_params_from_kwargs` sets **only the keys present in kwargs**
   (`parametrised_sweep.py:55-63`) — sweep inputs and const inputs, never result
   params. `get_results_values_as_dict` reads whatever value each result param
   currently holds (`parametrised_sweep.py:104-110`). Nothing anywhere resets result
   params between samples.
5. **Const inputs clobber constructor values.** When `const_vars` is not given,
   `plot_sweep` uses `get_input_defaults()` (`bencher/bencher.py:376`), which returns
   the **class-declared** defaults (`parametrised_sweep.py:126-138`), and those are
   re-applied to the instance every sample via kwargs. So even param values passed to
   the constructor do not survive into samples — bencher re-parameterizes the worker
   from sweep values each call.
6. **Identity.** The sample-cache key hashes only the sorted function inputs plus the
   tag (`bencher/worker_job.py:63`); const-var *values* also enter
   `BenchCfg.hash_persistent` (`bencher/bench_cfg.py:801`). Plain instance attributes
   enter neither — but anything stored as a *param* does, via const-vars.
7. **`sampling_context`.** `bn.run()` recently gained a run-scoped context manager
   that wraps only the sampling phase (`bencher/run.py:81`, used at `run.py:224-235`;
   commit `8ea771e`, CHANGELOG 1.90.0). It solves "release resources before the Panel
   server blocks", but offers **no way to pass the resource into the worker** — users
   still need globals/ContextVars to bridge the gap.
8. **The singleton.** `ParametrizedSweepSingleton`
   (`bencher/variables/singleton_parametrized_sweep.py:66-121`) exists to let users
   keep expensive state alive across bencher's re-instantiations: per-subclass
   instance via `__new__` (`:81-85`), truthy-once `init_singleton()` with
   context-manager rollback (`:94-114`), manual `reset_singleton()` (`:116-121`). The
   state lives in class attributes (`:77-78`) and therefore **leaks across runs in
   the same process** unless the user remembers to reset.

## 2. Pain patterns (all verified against the paths above)

### P1 — no sanctioned resource injection

A benchmark that needs a live handle (GPU simulator, database connection, hardware
rig) cannot rely on constructor injection: `bn.run(MyClass)` and the
`worker_input_cfg` path construct with no args (§1.1), constructor-set *param* values
are clobbered by const defaults (§1.5), and parallel executors re-pickle the instance
per job (§1.2). The observed workaround is module-level globals or ContextVars set by
an outer context manager and read back inside `__init__`/`benchmark()`, guarded by
hand-rolled "did the context change since my singleton initialized?" checks. The
singleton class papers over this and adds its own cross-run leak (§1.8).

### P2 — stale result carry-over

Result variables already declare NaN defaults *by design* so that "unrecorded sample
= missing = dropped from aggregation" (`bencher/variables/results.py:115-128` and the
`ResultBool` rationale at `:148-161`). But because the same instance is reused for
every sample with no reset (§1.4), a `benchmark()` that returns early leaves the
previous sample's value in place — the returned dict contains the stale value, it is
written into the dataset **and persisted into the sample cache** under the new
sample's key. The defensive convention (manually re-assign NaN at the top of every
`benchmark()`) is boilerplate every user must rediscover. Worse, the behavior is
executor-dependent: serial execution carries state across samples, while
process-pool executors unpickle a pristine pre-run copy per job (§1.2), so the bug
appears and disappears when switching `Executors`.

### P3 — no setup/teardown hooks

There is no per-sample or per-run hook on `ParametrizedSweep` (grep confirms: no
`setup`/`teardown` symbols in `parametrised_sweep.py`, `worker_manager.py`,
`sweep_executor.py`). Cleanup ends up in `__del__`, `atexit`, or externally-called
functions that some entry points forget. `sampling_context` (§1.7) covers only the
outermost `bn.run()` scope.

## 3. Research questions (resolve before implementing)

1. **Reset scope.** Which of the 13 `ALL_RESULT_TYPES` (`results.py:470-484`) have
   meaningful declared defaults, and do any (e.g. `ResultReference`,
   `ResultContainer`, `ResultHmap`) break if reset with `deepcopy(param.default)`?
   Does `param.update` validation accept every default (NaN bounds are already
   special-cased for `ResultBool` at `results.py:163-179`)?
2. **Legacy `__call__` path.** Workers that override `__call__` directly (deprecated,
   `worker_manager.py:96-104`) manage their own dispatch. Can the reset live in
   `ParametrizedSweep.__call__`'s new-style branch only, with a public
   `reset_result_vars()` helper for legacy classes — or should it live in
   `worker_kwargs_wrapper` where it would also cover legacy instances but not plain
   functions?
3. **Carry-over dependents.** Search examples/tests for workers that *intentionally*
   accumulate state in a result param across samples (counters, running bests). Does
   anything in-repo rely on it? This decides opt-out vs opt-in default.
4. **Hook placement vs cache.** When every sample is a cache hit, the worker never
   runs (`job.py:270-280`). Should `setup_run()` be skipped entirely, or run lazily
   before the first actual execution? Recommendation: lazy — a run of pure cache hits
   should not spin up a simulator.
5. **Parallel semantics.** Per-sample hooks would execute in the child process on a
   per-job unpickled copy; run-level hooks in the parent. Verify how
   `ParametrizedSweepSingleton.__new__` interacts with unpickling (protocol 2
   `__newobj__` calls custom `__new__`, so child-side copies may alias the child's
   singleton). Document, don't fight, these semantics.
6. **Resource identity.** Injected resources must stay out of all hashes (§1.6
   confirms plain attributes already are). But a resource that *semantically changes
   results* (different simulator build) is then invisible to the cache. Is the
   existing `tag` mechanism the sanctioned salt, or does `to_bench` need a
   `cache_salt`? Recommendation: document `tag`; no new knob.

## 4. Proposed design (refine against the research above)

### 4.1 Automatic result-var reset (the guarantee)

At the top of the new-style `__call__` branch (`parametrised_sweep.py:220-224`),
before `update_params_from_kwargs`: reset every result param to
`deepcopy(param_obj.default)`. Expose it as `reset_result_vars()` so legacy
`__call__` overriders and tests can call it. Opt-out via a class attribute
(e.g. `reset_results_between_samples: ClassVar[bool] = True`) for workers that
deliberately accumulate. This turns the *documented intent* of the NaN defaults
(`results.py:121-127`) into an enforced invariant and makes serial and parallel
executors behave identically.

### 4.2 Per-sample hooks

`setup_sample()` / `teardown_sample()` no-op methods on `ParametrizedSweep`.
Ordering per sample: reset result vars → `update_params_from_kwargs` (so setup sees
this sample's inputs) → `setup_sample()` → `benchmark()` → `teardown_sample()` in a
`finally:` (cleanup must run even when `benchmark()` raises) →
`get_results_values_as_dict()`. Error semantics: a raising `setup_sample` propagates
exactly like a raising `benchmark()` does today (serial: aborts the sweep; parallel:
fails the future). A "skip this sample, record defaults, continue" exception is
deliberately **out of scope** — note it as follow-up, since it changes sweep-failure
semantics for everyone.

### 4.3 Run-level hooks

`setup_run()` / `teardown_run()` invoked around the job loop in
`calculate_benchmark_results` (`bencher.py:945-1002`), parent-process only,
`teardown_run` in a `finally:`. Lazy `setup_run` per research question 4. Interaction
with `BenchRunner.add_bench` (`bench_runner.py:234-253`): hooks fire once per
`plot_sweep`, i.e. once per progressive iteration — document this.

### 4.4 Resource injection

Bless the pattern "construct the instance yourself, hand it to bencher" (already
works via `to_bench()` and `bn.run(instance)`, `run.py:162-174`) and close the gaps:

- Add `resources: Any | None = None` handling to `ParametrizedSweep.__init__`,
  stored as a plain attribute `self.resources` — *outside* the param namespace so it
  can never leak into const-var hashing (§1.6) or be clobbered by
  `update_params_from_kwargs`.
- Thread `resources=` through `to_bench` / `create_bench`
  (`parametrised_sweep.py:247-249`, `factories.py:20-44`) and `bn.run(target,
  resources=...)` so `bn.run(MyClass, resources=...)` forwards it to the
  constructor instead of the current no-arg instantiation (`run.py:157-158`).
- Parallel executors require picklable workers already; fail with a clear error
  message if `resources` is unpicklable and the executor is not `SERIAL`, rather
  than a deep `PicklingError`.
- Do **not** deprecate `ParametrizedSweepSingleton` in this plan; re-scope its
  docstring to its remaining niche (cross-`Bench` sharing within a process) and
  point new code at `resources=`.

### 4.5 Layering (document in one place)

| Scope | Mechanism | Runs where |
|---|---|---|
| Whole sampling phase of `bn.run` | `sampling_context` (`run.py:81`) | parent process |
| One `plot_sweep` run | `setup_run` / `teardown_run` | parent process |
| One sample | `setup_sample` / `teardown_sample` | worker process |
| Data plumbing | `resources=` on constructor / `to_bench` / `bn.run` | travels with the instance |

## 5. Phased implementation (independently shippable)

- **Phase 1 — reset guarantee.** `reset_result_vars()` + auto-reset in `__call__` +
  opt-out flag + tests (research Q1-Q3 first). Smallest diff, highest value.
- **Phase 2 — per-sample hooks.** `setup_sample`/`teardown_sample` with the §4.2
  ordering; tests for exception paths and parallel executors.
- **Phase 3 — run hooks + resources.** §4.3 and §4.4 together (resources are what
  run hooks mostly manage); docs page covering §4.5; CHANGELOG entries per phase.

## 6. Acceptance criteria

- A worker whose `benchmark()` returns early on sample N records the declared
  default (NaN → missing) for untouched result vars, not sample N−1's value —
  under both `Executors.SERIAL` and `Executors.MULTIPROCESSING`.
- Opt-out flag restores today's carry-over behavior; a test pins it.
- Hook ordering test: reset → params → setup → benchmark → teardown(finally) →
  collect; teardown runs when `benchmark()` raises.
- `resources=` object reaches `benchmark()` via `self.resources` from all three
  entry styles (`Bench(...)`, `to_bench()`, `bn.run(Class, resources=...)`).
- Hash/key invariance tests: `BenchCfg.hash_persistent` and
  `function_input_signature_pure` are byte-identical with and without `resources`
  and with and without hooks defined.
- Existing tests (`test_parametrized_sweep.py`, `test_singleton_parametrized_sweep.py`,
  `test_worker_manager.py`, `test_sweep_executor.py`) still pass; `pixi run ci` green.

## 7. Migration & backward compatibility

- Auto-reset is behavior-changing for workers that (accidentally or not) relied on
  carry-over. Ship it default-ON with the class-level opt-out, a headline CHANGELOG
  entry, and a one-release `FutureWarning` **only if** research Q3 finds in-repo
  reliance; otherwise default-ON immediately — the current behavior records
  silently-wrong data, which is worse than any plausible carry-over use.
- No cache key changes, so no `CACHE_VERSION` bump — but cached samples written
  before Phase 1 may contain stale-carry-over values; mention `clear_tag` /
  `overwrite_sample_cache` as the remedy in the CHANGELOG.
- `sampling_context` is unchanged and remains the right tool for "release before the
  server blocks"; the new docs must show it composing with `resources=`.

## 8. What NOT to do

- Do not put resources in the param namespace or in any hash (const-var values are
  hashed at `bench_cfg.py:801`).
- Do not add skip-sample/retry semantics to hook exceptions in this plan.
- Do not remove or rename `ParametrizedSweepSingleton`.
- Do not reset *input* params to defaults — const-vars already re-apply them per
  sample (§1.5); changing that is out of scope.

## 9. Coordination

- **Plans 07/08 (core cleanup/refactors):** Phase 3 touches
  `calculate_benchmark_results`; land before or rebase after any `bencher.py` split.
- **Architecture A4 (caching):** the hash-invariance tests here become fixtures for
  A4's key module; resource identity deliberately stays out of keys (research Q6).
- **Plan 05 (test coverage):** the executor-matrix tests added here should slot into
  its parallel-executor coverage gap.
