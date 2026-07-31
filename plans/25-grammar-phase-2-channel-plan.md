# Plan 25 — Grammar Phase 2: Channel Vocabulary, `Plan` Type, and Shadow Planner

**Goal:** Implement phase 2 of the A6 migration
([A6 — Grammar of ND data](architecture/A6-grammar-of-nd-data.md), Law 10 step 2):
the closed dimension→channel vocabulary (Law 5) derived from the `RESULT_SPECS`
registry, the frozen `Plan` type and transform records (Laws 2/5/7), a deterministic
planner implementing default assignment policy v1.1 (Laws 6/7) with `explain()`, and a
**shadow-mode** harness that asserts agreement with today's selection across the whole
gallery — every divergence cited to a numbered A6 §6 finding. The golden-plan corpus is
born here, before any renderer changes. **Zero rendering changes; zero visual changes**
— phase 3 is the first phase allowed to alter a pixel.

**Branch names:** one `plan/grammar-p2-*` branch per phase (each phase is one PR).

**Citations pinned to:** `main` @ `398bdd96` (post plan 23 P4 / PR #1030 and the P2
warn-not-crash amendment / PR #1032, 2026-07-31). Per plans-README rule 7, confirm each
`file:line` against the current tree before relying on it; the symbol is the durable
reference.

**⚠️ Read first:** A6 §2 Laws 5–7 and Law 10 (this plan implements exactly its phase-2
step), A6 §5–6 (the empirical baseline and the 24 findings — the shadow harness's
oracle), plan 22 §"Amendments" (what phase 1 actually became), and plan 23 D3/P4 (the
`RESULT_SPECS` registry this plan derives from). §2.6 below lists where A6's own
citations have gone stale; this plan's §2 is the refreshed baseline.

**Two owner principles bind every design choice here** (both resolved on the record):

- **(a) bencher never crashes mid-run** — plan 23 §10 "P2-amendment" (owner decision,
  2026-07-31): failures degrade visibly, never abort. The rendering-side mechanism
  already exists: `RenderFailedWarning` + `report_render_failure`
  (`bencher/results/render_failure.py:30-58`, PR #1027) — an ERROR log, a warning a
  strict pipeline can promote, and a labelled failure pane in the report. The planner
  is designed so this principle is structural, not aspirational (D6).
- **(b) long-term correctness beats short-term convenience** — no shims that would let
  a wrong plan render "close enough"; divergences from today's behavior are recorded
  and reviewed, not absorbed.

---

## 1. Scope and non-goals

In scope (all additive; no existing module's behavior changes):

- **`bencher/grammar/`** — a new package: channel vocabulary, kind→channel capability
  derivation from `RESULT_SPECS`, frozen `Plan`/transform/mark-declaration record
  types, the planner, `explain()`. On the strict `ty` list from day one (plan 23 D1 —
  new code has no legacy excuse).
- **Shadow harness + divergence ledger** — test-only (A6 Law 10: "Shadow mode exists
  only inside phase 2's test suite").
- **Golden-plan corpus** — checked-in serialized plans with a regeneration task and a
  CI diff check. This repo has no snapshot infrastructure (§2.7); this plan creates the
  first, following the documented-update-procedure precedent of
  `TestGoldenBenchCfgHash` (`test/test_hash_persistent.py:766-807`).

Out of scope (recorded so nobody "helpfully" pulls them forward):

- **Any renderer change.** `_to_panes_da`, `map_plot_panes`, the composable containers,
  rerun, video — untouched. Phase 3 rewrites panel/holoviews as plan execution; phase 4
  does rerun/video. The DoD greps enforce that nothing under `bencher/results/` or
  `bencher/plugins/` imports `bencher.grammar` (§8).
- **The Law 8 API surface** (`res.view()`, `views=`, `bn.compose`) — phase 5.
- **Plan-at-collect storage** (Law 9's stored plans). Deferred to phase 3 with
  rationale: a stored plan with no consumer is dead weight plus a compatibility surface
  for old pickles; nothing in Law 9 requires storing before a renderer reads plans.
  Law 9's *cache* half — nothing plan-shaped ever enters a cache key — is enforced
  starting now (§7).
- **Backend capability tables for plotly/video/rerun** (Law 3). Phase 2 ships the
  capability-table *type* and one seed table for the panel/holoviews backend — the
  minimum the planner needs to shadow today's auto path. The other backends' tables
  land with their lowering phases (3–4), where they can be validated against real
  lowerings instead of guessed.
- **Opening the mark registry to entry points** (Law 5's "marks are open"). Phase 2's
  mark declarations are an internal table keyed by the existing plugin names
  (`bencher/plugins/builtins.py:66-139`) so phase 3 can migrate name-by-name; the
  public entry-point promise ships with phase 5's API.
- **`ResultHmap` removal** — phase 3 (plan 22 D6 schedule unchanged). The planner
  treats it as unplannable-deprecated (D3).
- **Fixing any of the §2.4 live findings** in the legacy pathways (e.g. the video
  `reverse` bug, the surface double-filter). Phase 3/4 deletes those code paths; fixing
  them now would churn the shadow baseline twice. The one exception is documented in
  §10 (registry failure-pane unification), and even that is deferred.

## 2. Measured facts (verified 2026-07-31 against `398bdd96`; do not re-litigate)

### 2.1 What landed between A6's acceptance (2026-07-30) and today

A6's header says "No implementation yet". **Stale.** Since acceptance:

1. **Phase 1 (Law 1) is complete** — plan 22, PRs #1019/#1021, plus follow-ups: blob
   store GC (#1022), dedup-mtime fix and worker-contract amendment (#1030/#1031/#1032).
   `ResultDataSet` cells are content-addressed blob paths
   (`bencher/blob_store.py:148` `materialize_blob`, `:210` `load_blob`, layout
   `<cachedir>/blobs/<sha256[:16]><ext>`); the `isel(over_time=-1)` render restriction
   is gone (removal documented at `bencher/results/bench_result_base.py:1112-1121`);
   `result_is_missing` is the single missingness oracle
   (`bencher/variables/results.py:914`); `ResultHmap` is deprecated
   (`bencher/variables/results.py:269-277`) — **deprecated only, not removed**; A6
   Law 1's "deprecated and removed" describes the post-phase-3 end state.
2. **The result-type registry exists** — plan 23 P4 (PR #1030).
   `RESULT_SPECS: dict[type, ResultSpec]` (`bencher/variables/results.py:644`),
   `ResultKind` StrEnum with 12 members (`:576`), `ResultSpec` frozen dataclass
   (`:598-636`: `kind`, `missing_fill`, `fill_dtype`, `missing_sentinels`, `is_scalar`,
   `is_panel`, `is_media`, `is_data_var`, `multidim`, `reference_backed`),
   `result_spec()` most-derived-first resolution (`:796`), `result_kind()` (`:844`),
   exemption list `RESULT_SPEC_EXEMPT` (`:959`). The nine tuples are now derived values
   (`PANEL_TYPES` `:817`, `SCALAR_RESULT_TYPES` `:819`, …). This is the registry plan 23
   §8 told this plan to derive the channel vocabulary from.
3. **The degrade-visibly mechanism exists** — PR #1027. `RenderFailedWarning`
   (`bencher/results/render_failure.py:30`), `report_render_failure(what, exc)`
   (`:34-58`: ERROR log with `exc_info`, warning at `stacklevel=3`, labelled Markdown
   failure pane), publicly exported (`bencher/__init__.py:186`). Seven call sites:
   `bencher/results/bench_result.py:357,362,492,509`,
   `bencher/optuna_conversions.py:175,187`, `bencher/run.py:202`. A6 predates this;
   this plan makes it the planner's failure contract (D6).
4. **The worker-contract warn-not-crash pattern exists** — `WorkerContractError`
   (`bencher/job.py:118`), `WorkerContractWarning` (`:130`), `SampleFailure` (`:165`),
   consumed by `store_results` (`bencher/result_collector.py:412-489`), surfaced by the
   auto-inserted failed-samples summary (`bencher/results/bench_result.py:463-470`).
   This is the codified form of owner principle (a).
5. **`ReduceType` matching is exhaustive** — plan 23 P1: `_resolve_auto`
   (`bencher/results/bench_result_base.py:248-268`) normalizes `None`/`AUTO` and the
   `to_dataset` match ends in `assert_never` (`:383-384`). Law 2's replacement of
   `ReduceType` by mark-owned spread is unchanged; the starting point is just cleaner.

### 2.2 The rendering pathways, recounted (A6 said nine; today: nine, plus growth)

All nine of A6 §1's pathways exist, none renamed:

| # | A6 name | Entry point today |
|---|---|---|
| 1 | hvplot numeric | `map_plot_panes`, `bencher/results/bench_result_base.py:651-720`; leaf `*_ds` callbacks e.g. `to_line_ds` (`holoview_results/line_result.py:95`), `to_bar_ds` (`bar_result.py:83`), `to_heatmap_ds` (`heatmap_result.py:94`) |
| 2 | hand-built hv elements | `DistributionResult._plot_distribution` (`holoview_results/distribution_result/distribution_result.py:82-127`), `_build_curve_overlay` (`holoview_result.py:234-293`), `BandResult._build_band_overlay` (`band_result.py:243-303`) |
| 3 | HoloMap over-time | `HoloviewResult._build_time_holomap` (`holoview_results/holoview_result.py:327-379`) |
| 4 | per-sample panes | `map_sample_panes` → `_to_panes_da` → `ds_to_container` (`bench_result_base.py:617-649`, `:883-972`, `:1299-1366`) |
| 5 | base64 slider hack | `_pane_over_time_slider` (`bench_result_base.py:974-1049`) |
| 6 | rerun over-time grid | `_pane_over_time_grid` (`bench_result_base.py:1066-1103`) — **not** in `rerun_result.py`/`video_summary` as A6 §1 implies |
| 7 | video composition | `VideoSummaryResult._to_video_panes_ds` (`video_summary.py:176-245`) + `ComposableContainerVideo.render` (`composable_container/composable_container_video.py:113-184`) |
| 8 | plotly direct | `VolumeResult.to_volume_ds` (`volume_result.py:76-115`), `SurfaceResult.to_surface_ds` (`holoview_results/surface_result.py:90-171`) |
| 9 | rerun whole-sweep recorder | `RerunResult.to_rerun` (`rerun_result.py:50-143`), blueprint at `_build_blueprint` (`:379-391`) |

The surface has **grown since the A6 audit**, in three ways the phase-3/4 migration
must budget for (recorded here so the "nine pathways" framing is not taken literally):

- **A tenth member of the over-time-grid family:** `_pane_over_time_dataset`
  (`bench_result_base.py:1105-1151`), added by plan 22 D4 for blob-backed
  `ResultDataSet` history — dispatched from `_to_panes_da` at `:960-969`.
- **The `TabularSpec` family** (`holoview_results/tabular_spec.py:167`, `.build` at
  `:202`) with four xy result classes (`xy_scatter_result.py:56-82` builds `hv.Points`;
  siblings `xy_curve_result.py`, `xy_hexbin_result.py`, `xy_histogram_result.py`) —
  a new hand-built-hv pathway registered named-only in the plugin registry.
- **`RerunSummaryResult`** (`rerun_summary.py:48`, recursion `_compose_ds:194-254`) is
  the *second* hand-synced rerun recursion A6 §Law 10 phase 4 refers to; it also
  independently reproduces the video `reverse` omission (§2.4).

Sizing: `bencher/results/**` is 9,586 lines across 47 files at this commit.

### 2.3 The filter dialects, recounted (A6 said three; confirmed, plus one gate layer)

1. **`VarRange` counts** — `bencher/plotting/plot_filter.py:13-69` (`VarRange`),
   `:72-114` (`PlotFilter`, 7 range fields at `:75-81`), matching loop in
   `PlotMatchesResult` (`:117-181`). Call sites of `matches_result`:
   `bench_result_base.py:801` (the generic `filter()` gate),
   `holoview_results/surface_result.py:122` (the second, inner surface check — A6
   finding 17, still live), `video_summary.py:69-71`, `rerun_summary.py:112-114`, and
   `plugins/registry.py:248`. Two dead axes still gate every plot:
   `plt_cnt_cfg.vector_len`/`result_vars` (`bencher/plotting/plt_cnt_cfg.py:38-39`,
   read at `plot_filter.py:141-142`) — plan 23 C4/P6, not yet landed.
2. **`result_types` tuples** — the `isinstance` gate in `map_plot_panes`
   (`bench_result_base.py:675-678`) fed by per-plot declarations: `SCALAR_RESULT_TYPES`
   (`line_result.py:90`, `curve_result.py:47`, `band_result.py:48`), `(ResultFloat,)`
   (`heatmap_result.py:81`, `surface_result.py:85`, `histogram_result.py:49`,
   `volume_result.py:71`, `distribution_result.py:60`), bar's two-scenario loop
   (`bar_result.py:68-81`), `PANEL_TYPES` (`pane_result.py:31`), `(ResultDataSet,)`
   (`dataset_result.py:34`), `(ResultImage,)` (`video_summary.py:31`),
   `(ResultRerun,)` (`rerun_summary.py:54`), and the unmatchable `(ResultVar,)`
   (`scatter_result.py:48` — A6 finding 11, still live).
3. **`target_dimension` recursion depth** — declared at `map_sample_panes:623` (=0),
   `map_plot_panes:655` (=2), `filter:734` (=2), `to_panes_multi_panel:834` (=1);
   recursion predicate at `_to_panes_da` `bench_result_base.py:902`. Values in use:
   0 (panes/dataset/video/rerun/xy), 2 (most hvplot), 3 (volume), `cat_cnt + 1`
   (distribution — A6 finding 7), `None` → never recurses (band, resolved at
   `:847-848`).

Plus a **fourth gate layer** A6's count predates in its current form: the plugin
registry's selection ladder (`bencher/plugins/registry.py:190-284` `explain()`:
include/exclude → named-only `auto=False` → `requires` capability strings checked
against `BenchData.has()` (`plugins/bench_data.py:50-62`, unknown string silently
`False` — plan 23 C10) → `PlotFilter` → backend/priority). It is a *selection* layer,
not a shape dialect, but the planner replaces the shape-relevant part of it in phase 3,
so it is counted here. Note the builtins all register `PlotFilter.match_all()`
(`plugins/builtins.py:159,172`) and keep their real shape checks inside `to_plot` — so
`registry.explain()` alone does **not** reveal today's effective selection (this shapes
the shadow-harness design, D5).

### 2.4 A6 §6 findings spot-checked — the baseline is still the baseline

Every finding this plan's harness leans on was re-verified live at `398bdd96`:

| Finding | Status | Evidence |
|---|---|---|
| #11 unmatchable `ScatterResult` gate | live | `holoview_results/scatter_result.py:48` `(ResultVar,)` |
| #12 histogram `isel(over_time=-1)` cache alias | live | `histogram_result.py:37`; also `plt_cnt_cfg.py:174` (`_samples_per_point` measures only the last time point) |
| #13 hidden `ResultBool` re-reduce | live | `bench_result_base.py:700-705` overrides the caller's `reduce` |
| #17 surface double filter | live | outer `filter(...)` at `surface_result.py:77-88`, inner `matches_result` at `:122` |
| #20 video `reverse` not propagated | live | declared `video_summary.py:186`, applied `:192-193`, omitted from the recursive call `:217-225` — **and reproduced in `rerun_summary.py:202,:217-218,:238-244`**, which the A6 audit did not list |
| #22 signature fields computed, unread | live | `has_time`/`time_steps`/`samples_per_point` on `PltCntCfg` (A2 S1) still feed no selection |
| #24 hvplot implicit widget | live (behavioral) | named in comments at `bench_result_base.py:895`, `:946-950` |
| C4 dead filter axes | live | `plt_cnt_cfg.py:38-39` (plan 23 P6 pending) |
| B1 video-controls zip truncation | live | `video_controls.py:30-35` (plan 23 P3 pending; not a planner concern, listed for completeness) |

### 2.5 The registry-derivation premise, verified

`ResultKind` has exactly 12 members (`bool float vec image video path string dataset
rerun container hmap reference`, `variables/results.py:576-595`), each `ResultSpec`
carries the classification bits the channel capability function needs (`is_scalar`,
`is_panel`, `is_media`, `is_data_var`, `kind`), and `result_spec()` resolves deprecated
subclasses (`ResultVar` → `ResultFloat`'s spec) via isinstance fall-through (`:796-805`).
A total function over `ResultKind` with `assert_never` therefore covers every result
type that can legally exist, and CI already fails on an unregistered `Result*` class
(plan 23 P4 DoD). **This is what makes a closed channel vocabulary derivable now** — the
premise of plan 23 §8's instruction to write this plan after P4.

### 2.6 Stale A6 claims found while verifying (correct the doc, not the plan)

Recorded per plans-README rule 7; none invalidates A6's reasoning:

1. A6 header "No implementation yet" — phase 1 landed (§2.1.1); the header should say
   phase 1 is complete and link plan 22's amendments.
2. A6 §5 cites `hmap_kdims = sorted(...)` at `bencher.py:1059` — now
   `bencher/bencher.py:1107`.
3. A6 §1 places the "rerun over-time grid" pathway among the rerun/video files — it
   lives in `bench_result_base.py:1066-1103` (`_pane_over_time_grid`).
4. A6 Law 1 "ResultHmap is deprecated and removed" — deprecated only; removal is
   phase 3 (plan 22 D6). Phase 2 must plan *around* live hmaps, not assume them gone.
5. The "nine pathways" and "three dialects" counts are floors, not exact: §2.2 lists
   three growths (one of them created by phase 1 itself) and §2.3 a fourth gate layer.
6. A6 §6 finding 21 lists three divergent nesting orders; the rerun-summary `reverse`
   omission (§2.4) is a fourth instance of the same class, previously unlisted.
7. Law 5's "existing plugin registry (entry points group `bencher.plot_plugins`)" —
   group name confirmed (`plugins/registry.py:14` `ENTRY_POINT_GROUP`), but note
   `pyproject.toml` declares no entry points itself; builtins register imperatively at
   import of `bench_result` (`bencher/results/bench_result.py:591`). The group is a
   third-party surface only.

### 2.7 No golden/snapshot infrastructure exists

Measured: no `conftest.py` anywhere; zero non-`.py` files under `test/`; no
update-flag machinery. The two precedents are inline constants with documented update
procedures: `GOLDEN_BENCH_CFG_HASH_*` (`test/test_hash_persistent.py:741-763`) and the
pixel-MD5 goldens in `test/test_cartesian_pil_renderer.py:143-171`. The golden-plan
corpus (D7) is therefore new infrastructure and must carry its own regeneration task
and documented update procedure.

## 3. Problem statement

Phase 3 rewrites `_to_panes_da` + `map_plot_panes` as plan execution and phase 4
deletes the two rerun recursions and the video peel bug. Neither can start until:

1. **The plan exists as a type** — frozen, picklable, serializable — so a "did
   auto-deduction change?" question has a diffable answer (Law 6's golden plans).
2. **The planner reproduces today's behavior on today's gallery**, with every
   intentional divergence enumerated against A6 §6 *before* any renderer changes — so
   phase 3's visual diffs are attributable to reviewed decisions, not accidents.
3. **The channel/kind knowledge has one home.** Today the type→visual mapping exists in
   at least three copies (`ds_to_container` precedence chain,
   `bench_result_base.py:1299-1366` — with a fourth partial copy in
   `_dataset_sample_to_container` `:1202-1297`; `_log_result_var`'s isinstance ladder,
   `rerun_result.py:347-376`; `result_var_to_container`,
   `holoview_results/holoview_result.py:546-557`). The grammar package becomes the
   single derivation from `RESULT_SPECS`; the copies die in phases 3–4.

What makes this tractable *now* and not before: plan 23 P4. Deriving channel legality
from nine hand-maintained tuples would have re-scattered the knowledge; deriving it
from `RESULT_SPECS` is one total function (§2.5).

## 4. Proposed design

### D1 — Package layout and enforcement posture

```
bencher/grammar/
    __init__.py      # public re-exports; GRAMMAR_VERSION
    channels.py      # Channel enum, Frame enum, kind_caps()
    plan.py          # DimAssignment, Transform records, Spread, Plan, Reject, LayoutPlan
    marks.py         # MarkDecl + the seed mark table + panel-backend capability table
    planner.py       # plan_result_var(), plan_sweep(), explain(); policy v1.1
```

- Every module lands on the strict `ty` override list in the same PR that creates it
  (plan 23 D1's ratchet rule: "constructively modeled" ⇔ "strictly checked").
- Every `match` over `Channel`/`ResultKind`/`Frame`/transform unions ends in
  `assert_never` (plan 23 D2), and every match subject is constructed by the grammar
  package itself — no raw `param`-descriptor reads (plan 24 §2's precondition is
  satisfied by design: `PlanInputs` normalizes at the boundary, D4).
- Nothing under `bencher/results/` or `bencher/plugins/` imports `bencher.grammar` in
  this plan — enforced by a DoD grep (§8). The planner has consumers only in `test/`.

### D2 — The closed channel vocabulary (Law 5)

```python
class Channel(StrEnum):
    """Closed dimension-assignment vocabulary — A6 Law 5. Adding a member
    requires a GRAMMAR_VERSION bump and an owner-reviewed grammar change."""
    X = "x"
    Y = "y"
    Z = "z"
    OVERLAY = "overlay"
    FACET_ROW = "facet_row"
    FACET_COL = "facet_col"
    TABS = "tabs"
    TIME = "time"
    SPREAD = "spread"
```

Exactly nine members, explicit lowercase values (plan 23 D4: never `auto()` on a
`strenum.StrEnum` where the value is a contract — these strings become Law 8's kwarg
names in phase 5 and golden-file content now). `GRAMMAR_VERSION = "1"` lives beside it;
plans embed it; a vocabulary change bumps it (Law 5). `Color`, `Style`, `Animation`,
`EntityPath` are rejected candidates per Law 5 — a test pins the member count so adding
one is a visible, reviewed act.

### D3 — Kind capabilities derived from `RESULT_SPECS` (the "derive, don't redeclare" core)

```python
class Frame(StrEnum):
    """Shared-coordinate-frame classification for Overlay legality — A6 Law 5."""
    AXES = "axes"        # numeric marks: shared axes
    PIXELS = "pixels"    # image/video: shared pixel extents
    ENTITY = "entity"    # rerun: shared entity space
    NONE = "none"        # no shared frame: Overlay illegal, fall back to FacetCol

@dataclass(frozen=True)
class KindCaps:
    frame: Frame
    positional: bool          # value may drive X/Y/Z (a plottable magnitude)
    spread_stat: SpreadStat | None   # kind-based default statistical collapse (Law 2)

def kind_caps(kind: ResultKind) -> KindCaps:
    match kind:
        case ResultKind.FLOAT | ResultKind.VEC:
            return KindCaps(Frame.AXES, True, SpreadStat.MEAN_STD)
        case ResultKind.BOOL:
            return KindCaps(Frame.AXES, True, SpreadStat.BINOMIAL)   # Law 2.2
        case ResultKind.IMAGE | ResultKind.VIDEO:
            return KindCaps(Frame.PIXELS, False, None)
        case ResultKind.RERUN:
            return KindCaps(Frame.ENTITY, False, None)
        case ResultKind.PATH | ResultKind.STRING | ResultKind.DATASET \
             | ResultKind.CONTAINER | ResultKind.REFERENCE:
            return KindCaps(Frame.NONE, False, None)
        case ResultKind.HMAP:
            return KindCaps(Frame.NONE, False, None)  # unplannable-deprecated, D4
        case _ as unreachable:
            assert_never(unreachable)
```

Design points:

- **Derivation, not duplication.** The function is keyed on `ResultKind`, which only
  `RESULT_SPECS` produces (`result_kind()`, `variables/results.py:844`); a completeness
  test iterates `RESULT_SPECS` and asserts `kind_caps(spec.kind)` succeeds for every
  entry, and the `assert_never` makes a new `ResultKind` member a **static** error in
  the grammar package (`type-assertion-failure` is never ignored — plan 23 P1's
  meta-test already pins that). Together with plan 23 P4's registration guard, the
  chain "new `Result*` class → must have a spec → must have a kind → must have caps"
  has no silent link.
- **`missing`-awareness comes free:** the planner consults `result_is_missing`
  (`variables/results.py:914`) for observed-sample counts — never a hand-rolled NaN or
  sentinel check (plan 22 D5's oracle discipline; contrast finding C12's `0.0` fills in
  rerun, which phase 4 fixes).
- **Where per-spec bits are needed** (`is_panel` for the sample-mark decision,
  `is_data_var` to skip hmap/vec expansion), the planner reads the spec itself.
  **OWNER DECISION 2** records the alternative (adding a `frame` field to `ResultSpec`)
  and why derived-in-grammar is recommended.
- **`ResultReference`** plans like `CONTAINER` but the resulting `Plan` is tagged
  `same_process_only=True` — Law 1: nothing in the core algebra may *depend* on it, and
  the tag is how a phase-3 renderer refuses to pretend a stripped reference is
  renderable across a process boundary (it degrades to the labelled placeholder,
  principle (a)).
- **`ResultVec` deviation, recorded:** A6's planner invariant says "`ResultVec`'s index
  becomes a real dim (kills #10)". That is a *stored-data* change (the collector
  expands vecs to per-element columns today — `index_names()`,
  `variables/results.py:246-252`) and belongs to a phase that owns a cache-safety
  story for it (phase 3, alongside the other dataset-shape work). **Phase 2 plans each
  expanded column as an independent float result var, matching storage today.**
  OWNER DECISION 3.

### D4 — The frozen `Plan` type and its inputs (Laws 2, 5, 6, 7)

All records are frozen dataclasses, picklable, and JSON-serializable with sorted keys
(canonical bytes for golden files). Nothing here holds a live object, a dataset, or a
callable — a `Plan` is *pure description* (Law 9's picklability requirement arrives
free).

```python
@dataclass(frozen=True)
class DimAssignment:
    dim: str                 # dataset dim name; dims addressed by name (Law 8)
    channel: Channel

# Transform algebra (Law 2) — named, frozen, picklable records:
@dataclass(frozen=True)
class Select:    dim: str; value: Any
@dataclass(frozen=True)
class Aggregate: dims: tuple[str, ...]; fn: str          # "mean" etc.
@dataclass(frozen=True)
class Subsample: dim: str; stride: int
@dataclass(frozen=True)
class Squeeze:   dim: str; value: Any                    # size-1 dim -> constant
Transform = Select | Aggregate | Subsample | Squeeze

class SpreadStat(StrEnum):
    MEAN_STD = "mean_std"; BINOMIAL = "binomial"; MINMAX = "minmax"; QUARTILES = "quartiles"

@dataclass(frozen=True)
class Substitution:          # Law 3: planner-owned fallback, recorded and explainable
    requested: Channel; substituted: Channel; reason: str

@dataclass(frozen=True)
class ConstantDim:           # squeezed dims kept as provenance, never axes (Law 7)
    dim: str; value_repr: str

@dataclass(frozen=True)
class Plan:
    result_var: str
    mark: str                        # MarkDecl registry key == plugin name
    backend: str                     # "panel" in phase 2
    assignments: tuple[DimAssignment, ...]   # declaration order; every post-transform
                                             # dim appears exactly once (invariant)
    transforms: tuple[Transform, ...]
    spread: SpreadStat | None
    constants: tuple[ConstantDim, ...]
    substitutions: tuple[Substitution, ...]
    same_process_only: bool
    policy_version: str              # POLICY_VERSION at planning time (Law 6)
    grammar_version: str             # GRAMMAR_VERSION (Law 5)

@dataclass(frozen=True)
class Reject:
    result_var: str
    reasons: tuple[str, ...]
    suggestions: tuple[str, ...]     # e.g. "Aggregate(('lidar_id',), 'mean')" — the
                                     # planner suggests, never silently applies (Law 7.6)

PlanOutcome = Plan | Reject          # exhaustively matched by consumers

@dataclass(frozen=True)
class SweepPlan:                     # Law 5: one plan per result var + outer layout
    per_var: tuple[PlanOutcome, ...]
    outer_layout: Channel            # layout channel composing multi-var plans
```

**Planner inputs are a parsed boundary type**, not raw `param` objects (plan 24's
precondition — no `match` over descriptor reads):

```python
@dataclass(frozen=True)
class DimInfo:
    name: str
    size: int                        # observed, post-transform
    role: DimRole                    # INPUT_FLOAT | INPUT_CAT | REPEAT | TIME (StrEnum)
    declaration_index: int           # canonical order: input_vars decl order, repeat, over_time (A6 §5)
    discrete: bool                   # IntSweep-ness; annotation only in v1 (Law 7.3)

@dataclass(frozen=True)
class VarInfo:
    name: str
    kind: ResultKind                 # from result_kind() — the registry, nothing else
    observed_samples_per_point: int  # counted via result_is_missing over the RAW repeat
                                     # dim, all time points — NOT plt_cnt_cfg's
                                     # last-time-point-only _samples_per_point (§2.4 #12/#22)

@dataclass(frozen=True)
class PlanInputs:
    dims: tuple[DimInfo, ...]
    result_vars: tuple[VarInfo, ...]
    pins: Pins                       # frozen partial-constraint set (Law 6): any subset
                                     # of channel-by-dim-name / mark / backend / transforms
    prefs: Prefs                     # pane_layout successor knob etc. (grid-vs-tabs chain)
```

`PlanInputs.from_bench_result(bench_res)` is the only place the grammar touches bencher
objects; it reads `bench_res.ds` (the raw stored dataset) and result-var metadata —
**never through `to_dataset()`'s reduce cache** (finding #12's poisoned-cache class must
not gain a new client; see §7).

### D5 — The planner: policy v1.1, deterministic and explainable (Laws 3, 6, 7)

`plan_result_var(inputs, var) -> PlanOutcome` implements A6 Law 7's seven steps
literally — each step is a named function with its own unit tests, in this order:

1. `repeat` → `SPREAD` if the chosen mark accepts it, else `Aggregate(("repeat",), "mean")`.
   Never positional. Spread stat defaults from `kind_caps` (bool → binomial — Law 2.2's
   "kind-based default stat in one place", replacing the hidden re-reduce at
   `bench_result_base.py:700-705`).
2. Time dims with >1 **observed** points → `TIME`; size-1 time dims become
   `ConstantDim` provenance, absent for planning (finding #15).
3. Floats in declaration order → `X`, `Y` (`Z` only when a 3D mark/backend is in
   play); leftovers join the facet pool. `discrete` recorded as annotation only.
4. First-declared cat with ≤ `OVERLAY_BUDGET` levels → `OVERLAY` for marks whose
   target kind has a shared frame (`kind_caps().frame is not Frame.NONE`); otherwise the
   dim goes to the facet pool and a `Substitution(OVERLAY, FACET_COL, "no shared
   coordinate frame")` is recorded (Law 5).
5. Remaining dims → facet pool, nested last-declared-outermost (the current
   panel/rerun order; video conforms in phase 4 — findings #20/#21). Assigned
   `FACET_COL`/`FACET_ROW`/`TABS` per level honoring `prefs` (successor of
   `pane_layout`, `bench_cfg.py:364-371`).
6. Cardinality budgets with demote-then-reject: `OVERLAY ≤ 8` → facet level ≤ 6 →
   `TABS ≤ 20` → `Reject` with `suggestions` naming the `Aggregate`/`Subsample` the
   user could pin. The planner **never** applies an uninvited data transformation
   (Law 7.6). Budget constants are named module-level values folded into
   `POLICY_VERSION` (OWNER DECISION 1).
7. Mark by residual shape × `result_kind`; backend by fidelity over the seed capability
   table (panel/holoviews only in phase 2). Repeat thresholds gate on
   `observed_samples_per_point` (line at ==1; curve/box/violin at ≥2 — finding #23).

Planner invariants, each a test (they mirror A6 Law 7's bullet list):

- Plans bind to the post-transform shape; a squeezed dim is a `ConstantDim`, never an
  axis (#1/#2/#3/#17).
- Every post-transform dim has exactly one channel owner; an unassigned dim is a
  planner **bug** surfaced as `Reject("internal: unassigned dim …")`, never an implicit
  widget (#24).
- `PlanOutcome` is the only return type; there is no `override=True` anywhere in the
  grammar package (#4/#5) — a DoD grep pins it.
- A `MarkDecl` whose `target_kinds` is empty or names no `ResultKind` member fails at
  construction (#11/#16's class).
- Determinism (Law 6): same `PlanInputs` ⇒ byte-identical serialized plan. Enforced
  three ways: a repeat-invocation unit test, a hypothesis property test over generated
  shapes (the repo already uses hypothesis), and the golden corpus (D7).

`explain(inputs) -> str` renders the assignment trace, substitutions, budget checks and
mark/backend choice as a text table — same affordance shape as
`decisions_to_table` (`plugins/registry.py:31-42`) and `explain_selection`
(`bench_result.py:369-394`), which it will absorb in phase 3 (A6 supersedes A2 S3–S4).

**Mark declarations (marks.py):**

```python
@dataclass(frozen=True)
class MarkDecl:
    name: str                                  # == plugin name (builtins.py:66-139)
    target_kinds: frozenset[ResultKind]        # construction-checked non-empty
    accepted_channels: frozenset[Channel]
    spread: frozenset[SpreadStat]              # statistical collapses this mark can draw
    positional_dims: range                     # residual dims the mark consumes at the leaf
```

Seeded with the eight auto builtins (`bar`, `box_whisker`, `curve`, `line`, `heatmap`,
`histogram`, `volume`, `panes`) plus the named-only marks the golden corpus exercises
(`violin`, `surface`, `band`, `table`, the xy family, `video_summary`, `rerun`,
`rerun_summary`, sample marks for panel kinds). Names deliberately match the plugin
registry so phase 3's name-keyed replacement (Law 10.3) is a lookup, not a mapping
table. The declarations encode today's *intent* (e.g. distribution marks accept
`SPREAD=quartiles`, consume one cat dim + repeat), not today's bugs (e.g. no mark
declares `cat_range=(0,None)` with `input_range=(0,0)` — finding #16 is
unrepresentable because a `MarkDecl` has no contradictory dual bounds).

### D6 — Never crash: the planner's failure contract (owner principle a)

- The planner is a **total pure function**: `plan_result_var` returns `Plan | Reject`
  for every conforming `PlanInputs`; it raises only on non-conforming inputs
  (programmer error at the boundary parse, same posture as `normalize_executor`).
- In phase 2 the planner runs **only in tests**, where a raise is a loud test failure —
  correct.
- The phase-3 integration contract is stated now, once, so no later phase improvises:
  *any* exception or `Reject` on the auto path degrades through
  `report_render_failure(f"Plan for '{var}'", exc_or_reject)`
  (`render_failure.py:34-58`) — labelled pane, ERROR log, `RenderFailedWarning`, report
  continues. On the *pinned* path (Law 6: user pins that cannot be satisfied), the
  `Reject` with its reasons and suggestions **is** the visible artifact — loud, but
  still a pane, never an exception through the report build. This mirrors the
  worker-contract disposition (plan 23 §10 P2-amendment): record + warn visibly, never
  lose the run.
- Consequence for phase 2's own deliverables: `Reject` must carry enough structure
  (`reasons`, `suggestions`) to *be* that pane without reformatting. The golden corpus
  includes `Reject` outcomes (e.g. a 30-level StringSweep hitting every budget) so the
  degraded path is pinned from birth.

### D7 — Shadow harness, divergence ledger, golden corpus (Law 10 phase 2; Law 6)

**Corpus.** Three tiers:

1. **Synthetic shapes** — one per A6 §6 finding that is shape-reproducible (at minimum
   #1–#3, #6–#9, #15, #17, #19–#21, #23–#24), built as hand-constructed `PlanInputs`.
2. **The meta examples** (`bencher/example/meta/`) and a curated slice of the generated
   tree (`bencher/example/generated/`, discovered exactly as
   `test/test_split_render_examples.py:36-39` does) — real sweeps, executed once per
   test session with tiny sample counts.
3. **Golden plans**: `test/golden_plans/*.json` — one canonical-JSON file per corpus
   entry (sorted keys, one plan or reject per result var). Regenerated by a new pixi
   task `update-golden-plans` (a `python -m` entry in the test tree, not shipped in the
   wheel); the test asserts byte-identity and its docstring carries the update
   procedure verbatim from the `TestGoldenBenchCfgHash` precedent: *update goldens only
   after reviewing the plan diff, and say why in the PR.*

**Agreement measurement.** Because builtins hide their shape checks inside `to_plot`
(§2.3), `registry.explain()` is not a usable oracle on its own. The harness measures
today's behavior empirically, without asserting on pixels:

- Instrument `PlotFilter.matches_result` (it already receives `plot_name`) and
  `PlotMatchesResult` to record `(plot_name, matched)` during a `to_auto()` run —
  monkeypatched recorder, test-only.
- Instrument `to_panes_multi_panel`/`_to_panes_da` to record the actual peel trace:
  the ordered `(dim, role)` list each pathway realizes (outermost first), plus which
  leaf callback fired.
- Compare: (a) planner's chosen mark set vs the recorded matched set per sweep;
  (b) planner's `assignments` (facet nesting order, overlay dim, x dim, time channel)
  vs the recorded peel trace.

**Divergence ledger.** `test/shadow_divergence_ledger.py`: a frozen table of
`(corpus_entry, divergence_kind, a6_finding, rationale)`. The suite asserts **every**
observed disagreement matches exactly one ledger entry and every ledger entry cites an
A6 §6 finding number (or one of §2.6's newly recorded instances). An unexplained
divergence fails CI in either direction — including the direction where a legacy bug
this plan expected to shadow has been *fixed* under us (the ledger goes stale loudly,
plans-README rule 7 applied to tests).

Expected divergences, pre-seeded from §2.4: the planner will *not* reproduce #5/#6
(repeat peeled positionally under override), #13 (hidden bool re-reduce — the planner
declares binomial spread instead), #15 (size-1 time dropdown), #17 (surface double
filter), #20/#21 (video/rerun peel order — planner emits the panel order), #24
(implicit widget). Each ships as a ledger row on day one.

### D8 — Versioning (Laws 5 and 6)

- `GRAMMAR_VERSION = "1"` — the channel vocabulary. Bumped only by an owner-reviewed
  vocabulary change.
- `POLICY_VERSION = "1.1"` — Law 7's name for the default assignment policy, embedding
  the budget constants. Any change to assignment behavior bumps it; golden plans embed
  both versions, so a policy change is a reviewed golden diff (Law 6's "policy changes
  are visible versioned events").

## 5. Phases

Each phase is one PR on a `plan/grammar-p2-*` branch; `pixi run ci` and
`pixi run test-split` must pass; each adds its new files to the strict `ty` list.
**Ordering rationale:** vocabulary before records (records embed channels), records
before planner (the planner returns them), planner before shadow (the harness compares
it). P1–P3 are pure-additive library PRs reviewable in isolation; P4 is where the
empirical claims get tested against reality, so it is last and largest — and it is the
phase gate for A6 phase 3.

### P1 — Channel vocabulary + kind capabilities (`channels.py`)

- `Channel` (9 members, explicit values), `Frame`, `SpreadStat`, `KindCaps`,
  `kind_caps()` with `assert_never`, `GRAMMAR_VERSION`.
- **Tests:** member-count pin (9 channels; adding one fails a test *and* requires a
  version bump the test checks); completeness over `RESULT_SPECS` (every spec's kind
  has caps; run under `warnings.catch_warnings()` — instantiating `ResultHmap`/
  `ResultVar` warns, plan 23 D3 note); frame-legality table (image/video → PIXELS,
  rerun → ENTITY, scalar → AXES, path/string/dataset/container/reference → NONE);
  bool → binomial default.
- **DoD:** deleting a `case` arm from `kind_caps` fails `pixi run ty` with
  `type-assertion-failure`; `bencher/grammar/` contains no `isinstance` on `Result*`
  classes (grep, §8).

### P2 — Plan record types + serialization (`plan.py`, `marks.py`)

- `DimAssignment`, the four `Transform` records, `Substitution`, `ConstantDim`, `Plan`,
  `Reject`, `SweepPlan`, `PlanInputs`/`DimInfo`/`VarInfo`/`Pins`/`Prefs`,
  `POLICY_VERSION`; canonical JSON `to_json`/`from_json`; `MarkDecl` + the seed table +
  the panel-backend capability table.
- `PlanInputs.from_bench_result` (reads `bench_res.ds` and declaration metadata only).
- **Tests:** pickle round-trip; JSON round-trip is byte-stable and key-sorted; every
  record is frozen and hashable; `MarkDecl` with empty/unknown `target_kinds` raises at
  construction; `from_bench_result` on a real small sweep yields declaration-order
  dims, observed (not configured) `samples_per_point` counted across *all* time points
  via `result_is_missing`, and never touches `to_dataset`'s cache (assert
  `_to_dataset_cache` empty after extraction).
- **DoD:** grammar records import cleanly with no panel/holoviews import (keep the
  package light — it must be importable in the collect process; assert
  `sys.modules` free of `holoviews` after `import bencher.grammar` in a subprocess
  test, same technique as `test/test_render.py`).

### P3 — The planner (`planner.py`)

- Policy v1.1 steps 1–7 as named functions; budgets as named constants;
  `plan_result_var`, `plan_sweep`, `explain()`.
- **Tests:** one unit test per Law 7 step; the invariants list in D5 (each mapped to
  its finding numbers); determinism (repeat call + hypothesis property over generated
  `PlanInputs`); budget demote-then-reject chain including the `suggestions` payload;
  pins honored as hard constraints with unsatisfiable pins → `Reject` naming the
  conflicting pins (Law 6); `explain()` snapshot-tested on three canonical shapes
  (inline expected strings, `test_explain_selection.py` style).
- **DoD:** `grep -rn "override" bencher/grammar/` empty; planner is total over the
  corpus of P2's generated inputs (hypothesis finds no uncaught exception).

### P4 — Shadow harness, divergence ledger, golden corpus

- The instrumented recorder (D7), the three-tier corpus, the ledger, the golden files,
  the `update-golden-plans` task, and a `test/test_shadow_planner.py` +
  `test/test_golden_plans.py` pair.
- **Tests:** full-corpus agreement modulo ledger (both directions, D7); every ledger
  row cites a finding; golden byte-identity; `Reject` outcomes present in the corpus
  (budget overflow, unsatisfiable pins, hmap-only sweep).
- **DoD:** `pixi run generate-docs` diff-clean (zero visual change — the acceptance
  artifact for a phase that must not render anything differently); the plan-level DoD
  greps (§8) all pass; a PR comment records the final divergence count and its finding
  breakdown — that table is the input phase 3's visual diffs will be reviewed against.

## 6. OWNER DECISIONS

1. **Budget constants (P3).** Law 7 gives `Overlay ≤ 8`, facet level `≤ ~6`,
   `Tabs ≤ ~20`. Recommendation: pin exactly 8 / 6 / 20 as named constants inside
   `POLICY_VERSION = "1.1"`; tuning later is a policy bump with a golden diff — cheap
   and visible. The "~" must die here; a fuzzy budget cannot produce deterministic
   plans.
2. **Where kind→channel knowledge lives (P1).** Recommendation: derived in
   `bencher/grammar/channels.py` as a total function over `ResultKind` (D3), **not** a
   new `frame` field on `ResultSpec`. Rationale: plan 23's registry is the storage and
   classification contract; channel legality is grammar knowledge, versioned with
   `GRAMMAR_VERSION`, and the `assert_never` + completeness test give the same
   no-silent-link guarantee a spec field would. Alternative (spec field) recorded: it
   would put one more consumer inside `variables/results.py` and couple registry edits
   to grammar version bumps.
3. **`ResultVec` index-as-dim (deviation from A6 Law 7's invariant list).**
   Recommendation: defer the stored-shape change to phase 3 and plan per-expanded-column
   in phase 2 (D3). This is an explicit, recorded deviation: A6 says the vector index
   "becomes a real dim (kills #10)", but that is a collection-layer change to stored
   datasets with its own cache-safety story, and phase 2 is forbidden from touching
   stored data. The shadow ledger carries #10 as "deferred, not divergent".
4. **Golden corpus breadth (P4).** Recommendation: full generated-tree *shadow
   agreement* (cheap — planning is milliseconds) but byte-goldens only for a curated
   ~60-entry set (meta examples + finding shapes + reject cases), one JSON file per
   entry. Golden-diffing 200+ files on every policy tweak would train reviewers to
   rubber-stamp; 60 curated ones stay readable.
5. **Plan-at-collect wiring (Law 9).** Recommendation: phase 3 (§1 rationale — first
   consumer). If the owner wants plans persisted earlier for forward-compatibility of
   pickles, P4 can add the attribute write behind the same additive-`getattr` posture
   as PR #994; the recommendation stands against it (dead weight, second source of
   truth before any reader exists).
6. **Version literals (P1/P2).** Recommendation: `GRAMMAR_VERSION = "1"`,
   `POLICY_VERSION = "1.1"` (keeping A6's name for the audited policy). Strings, not
   ints — they end up in JSON and `explain()` output.

## 7. Cache safety

- **Law 9 layer 1 becomes enforceable now:** nothing plan-shaped enters any cache key.
  Phase 2 adds no field to any hashed class, so `hash_persistent()` is untouched by
  construction; the golden hash constants (`test/test_hash_persistent.py:741-743`)
  must not change, and **no `CACHE_VERSION` bump**. A new test pins the negative:
  `bencher/grammar` is imported by neither `bencher/identity.py` nor
  `bencher/worker_job.py` (grep-backed, §8), extending the `_hash_exclude` discipline
  of PRs #989/#994 exactly as Law 9 directs.
- **No stored-format change of any kind:** no dataset cell, sentinel, fill, blob, or
  history file is written differently. Phase 2 is additive modules + tests only. Old
  pickles are unaffected because nothing reads or writes a plan from a pickle yet
  (OWNER DECISION 5).
- **Read-path hygiene:** `PlanInputs.from_bench_result` reads `bench_res.ds` and
  declaration metadata; it must not call `to_dataset()`/`to_hv_dataset()` — the reduce
  cache they share is the one finding #12 shows being poisoned by an extra client, and
  the planner must not become the second histogram. Pinned by a P2 test.
- **Golden files are test fixtures, not cache artifacts** — they live in `test/`, ship
  in no wheel, and are exempt from `cache_management` accounting by location.
- **The shadow recorder is test-only monkeypatching**; it never runs in a user process,
  so it cannot perturb `_to_dataset_cache` semantics in production. (Inside the suite
  it *reads* real pathway behavior, which is the point.)

## 8. Definition of done (plan-level)

All four phases merged (or explicitly dropped with a note here), and:

- `pixi run ci` and `pixi run test-split` green on py311 and py313;
  `pixi run generate-docs` produces a byte-identical gallery (zero visual change).
- Every `bencher/grammar/*.py` file is on the strict `ty` override list;
  `type-assertion-failure` still never ignored (plan 23 P1 meta-test unchanged).
- The shadow suite passes with a fully-cited divergence ledger; the golden corpus is
  checked in with a working `update-golden-plans` task and a documented update
  procedure.
- Grep-level checks (each a line in a meta-test or the PR checklist):
  - `grep -rn "class Channel" bencher/` → exactly one definition; a test pins 9 members.
  - `grep -rn "GRAMMAR_VERSION\|POLICY_VERSION" bencher/` → one definition each, both
    in `bencher/grammar/`.
  - `grep -rln "bencher.grammar\|from .grammar\|from ..grammar" bencher/results/ bencher/plugins/ bencher/identity.py bencher/worker_job.py` → empty (no renderer wiring, no hash coupling).
  - `grep -rn "isinstance(.*Result" bencher/grammar/` → empty (all kind knowledge flows
    through `RESULT_SPECS`/`ResultKind`).
  - `grep -rn "override" bencher/grammar/` → empty (Law 7: no escape hatch).
  - `grep -rn "assert_never" bencher/grammar/` → non-empty, and no subject is a raw
    `param` attribute read (plan 24 A4's check, applied to the new package).
- Every A6 §6 finding number referenced by this plan appears in either a planner
  invariant test (P3) or a ledger row (P4) — a completeness assertion in the shadow
  suite, so a finding cannot fall between the two.

## 9. Deviations from A6 (recorded, per plans-README rule 7)

1. **§2.6's seven stale citations/claims** — line drift and count growth; A6's
   reasoning stands. This plan's §2 is the refreshed baseline for phases 3–5.
2. **`ResultVec` index-as-dim deferred to phase 3** (OWNER DECISION 3) — a stored-data
   change misfiled under planner invariants; deferring it is the conservative reading
   of "phase 2 is shadow-only".
3. **Backend capability tables scoped to panel/holoviews in phase 2** — Law 3's full
   table set arrives with the lowerings that can validate it (phases 3–4). The *type*
   ships now so the planner's fidelity-based backend choice has its final shape.
4. **Plan-at-collect deferred to phase 3** (OWNER DECISION 5) — Law 9 describes
   `collect()`'s end state; Law 10's phase list does not assign it, and this plan
   assigns it to the first phase with a consumer.
5. **Marks-open-via-entry-points deferred to phase 5** — Law 5 names the mechanism
   (`bencher.plot_plugins`, confirmed at `plugins/registry.py:14`); publishing it as a
   third-party promise belongs with the API phase, not the shadow phase.

## 10. Coordination

- **Plan 23 P3/P5–P12 (pending phases):** independent. P6 (`VarRange` constructors)
  overlaps phase *3*'s filter deletion, not this plan — whoever lands second rebases;
  P6 remains worthwhile because plugins keep `PlotFilter` for registry gating even
  after the planner owns shape decisions. P10's rerun fixes (C12) overlap phase 4;
  the divergence ledger notes any C12-adjacent disagreement as "legacy bug, fixed by
  phase 4" rather than shadowing the `0.0` fills.
- **Registry failure-pane unification (small, pre-phase-3):**
  `PluginRegistry.render`'s `_render_error_pane` (`plugins/registry.py:45-48`, used at
  `:310`) is a second failure pane that emits no `RenderFailedWarning`. It is currently
  unreachable from the report path (`to_auto` uses `select()` + its own
  `report_render_failure` handling), so it is not fixed here — recorded for phase 3,
  which rewrites that dispatch, to route it through `report_render_failure` or delete
  it.
- **A2:** this plan begins the supersession of S3–S4 that A6 declares; `explain()`
  (D5) is designed to absorb `explain_selection` in phase 3. Nothing in A2's landed
  S1/S2 is changed; the S1 signature fields (`has_time`, `time_steps`,
  `samples_per_point`) finally gain their consumer — as `PlanInputs`, recomputed
  correctly (§2.4 #12/#22) rather than read from `PltCntCfg`.
- **A5:** `Prefs` (D4) is the grammar-side successor of `pane_layout` and friends;
  where those knobs *live* remains A5's business. Phase 5's `View` API lands after A5's
  config-surface decisions or coordinates with them.
- **A3/A4:** golden-plan JSON is deliberately dumb (sorted-keys dataclass dumps), not a
  new manifest format — A3's netCDF-plus-manifest direction is unaffected.
- **A6 phases 3–5:** phase 3's plan doc should be written only after P4 here lands,
  against the final divergence ledger — the ledger is phase 3's review contract, the
  same way plan 23 §8 gated this plan on the P4 registry.
