# A5 — Configuration Surface Reduction

**Status:** Proposal. Absorbs PR #923's `BENCH_CFG_SPLIT_PLAN.md` as Phase 1 (with
amendments); states the merge condition for PR #1014 (SweepSpec); reshapes plan 13's
declaration bundle; coordinates with plan 10 (regression policy), A2 (plot specs),
and A3/A4 (the composition break converges with A3's BenchData contract).

Field inventories and consumer greps below were generated against `main` on
2026-07-30 (post-#1017). **Regenerate before executing any phase** — this document
goes stale every time a parameter is added, and the whole point is that no more get
added without a home.

---

## 1. The problem: surface = knobs × homes

The configuration surface is not large because bencher has many features. It is
large because most knobs live in **several places at once**, and every extra home
needs precedence rules against every other home — so surface grows multiplicatively
while features grow linearly.

Verified counts (2026-07-30):

| Surface | Size |
|---|---|
| `BenchRunCfg` | 54 param fields |
| `BenchCfg` | 73 param fields (**inherits all 54** — `bench_cfg.py:660`) |
| `Bench.plot_sweep` | 16 kwargs (`bencher.py:298`) |
| `bn.run` | 17 kwargs |
| `BenchRunner.run` | 16 kwargs |

Homes-per-knob, the actual disease:

| Knob | Homes today |
|---|---|
| `repeats` | `BenchRunCfg` field, `bn.run` kwarg, `BenchRunner.run` kwarg, `from_cmd_line` flag (+ plan 13 would add a declared default = 5th) |
| `auto_plot` | `plot_sweep` kwarg **and** `BenchRunCfg` field, resolved against each other in `plot_sweep`'s body |
| `tag` | `plot_sweep` kwarg, folded with `run_cfg.run_tag` by string concatenation (`bencher.py`); plans 13 D3 and 18 D5 each add a tier — the draft precedence table is **six levels deep for one string** |
| `over_time`, `cache_samples`, `backend`, `show` | `BenchRunCfg` field + re-enumerated kwargs on both `bn.run` and `BenchRunner.run` |

Three structural causes:

**C1 — `class BenchCfg(BenchRunCfg)`.** The declaration *is-a* run config, so all 54
run knobs appear on the declaration object, and `hash_persistent()`
(`bench_cfg.py:784-851`) must hand-enumerate which of 73 fields count for cache
identity. That enumeration is the bug class plans 09/15/16 keep patching, and A4 W4
documents its scattered downstream copies.

**C2 — entry points re-enumerate instead of accepting objects.** `bn.run`,
`BenchRunner.run`, and `from_cmd_line` each restate a subset of `BenchRunCfg` as
kwargs with their own defaults. Plan 13's P1 documents the resulting drift.

**C3 — accretion is never culled.** Nine fields are provably dead today (§4,
Phase 0) — declared, documented, in some cases *set* by library code and tests, and
read by nothing.

**The empirical evidence that homes are the disease:** PR #688 split `bench_cfg.py`
into sub-configs (merged 2025-12-28) and was reverted by #704 — not because the
split was wrong, but because it kept **both** access patterns alive
(flat names delegating to nested slots via `__getattr__`). Two homes per knob,
plus delegation machinery to reconcile them, was the entire complexity. PR #923's
plan draws the right lesson: kill the flat layer. A5 generalizes that lesson to the
whole configuration system.

---

## 2. Two standing rules

These apply from the moment this document is accepted, before any phase executes:

**R1 — One home per knob.** Every knob belongs to exactly one config object. Entry
points accept config objects, never re-enumerated kwargs. A PR adding a kwarg to
`plot_sweep`/`bn.run`/`BenchRunner.run` must instead add a field to the owning
object. (`series_id` in #1012 was the last kwarg admitted under the old regime;
under R1 it would have been a `SweepSpec` field.)

**R2 — Every new surface names its funeral.** A new configuration surface is
accepted only together with the deprecation it funds. `SweepSpec` (#1014) is
admissible *because* `plot_sweep`'s declarative kwargs become sugar over it
(Phase 3). Plan 13's bundle is admissible *because* `bn.run`'s kwarg list shrinks
(Phase 4). A surface that only adds is refused.

---

## 3. Target architecture: four objects

The domain decomposes the same way the data does — along orthogonal axes:

| Object | Axis | Contents | Hashed for cache identity? |
|---|---|---|---|
| `SweepSpec` (#1014) | **what** is measured | input/result/const vars, tag, series_id, title, descriptions | **yes — it *is* the key** |
| `RunCfg` (slimmed, ~20 fields in 3 groups) | **how** samples are collected | execution (repeats, sampling, executor), cache policy, time/history | identity subset only (repeats, over_time, run_tag) |
| Analysis — methods on `BenchResult` | **how** results are judged | `RegressionCfg` (9 fields), `aggregate`/`agg_fn` | no — re-runnable on cached data |
| `ReportCfg` / A2 plot specs | **how** results are shown | plot selection & sizing, backend, pane layout, verbosity, server | no |

`BenchCfg` becomes **composition, not inheritance**: `spec + run`, with analysis and
report applied to the result afterward. The payoff is that **the hash boundary
becomes the object boundary**: cache identity is `hash(spec) + hash(run.identity())`,
enforced by the type system instead of by a hand-maintained field list inside
`hash_persistent`. Changing analysis or report config can never invalidate collected
samples, *by construction* — today that invariant is maintained by carefully not
mentioning those fields in the hash.

Effective identity (tag, series, cache key) becomes a **pure function of
`(spec, run)`** — replacing the `run_cfg.run_tag + tag` string concatenation that
forces cross-object precedence rules (§6).

---

## 4. Field disposition table

Every current field, its destination, and (for deletions) the evidence. Groups
follow #923's mapping except where annotated. **Regenerate consumer greps before
executing.**

### DELETE — dead today (Phase 0)

Consumer grep: `grep -rn "\.<field>\b" bencher/` excluding `example/generated`,
declarations, and docstrings.

| Field | Declared | Evidence of death |
|---|---|---|
| `raise_duplicate_exception` | `BenchRunCfg` **and** `BenchCfg` (twice!) | #923's finding: no consumer anywhere |
| `serve_pandas` | `bench_cfg.py:290` | zero consumers |
| `serve_pandas_flat` | `bench_cfg.py:295` | zero consumers |
| `serve_xarray` | `bench_cfg.py:300` | zero consumers |
| `use_holoview` | `bench_cfg.py:312` | zero consumers |
| `use_optuna` | `bench_cfg.py:314` | **set** by examples/meta-generators, **read by nothing** — optuna rendering is driven by plot callbacks, not this flag |
| `nightly` | `bench_cfg.py:211` + a `--nightly` CLI flag | zero consumers |
| `headless` | `bench_cfg.py:215` | **set** in tests, read by nothing |
| `only_hash_tag` | `bench_cfg.py:251` | A4 W6: set by `BenchRunner` (`bench_runner.py:177,422`), read only by a describe-string; the sample key is unconditionally tag-only. A4's `SampleKey.scope` restores the choice properly |

### SweepSpec — the declaration (from `BenchCfg` / `plot_sweep`)

`input_vars`, `result_vars`, `const_vars`, `title`, `description`,
`post_description`, `tag`, `series_id`.

### RunCfg.execution

`repeats`, `subsampling_divisions`, `samples_per_var`, `executor`, `dry_run`,
`only_plot` (execution-mode gate, per #923), `pass_repeat` (moves from
`BenchCfg`/`plot_sweep`), `sample_order` (moves from `plot_sweep` kwarg).

### RunCfg.cache

`cache_results`, `cache_samples`, `clear_cache`, `clear_sample_cache`,
`overwrite_sample_cache`, `cache_size`. (A4 Phase C absorbs this group into its
storage interface; the *user-facing* fields stay here.)

### RunCfg.time

`over_time`, `clear_history`, `on_history_reset`, `max_time_events`, `time_event`,
`time_src` (moves from `plot_sweep` kwarg).

### RunCfg top-level

`run_tag`, `run_date`.

### Analysis — leaves the run config entirely (Phase 2)

| Field(s) | Destination |
|---|---|
| `regression_detection`, `regression_method`, `regression_min_history`, `regression_mad`, `regression_percentage`, `regression_delta`, `regression_absolute`, `regression_overrides`, `regression_fail` | `RegressionCfg` (built in Phase 1), consumed by `BenchResult.check_regressions(cfg)`; per-var thresholds align with plan 10's direction of declaring policy on the result variable |
| `agg_fn`, `agg_over_dims` (`BenchCfg`), `aggregate`/`agg_fn` (`plot_sweep` kwargs) | `BenchResult.aggregate(...)` — already excluded from `hash_persistent`, i.e. already post-hoc in all but calling convention |

### ReportCfg (Phase 1 groups it; A2 is the long-term owner)

`auto_plot` (single home — the `plot_sweep` kwarg dies), `plot_size`, `plot_width`,
`plot_height`, `pane_layout`, `backend`, `max_slider_points`,
`show_aggregated_time_tab`, `show_aggregate_plots`, `summarise_constant_inputs`,
`plot_callbacks` (from `BenchCfg`; A2's serializable plot specs replace the
callables). The four *live* print flags — `print_bench_inputs`
(`result_collector.py:352`), `print_bench_results` (`result_collector.py:371`),
`print_pandas`/`print_xarray` (`bencher.py:800`) — collapse into one
`verbosity` knob (0 = silent, 1 = inputs, 2 = results + tables).

### ReportCfg.server (replaces `BenchPlotSrvCfg`)

`port`, `allow_ws_origin`, `show` (+ `ShowMode`, `normalize_show`, per #923).

### Derived / internal — not user surface

`all_vars`, `iv_time`, `meta_vars`, `hash_value`, `has_results`, `result_hmaps`,
`bench_name` stay on the composed internal object (Phase 5 / A3's BenchData);
they were never meant to be set by users and stop being visible as "config".

### Entry-point kwargs

| Today | Destination |
|---|---|
| `plot_sweep(title, input_vars, result_vars, const_vars, description, post_description, tag, series_id)` | sugar over `SweepSpec` (Phase 3) |
| `plot_sweep(time_src, pass_repeat, sample_order, run_cfg)` | `RunCfg` |
| `plot_sweep(aggregate, agg_fn)` | `BenchResult.aggregate` |
| `plot_sweep(plot_callbacks, auto_plot)` | `ReportCfg` / A2 |
| `bn.run` / `BenchRunner.run` re-enumerations (`repeats`, `subsampling_divisions`, `cache_samples`, `over_time`, `backend`, `show`, …) | deleted; both take `run: RunCfg` + `report: ReportCfg` (Phase 4) |
| `BenchRunner.run(max_subsampling_divisions, max_repeats, min_level, start_repeats)` | stay runner-owned as one `EscalationCfg` group — escalation policy is genuinely the runner's axis |
| `bn.run(save, publish, publisher, grouped, optimise, sampling_context)` | runner/report concerns; survive as `bn.run` parameters (it is the orchestration entry point) but stop shadowing `RunCfg` fields |

---

## 5. Phases

**Release sequencing (owner decision, 2026-07-30):** the current all-additive work
(plans 15–21: identity, duplicates, fault tolerance, SweepSpec phase 1,
single-point ranges, unnamed-parameter rejection) ships first as a normal minor
release. The breaking Phase 0–2 train below targets the **next major release** and
is the continuing iteration of this plan; nothing in it starts until that release
is cut. R1/R2 apply immediately regardless — they constrain new surface, not the
release in flight.

Each phase is independently shippable. Phases 0–2 form **one breaking release
train** (one major bump, one rename table, one `CACHE_VERSION` bump) — users must
learn the new names exactly once. `holobench` ships no runtime deprecation
warnings, so per #923 the break is signaled loudly instead: major version, full
rename table in the changelog, history-baseline wipe called out.

### Phase 0 — Cull (small PR, released with the train)

Delete the nine dead fields (§4) plus their docstring entries, CLI flag
(`--nightly`), setters (`bench_runner.py:177,422` for `only_hash_tag`; test
usages). Deleting a param field makes setting it a hard error — that is the point,
and why this rides the major train.

*Acceptance:* consumer grep for the nine names returns nothing outside
`CHANGELOG.md` and this file; `pixi run ci` green.

### Phase 1 — The #923 split, amended

Execute `BENCH_CFG_SPLIT_PLAN.md` (nested sub-configs, no flat aliases, no
delegation — its own acceptance criteria apply) with three amendments:

1. **No `DisplayCfg`.** Its dead fields die in Phase 0; the four live print flags
   collapse to `ReportCfg.verbosity`. Grouping dead weight preserves it.
2. **Groups are ownership boundaries, not taxonomy.** `RegressionCfg` and
   `ReportCfg` (#923's `VisualizationCfg` + `ServerCfg`) are built here but
   annotated as *departing* in Phase 2 — their class definitions are the migration
   vehicle: relocating a whole object is a one-line break; relocating nine flat
   fields is nine.
3. **The `BenchCfg(BenchRunCfg)` keep-decision is reopened.** #923 predates
   `SweepSpec`; the inheritance is deferred to Phase 5, not endorsed.

### Phase 2 — Analysis off the run (same release train)

`run_cfg.regression` slot is removed; regression is invoked as
`result.check_regressions(RegressionCfg(...))` (and by `bn.run` when a
`RegressionCfg` is passed). `aggregate`/`agg_fn` become
`BenchResult.aggregate(...)`. Neither touches `hash_persistent` — they never did —
so analysis becomes re-runnable against cached data without re-sweeping, which is
what the orthogonality buys.

*Acceptance:* no `regression_*` or `agg_*` field reachable from `RunCfg`; a test
proving a regression-policy change on a fully-cached benchmark triggers zero
worker calls.

### Phase 3 — SweepSpec becomes the canonical declaration

Precondition: #1014 phase 1 merged (spec + `bind()` only — hold the
`title: str | SweepSpec` positional overload until §6 is confirmed; fix the
duplicate `sweep_executor` import; fix the `tag or None` edge that treats an
explicit `tag=""` as unset).

Then invert the relationship: `plot_sweep`'s declarative kwargs **internally
construct a `SweepSpec`**, so there is exactly one declaration path and kwargs are
sugar that cannot drift. The `plot_sweep` signature is frozen — new declarative
capability lands as a spec field (R1).

*Acceptance:* `plot_sweep(**kwargs)` and `plot_sweep(spec)` produce identical
`BenchCfg` hashes via the same internal path; a grep-able marker test pins the
signature length.

### Phase 4 — Entry points take objects; precedence implemented once

`bn.run(target, run=None, report=None, ...)` and
`BenchRunner.run(run=None, report=None, escalation=None)` replace the 16–17-kwarg
lists. Plan 13's spine (**env > call-site > declared > library default**) is
implemented as **one generic overlay resolver** over `RunCfg` fields — not per-knob
logic in three entry points. Plan 13's decorator is reshaped to attach existing
objects rather than re-enumerating knobs:

```python
@bn.benchmark(spec=LATENCY, defaults=bn.RunCfg(execution=bn.ExecutionCfg(repeats=5)),
              category="Planning")
```

Only genuinely new metadata (`category`, `order`) earns new fields; P4b's display
alias belongs on the result variable itself.

*Acceptance:* adding an env override for any `RunCfg` field requires zero new
code; `from_cmd_line` registers flags via the sub-configs (#923's
`add_cli_args`/`apply_cli_args`).

### Phase 5 — Break the inheritance (with A3)

`BenchCfg(BenchRunCfg)` becomes composition: the internal object holds
`spec: SweepSpec` + `run: RunCfg` + derived fields. Cache identity becomes
`hash(spec) + hash(run.identity())`, preserving `hash_persistent`'s documented v5
semantics (title excluded; input order folded; result/const vars unordered;
`include_result_vars=False` history variant) — only the *derivation* moves from
field-enumeration to object boundary. A3's BenchData contract (netCDF + JSON
manifest) is the natural vehicle; A3 Phase D2 and this phase should be planned as
one piece of work.

*Acceptance:* `hash_persistent`'s invariant tests pass unchanged;
`isinstance(bench_cfg, BenchRunCfg)` is False; no rendering or analysis field is
*representable* on the hashed objects.

---

## 6. Tag ownership (resolves plan 13 D5 and plan 18 D5)

The six-tier tag precedence exists only because `tag` has multiple homes and the
effective tag is assembled by concatenation (`run_cfg.run_tag + tag`). Under A5:

- `tag` lives on **`SweepSpec` only** — it is measurement identity and is hashed.
- `run_tag` lives on **`RunCfg` only** — it is run/batch identity.
- The effective cache/history/report identity is a **pure function of
  `(spec, run)`**, defined next to the key module (A4 §3.2), replacing
  concatenation.

Precedence then collapses to the standard spine with one entry per tier:
env (`BENCHER_TAG`) > call-site (`plot_sweep(tag=…)`, which under Phase 3 is sugar
for overriding the spec) > `spec.tag` > decorator defaults > `""`. Tiers cannot
collide because no two of them are the same kind of thing.

**OWNER DECISION:** confirm `spec.tag` over decorator defaults (this is plan 18
D5's tier 3-over-4, now derivable from "the spec states what is measured") before
Phase 3's positional-overload step.

---

## 7. Risks

- **Two breaks instead of one.** Phase 5 is a second major break after the
  Phase 0–2 train. Mitigation: Phases 0–2 change *names*; Phase 5 changes
  *construction* — most user code (`plot_sweep(...)` calls) is untouched by
  Phase 5, so the second break is far smaller. Do not attempt to merge them into
  one mega-release; #688 shows what over-scoping this refactor does.
- **#923's plan drifting stale.** It regenerated its inventories once already.
  Both documents carry the same instruction: regenerate before executing.
- **SweepSpec becoming a rival config.** Guarded by #1014's
  `test_run_configuration_has_no_field` and R2; Phase 3's inversion is the
  structural fix — a front-end cannot drift from a back-end it *is*.
- **The overlay resolver and param's set-tracking.** Plan 13 documents that param
  cannot distinguish "set to the default" from "unset"; the resolver inherits that
  caveat. Document it; fixing param is out of scope.

---

## 8. Relationship to other plans and PRs

| Item | Relationship |
|---|---|
| PR #923 | Absorbed as Phase 1, with §5's three amendments; its acceptance criteria and migration sequence apply |
| PRs #688 → #704 | The evidence base for R1; no compatibility shims survive any phase |
| PR #1014 (SweepSpec) | Phase 3 precondition and merge condition: phase-1 subset now, positional overload after §6 |
| Plan 13 | Its precedence spine survives as Phase 4's resolver; its decorator is reshaped to attach objects; its D5 is resolved by §6 |
| Plan 10 | Per-var regression thresholds and Phase 2's `RegressionCfg` are the same direction — coordinate the `RegressionCfg` field set |
| Plan 18 D5 | Resolved by §6 |
| A2 | `ReportCfg` + serializable plot specs are A2's surface; Phase 1 only groups the fields A2 will own |
| A3 | Phase 5 converges with A3 Phase D2 — plan as one piece of work |
| A4 | `RunCfg.cache` fields front A4's storage interface; `only_hash_tag`'s deletion (Phase 0) is completed by A4's `SampleKey.scope` |
