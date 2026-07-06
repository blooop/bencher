# Plan 10 — Regression Policy on Result Variables & Structured Verdict Export

**Goal:** Let a result variable *carry its own regression policy* — method, threshold,
and a first-class **severity** (`gate` / `notify` / `info`) — instead of forcing every
CI consumer to maintain an out-of-band registry that is sliced into
`BenchRunCfg.regression_overrides` per run. Then make the verdicts leave the library
as a canonical, schema-versioned JSON contract plus a one-call aggregate
(`report.has_gate_regressions`) so a merge gate needs zero parsing, while notify-only
regressions can feed Slack messages or PR comment tables without ever blocking.

**⚠️ Read first:** `bencher/regression.py` mixing detection + rendering is plans 07/08
territory (`plans/README.md:80`, `plans/08-core-refactors.md:22` Task 1 extracts the
rendering half into `regression_rendering.py`). This plan touches only the *detection
and report* half (`RegressionResult`/`RegressionReport`/`detect_regressions`) and the
export layer — do not restructure rendering here. If plan 08 Task 1 has already
landed, the same symbols simply live in two files; the changes below are unaffected.

**Rules:**
- Always use the pixi environment (`pixi run ...`, e.g. `pixi run pytest`). Never run
  tools directly.
- Work on a feature branch, never `main` (merging to `main` with a version bump
  auto-publishes to PyPI — see plans/01).
- Default behavior must not change for existing users: severity defaults must
  reproduce today's `regression_fail` / report output exactly.
- Class-level policy must NOT invalidate the `over_time` history cache (see §2 G1 —
  this is a hard requirement, enforced by the slot-coverage contract).
- If a step fails in a way this plan does not cover, stop and report rather than
  improvising.
- **Line numbers are as-of the current `main` (CHANGELOG ≤ 1.113.0) and will
  rot** — the durable reference is always the named symbol (`detect_regressions`,
  `_normalize_overrides`, `RegressionResult.to_dict`, `_hash_exclude`, …). If a
  cited line has moved, grep the symbol; the responsibility, not the address, is
  what the plan depends on.

---

## 1. Background — how policy and verdicts flow today

