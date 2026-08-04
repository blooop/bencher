# A0 — Shipped Baseline: which A2–A6 claims landed code already satisfies

**Status:** Fact table, not a proposal. Nothing here decides anything; it records what is
true of the tree so the A2/A3/A4/A5 disposition tickets stop reasoning against stale
`Status:` lines.

**Audited against:** `main` @ `639ca4b53ec256f41b0efc2b9abc96c5064fd86f`
(2026-08-04, `pyproject.toml` version `1.117.0`). Every `file:line` below was read at
that commit; per `plans/README.md` rule 7 the **symbol** is the durable reference and the
line number is the convenience. Counts marked *(measured)* were produced by executing
against the installed package in the pixi environment, not by reading the doc they check.

**Why this exists:** 44 PRs merged in the 2026-07-27→08-03 window. A2's `Status:` line is
from 2026-07-11, A3/A4 say "Proposal" with no date, A5's inventories say 2026-07-30, and
A6 says "No implementation yet" while its phase 1 shipped as #1021 on 2026-07-31. The
dispositions downstream of this document branch on facts none of those lines carry.

---

## 0. Verdict vocabulary

| Verdict | Meaning |
|---|---|
| **SHIPPED** | The claim is satisfied by code in the tree. The disposition is "already shipped". |
| **PARTIAL** | Some of the claim landed; the named remainder has not. Both halves are stated. |
| **OPEN** | No code in the tree addresses it. The claim stands as written. |
| **STALE** | The claim's *evidence* no longer matches the tree, independent of whether its conclusion still holds. |

---

## 1. A6 Law 1 — canonical self-describing dataset (what #1021 actually shipped)

PR #1021 ("plan 22 + implementation: self-describing canonical dataset (A6 phase 1)",
merged 2026-07-31) is real and substantial. A6's "No implementation yet" line
(`A6-grammar-of-nd-data.md:5`) is **STALE**.

