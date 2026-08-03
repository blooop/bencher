# Plan 26 — Post-merge audit remediation (2026-07-27 → 2026-08-03 merge window)

**Status:** proposed. **Risk:** Low–Med per phase (R1 touches history persistence — treat as Medium).
**Citations taken against:** `origin/main` @ `239a4c41` (2026-08-03); every load-bearing citation
below was re-confirmed against that tree when this plan was written. Line numbers go stale anyway;
the symbol is the durable reference — re-verify before relying on it (plans/README.md rule 7).

## 0. Context

Between 2026-07-27 and 2026-08-03, 44 PRs merged with less review than usual: the plan 23
constructive-modeling wave (P1–P11), the identity/declaration stack (plans 15–21), the blob-store
reachability GC (#1022), A6 grammar phase 1 (#1021), the four intra-sample chart types
(#990–#993), and the rerun composition stack (#1007/#1015/#1017). A nine-agent retrospective
audit reviewed every one of those PRs against `origin/main` @ `239a4c41`, verifying each suspected
issue empirically (findings a later PR had already fixed were dropped).

Overall verdict: the week's work is in much better shape than "merged without sufficient review"
suggests — test discipline is unusually high, and several suspected bugs turned out to be pinned
by tests (§11 lists the all-clears so future audits don't re-check them). But the audit confirmed
one HIGH data-loss defect, a cluster of fail-open edges around the new GC, several
cache-poisoning paths, and a set of consistency/debt items that get more expensive the longer
they age. This plan owns all of them.

Each phase below is an independently-shippable PR unless noted. Every phase follows the ground
rules in `plans/README.md` (pixi env, `pixi run ci` before commit, feature branches, no version
bumps unless stated).

## 1. Phase summary and recommended order

| Phase | Subject | Severity driver | Effort |
|-------|---------|-----------------|--------|
| R1 | History adoption can destroy/corrupt trends (#1012) | **HIGH — silent data loss** | Medium |
| R2 | Blob paths are absolute + CWD-dependent (#1021) | HIGH — silent degradation | Small |
| R3 | Blob-GC fail-open hardening (#1022/#1031) | MED — all edges point toward deletion | Small–Med |
| R4 | Worker-contract completeness (#1029/#1032) | MED — cache poisoning, abort paths | Medium |
| R5 | Failure-retention matrix (plan 21, #1013) | MED — flakes become permanent | Small–Med |
| R6 | Rerun composition lifecycle (#1007/#1017) | MED — perf + load-bearing files GC'd | Medium |
| R7 | ResultSpec registry single-source hardening (#1030) | MED — desync by design | Small |
| R8 | Container/renderer precedence contract (#989/#994) | MED — documented claim is false | Small |
| R9 | Constructive-modeling stragglers (coordinate with P12) | MED-LOW | Medium |
| R10 | ty gate hardening (#1026/#1033) | MED-LOW — gate bypass routes | Small |
| R11 | Small verified bug batch | LOW each, cheap | Small |
| R12 | Release v1.118.0 + doc/plan bookkeeping | Process | Small |
| R13 | Open-PR dispositions (incl. #760 CVE path) | **#760 is time-sensitive** | Varies |

Do **R1 first** (only live silent-data-destruction path), then R3 (deletion-direction hardening
while #1022 is fresh), then R2. R13's #760 item (CVE-2025-69872) should start in parallel — it is
the only externally time-sensitive item. R12's release cut should follow R1/R4/R11 landing so the
fixes ship together.

---

## 2. R1 — History adoption safety (HIGH; from #1012, plan 15)

**Evidence (all reproduced empirically):**
- `_adopt_or_report_reset` (`bencher/result_collector.py:622-690`) classifies "pure rename" by
  `stored_summary == config_summary`, but summary rows carry only `(name, type, units)` per
  variable (`bencher/history.py:197-215`) — none of the fields (bounds, samples, step,
  sample_values) that move the history key via `hash_persistent()`. Resampling or re-bounding is
  therefore indistinguishable from a rename. No declared `series_id` is needed — the default
  `bench_name:tag` series hits this.
- Repro A: `samples_per_var` 3→5 logs INFO "history adopted", **deletes the old record**
  (`del cache[old_key]`, `result_collector.py:676`), then reconciliation discards the adopted
  dataset as dimension-incompatible. Net: trend permanently destroyed while the log claims it was
  carried over. Pre-#1012 behavior (full_reset WARNING, old record left recoverable) was strictly
  better.
- Repro B: bounds (0,1)→(0,0.5) at equal sample count passes the dimension check and
  **outer-joins** the two grids: the served dataset has a coordinate grid no run ever sampled,
  with NaN holes — one trend spanning two input spaces. The merge is the unqualified
  `xr.concat([ds_old, fresh], "over_time")` at `bencher/history.py:441`, which relies on concat's
  default outer join; xarray is deprecating that default, so this path also emits a FutureWarning
  today and becomes a hard mid-load error under a future xarray.
- The delete at `result_collector.py:676` runs **before** `apply_policy` and before the merged
  record persists, so `on_history_reset="error"` can raise *after* the old record was deleted and
  *before* anything new was written — total loss under the exact policy whose purpose is "a CI
  run can never silently lose a baseline". The in-function comment claiming policy-before-persist
  is now false on the adoption path.
- Ping-pong: two different benchmarks sharing a `series_id` whose coarse summaries match
  alternately adopt-and-delete each other's record at INFO level.

**Fix:**
1. Derive the adoption predicate from the same inputs `hash_persistent()` uses — fold each
   variable's `hash_persistent()` (or bounds/samples/step/sample_values) into the
   `config_summary` rows — or gate adoption on full coordinate/dimension compatibility of the
   stored dataset. Anything not provably a pure rename falls back to `full_reset`.
2. Move `del cache[old_key]` to after the merged record persists (restores the plan 14
   pre-persist guarantee; any exception in `reconcile` no longer loses data).
3. Add the summary-version note: bump the summary format so old summaries (which lack the new
   fields) are treated as not-adoptable rather than spuriously equal.

**DoD:** both repros above produce a `full_reset` warning with the old record preserved under its
key; `on_history_reset="error"` provably leaves the store untouched on every path (test with a
raising `reconcile`); a same-summary different-grid pair can never outer-join. The cross-layer
principle — plan 16 proved hand-kept transcriptions of the hashing rule drift; plan 15 must not
base a **destructive** decision on one — goes into the plan 15 doc as an amendment.

## 3. R2 — Blob path portability (HIGH; from #1021, A6 phase 1)

**Evidence:** `_materialize_dataset_value` (`bencher/result_collector.py:183`) stores
`Path("cachedir").absolute()` — an absolute, CWD-dependent path — into cells that persist in
over_time history and `save_result` pickles. Renaming an ancestor directory, running from a
different CWD, or mounting a shared cache elsewhere silently degrades every `ResultDataSet` cell
to a placeholder, including historical events for which the blob is the only copy. Plan 22's
coordination section promised a plan-12 note for this; it was never written (plan 12 has no
mention of blobs).

**Fix:**
1. Content addressing makes relocation trivial — the basename *is* the content hash.
   `_dataset_sample_to_container` (`bencher/results/bench_result_base.py:1242`) should retry
   `<current cachedir>/blobs/<basename>` when the stored absolute path does not exist, before
   degrading to the placeholder.
2. Amend plan 12's inventory to include `result_collector.py`'s `cachedir` literal.
3. While in the file: add render-time caching for `load_blob` (`bench_result_base.py:1242`
   re-reads and re-parses the blob per call — one report renders a `ResultDataSet` var through
   multiple passes × N over_time events; an `lru_cache` keyed on `(path, mtime_ns, size)` in
   `blob_store`, byte-sized, closes the one uncached disk hop on the render path).
4. Narrow `_materialize_dataset_value`'s broad except (`result_collector.py:190-200`): an OSError
   is currently logged as "could not be pickled" and retried down a path that fails identically.
   Catch `(pickle.PicklingError, TypeError, AttributeError)`.

**DoD:** a test that materializes a blob, relocates the cachedir (or fakes the stored path), and
asserts the cell still renders; plan 12 amended.

## 4. R3 — Blob-GC fail-open hardening (from #1022/#1031)

The GC's stated philosophy is "the safe direction must be the one you get by accident". It is
honored for unreadable roots, `dry_run`, and tmp files — but the remaining fail-open edges all
point the same way: toward deletion.

**Fixes (one PR):**
1. `min_age_seconds` defaults to `0.0` with `dry_run=False` reachable
   (`bencher/cache_management.py:723`). Under default config the scanned roots
   (`benchmark_inputs`, `history`) are empty, so *every* blob a concurrent sweep just wrote is
   "unreferenced" — `bn.clean_orphaned_blobs(dry_run=False)` with defaults deletes live data.
   Default to ~3600 (match the pixi task) or refuse `dry_run=False` with `min_age_seconds == 0`.
2. No `CACHE_VERSION` guard: the GC reads caches directly without comparing
   `cachedir/CACHE_VERSION` to the library's (`cache_management.py:60`); a record that unpickles
   but stores references in a shape the walker doesn't descend yields a silently **empty** live
   set → delete everything. Treat missing/mismatched `CACHE_VERSION` and unknown
   `record["format"]` as unreadable (abort), same as a corrupt record.
3. `_MAX_REF_WALK_DEPTH` exhaustion silently drops references (`cache_management.py:537`).
   Record into `unreadable` (abort) or log loudly.
4. `extra_roots` directory mode globs only `*.pkl` (`cache_management.py:614`) while
   `save_result` accepts any extension — a protected archive of `.pickle` files gets zero
   protection with zero warning. Warn when a directory root contributes no files, or glob all
   files and treat un-unpicklables as unreadable.
5. `.tmp-<uuid>` files from crashed writers are permanently unreclaimable
   (`cache_management.py:682-685`, `blob_store.py:203-205`). GC should delete `.tmp-*` older
   than `min_age_seconds`.
6. #1031's `except OSError: pass` in `materialize_blob` (`blob_store.py:196-199`) conflates
   "blob vanished" with `EPERM`/`EROFS` (shared multi-user or read-only cachedir), falling
   through to a pointless full rewrite that can newly raise `PermissionError`. Split:
   `except FileNotFoundError: pass` (rewrite), `except OSError: return str(blob_path)`.

**Longer-term (record, don't build now):** the scan is O(total cache bytes) per invocation —
`_scan_cache_for_blob_names` (`cache_management.py:568-596`) unpickles every cached
`BenchResult` each run. A4's write-time `ArtifactManifest` (§3.3) replaces scan-the-world with
cheap refcounting and fixes items 2–3 as a class. R12 amends A4 to absorb the blob store — the
A4 doc currently doesn't know the blob store or this GC exists, and the GC's
`utime`/`stat`/atomic-`replace` semantics won't survive A4's object-store direction.

**DoD:** each edge above has a test asserting the *abort/protect* direction.

## 5. R4 — Worker-contract completeness (from #1029/#1032)

The #1029→#1032 reversal (abort → record-and-warn) ended up coherent on the sweep path, but the
edges are inconsistent:

1. **Contract-violating payloads are cached before validation.** `JobFuture.result()` writes via
   `_cache_and_return` (`bencher/job.py:381-385`) before `store_results` validates; a wrong-length
   `ResultVec` or missing-key dict persists under the job key. With `cache_samples=True`: the
   user fixes their worker, re-runs, and the cached broken payload is served and re-warned
   forever (keys hash inputs, not worker code); on that warm re-run the sample never reaches the
   worker, so `failed_fraction` is 0.0 and a float-threshold `fail_on_sample_error` can never
   fire. This directly contradicts `record_caught_sample`'s documented property
   (`result_collector.py:376-378`) and P5's never-cache-a-`None` construction. Fix: validate
   shape before the cache write, or evict the key in `record_contract_violation`.
2. **A missing hmap key still aborts the sweep.** `result_collector.py:499-500` raises a bare
   `KeyError` for a raw-dict worker omitting a declared `ResultHmap` key — the byte-identical
   shape #1032 converted for result_vars at `:514-525`. Move under the same
   `WorkerContractError` handling.
3. **The optimize path is outside the whole story.** `_run_optuna_job`
   (`bencher/bencher.py:1656`; its `submit(job).result()` at `:1687` runs under
   `study.optimize(..., catch=catch)` at `:1447`, as the comment at `:1681-1683` records): with
   `catch` unset a
   `WorkerReturnedNothingError` aborts the run (the outcome #1032 forbids); with
   `catch=Exception` optuna absorbs it — no `failed_samples` record, no warning, no report entry.
   Both PRs document the asymmetry in comments; no phase owns it. Route optimize-path contract
   errors through the same record-and-warn machinery (or explicitly re-raise past optuna's
   `catch`), and give the optimize path a failed-samples report section.
4. **The report pane overstates.** `failed_samples_markdown` claims failed cells "hold the
   missing-value sentinel" (`bench_result.py:160-163`) but result vars stored before the
   violating one keep real values (`result_collector.py:491-494` admits this). Either roll back
   the partial store (validate the whole dict first — same fix as item 1) or fix the wording.
5. **Markdown table injection:** `bench_result.py:169-174` interpolates raw input values and
   error text into a `|`-table unescaped. Escape `|` and newlines in values.

**DoD:** a violating worker + `cache_samples=True` + fix + re-run test proving the fixed worker
actually re-executes; hmap-omission recorded not raised; an optimize-path contract violation
appears in `failed_samples` under both `catch` regimes.

## 6. R5 — One failure-retention answer (from #1013, plan 21)

Today "does a flake become permanent?" has three answers: sample cache — never persisted
(verified sound on both executor paths); benchmark result cache — **persisted and never
retried**; over_time history — **persisted even when the run then fails CI**.

1. `run_sweep` writes the finished `BenchResult` — holes, `failed_samples` and all — into the
   benchmark cache unconditionally (`bencher/bencher.py:909`), and a later `cache_results=True`
   hit skips the sweep and deliberately skips the policy (`bencher.py:930-938`). One flake + a
   warm benchmark cache = a permanent hole no rerun retries until `clear_cache`. Fix: skip (or
   mark) the benchmark-cache write when `n_failed > 0` (opt-out kwarg if someone wants degraded
   caching), and say so in the caching docs.
2. With `over_time=True`, the NaN-holed event merges into history (~`bencher.py:875`) *before*
   `_enforce_sample_error_policy` raises (`bencher.py:938`) — a CI job failing on
   `fail_on_sample_error=True` still permanently appends the degraded event, and the retry
   appends a second one. Enforce before the history persist (or document loudly).
3. `plot_sweep` mutates the caller's `run_cfg` in place — four writes now
   (`bencher.py:513-531`: `catch`, `executor`, `on_history_reset`, `cache_results` under
   `only_plot`). Deepcopy caller-supplied run_cfg once at entry.
4. Small: a locally-defined exception class in `catch` makes the unconditional benchmark-cache
   pickle fail *after* the whole sweep ran (fix falls out of item 1); fault-tolerance tests cover
   `ResultFloat` only — add one `catch=` test each over media/int/bool result types.
5. Write the retention matrix (sample cache / benchmark cache / history × flake outcome) into
   `docs/caching.md` once #1049 merges — one table ends the ambiguity.

## 7. R6 — Rerun composition lifecycle (from #1007/#1017)

1. **Composition re-renders on every run, including 100% cache-hit runs.** The sample cache
   stores the raw un-rendered `ComposableContainerRerun` (`bencher/job.py:383-386`);
   `_materialize_result_value` calls `render()` inside `store_results`
   (`result_collector.py:154-163`, `:526`), which runs for every `JobFuture`, hit or miss. Each
   run re-reads and re-merges every child `.rrd` and writes a **new** composed file. The
   generated examples' comment ("materializes … before the result enters Bencher's cache") is
   false. Fix: materialize inside the job while `_current_job_key` is set (`job.py:405`) so the
   rendered path is what gets cached — and fix the four example comments.
2. **Composed `.rrd`s live in a bucket the media GC deletes unconditionally while reports serve
   them from disk.** Because `render()` runs post-cache, `gen_rerun_data_path` takes the UUID
   fallback (`bencher/utils.py:280-283`) → a bare file that `clean_orphaned_media` treats as a
   legacy orphan (`cache_management.py:389-402`) — yet `rrd_file_to_pane` serves from disk via
   `/rrd_static/` (`utils_rrd.py:78-84`). So `cache-clean-orphans` breaks live reports, and
   nothing else ever reclaims the files (they accrete one per sample per run, per item 1). Fixing
   item 1 gives them a job-key home; otherwise define a `composed/` policy with reachability from
   cached values. This wants a deliberate policy, not per-PR patches — `_materialize_result_value`
   is a generic hook and the precedent will be copied.
3. **Merge scaling:** `_compose_ds` re-encodes the whole sweep's recording bytes once per
   dimension level and holds ~2× total size in RAM (`rerun_summary.py:236-255`,
   `composable_container_rerun.py:269-283`, `:503`); intermediates are never deleted. Acceptable
   for the opt-in feature today — record as known debt; delete intermediates after the parent
   consumes them as the cheap first step.
4. **Test hygiene:** `test/test_rerun_summary.py:10` and
   `test/test_composable_container_rerun.py:4` hard-import `rerun` (collection error without the
   optional dep — precedent is `pytest.importorskip`, cf. `test_docs_scrollbars.py:27`). The
   rerun-less configuration is belief, not evidence: add a minimal no-rerun CI check (install
   without the rerun feature, `import bencher`, run a smoke subset).
5. Small, latent: `reverse` isn't forwarded into the `_compose_ds` recursion
   (`rerun_summary.py:239-245`, same quirk as `video_summary.py:217-225`) — fix both or fix the
   docstring; a `compose_method_list` of exactly `num_dims` entries silently ignores its last
   entry (`rerun_summary.py:229-230`) — validate length; the recursion itself is duplicated with
   `_to_video_panes_ds` — extract when next touched.

## 8. R7 — ResultSpec registry: make "single source of truth" true (from #1030)

1. **Freeze the registry.** `RESULT_SPECS` is a plain mutable dict (`bencher/variables/results.py:644`)
   whose nine derived tuples are frozen import-time snapshots (`:817-879`, plus
   `parametrised_sweep.py:15`). Demonstrated live: post-import registration makes `result_spec()`
   resolve a type that `PANEL_TYPES`/`DATA_VAR_RESULT_TYPES` exclude — classifies but gets no
   dataset column and no rendering, failing far from cause (the exact ResultVolume-trap shape the
   PR closed). A6 phase 2 will derive its channel vocabulary from this registry — freeze it
   (`types.MappingProxyType` + docstring "import-time only") **before** a second consumer family
   builds on snapshots of it. plan 25 should note the constraint.
2. **`missing_sentinels` is write-only in production** (two independent reviewers converged on
   this): the read-side oracle `result_is_missing`/`_dataset_cell_is_missing`
   (`results.py:894-940`) never reads it, and the agreement test checks one direction only.
   Either drive the oracle from the spec (adding an explicit promotion/dual-generation field) or
   mark the field declarative-only in its docstring. Do this before phase-2 consumers read
   `spec.missing_sentinels` directly and get a narrower predicate than the oracle.
3. Document the residue in the registry docstring: the declaration-time guard fires only for
   `bencher.variables.results`-module classes (`parametrised_sweep.py:86`) — external result-like
   classes still silently classify as inputs; render-behavior enumerations survive outside the
   registry (`bench_result_base.py:965` over_time slider, `holoview_result.py:555`,
   `result_collector.py:292` exact-type `ResultVec` check with no else). "One-place extension"
   holds for classification only — say so where the next extender will read it.
4. Housekeeping: `_MEDIA_RESULT_TYPES` is underscore-private but imported cross-module
   (`result_collector.py:44`); `TestDerivedTuplesMatchPreRegistryLiterals` says "delete after one
   release" with no tracker — tie to the v1.118 release note; stale commented import at
   `results.py:48`.

## 9. R8 — Container/renderer precedence contract (from #989/#994)

1. **The documented uniform precedence is false for `ResultReference`.** #994's CHANGELOG:
   "renderer-supplied, then the sample's, then the class's, then the type's default." True for
   `ResultDataSet` and String/Path/Container; false for `ResultReference` — the declared
   container returns *before* the renderer-supplied check
   (`bencher/results/bench_result_base.py:1350-1358` vs `:1359`), so `to_panes(container=...)` /
   `to_video` cannot override a declared container on a `ResultReference` but can on a
   `ResultDataSet`. No test pins either ordering (test_declared_container.py never passes both).
   Pick one order (renderer-first, matching the changelog), fix, and add the missing
   both-supplied precedence test for every type.
2. **Two calling conventions for `container`.** A `ResultDataSet` container is called with the
   object alone (`bench_result_base.py:1259-1260`) while every other renderer-supplied container
   gets `container(val, styles=..., **kwargs)` (`:1360`). Latent failure: `PaneResult.to_video`
   passes a video container that, on a sweep also holding a `ResultDataSet`, is invoked
   single-arg with a DataFrame. Near-term: exclude `ResultDataSet` from the video pane pass.
   Real fix is A6 Law 1 territory — record it in plan 25 rather than inventing a third contract.
3. Note-only: `ResultImage`/`ResultVideo` have no `container` slot (declaring one raises loudly —
   fine), so #994's title oversells; defer to A6.

## 10. R9 — Constructive-modeling stragglers (coordinate with in-flight P12)

P12 (Tier-B ratchet, current branch) includes a "final strict-list review". Hold that review to
this list, and fold the small fixes in where the files are already being touched:

1. **`VarRange` raw constructor is an unvalidated hole** (`bencher/plotting/plot_filter.py:47-64`):
   `bn.VarRange(0)` — the *old* public spelling — constructs silently and dies later with
   `AssertionError: Expected code to be unreachable` (`:118/:151/:168`), the exact misdirecting
   failure #1039 was written to prevent, in the same cluster. `__post_init__` isinstance check
   raising a `TypeError` that names the six named constructors.
2. **P8's DoD is unmet at the fifth match site:**
   `composable_container_video.py:158-161` still ends `match render_cfg.compose_method` with
   `case _: raise RuntimeError`, and the file isn't strict-listed. `assert_never` arm +
   strict-list.
3. **Strict-list additions** so the new `assert_never`s stop being decorative: `plot_filter.py`,
   `utils.py`, `plugins/bench_data.py`, `results/bench_result_base.py` (the statement-form AggFn
   ladder is not caught by P12's global `invalid-return-type`).
4. `HistoryEvent` is not frozen (`bencher/history.py:99-100`) — `event.kind = "typo"` bypasses
   the `__post_init__` parse; freeze it.
5. **`IntSweep.with_bounds` coercion bypasses both plan-17 guards** (verified):
   `with_bounds(4.4, 4.6)` coerces to zero-width `[4,4]` silently (pre-PR raised);
   `with_bounds(4.4, 4.6, samples=5)` sails past the contradiction guard. Re-check
   `low == high` **after** `_coerce_bound` (`bencher/variables/sweep_base.py:231-239`). Also:
   `bounds=(nan, nan)` passes the `bounds[0] > bounds[1]` guard (`inputs.py:746`); reject NaN.
6. `set_worker_class` accepts any `type` (`worker_manager.py`) — require a `ParametrizedSweep`
   subclass so `set_worker_class(int)` fails at the call, not inside param internals.
7. `_dedupe_result_vars` silently keeps the first of two same-named result vars with different
   `units`/`meaning_version` (`sweep_executor.py`, ~line 100) although `column_identity` treats
   those as different measurements; conflicting result declarations should raise like consts do.
8. `SweepSpec` frozen-ness is shallow — `bind()` returns the same dict objects
   (`sweep_spec.py:258-260`); deep-freeze (tuples of pairs) or deep-copy in `bind()`.
9. Dead duplicate vocabulary: `Axis.from_horizontal` and `ComposeType.from_horizontal`
   (`composable_container_base.py:50`, `:77`) have zero callers — delete.
10. Handover-floor leftovers hidden by Tier-C ignores: `to_panes_multi_panel`'s
    `plot_callback: Callable | None = None` forwarded into a required-`Callable` parameter
    (`bench_result_base.py:836-840` vs `:890`); `pane_collection: pn.pane = None` defaults
    (`:682`, `:762`); `run.py:54`'s `# ty: ignore` where `callable()` deletes it.
11. **Convention decision, record in plan 24:** #1034 stores plain `str` in `BenchCfg.agg_fn`
    (docstring: members must NOT be stored) while #1039 stores enum members in
    `BenchRunCfg.on_history_reset` (docstring: the field's type must be true for every reader).
    Both docstrings claim authority. Pick one for the next enum-ified param field.
    Related unowned item: migrate third-party `strenum` → stdlib `enum.StrEnum` (3.11 floor makes
    it vestigial); the documented `auto()` semantics trap (`Executors`/`SampleOrder` values)
    means this needs value-pinning tests, which mostly already exist.
12. Plan 23 bookkeeping: §10 has implemented-amendment records only for P1/P2/P5/P6 — add
    P7–P11's deviations (P9's four-variant redesign, P8's skipped video site, #1035's missing
    CHANGELOG) so the plan's audit trail is complete before archiving; delete
    `plans/23-handover.md` when P12 lands (its own header requires it).

## 11. R10 — ty gate hardening (from #1026/#1033)

1. **The override meta-test is porous.** `test/test_ty_gate.py:100-106` only flags
   `[[tool.ty.overrides]]` blocks whose include pattern starts with `bencher/`. Uncovered bypass
   routes: `include = ["**"]`, exclude-only blocks, `[tool.ty.src].exclude`, and a new `.ignore`
   file (the task runs `--respect-ignore-files`). Replace TOML pattern-matching with an
   effective-config probe: seed a Tier-A violation in a temp file under `bencher/`, run
   `ty check` with the repo config, require nonzero exit. Closes all four routes at once.
2. **The #1033 ceiling raise changed nothing that runs:** `pixi.lock` still resolves ty 0.0.56 in
   every environment. Re-lock to 0.0.65 and raise the floor to the version the probes pin
   (`ty>=0.0.13` is meaningless).
3. The extra_panels regression class (the one that already slipped through CI once) still has no
   pin for its static non-`Viewable` arm: `test/test_extra_panels.py` covers callables and
   `pn.pane.Markdown` only — add plain-`str` and `hv` element cases (two lines each).

## 12. R11 — Small verified-bug batch (one PR)

Each verified live on `239a4c41`:
1. `xy_curve(markers=True)` applies user `**opts` to both Curve and marker Scatter
   (`xy_curve_result.py:99-107`) — `interpolation=` raises `ValueError` on the Scatter, breaking
   the factory's documented contract. Apply user opts to the Curve only.
2. `xy_histogram(column=<non-numeric>)` dies with a raw numpy conversion error
   (`xy_histogram_result.py:66`, `:84`) instead of the module's branded message — dtype-check
   named columns in `_counts`/shared-range. Also fold `XYCurve._resolve_columns`'s duplicated
   emptiness check (`xy_curve_result.py:69-71`) back into `tabular_spec.resolve_columns`.
3. Scorecard/report: `"regressed": "false"` (string, from a hand-edited summary) is truthy at
   `report_export.py:233` and `scorecard/model.py:78` — the PR's own degrade-never-lie thesis
   applied to every numeric field but not the boolean. Coerce explicitly + one hostile-record test.
4. #1027 under `-W error`: `report_render_failure` warns *inside* the except handler
   (`render_failure.py:46-50`), so one bad plot aborts the whole report build mid-loop for
   exactly the strict-CI audience the PR targets. Collect and emit warnings after the render
   loop (failure panes still placed). Also file the documented-but-untracked `map_plot_panes`
   all-or-nothing gap (one raising PANEL_TYPES var discards all sibling panes in the group).
5. Thumbnail generation (#996): every selector-miss falls back to a full-page screenshot with no
   signal, and the tests run entirely against fakes — a Bokeh class rename passes CI while all
   thumbnails silently regress. Count and print fallbacks in `generate_all`; fail generate-docs
   when the fallback rate jumps.
6. `example_meta.py:43` still declares a `ResultHmap`, so every generate-docs run trips bencher's
   own deprecation and `-W error::DeprecationWarning` consumers break on our example — migrate it
   (open item from #1021's CHANGELOG).

## 13. R12 — Release + documentation/plan bookkeeping

1. **Cut v1.118.0.** Two breaking changes (#1025 `build!`, #1034 `refactor!`) and the plan-23 fix
   wave (video buttons, scorecard verdicts, worker-contract warnings) are stacking unreleased
   since the 07-31 tag; PyPI users sit on known-buggy video controls and scorecard verdicts.
   Prefer landing R1 + R11 first so the fixes ship in the same cut. (Do the bump in its own PR
   per ground rule 4.)
2. Retroactive CHANGELOG entries: #1035 shipped none despite two user-visible changes
   (`BenchData.has()` now raises on unknown capability — public plugin API; rerun renders gaps
   instead of fabricated `0.0`). Amend #1045's "attributes all unchanged" claim (stale-instance
   rebinding semantics did change, deliberately).
3. Plan-doc amendments (all one-liners to keep records honest):
   - **A4**: absorb the blob store + reachability GC (currently unmentioned); note the GC's
     local-FS assumptions and that §3.3 manifests supersede scan-based reachability.
   - **A6/plan 25**: add the four xy_* types + `TabularSpec` + `render_data_samples` to the
     pathway inventory (stale on arrival); add `legacy_trusted` + `_accepts_keyword` to phase 3's
     deletion budget; record the Law-1 sentinel divergence (permanent `"NAN"`/`-1` dual
     generation vs "None/empty") in §2.6's stale-claims list; note the R7 freeze constraint.
   - **plan 15**: record the R1 adoption-predicate amendment.
   - **plan 12**: the blob-path note plan 22 promised (done in R2).
   - **plan 02**: annotate stale steps — step 2 (#760 "fix CI & merge" is now dangerous, see
     R13), step 5 (#799 rebase advice), step 8 (#923 "default: close" reversed by A5's
     dependency on the doc).
4. Memory-holes worth one line each in plan 08/07's backlog: `Bench`'s writable worker mirrors
   (`bencher.py:202-204`) still desync-able after P9 (plan 11 territory); optuna `catch=`
   asymmetry documented at `bencher.py:1694-1697` (owned by R4 item 3).

## 14. R13 — Open-PR dispositions (as of 2026-08-03)

| PR | Verdict | Key evidence |
|----|---------|--------------|
| #1050, #1051 (deps) | **MERGE** | Green; no conflict with the ty ceiling (dev group untouched); pandas 3.0.5 matches the 3.11 floor. |
| #1049 (plan 06 docs) | **MERGE as-is, soon** | Every load-bearing claim verified against `239a4c41` (cache-key rule, dead `only_hash_tag`, unconditional cache write, GC/`extra_roots`, regression table, gallery link stems); RTD green; toctree/`myst_heading_anchors` wiring correct. Sitting invites conflicts with A5 Phase 0 and plan-23 docstring churn. One future touch-up noted: "Both are diskcache stores" dies with #760's replacement. |
| #923 (bench_cfg split plan) | **MERGE after doc-only fixes** | A5 §5 *depends on* this doc by name (cites it six times) — closing it orphans A5 Phase 1. Fixes: move `BENCH_CFG_SPLIT_PLAN.md` → `plans/architecture/A5-phase1-bench-cfg-split.md` (plan 03 keeps `*_PLAN.md` out of the root); add "read with A5's three amendments" header; link from A5 + plans/README. |
| #253 (dimension grid, 2023) | **CLOSE** | Target files no longer exist; dead imports; ancient pins; plan 02 step 7 pre-authorized closure. |
| #908 (auto-generate rerun examples) | **CLOSE**, redo ~40-line delta | Superseded by the literal-`class_code` convention #1007/#1017 settled; its own generated-file-as-input mechanism is worse; stale class snapshot (missing `omega_n`). Residual: convert the two remaining `generate_meta_rerun.py:110-153` importers to literal `class_code`, delete `example_rerun_over_time.py`/`example_rerun.py`, retarget `demo_rerun`. Keep `example_rerun2.py` (sole usage example of `rrd_to_pane`/`publish_and_view_rrd`). |
| #799 (netCDF history_dir) | **CLOSE**, harvest into A4 C4 | Rewrites a `load_history_cache` that plans 09/14/15/16 have rewritten twice since; merging would delete reconciliation and corrupt reset detection. Harvest `_sanitize_for_netcdf`/`_clean_attrs`/`_force_numpy` (pandas-3 ArrowStringArray fix main still lacks) when A4 C4 happens. |
| #760 (diskcache→minimalkv, CVE-2025-69872) | **REWORK — time-sensitive** | CVE still live (`diskcache<=5.6.3` pinned, upstream has no fix). But merging as-is is now *dangerous*: #1022's GC has three `diskcache.Cache` sites #760 never touches — if writes go to minimalkv while `_scan_cache_for_blob_names` (`cache_management.py:576`) scans diskcache, the live set is empty and **GC deletes every blob**. Path: fresh A4 Phase C1 PR on current main reusing #760's `store.py` design (+`__len__`/`iterkeys()`/`size_limit`, batched tag/volume writes), converting all call sites in one commit; `CACHE_VERSION` 5→6 makes migration free. Interim: plan 04 Task 1's README warning about untrusted cache dirs. Note `__getitem__` still `pickle.loads` — only A4 C4/A3 close the CVE *class*. |
| #941 (bencher.ci module, draft) | **REWORK to plan 10 phase 3** | Its summary format is the second verdict artifact plan 10 §7 forbids; `_apply_threshold` re-implements detector decisions wrongly (adaptive/delta judged with percentage semantics, predates young-baseline). Salvage: the PR-comment renderer on `RegressionReport.to_markdown()` and an exit-code gate subcommand (plan 10 §3 Q6's "concrete need" — cite this PR there). |

## 15. Audit all-clears (do not re-investigate)

For future audits: these were explicitly checked and found sound on `239a4c41` —
#1046's unreachability claim (verified at the pre-deletion commit); #1025's 3.10 drop (clean:
`requires-python` enforced, no stragglers); #1003 (no findings); #1048 (no findings); #1009
(complete removal, regression-guarded); blob-store write atomicity, GC dry-run abort semantics,
and cross-process races (all test-pinned); #1028's pin survived the ResultSpec refactor; the
video-button wiring is end-to-end pinned (`trigger("clicks")`); `WorkerJob` cached-property
hashing is byte-identical to the old eager hashes (no cache invalidation, no perf change);
`None` results are never sample-cached on either executor path; C13 executor normalization and
the StrEnum migration tripwires; #1001's `bounds=(x,x)` vs `values=[x]` identity distinction;
#1010's identity machinery (mutation-free `identity_of`, CACHE_VERSION folding, behavioral
coverage maps — a test pattern worth copying); #1014's bind determinism; the four xy_* chart
types genuinely share `TabularSpec` (no copy-paste drift; ~120 real assertions, not smoke);
#1015's fix and its precedence test; #1027's uniform conversion of all six render-failure sites;
`hash_persistent` golden values unmoved by the entire week (over_time keys safe).