Build on, don't re-invent: per-variable thresholds already exist. CHANGELOG 1.112.0
(2026-07-02, PR #974) added `BenchRunCfg.regression_overrides`
(`bencher/bench_cfg.py:454`) — `{var_name: bare_number | {method: threshold}}`,
validated by `_normalize_overrides` (`bencher/regression.py:1348`). The rest of the
pipeline:

- **Config** lives on `BenchRunCfg`: `regression_detection` (`bench_cfg.py:400`),
  `regression_method` (`:406`, one of percentage/adaptive/delta/absolute), the four
  benchmark-wide thresholds (`:416`–`:452`), `regression_overrides` (`:454`), and
  `regression_fail` (`:480`, raise `RegressionError` on any regression).
- **Detection**: `detect_regressions(dataset, bench_cfg, run_cfg)`
  (`regression.py:1444`) iterates `bench_cfg.result_vars` (`:1515`), resolves each
  var's checks as `overrides.get(var_name, primary_checks)` (`:1523`) — an override
  entry *replaces* the benchmark-wide method entirely, and disables the adaptive
  sparse-history fallback (`allow_sparse_fallback=not is_override`, `:1563`).
- **Wiring**: `Bench` runs detection after history merge (`bencher/bencher.py:742-747`);
  on any regression it logs `summary()` as a warning and raises `RegressionError`
  when `regression_fail` is set. The report is stored as
  `bench_res.regression_report` and survives the collect/render split pickle.
- **Verdict objects**: `RegressionResult` (`regression.py:42`) carries variable,
  method, regressed, current/baseline, change_percent, threshold, direction, details
  (+ plot arrays); `RegressionReport` (`:121`) has `has_regressions` (`:127`),
  `summary()` (`:135`), `to_markdown()` (`:146`), `to_dict()` (`:170`).
- **Export**: `bencher/report_export.py` already emits the verdicts —
  `result_to_dict` (`:122`) embeds `regression_report.to_dict()` verbatim under a
  `"regressions"` key (`:141-145`), under `SCHEMA_VERSION = 1` (`:42`).
  `BenchReport.save(emit_json=...)` (`bencher/bench_report.py:248`, `_emit_json`
  `:334`) writes it as `result.json` next to the HTML. `compare_results` (`:210`)
  reuses the same detectors for A/B diffs, and `bencher.scorecard` builds its cell
  verdicts from this JSON (`bencher/scorecard/model.py:13,61`).
- **Publishing**: the `Publisher` protocol (`bench_report.py:114`) is
  `publish(report) -> str | None`; `BenchRunner` calls it with the whole
  `BenchReport` (`bencher/bench_runner.py:504-518`), which holds `bench_results`
  (`bench_report.py:143`) — so publishers can already *reach* verdicts, but only by
  walking internals.

## 2. The gaps

### G1 — policy lives far from the metric it governs

A metric's threshold is a property of the metric ("success_rate must hold ≥ 0.95"),
but the only per-variable hook is run-level. A CI suite that reuses one
`ResultBool("success_rate")` across 20 benchmarks must keep a
`{benchmark: {metric: spec}}` registry in its own code and slice it into
`regression_overrides` at every `plot_sweep` call site. The natural home — the
result-variable class declaration — has no field for it.

**Hash hazard (the reason this is subtle):** result vars are hashed into the
benchmark's persistent cache/history key via `_hash_slots`
(`bencher/variables/results.py:50`), which hashes **every `__slots__` entry not in
`_hash_exclude`**, and a slot-coverage test enforces that each new slot is explicitly
classified (`results.py:25`). `ResultFloat` already excludes `direction` precisely so
that retargeting the optimizer doesn't wipe `over_time` history (`results.py:102-107`);
CHANGELOG 1.102.0 notes the same for `default`. A naively-added `regression` slot
would make *tightening a threshold* discard the very history the detector needs.
The new slot **must** be in `_hash_exclude`.

### G2 — no severity concept

Two tiers are common in CI: hard-gating ("fail the merge") vs notify-only ("post a
heads-up, never block"). Bencher has one bit: `regression_fail` raises on *any*
regression (`bencher.py:744-747`), so users run two parallel configurations (a gating
override map + a notify override map) and diff two output files. The scorecard
already wants this distinction and has to approximate it presentationally
("passed" vs "trend", `scorecard/model.py:61`).

### G3 — export is close but not CI-complete

`result_to_dict` rows (via `RegressionResult.to_dict`, `regression.py:95`) lack
severity and units, and the aggregate block has only `has_regressions` — a CI step
that wants "exit nonzero iff a *gating* metric regressed, but render *all* movements
as a PR-comment table" still re-walks `bench.results[*].regression_report` and
serializes its own format. **Scope this as extending/normalizing
`report_export.py`, not a parallel artifact.**

### G4 — publishers are verdict-blind

A publisher that posts to chat or a PR comment gets a `BenchReport` and must reach
into `report.bench_results[i].regression_report` (private-ish, pickle-shaped) to say
anything smarter than "report published at URL".

## 3. Research questions (resolve before implementing)

1. **Spec grammar unification.** Should the class-level spec reuse the
   `regression_overrides` grammar (bare number / `{method: threshold}`,
   `regression.py:1348`) extended with severity, so there is exactly one grammar and
   one validator? Recommendation: yes — `RegressionSpec` normalizes to the same
   `{method: threshold}` shape and `_normalize_overrides` becomes the shared
   validator. Decide where the shared normalizer lives if plan 08 has split the file.
2. **Severity granularity: per-variable or per-check?** A var can carry multiple
   independent checks (`{'percentage': 15.0, 'absolute': 1.0}` — trend + hard floor),
   and "notify on trend, gate on floor" is a real pattern. Recommendation: severity
   is a property of a *check*; `RegressionSpec` is one check and the class attribute
   accepts a list. For dict shorthand, a reserved `"severity"` key applies to all
   checks in that dict (verify `_normalize_overrides` currently warns-and-drops
   unknown keys, so reserving one is backward-safe).
3. **Precedence semantics.** Overrides today *replace* the benchmark-wide method
   wholesale. Should a run-level override replace the class-level spec the same way
   (recommended: yes, replacement — one rule everywhere), or field-merge with it?
   Does an empty-dict override (`{}` = opt out, `bench_cfg.py:466`) also silence a
   class-level spec? (Recommended: yes — the run always wins.)
4. **Does a class-level spec imply detection?** `detect_regressions` runs only when
   `run_cfg.over_time and run_cfg.regression_detection` (`bencher.py:742`) and
   returns early without an `over_time` dim (`regression.py:1475`). A declared
   absolute gate silently not running is a trap; auto-enabling changes run behavior
   based on a class attribute. Recommendation: do not auto-enable in this plan; log
   a clear warning when specs exist but detection is off, and pose
   history-free-checks-without-over_time as follow-up work.
5. **Schema versioning policy for additive fields.** `SCHEMA_VERSION` is 1
   (`report_export.py:42`) with no stated additive policy. Adding `severity`,
   `units`, `has_gate_regressions`, `severity_counts` is additive. Recommendation:
   keep `1` and document "additive keys do not bump" in the module docstring; bump
   only on breaking shape changes. Confirm the scorecard reader tolerates the new keys.
6. **Aggregate helper surface.** Is `RegressionReport.has_gate_regressions` (+
   severity-aware `regression_fail`) enough for CI, or is a file-level helper that
   reads `result.json` and returns an exit code worth shipping (e.g. for pipelines
   where detection and gating run in different jobs)? Recommendation: properties +
   severity-aware raise in phase 1; JSON-reading CLI helper only if phase 3 finds a
   concrete need.

## 4. Proposed design (refine against §3)

**4.0 Semantics at a glance (single source of truth).** The rest of §4 elaborates;
this is the authoritative statement of precedence and severity.

*Precedence* — resolved once per variable inside `detect_regressions`, highest wins:

1. run-level `regression_overrides[var]` — including `{}`, which opts the variable
   **out** of detection entirely (`bench_cfg.py:466`);
2. class-level `rv.regression` (`RegressionSpec`);
3. benchmark-wide `regression_method` + thresholds.

Resolution is **replacement, not merge**: the winning layer supplies that
variable's complete check set (matching today's override behavior at
`regression.py:1523`), and a variable resolved from layer 1 or 2 disables the
adaptive sparse-history fallback (`allow_sparse_fallback=False`, `:1563`).

*Severity* — a property of each **check** (default `gate`, so existing behavior is
unchanged); a variable with multiple checks may mix them:

| severity | in `has_regressions` | in `has_gate_regressions` | `regression_fail=True` raises? | log level |
|----------|:---:|:---:|:---:|---------|
| `gate`   | yes | yes | **yes** | warning |
| `notify` | yes | no  | no      | warning |
| `info`   | yes | no  | no      | info    |

Each check is judged independently, so a `{percentage: notify, absolute: gate}`
variable raises iff its *gate* check regresses while still reporting the notify
movement. `has_regressions` keeps its current meaning ("any check regressed").

**4.1 `RegressionSpec` + class-level declaration.**
```python
duration = bn.ResultFloat(units="s",
    regression=bn.RegressionSpec(method="percentage", threshold=20.0, severity="gate"))
# shorthand: regression=1.0  (absolute limit)  |  regression={"percentage": 15.0,
#     "absolute": 1.0, "severity": "notify"}   |  regression=[spec1, spec2]
```
Stored in a new slot on `ResultFloat` (inherited by `ResultBool`), listed in
`_hash_exclude` (G1). Validated eagerly through the shared normalizer so a typo warns
at declaration, mirroring `_normalize_overrides`' warn-don't-raise contract.
Precedence: `regression_overrides[var]` (run) ▸ `rv.regression` (class) ▸
benchmark-wide `regression_method`+threshold — resolved in one helper inside
`detect_regressions`, with class specs treated like overrides for
`allow_sparse_fallback` (a declared var is never judged by a knob outside its spec).
`compare_results` picks class specs up for free since it calls `detect_regressions`
with the candidate's `result_vars` (`report_export.py:254-255`).

**4.2 Severity.** `severity: str = "gate"` on `RegressionResult` (defaults keep
today's behavior: every current check gates). `RegressionReport` gains
`has_gate_regressions`, `gate_regressions`, and `severity_counts()`;
`has_regressions` keeps meaning "any". `Bench` raises `RegressionError` only when a
*gate* check regressed; notify regressions log a warning, info logs info
(`bencher.py:744-747`). `to_markdown()` gains a Severity column so the in-report
panel (`bencher/results/bench_result.py:329-338`) shows tiers.

**4.3 Export.** Extend `RegressionResult.to_dict` with `severity` and `units`, and
`RegressionReport.to_dict` with `has_gate_regressions` + `severity_counts` — flowing
into `result.json` automatically via `report_export.py:141-145` and
`save(emit_json=True)`. No new artifact, no parallel path.

**4.4 Publisher awareness.** Keep the `Publisher` protocol unchanged (structural,
runtime-checkable — widening its signature breaks implementers). Instead add
`BenchReport.verdict_summary() -> dict` aggregating severity counts and regressed
rows across `self.bench_results`, so a publisher (or `BenchRunner` after
`bench_runner.py:504-518`) composes a Slack message / PR comment from a stable
accessor instead of walking internals. Document the pattern with a small example
publisher; consider logging the gate summary next to the published URL.

## 5. Implementation phases (each independently shippable, with CHANGELOG entry)

1. **Severity plumbing** — `RegressionResult.severity` (+ `units`), report
   properties, severity-aware `regression_fail`, markdown/JSON columns,
   `verdict_summary()`. No new config surface yet; overrides gain the reserved
   `"severity"` key. Tests in `test/test_regression.py` + `test/test_report_export.py`.
2. **`RegressionSpec` + class-level declaration** — slot + `_hash_exclude` (with an
   explicit test that setting/changing `regression` leaves `hash_persistent()`
   unchanged), shared normalizer, precedence helper, detection-off warning (§3 Q4).
3. **Docs + consumers** — module docstring additive-schema policy, gallery example
   (declare gate+notify specs, show `result.json` and a rendered PR-comment-style
   table via `method_cells`, `regression.py:233`), scorecard severity awareness
   (additive), optional JSON exit-code helper per §3 Q6.

## 6. Acceptance criteria

- Declaring `regression=` on a result var changes neither `rv.hash_persistent()` nor
  `BenchCfg.hash_persistent()` (regression test; slot-coverage test updated).
- Precedence proven by tests: run override beats class spec beats benchmark-wide;
  `{}` override silences a class spec.
- With one gate and one notify check regressed: `has_regressions` True,
  `has_gate_regressions` True; with only the notify check regressed:
  `regression_fail=True` does **not** raise, warning still logged.
- `result.json` rows carry `severity`/`units`; aggregate block carries
  `has_gate_regressions` + counts; existing consumers (scorecard tests) still pass
  with `SCHEMA_VERSION` handling per §3 Q5.
- Old pickled results (pre-severity `RegressionResult`) still render and export —
  attribute access via defaults, verified by a compat test (the collect/render split
  loads pickled results in a separate process).
- Defaults reproduce today's behavior byte-for-byte in `summary()`/`to_markdown()`
  when no severity is declared. `pixi run ci` green.

## 7. What NOT to do

- Do not move or refactor rendering code (`build_regression_overlay`,
  `render_regression_png`) — that is plan 08 Task 1.
- Do not change `hash_persistent` semantics — that is plan 09 / architecture A4;
  this plan only *avoids* touching the hash via `_hash_exclude`.
- Do not widen the `Publisher.publish()` signature or add a second publish method.
- Do not auto-enable regression detection from a class-level spec (§3 Q4) without
  owner sign-off.
- Do not invent a second JSON artifact next to `result.json`.

## 8. Coordination

- **Plan 08** (regression.py detection/rendering split): land order is flexible;
  whichever lands second rebases mechanically. Keep this plan's edits confined to
  the detection/report symbols so the split stays clean.
- **Plan 09 / A4** (cache-key semantics): independent as long as the new slot is
  excluded from hashing; if plan 09 lands first, its slot-coverage/name-hash tests
  are the ones to extend.
- **A3 (BenchData contract)**: the enriched `result.json` verdict block is a natural
  early piece of A3's JSON manifest — keep field names stable and note them in A3.
- **Scorecard (1.113.0)**: `cell_verdict`'s gated/ungated split gains a principled
  basis from severity; coordinate additively so existing summary JSONs keep rendering.
