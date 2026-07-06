# Plan 13 — Benchmark Declaration Bundle & Run Defaults

**Goal:** Give a benchmark one declaration-level home for its run defaults
(repeats, tag, sampling context, …) and report metadata (category, display
aliases), consumed uniformly by `bn.run`, `BenchRunner`, and test harnesses —
with first-class env-var overrides and one explicit precedence rule:
**env > call-site > declared > library default**.

**Branch name:** `feat/benchmark-declaration-bundle`

**⚠️ Read first:** Phases 1–3 touch how `run_cfg` values are resolved; the
`hash_persistent()` cache/history contract (plan 09, `bencher/bench_cfg.py:757`)
must not observe any new field. Every phase is independently shippable; do
1 → 2 → 3 in order; 4 and 5 are independent.

---

## Problem statement (with evidence)

### P1 — Run configuration has no home on the benchmark itself

A benchmark function (`def my_bench(run_cfg, report) -> bn.Bench`) carries no
defaults. Every entry point re-specifies them:

- `bn.run` hardcodes `repeats: int = 1` (`bencher/run.py:68`) and takes
  `sampling_context`, `over_time`, `publisher`, … per call (`bencher/run.py:64-83`).
- `BenchRunner.run` repeats the same parameter list with its own `repeats=1`
  default (`bencher/bench_runner.py:296-317`).
- `from_cmd_line` re-declares `--repeats` a third time (`bencher/bench_cfg.py:542-547`).