| # | Law 1 claim | Verdict | Evidence |
|---|---|---|---|
| L1.1 | Non-numeric cells are content-addressed paths into a cache store | **SHIPPED** | `bencher/blob_store.py` — `materialize_blob()` (`blob_store.py:148`) writes `<cache_dir>/blobs/<sha256[:16]><ext>`; `load_blob()` (`blob_store.py:210`) dispatches on extension. Formats: parquet / netCDF3 / `.da.nc` / `.bin`, pickle fallback. |
| L1.2 | `ResultDataSet` payloads materialize **at collect** | **SHIPPED** | `_materialize_dataset_value()` (`result_collector.py:166`), called from `ResultCollector.store_results` at `result_collector.py:537`. The cell stores the path string. |
| L1.3 | No run-local indices for dataset payloads | **PARTIAL** | True for `ResultDataSet` (L1.2). `ResultReference` (`variables/results.py:466`) still stores a run-local `object_index` slot — but Law 1 *keeps* it as the documented same-process escape hatch, so this is by design, not a gap. |
| L1.4 | Blob store deduplicates across repeats/time points | **SHIPPED** | Content addressing is the mechanism; a content hit refreshes mtime rather than rewriting (`blob_store.py:188-199`). Note the deliberate 64-bit truncated-digest collision risk documented at `blob_store.py:48-59`. |
| L1.5 | `isel(over_time=-1)` hack is killed | **OPEN** | Nine live sites remain. Legitimate history reads: `regression.py:1628`, `result_collector.py:844`. **Illegitimate (the hack Law 1 names):** `results/histogram_result.py:37` (see finding #12, §8), `plotting/plt_cnt_cfg.py:171` (inside `_samples_per_point`), `report_export.py:186` (`_snapshot_ds`). |
| L1.6 | `result_is_missing()` is the single missingness oracle | **PARTIAL** | The function exists (`variables/results.py:914`) and is used by the rerun and pane paths (`results/rerun_result.py:310,329,348,374`, `results/rerun_summary.py:260`, `results/bench_result_base.py:1096,1266`). It is **not** used by the numeric/holoviews reduction path, which still tests NaN directly, nor by `plt_cnt_cfg._missing_mask` (`plotting/plt_cnt_cfg.py:150-177`, a second implementation matched to `result_vars` by name). Two oracles, not one. |
| L1.7 | `ResultHmap` is deprecated and removed | **PARTIAL** | Deprecated: a `DeprecationWarning` naming the A6 migration fires at `variables/results.py:271`. **Not removed** — still exported (`bencher/__init__.py:128`), still special-cased in `Bench.plot_sweep` (`bencher.py:637-641`, `bencher.py:1430-1436`), still a `BenchCfg` field (`bench_cfg.py:824` `result_hmaps`), still rendered (`results/holoview_results/holoview_result.py:663,689`), still the reason `hmap_kdims` exists (`bencher.py:1103`). |
| L1.8 | The `.pkl` escape in the blob store is acknowledged debt | **SHIPPED (as debt)** | `blob_store.py:26-30` names A3 as the owner of tightening it. This is the pickle surface A3 §3 wants gone; it is now *concentrated in one function* rather than scattered, which is a real reduction in A3's blast radius. |

**Net:** Law 1's *data-layer* half is shipped. Its *cleanup* half — killing the
`isel(over_time=-1)` sites, unifying the missingness oracle, deleting `ResultHmap` — is
not. A phase-3 plan cannot assume any of the three.

---

## 2. A6 Law 9 / A3 phases D1–D3 — what crosses the collect/render boundary

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| L9.1 | The split boundary is still pickle | **OPEN — confirmed as written** | `render.py:34` imports `pickle`; `save_result()` (`render.py:44`) is `pickle.dump` of the whole `BenchResult` with `object_index` stripped; `load_result()` (`render.py:72`) is `pickle.load`. A3 §1's "arbitrary-code-exec on load" claim holds verbatim. |
| D1.1 | A `BenchData`-shaped frozen type exists (#932) | **SHIPPED, but not A3's type** | `@dataclass(frozen=True) class BenchData` at `plugins/bench_data.py:57`, with `RunMeta` at `:50`. |
| D1.2 | `BenchResult.to_bench_data()` exists | **SHIPPED** | `results/bench_result.py:283`. |
| D1.3 | `BenchData` matches A3 §2's target contract | **OPEN** | It does **not**. Missing: `VarSpec` (no such symbol anywhere — `input_vars`/`result_vars` are bare `tuple`s of live `param` objects), `DataSignature` (the field is `plt_cnt_cfg: PltCntCfg`), `plot_specs`, `artifacts: ArtifactManifest`, and `run_meta.schema_version` (`RunMeta` has `name`/`timestamp`/`sweep_hash` only). It *violates* A3 design rule 1 by carrying `cache: CacheHandle` and `legacy_result: Any` (`bench_data.py:68,74`) — live objects, explicitly transitional. |
| D2.1 | `save_bench_data()` / `load_bench_data()` directory format | **OPEN** | No such symbols. No netCDF+JSON run directory anywhere. |
| D3.1 | Split-render default flipped to the directory format | **OPEN** | `BENCHER_FORCE_SPLIT_RENDER` still routes through `save_result`/`load_result`. |
| L9.2 | Anything stores a plan | **OPEN** | No `Plan`, `View`, `Channel`, `Mark`, `Transform`, or capability-table type exists in `bencher/`. Plan 25 (A6 phase 2) has not started. |
| L9.3 | `collect()` exists and is plan-free | n/a | `Bench.collect()` at `bencher.py:705`. It samples and pickles; there is no plan to store, so Law 9's "plan at collect" is entirely future work. |

**Net:** A3 D1 is **not** shipped in the sense A3 means. #932 landed a *plugin handoff
type that reuses the name* `BenchData`. Treating "#932 landed BenchData" as "D1 is done"
would be a category error — the disposition ticket must decide whether A3's contract
absorbs, renames, or replaces the existing type. This is a naming collision with real
consequences and is exactly the case A6's Notes flag for `/ubiquitous-language`.

---

## 3. A4 §3.3 / phase C3 — blob store, the #1022 GC, and media

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C3.1 | A manifest exists per cache value | **OPEN** | `grep -rn "manifest" bencher/` returns **zero** hits. No `ArtifactManifest`, no per-value artifact list. |
| C3.2 | Eviction deletes through the manifest | **OPEN** | Follows from C3.1. |
| C3.3 | What #1022 actually shipped | **SHIPPED (different mechanism)** | *Reachability* GC by scanning, not manifests: `blob_reachability()` (`cache_management.py:625`), `clean_orphaned_blobs()` (`:724`), `print_orphaned_blobs()` (`:807`). It walks the `benchmark_inputs` and `history` caches (`_BLOB_REFERENCE_CACHES`, `:448`) collecting blob *names* out of values (`_walk_blob_references`, `:533`, depth-capped at `_MAX_REF_WALK_DEPTH = 8`, `:462`) and deletes unreferenced files under `blobs/`. |
| C3.4 | `clean_orphaned_media` survives | **YES** | `cache_management.py:367`, still the path-convention walk over `_MEDIA_FOLDERS = ("img","vid","rrd","generic")` (`:78`), keyed off `_collect_sample_cache_keys` (`:352`). It is the *mechanism* for media, not a backstop. Media and blobs are two separate, differently-designed GCs. |
| C3.5 | Plan 27 L9 / plan 26 R2: the GC's missing `CACHE_VERSION` guard | **STILL PRESENT** | `ensure_cache_version()` (`cache_management.py:119`) has exactly one caller: `Bench.__init__` (`bencher.py:197`). Neither `blob_reachability`, `clean_orphaned_blobs`, nor `clean_orphaned_media` calls it. A stale cachedir plus a GC that reads it anyway still yields an empty live set. **A6's map Notes are correct that this must be fixed before or with any `CACHE_VERSION` bump.** |

**Net:** C3 is **not** partly shipped by #1022. #1022 solved the same *problem* (blob
orphaning) with the *opposite* mechanism (scan-and-reach vs. declare-and-delete). The A4
disposition must rule on whether the manifest claim survives at all now that a working GC
exists without one — and whether media (still path-convention) is folded in.

---

## 4. A4 W1 / W4 / W6 — the sample key and where hashes live

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| W1 | Worker source code is not in the sample key | **OPEN — confirmed** | `WorkerJob.function_input_signature_pure` (`worker_job.py:73`) = `hash_sha1((self.fn_inputs_sorted, self.tag))`. No `code_hash`, no `hash_worker_source` flag, no `inspect.getsource` call anywhere in `bencher/` outside the meta-performance generator (`example/meta/generate_meta_performance.py:108`, unrelated). The single worst footgun is untouched. |
| W4a | `bench_cfg_sample_hash` is threaded and read by nothing | **STILL DEAD** | Computed at `bencher.py:838`, passed through `bencher.py:1123` into `WorkerJob.bench_cfg_sample_hash` (`worker_job.py:47`). The only other references are docstrings and `test/test_worker_job.py:124` — a test whose *name* (`test_bench_cfg_sample_hash_does_not_affect_pure_signature`) pins the deadness. |
| W4b | The stale comment claiming it is included | **FIXED** | `worker_job.py:76-79` now states it is "kept separately … and deliberately not folded in here." A4 W4's comment complaint is **STALE**; its dead-field complaint stands. |
| W4c | Three `hash_persistent` variants | **STILL THREE** | `hash_persistent(True)` (result), `hash_persistent(True, include_result_vars=False)` (history), `hash_persistent(False)` (sample) — composed at `bencher.py:828`, `:835`, `:838`. |
| W4d | Key logic is scattered / nobody can answer "what invalidates what?" | **PARTIAL — materially improved** | `bencher/identity.py` (new, from #1010) is a *documented single place* that names all three keys and their contributing/excluded fields: `IDENTITY_FIELDS` (`identity.py:33`), `EXCLUDED_FIELDS` (`:44`), `SweepIdentity.explain()` (`:77`), `identity_of()` (`:241`, composing all three at `:265-267`), `sweep_identity()` (`:151`). It is an **inspection** surface, not A4's `caching/keys.py`: the runtime keys are still composed at the `bencher.py` call sites, and `hash_persistent` still lives on `BenchCfg` (`bench_cfg.py:922`). W4's *diagnostic* half is answered; its *structural* half is not. |
| W6 | `only_hash_tag` is a dead flag | **STILL DEAD, now documented** | Declared at `bench_cfg.py:301`; its own docstring at `bench_cfg.py:176` reads "Dead flag; no reader." Written by `bench_runner.py:177` and `:424` and by an example (`example/example_sample_cache_context.py:55`); the only read is the describe string at `bench_cfg.py:1153`. |

---

## 5. A2 S1 / S2 — signature enrichment and centralized matching

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| S1 | Enriched signature fields on `PltCntCfg` | **SHIPPED** | `has_time` (`plt_cnt_cfg.py:44`), `time_steps` (`:47`), `result_kinds` (`:50`), `cat_levels` (`:53`), `samples_per_point` (`:56`), computed at `:114-125`. |
| S1b | The new fields are consumed by selection | **OPEN** | `PlotFilter` still has exactly five ranges — `float_range`, `cat_range`, `panel_range`, `repeats_range`, `input_range` (`plotting/plot_filter.py:183-187`) — and `PlotMatchesResult`'s `match_candidates` (`plot_filter.py:226-232`) reads only `float_cnt`, `cat_cnt`, `panel_cnt`, `repeats`, `inputs_cnt`. The signature fields are propagated into the aggregation shadow config (`bench_result_base.py:825-833`) and otherwise unread. A2 P4 stands. |
| S2a | `explain_selection()` shipped | **SHIPPED** | `results/bench_result.py:369`. |
| S2b | Matching is centralized out of each `to_plot` | **OPEN — confirmed as written** | Built-ins still register a permissive default `PlotFilter()` (`plugins/builtins.py:159`, `:172`), and shape checks still live in each `to_plot` calling `BenchResultBase.filter()` (`bench_result_base.py:778`). |
| P5 | Render failure is a silent log line | **FIXED** | `to_auto` (`bench_result.py:303`) now wraps both the plugin and legacy-callback paths and appends `report_render_failure(...)` panes on exception. A2's P5 row is **STALE** — both halves (selection and render failure) are now visible. |
| S3 | A serializable `PlotSpec` type exists | **OPEN** | No `PlotSpec`, no `DataSignature`, no `VarSpec` symbol anywhere in `bencher/`. Only the enriched `PltCntCfg`. `plot_callbacks` is still a list of callables on `BenchCfg`. |

---

## 6. A5 §4 — the nine dead fields, and regenerated counts

### 6.1 The nine dead fields — all nine still declared, all nine still dead *(measured)*

Consumer grep at this commit (`grep -rn "\.<field>\b\|\b<field>=" bencher/`, excluding
`example/generated` and the declaration file):

| Field | Declared | Readers | Writers |
|---|---|---|---|
| `raise_duplicate_exception` | `bench_cfg.py:385` (`BenchRunCfg`) **and** `bench_cfg.py:843` (`BenchCfg`) — A5's "(twice!)" is confirmed; it is the only shadowed field, which is why the own-body counts in §6.2 sum to one more than the total | none | none |
| `serve_pandas` | `BenchRunCfg` | none | none |
| `serve_pandas_flat` | `BenchRunCfg` | none | none |
| `serve_xarray` | `BenchRunCfg` | none | none |
| `use_holoview` | `BenchRunCfg` | none | none |
| `use_optuna` | `BenchRunCfg` | none | `example/example_workflow.py:81,117`, `example/meta/generate_meta_workflows.py:295`, `example/meta/generate_examples.py:466` |
| `nightly` | `BenchRunCfg` | none | none |
| `headless` | `BenchRunCfg` | none | none (the `headless=True` grep hits are Playwright's, `example/meta/generate_examples.py:333,880`) |
| `only_hash_tag` | `bench_cfg.py:301` | describe string only (`bench_cfg.py:1153`) | `bench_runner.py:177,424`, `example/example_sample_cache_context.py:55` |

A5 Phase 0 has **not** executed and its evidence still holds verbatim.

### 6.2 Regenerated surface counts *(measured against the installed package)*

| Surface | A5 (2026-07-30) | Now (`639ca4b5`) | Note |
|---|---|---|---|
| `BenchRunCfg` param fields | 54 | **56** | 53 declared in its own body + 3 inherited from `BenchPlotSrvCfg` (`port`, `allow_ws_origin`, `show`); excludes param's `name` |
| `BenchCfg` param fields | 73 | **75** | inherits all 56; 20 declared in its own body, one of which redeclares an inherited field |
| `Bench.plot_sweep` kwargs | 16 | **16** | unchanged |
| `bn.run` kwargs | 17 | **17** | unchanged |
| `BenchRunner.run` kwargs | 16 | **16** | unchanged |
| `issubclass(BenchCfg, BenchRunCfg)` | True | **True** | A5 C1 / Phase 5 untouched |

The `bench_cfg.py` field set is **byte-identical** to the 2026-07-30 baseline commit
(`6252d7c8`) — a field-name diff across that range is empty in both directions. The +2
delta is therefore a **counting-method difference in A5, not drift**: A5's 54/73 almost
certainly excluded the inherited `BenchPlotSrvCfg` fields or param's `name` differently.
A5's instruction to regenerate before executing any phase stands, but nothing has been
added since it was written.

---

## 7. A6 §6 — which of the 24 findings still reproduce

Checked at `639ca4b5`. "(V)" marks A6's own execution-verified findings. One finding
(#12) was re-verified by execution here; the rest are code-level.

| # | Finding | Verdict | Evidence at this commit |
|---|---|---|---|
| 1 | Two rival role sources (classification vs leaf position) | **REPRODUCES** | `plt_cnt_cfg.float_vars` (`plt_cnt_cfg.py:34`) vs leaf `dims[0]`/`dims[-1]` in `_to_panes_da` (`bench_result_base.py:918`). |
| 2 | (V) Interleaved `[f1,c1,f2]` breaks heatmap/surface | **REPRODUCES** | `_pick_xy_axes()` (`results/holoview_results/heatmap_result.py:86`), called at `:114,159,203`, still picks from the pre-peel var lists. |
| 3 | (V) 1-sample float dim + `squeeze(drop=True)` → `DataError` swallowed | **PARTIAL** | The squeeze is still there (`bench_result_base.py:418`). The **swallow is fixed**: `to_auto`'s broad except now emits a visible `report_render_failure` pane (`bench_result.py:303` body) instead of a log line. The underlying error remains; it is now legible. |
| 4 | (V) bar's rejection Markdown returned as the plot when `print_debug` | **REPRODUCES** | `BenchResultBase.filter()` returns `matches_res.to_panel()` on reject (`bench_result_base.py:861`), and `to_panel()` returns a Markdown pane iff `print_debug` (`plot_filter.py:255-262`). Mitigated only inside `to_auto`, which forces `print_debug = False` for the duration. |
| 5 | `override=True` default on every direct `to_*()` | **REPRODUCES** | e.g. `curve_result.py:27`, `volume_result.py:20,42`, `band_result.py:25,32`, `distribution_result/violin_result.py:32`. `to_auto` passes `override=False` (`bench_result.py:309`), so this is a direct-call-only hole, as documented. |
| 6 | (V) Surviving `repeat` peeled as outermost facet | **REPRODUCES** | `_to_panes_da` (`bench_result_base.py:918`) excludes only `over_time` from `pane_dims`; `repeat` has no reserved role. |
| 7 | Distribution's `target_dimension = cat_cnt + 1` | **REPRODUCES** | `distribution_result/distribution_result.py:58` (comment still reads "+1 cos we have a repeats dimension"); same at `scatter_jitter_result.py:60`. |
| 8 | (V) `horizontal` from hv dim count vs xarray dim count | **REPRODUCES** | Top level: `horizontal=pane_dims <= target_dimension + 1` where `pane_dims` comes from `len(hv_dataset.dimensions())` (`bench_result_base.py:873,888`). Recursion: `horizontal=len(sliced.sizes) <= target_dimension + 1` (`:912`). Two different counts, unchanged. |
| 9 | No cardinality guard anywhere | **REPRODUCES** | `PlotFilter` (`plot_filter.py:175`) has no level-count range; `cat_levels` is computed and unread (§5, S1b). |
| 10 | `vector_len`/`result_vars` dead filter axes; `ResultVec` unrenderable | **PARTIAL — half fixed** | The dead axes are **deleted** (plan 23 P6/C4): `vector_len` survives only in `test/test_plugins.py:685-708`, which asserts its absence. `ResultVec`'s index is **still not a dim** — `ResultVec` is still a `param.List` (`variables/results.py:201`) expanded to one column per element. |
| 11 | `ScatterResult` gates on deprecated `ResultVar` subclass | **REPRODUCES** | `ScatterResult` still registered (`plugins/builtins.py:105`, `results/bench_result.py:75`) with the same gate; no construction-time check for unmatchable gates exists. |
| 12 | (V) Histogram's over_time snapshot aliases `_to_dataset_cache` | **REPRODUCES — re-verified by execution** | `histogram_result.py:38-40` builds the snapshot via `__class__.__new__` + `__dict__.update(self.__dict__)`, which copies the **reference** to `_to_dataset_cache` (`bench_result_base.py:153`). The cache key (`_to_dataset_cache_key`, `:291`) contains no dataset identity, so the `isel(over_time=-1)` is discarded on a warm `NONE` entry. Reproduced on a 3-step `over_time` dataset: parent `NONE` → `over_time` size 3, snapshot `NONE` → size **3** (expected 1), `snap._to_dataset_cache is parent._to_dataset_cache` → `True`. |
| 13 | Hidden `ResultBool` re-reduce inside `map_plot_panes` | **REPRODUCES** | `bench_result_base.py:758` (`isinstance(rv, ResultBool) and "repeat" in hv_dataset.data.dims`), independent of the reduce already decided at `:393`. |
| 14 | `hmap_kdims` alphabetically sorted | **REPRODUCES** | `bencher.py:1103` `bench_res.bench_cfg.hmap_kdims = sorted(dims_name)`; consumed at `holoview_result.py:663`. Dies with `ResultHmap`, which is deprecated but present (§1, L1.7). |
| 15 | (V) Size-1 `over_time` leaks as a dropdown / redundant facet | **REPRODUCES** | Both guards are `> 1`: `to_panes_multi_panel` (`bench_result_base.py:874-879`) and `_to_panes_da` (`:931`). At size 1 the dim falls through into `pane_dims` and becomes a facet level. |
| 16 | Histogram's self-contradictory filter | **REPRODUCES** | `histogram_result.py:43-45`: `float_range=exactly(0)`, `cat_range=unbounded()`, `input_range=exactly(0)` — cats are admitted by one range and forbidden by another. (A6 wrote the ranges as `(0,None)`/`(0,0)`; the spelling changed to the `VarRange` constructors, the contradiction did not.) |
| 17 | Surface filters twice with different bounds | **REPRODUCES** | `to_surface` → `float_range=at_least(2)` (`surface_result.py:79`); `to_surface_ds` → `float_range=exactly(2)` (`:118`). |
| 18 | Volume indexes `input_vars[0..2]` positionally | **PARTIAL** | Positional indexing survives (`volume_result.py:83-85`). The `VarRange(-1, 0)` negative bound is **gone** — no negative `VarRange` construction exists in the tree; `VarRange` now has named constructors (`exactly`, `at_least`, `unbounded`) over a `_Bounds` type (`plot_filter.py:23-64`, plan 23 work). |
| 19 | `IntSweep` fully conflated with `FloatSweep` | **REPRODUCES** | `plt_cnt_cfg.py:95`: `isinstance(iv, (IntSweep, FloatSweep, *TIME_TYPES))` → `float_vars`. No discreteness metadata recorded. |
| 20 | (V) video_summary's `reverse` not propagated into recursion | **REPRODUCES** | `_to_video_panes_ds` reverses `dims` at `video_summary.py:194-195` but the recursive call at `:216-224` omits `reverse=`, so it defaults `False`. Peel order stays `first, last, second-to-last, …`. |
| 21 | (V) Three pathways nest `[c1,c2]` differently | **REPRODUCES** | Panel peels `pane_dims[-1]` (`bench_result_base.py:918` body); video peels `dims[-1]` **after** reversing (`video_summary.py:194,209`); rerun peels `cat_dims[-1]`. Follows from #20 being unfixed. |
| 22 | `has_time`, `time_steps`, `samples_per_point` read by nothing | **PARTIAL** | They are now *propagated* into the aggregation shadow config (`bench_result_base.py:825-833`) — but nothing *decides* on them (§5, S1b). "Computed but read by nothing that changes behavior" still holds. |
| 23 | Repeats gating uses configured `repeats`, not observed samples | **REPRODUCES** | `plot_filter.py:229` gates `repeats_range` on `plt_cnt_cfg.repeats`, which is assigned `bench_cfg.repeats` at `plt_cnt_cfg.py:114`. `samples_per_point` (`plt_cnt_cfg.py:56`) — the correct input, computed by `_samples_per_point` (`:150`) — is not used by the gate. |
| 24 | hvplot's implicit groupby widget for unassigned leaf dims | **REPRODUCES** | No planner exists; nothing rejects an unassigned dim. |

**Tally: 20 reproduce, 4 partial (#3, #10, #18, #22), 0 fully fixed.** Two findings
(#16, #18) had their *evidence spelling* change with plan 23's `VarRange` constructors
while the defect stood — cite the new spelling, not A6's. The plan-23 wave (P1–P12) and #989/#994 fixed **type-level representability**
(dead filter axes deleted, negative `VarRange` bounds unconstructible, exhaustive matches)
and made failures **visible** (#3's swallow, A2 P5) — but touched none of the
dimension-assignment logic A6 phases 3/4 exist to replace. **Every phase-3/4 visual diff
still has a live §6 finding to cite.**

---

## 8. Plans 10, 11, 12, 13

| Plan | Verdict | Evidence |
|---|---|---|
| **10 — Regression policy & verdict export** | **OPEN; G3 partially pre-satisfied** | No `severity` field on `RegressionResult` (`regression.py:49-83`) and no `units` — G2 stands. No `report.has_gate_regressions`. **But** `report_export.py` already exists with `SCHEMA_VERSION = 1` (`:43`), `result_to_dict`/`result_to_json` (`:123`,`:169`), `compare_results`/`comparison_to_json` (`:304`,`:384`), and `RegressionReport.to_dict()` (`regression.py:199`) already emits a **`has_blocking_regressions`** aggregate (`regression.py:146`) — derived from `young_baseline` (`:83`), i.e. baseline maturity, **not** from a declared gate/notify severity. Plan 10's phase 1 must be re-scoped around this: the aggregate name it wanted is taken by a different concept. No `RegressionSpec`, no class-level `regression=` declaration. |
| **11 — Worker lifecycle & resource injection** | **OPEN** | No `setup_run`/`teardown_run`/`setup_sample`/`teardown_sample` hooks, no resource-injection surface. The only trace is a docstring at `worker_manager.py:309` acknowledging that workers hold live resources. |
| **12 — Portable artifact paths & cache config** | **OPEN** | No `bencher/paths.py`; no `BENCHER_CACHE_DIR`, no `set_cache_dir`, no root resolver. **13** hard-coded `"cachedir"` string literals remain in `bencher/` outside examples — including the new blob path (`result_collector.py:183` `Path("cachedir").absolute()`), which means #1021 *added* a CWD-relative literal that plan 12 will have to sweep up. |
| **13 — Benchmark declaration bundle & run defaults** | **OPEN** | No `@bn.benchmark` decorator (the `benchmark` symbol in `variables/parametrised_sweep.py:251` is the sweep worker method, unrelated), no env-override resolver, no `display_name` on result variables (`scorecard/discover.py:30` uses the name for the tag registry, not the result var). |

---

## 9. Headline counts

**Load-bearing claims audited: 71** (8 Law-1 + 8 Law-9/A3 + 5 A4-C3 + 6 A4-W + 6 A2 +
10 A5 + 24 A6-§6 + 4 plans).

| Verdict | Count | Which |
|---|---|---|
| **SHIPPED / fixed** | 11 | L1.1, L1.2, L1.4, L1.8 (as acknowledged debt), D1.1, D1.2, C3.3 (by a different mechanism), S1, S2a, A2 P5, A4 W4b |
| **PARTIAL** | 9 | L1.3, L1.6, L1.7, W4d, §7 findings #3, #10, #18, #22, plan 10 |
| **OPEN / confirmed as written** | 50 | L1.5; L9.1, D1.3, D2.1, D3.1, L9.2; C3.1, C3.2, C3.4, C3.5; W1, W4a, W4c, W6; S1b, S2b, S3; all 9 dead fields + the `BenchCfg(BenchRunCfg)` inheritance; the 20 reproducing §6 findings; plans 11, 12, 13 |
| **n/a** | 1 | L9.3 (`collect()` has no plan to store yet) |
| **STALE evidence** (overlaps the rows above) | 4 | A6's "No implementation yet" (`A6-grammar-of-nd-data.md:5`); A4 W4's stale-comment complaint (`worker_job.py:76-79` is now correct); A2's P5 row; A5's 54/73 counts (counting-method difference, not drift) |

**Read that as: 11 of 71 satisfied, 9 half-satisfied, 50 still open.** The satisfied
fraction concentrates almost entirely in one place — A6 Law 1's data layer, plus the
diagnostics work (`explain_selection`, render-failure panes, `identity.py`). Nothing in
A3's contract, A4's manifests or code hash, A2's specs, or A5's cull has moved.

**The three facts the disposition tickets were waiting on:**

1. **A4 phase C3 is not partly shipped by #1021/#1022.** Zero manifests exist. #1022
   shipped a *reachability scan* — a different mechanism for the same problem — and
   `clean_orphaned_media` remains the path-convention mechanism for media. The A4
   disposition rules on manifests-vs-reachability, not on "how much of C3 is left".
2. **A3 phase D1 is not shipped by #932.** A frozen type *named* `BenchData` exists and
   is a plugin handoff object; it lacks `VarSpec`, `DataSignature`, `plot_specs`,
   `artifacts`, and `schema_version`, and carries two live-object fields A3 forbids. The
   A3 disposition faces a naming collision, not a completed phase.
3. **A6 phase 1 did ship (#1021), and A6's own `Status:` line is the stalest line in
   `plans/architecture/`.** The data layer landed; the cleanups Law 1 promised
   (`isel(over_time=-1)`, one missingness oracle, `ResultHmap` removal) did not, and all
   24 §6 findings still have live citations.

**One fact for the route ticket:** plan 27 L9 / plan 26 R2 — the GC's missing
`CACHE_VERSION` guard — is **still present** at this commit
(`cache_management.py:119` has exactly one caller, `bencher.py:197`). Any phase that
bumps `CACHE_VERSION` is blocked on it.