So across dozens of modules, the `__main__` block and the test-harness call
inevitably drift (repeat counts diverge; one passes a `publisher`, the other
doesn't). The only existing seam, `BenchRunCfg.with_defaults`
(`bencher/bench_cfg.py:594-625`), runs inside the benchmark body after the
entry point has built the `run_cfg`, cannot influence `bn.run`-level knobs
(`show`, `save`, `publish`, `sampling_context`), and is invisible to harnesses
that want to *read* a benchmark's intended configuration without running it.

### P2 — Environment-variable overrides are reinvented downstream

Unattended/CI/agent loops need to override repeats and headless behavior
without editing source, but bencher reads exactly one behavior env var today —
`BENCHER_FORCE_SPLIT_RENDER` (`bencher/bencher.py:761`), nothing for repeats or
`show` — so every project grows ad-hoc `os.environ.get("BENCH_REPEATS")` shims
around each `__main__`, each with its own parsing bugs.

### P3 — Default tag derivation forces frame inspection downstream

Nothing derives a cache/report tag from the benchmark callable, even though
`bn.run` holds it — its signature has no `tag=` at all (`bencher/run.py:64-83`).
`plot_sweep(tag="")` defaults to empty (`bencher/bencher.py:281`), the
effective cache tag is `run_cfg.run_tag + tag` (`bencher/bencher.py:524`), and
`run_tag` defaults to `""` (`bencher/bench_cfg.py:387`). `BenchRunner` *does*
use `fn.__name__`, but only for its own name (`bencher/bench_runner.py:96-98`)
and for report naming, where an empty `run_tag` falls back to today's date
(`bencher/bench_runner.py:449-467`). So wrappers that want "tag defaults to
the function's name" resort to `inspect.currentframe().f_back` hacks.

### P4a — Scorecard grouping lives in an external registry

The scorecard (added in 1.113.0, `CHANGELOG.md`) groups rows by a
caller-maintained registry `tag -> (category, display_name, description)`
(`bencher/scorecard/config.py:53`); unregistered tags fall into "Other" via a
name heuristic (`bencher/scorecard/discover.py:19-35`). The tag is recovered
from the *directory name* (`bencher/scorecard/discover.py:50-54`) because the
summary JSON from `result_to_dict` carries only `bench_name`, `provenance`,
`metrics`, `regressions` (`bencher/report_export.py:122`, :157) — no category.
The author cannot self-declare grouping; a parallel registry is hand-synced.

### P4b — Result variables have no render-time display alias

A result var's `.name` is its identity everywhere: dataset column
(`bencher/result_collector.py:229`), summary metric key
(`bencher/report_export.py:58`), plot axis (`as_dim` returns
`hv.Dimension((self.name, self.name), ...)`, `bencher/variables/results.py:133-134`).
Input and result vars are param attributes of one `ParametrizedSweep` class,
so they cannot share a name — when the natural label is taken (an input
`planning_time` budget vs. the measured planning time), users keep an awkward
identity name and maintain external rename maps, e.g. the scorecard's
`aliases` (`bencher/scorecard/config.py:54`, `bencher/scorecard/model.py:18-47`).

---

## Proposed design

One precedence spine, applied per knob: **env > call-site kwarg > declared
default > library default**. "Call-site" includes fields the caller set on an
explicit `run_cfg`; declared defaults merge via `BenchRunCfg.with_defaults`'s
still-at-param-default heuristic (`bencher/bench_cfg.py:623`), so a call-site
value equal to the library default is indistinguishable from unset — document
this; fixing set-tracking in param is out of scope.

### D1 — `@bn.benchmark(...)` declaration bundle

New module `bencher/declaration.py` (keeps `bencher.py`'s 1,529 lines from
growing; see plans 07/08):

```python
@bn.benchmark(
    tag="pathfinding",              # P3: also the scorecard/report tag
    repeats=5, subsampling_divisions=3, over_time=True, max_time_events=20,
    category="Planning", order=10,  # P4a
    sampling_context=make_gpu_ctx,  # zero-arg FACTORY, not an instance
)
def bench_pathfinding(run_cfg, report) -> bn.Bench: ...
```

- Returns the function unchanged with `fn.__bench_declaration__ =
  BenchDeclaration(...)` (frozen dataclass). No wrapper — signature-sniffing in
  `_execute_bench_fn` (`bencher/bench_runner.py:272`) keeps working.
- `sampling_context` is declared as a zero-arg factory because context-manager
  instances are single-use; `bn.run`'s existing instance kwarg
  (`bencher/run.py:81`) stays the call-site form and wins over the factory.
- Public `bn.get_declaration(target) -> BenchDeclaration | None` so test
  harnesses and batch runners read the same bundle without running anything.
- Consumption: `bn.run` resolves the bundle before building `_run_kwargs`
  (`bencher/run.py:209-221`); `BenchRunner.run` applies it per bench-fn inside
  its loop (`bencher/bench_runner.py:429-432`) since one runner can hold
  differently-declared functions; `run_cfg`-shaped fields merge via
  `BenchRunCfg.with_defaults`.
- To distinguish "caller passed `repeats=1`" from "default", the
  declaration-overridable kwargs of `bn.run`/`BenchRunner.run` switch to the
  `UNSET` sentinel (`bencher/utils.py:529`, already the pattern for
  `subsampling_divisions`, `bencher/run.py:67`); effective fallbacks unchanged.

### D2 — Env overrides in `bn.run`

Resolved once, at the top of `bn.run` (the canonical unattended entry point).
`BenchRunner` stays env-free so programmatic composition is deterministic.

| Variable | Type | Maps to |
|---|---|---|
| `BENCHER_REPEATS` / `BENCHER_MAX_REPEATS` | int | `repeats` / `max_repeats` |
| `BENCHER_SUBSAMPLING_DIVISIONS` / `BENCHER_MAX_SUBSAMPLING_DIVISIONS` | int | sampling resolution |
| `BENCHER_SHOW` | ShowMode/bool | `show` (headless = `BENCHER_SHOW=none`) |
| `BENCHER_SAVE`, `BENCHER_PUBLISH`, `BENCHER_OVER_TIME`, `BENCHER_CACHE_SAMPLES` | bool | same-named kwargs |
| `BENCHER_TAG` | str | effective tag (D3) |

Parsing is **strict**: a set-but-unparsable value raises `ValueError` naming
the variable and its accepted values — a silently ignored override in CI
produces wrong data, worse than a crash. An empty value counts as **unset**
(falls back to the declared/library default), so a per-invocation assignment
prefix such as `BENCHER_REPEATS= python -m my_benchmarks` — a POSIX var-assignment
prefix, no space after the `=`, setting the variable to empty for that one
command — is a no-op rather than an error. Bools accept `1/0/true/false/yes/no`
(case-insensitive); `BENCHER_SHOW` goes through `normalize_show`
(`bencher/bench_cfg.py:44`) plus the bool spellings. No lenient mode.

### D3 — Tag defaulting from the callable

`bn.run` gains `tag: str | None = None`. Effective tag = `BENCHER_TAG` >
`bn.run(tag=)` > declared `tag` > **(decorated targets only)**
`target.__name__` > legacy `""`. It is written into `run_cfg.run_tag` only when
`run_tag` is still empty (never clobbers an explicit one), flowing into cache
identity via `bencher/bencher.py:524` and replacing the date suffix at
`bencher/bench_runner.py:449-453`. The `__name__` fallback is gated on the
decorator because the tag is hashed (`bencher/bench_cfg.py:793`): auto-tagging
*undecorated* benchmarks would silently re-key every existing cache/history,
while decorated ones are a new opt-in surface with no history to break.
Renaming a decorated function re-keys its cache; document at the decorator.

### D4 — Category/order flow into summaries and the scorecard

- `plot_sweep` gains `category: str | None = None, order: int | None = None`
  (`bencher/bencher.py:271`), also settable in the declaration (plot_sweep
  wins — the closer call site). Stored as new `BenchCfg` params next to
  `description` (`bencher/bench_cfg.py:701`). `hash_persistent` folds an
  explicit tuple (`bencher/bench_cfg.py:787-801`), so new params stay out of
  cache identity by construction — mirror the title-exclusion note (:779-782).
- `result_to_dict` exports `category`/`order` when set
  (`bencher/report_export.py:122`; extend the payload at :157) — additive
  optional keys, `schema_version` unchanged.
- `discover_summaries` prefers, per tag: registry entry
  (`bencher/scorecard/discover.py:29-35`) > summary-embedded category >
  `other_category` — the registry stays the downstream *override* (consistent
  with call-site > declared). `order` sorts within category before the
  display-name sort (`bencher/scorecard/discover.py:80-82`).

### D5 — `display_name` on result variables

- Add a `display_name: str | None = None` slot to `ResultFloat` (and each
  `Result*` class with a rendered label), appended to `__slots__` **and**
  `_hash_exclude` (`bencher/variables/results.py:102-107`) so `_hash_slots`
  (`bencher/variables/results.py:50-86`) never hashes it; the slot-coverage
  test in `test/test_hash_persistent.py` then enforces the exclusion.
- Rendering: `as_dim` becomes
  `hv.Dimension((self.name, self.display_name or self.name), unit=self.units)`
  (`bencher/variables/results.py:133-134`) — holoviews labels flow to plots for
  free. `result_to_dict` adds `"display_name"` beside `"variable"`
  (`bencher/report_export.py:58`). The scorecard keeps column *identity* on the
  (aliased) variable name and uses `display_name` only as header text, when all
  benchmarks sharing the column agree (`bencher/scorecard/model.py:50-58`).
- The dataset variable stays `rv.name` (`bencher/result_collector.py:229`) —
  display_name is render-time only and never enters storage or hashing.

---

## Phased steps

1. **Declaration bundle:** add `bencher/declaration.py` (`BenchDeclaration`,
   `benchmark`, `get_declaration`), export beside `run`
   (`bencher/__init__.py:172`); consume in `bn.run` and `BenchRunner.run`;
   flip declaration-overridable kwargs to `UNSET`.
2. **Env overrides:** `_apply_env_overrides()` in `run.py` per the table;
   document precedence in the `bn.run` docstring.
3. **Tag rule:** `tag=` kwarg on `bn.run`, `BENCHER_TAG`, `__name__` fallback.
4. **Category/order:** `plot_sweep` + declaration → `BenchCfg` →
   `result_to_dict` → scorecard discover/order.
5. **display_name:** result-var slot, `as_dim`, export, scorecard header.

Run `pixi run ci` per phase; one PR per phase.

## Tests / acceptance criteria

- Declared `repeats=5` used when call-site omits; `bn.run(fn, repeats=2)` wins;
  `BENCHER_REPEATS=9` beats both (monkeypatched env).
- Undecorated function through `bn.run`/`BenchRunner` with no env set produces
  a `BenchCfg` with identical `hash_persistent(...)` and field values to
  pre-change (regression test pinning the resolved config).
- Env: unparsable value raises `ValueError` naming the variable; empty string
  is unset; `BENCHER_SHOW=none` starts no Panel server.
- Tag: decorated fn without tag gets `fn.__name__` in `run_cfg.run_tag`;
  undecorated keeps `""` + date suffix (`bencher/bench_runner.py:452`); an
  explicit `run_cfg.run_tag` is never overwritten.
- `sampling_context` factory is invoked once per `bn.run` call and exits
  before `br.show` (parallel to the path at `bencher/run.py:228-235`).
- Category/order/display_name never change `BenchCfg.hash_persistent` or any
  result-var `hash_persistent()`; summary JSON round-trips them; the scorecard
  groups by embedded category without a registry, and a registry entry still
  overrides. Slot-coverage + determinism tests in
  `test/test_hash_persistent.py` stay green.

## Migration & compatibility

- Everything is opt-in; no existing call sites change behavior. `bn.run`'s
  kwarg defaults change spelling (`1` → `UNSET`) but not effect.
- Summary JSON gains only optional keys; `ScorecardConfig.registry`/`aliases`
  remain supported indefinitely as overrides.
- **Plan 09 interaction:** plan 09 proposes folding the variable *name* into
  the per-variable hash (its D2). `display_name` must stay excluded whichever
  lands first — if plan 09 lands second it must hash `name` explicitly, not
  "all slots"; if first, this plan's `_hash_exclude` entry suffices.

## Risks

- `with_defaults`'s equals-default heuristic can treat an explicit `repeats=1`
  as unset and let a declared default win — pre-existing, documented
  limitation (`bencher/bench_cfg.py:623`).
- Env overrides apply to *every* `bn.run` in the process (e.g. a harness
  invoking many benchmarks) — intended, but harnesses needing isolation must
  scrub `BENCHER_*`; add a docs note.
- Renaming a decorated function re-keys its cache/history (same blast radius
  as renaming a tag today).
- Strict env parsing turns a typo into a crash in CI — intended; note it in
  the CHANGELOG.

## Coordination

- **Plan 09** (hash semantics): display_name exclusion, above; cross-reference
  both PRs.
- **Plans 07/08** (core cleanup): new code goes in `bencher/declaration.py`,
  not `bencher.py`/`bench_cfg.py`.
- **Plan A3** (BenchData contract): category/order/display_name belong in the
  JSON manifest, not the netCDF — align field names when A3 lands.
- CHANGELOG entries per phase; do not bump the version (plans/README.md rule 4).
