# A6 — Grammar of ND Data

**Status:** Design accepted (owner-reviewed decision record, 2026-07-30). Supersedes the
selection mechanics of A2 phases S3–S4 and extends A1's "backends over plotters"
decision into a full unification. No implementation yet; phase 1 plan:
[plans/22-grammar-phase-1-data-model.md](../22-grammar-phase-1-data-model.md).
**Scope:** One unified slicing/plotting architecture for all result types and all
backends (holoviews/panel, plotly, video, rerun). Replaces the nine divergent rendering
pathways, three filter dialects, and four composition dialects with: a canonical
self-describing dataset, a declarative transform algebra, a frozen dimension→channel
`Plan`, and per-backend lowerings driven by capability tables.

Decisions below were resolved one-by-one in a design interview and are recorded as
**Laws** (owner-accepted, binding) with their alternatives and rationale. Two audits
ground them: an architectural map of the results/plotting system, and an empirical
audit of dimension-assignment rules (§6) that verified 24 edge cases.

---

## 1. The problem, precisely

Nine rendering pathways exist (hvplot numeric, hand-built hv elements, HoloMap
over-time, per-sample panes, base64 slider hack, rerun over-time grid, video
composition, plotly direct, rerun whole-sweep recorder). They diverge on exactly four
questions:

1. **Who consumes `over_time`** — pane recursion, hvplot groupby, rerun timeline, or
   nobody (plus an undocumented sixth mechanism: hvplot's implicit widget for any
   unassigned dim).
2. **Who decides layout** — `_to_panes_da` + `ComposableContainerPanel`,
   `ComposableContainerVideo`, plotly's scene, or `rrb.Blueprint` (with `RerunResult`
   containing two hand-synchronized copies of the same recursion).
3. **Where shape eligibility is decided** — a `PlotFilter` before recursion, nowhere
   (panes, rerun, table), or twice with different bounds (surface).
4. **What type→visual mapping looks like** — `ds_to_container`'s precedence chain,
   `_log_result_var`'s isinstance ladder, and `result_var_to_container`: three
   independent copies of the same knowledge.

Dimensionality eligibility is declared in three incompatible dialects: `VarRange`
counts, `result_types` tuples, and `target_dimension` recursion depth. Every divergence
is a *dimension-assignment* question, not a rendering question. The unifying object is
the thing all pathways implicitly compute and throw away: **an assignment of each
dataset dimension to a visual channel**.

The goal (owner's words): a grammar of ND data — make it easy to sample arbitrary
slices of ND functions, then easy to slice/compose that dataset afterwards via a set of
rendering backends, with a good default rendition and easy customisation of both
preprocessing and final display.

---

## 2. The Laws

### Law 1 — Canonical self-describing dataset

The canonical form is an xarray Dataset where every result variable carries a declared
`kind` (the existing `result_kind()` vocabulary) and **every non-numeric cell is a
content-addressed path into the cache store**, materialized at collect time. No
run-local indices.

- `ResultDataSet` payloads serialize at collect (parquet/netcdf under `cachedir`);
  the cell stores the path — generalizing the move PR #1007 made for rerun
  (`ComposableContainerRerun` materialized to one `.rrd` at collection). Kills the
  `isel(over_time=-1)` hack; dataset history becomes renderable.
- One missing-value discipline: NaN for numerics, `None`/empty for blob cells,
  `result_is_missing()` as the single oracle.
- `ResultReference` survives as the documented same-process escape hatch; nothing in
  the core algebra may depend on it.
- `ResultHmap` is deprecated and removed (the only type whose data lives outside the
  dataset; its use case is `ResultContainer` + a sample mark).

**Consequence:** "slice then render" is legal from any process on any slice after any
pickle round-trip — the precondition for everything below.

### Law 2 — Transforms are data ops; marks own statistical collapse

Rejected alternative: reduction as dataset preprocessing (today's `ReduceType` inside
`to_dataset`, `_std` suffix columns, the shadow-`PltCntCfg` swap, the hidden
`ResultBool` re-reduce). Accepted:

1. **Transforms** are pure `dataset → dataset` ops that change what data exists:
   `Select`, `Aggregate(dims, fn)`, `Subsample`, `Squeeze`. Named, frozen, picklable
   records; the chain is part of the plan.
2. **Marks declare dim consumption**, including statistical spread:
   `Line(spread=repeat)` → mean + band; `Box(spread=repeat)` → quartiles — computed at
   lowering time from the raw repeat dim, never baked into the canonical dataset.
   `ResultBool`'s binomial SE becomes the kind-based default stat in one place.
   `MINMAX` becomes `Spread(stat="minmax")`. Backends may memoize derived stats keyed
   on `(plan, dataset-hash)`; that cache is never canonical data.
3. **`over_time` stops being special**: an ordinary dim assigned to the `Time`
   channel. Five mechanisms become one channel with four lowerings.

### Law 3 — Backend capability tables; planner-owned fallback

Each backend exports a static capability table: per channel and per mark, fidelity
`native | approx | none`. The **planner** owns fallback via a documented substitution
chain (e.g. `Time → Tabs`), records substitutions in the plan (visible in `explain()`),
and uses total fidelity for backend selection when the user hasn't pinned one.
Backends are dumb translators. Rejected: backend-owned degradation (re-scatters the
knowledge) and hard rejection (hostile to the auto path).

### Law 4 — One composition algebra

`ComposeType.{right,down,sequence,overlay}` is a lossy four-way-ambiguous encoding of
the channel vocabulary (`sequence` means Tabs in panel/rerun but temporal concatenation
in video). Replaced by: **a `Compose` node = items + a layout channel**, with

- **two producers**: the planner (items from slicing a sweep dim) and the user directly
  (`compose([a, b, c], along="facet_col")` over any ad-hoc collection — inside
  `benchmark()`, or post-hoc). PR #1007's API becomes sugar over the same channels.
- **two evaluation modes**: `materialize` → a blob cell (webm, merged rrd, parquet;
  content-addressed per Law 1) and `view` → a live backend view. Which applies is a
  backend/medium property in the capability table, not a separate API.

Corollary: the grammar operates on **any conforming dataset** — a bencher sweep is one
producer of canonical datasets, not a privileged one.

### Law 5 — Closed channel vocabulary; open marks

Channels (closed, versioned): **`X, Y, Z, Overlay, FacetRow, FacetCol, Tabs, Time,
Spread`**. Nothing else; anything not a dimension assignment is mark styling.

- **`Overlay`** (owner-specified semantic): render items at the same canonical position,
  alpha-composited (default opacity 1/N, user knob). Legal only where a shared
  coordinate frame exists — axes for numeric marks, pixel extents for image/video,
  entity space for rerun; the planner checks the frame and falls back to `FacetCol`
  otherwise. `Color` is the plotting-backend styling parameter of `Overlay`, not a
  channel.
- Rejected channel candidates: `Style/Dash` (second overlay dim), `Animation`
  (distinct from `Time`), user-visible `EntityPath` (a rerun lowering detail).
- **Marks are open**, registered via the existing plugin registry (entry points group
  `bencher.plot_plugins`). A mark declares: accepted channels, targeted `result_kind`s,
  per-backend lowerings. Nobody adds channels without a grammar version bump.
- **Multiple result vars**: one plan per result var, composed by an outer layout node
  using the same channels — report structure and within-plot structure are one algebra.
  Multi-target marks (xy scatter) declare two target slots.

### Law 6 — Partial constraints; deterministic completion

A plot request is a **partial constraint set** the planner completes: `view()` with no
pins is the auto default; any subset of channel/mark/backend/transform pins is honored
as hard constraints; jointly unsatisfiable pins fail loudly with `explain()`.
**Determinism law:** same canonical dataset shape + same pins + same planner policy
version ⇒ byte-identical plan. The default policy is versioned and documented; policy
changes are visible versioned events (plans record the policy version). Golden-plan
files in CI turn "did auto-deduction change?" into a reviewed diff.

### Law 7 — Default assignment policy v1.1

Grounded in the §6 audit. What the current system gets right and keeps: **declaration
order is the priority gradient** — canonical dim order is `input_vars` declaration
order, then `repeat`, then `over_time`; earliest-declared dims sit closest to the data
(axes/overlay), last-declared dims become the outermost grouping.

For a post-transform dataset, in order:

1. `repeat` → `Spread` if the mark accepts it, else `Aggregate(mean)`. Never
   positional (today it is peeled as an outer facet whenever it survives — audit #5).
2. Time dims with >1 **observed** points → `Time`; size-1 time dims are absent for
   planning, coordinate kept as provenance (audit #15).
3. Floats in declaration order → `X`, `Y` (`Z` only when a 3D mark/backend is in
   play); leftovers join the facet pool. Int-ness recorded as discreteness metadata
   (annotation only in v1; audit #19).
4. First-declared cat with ≤ 8 levels → `Overlay` for numeric marks; blobs skip
   (Law 5 frame check).
5. Remaining dims → facet pool, nested **last-declared outermost** (current
   panel/rerun behavior; video is *changed* to conform — its current order is a
   verified bug, audit #20/#21). Assigned `FacetCol`, `FacetRow`, `Tabs` per level,
   honoring the grid/tabs preference knob (successor of `pane_layout`).
6. **Cardinality budgets with demote-then-reject**: `Overlay` ≤ 8 → facet level ≤ ~6 →
   `Tabs` ≤ ~20 → reject with an explanation suggesting an `Aggregate`/`Subsample`
   transform. The planner never invents a data transformation the user didn't ask for.
   (Today: zero guards; a 30-level StringSweep produces 30 legend entries, and curve's
   overlay takes a Cartesian product across all groupby dims — audit #7/#9.)
7. Mark by residual shape × `result_kind`; backend by fidelity (Law 3). Repeat
   thresholds preserved (line at observed samples == 1; curve/box/violin at ≥ 2),
   gated on **observed** `samples_per_point`, not configured `repeats` (audit #23).

Planner invariants (each kills a verified bug class — see §6):
- Plans bind to the **post-transform shape**; a squeezed dim is a constant annotation,
  never an axis (kills #1/#2/#3/#17).
- Every dim has exactly one channel owner; an unassigned leaf dim is a planner error,
  not an implicit hvplot widget (kills #24).
- Selection returns typed `Match | Reject(reason)`; no `override=True` escape hatch —
  a direct call requests a pinned plan and gets a typed error on shape mismatch
  (kills #4/#5).
- Reduction decided once per (mark, result var) in the plan; views are pure functions
  of a dataset; caches keyed on dataset identity (kills #12/#13).
- Type gates over `result_kind` strings; an unmatchable gate is a construction-time
  error (kills #11); `ResultVec`'s index becomes a real dim (kills #10).
- Layout orientation is a function of facet depth alone, never data-variable count
  (kills #8). One ordering rule (declaration); the alphabetical `hmap_kdims` sort dies
  with `ResultHmap` (kills #14).

### Law 8 — API surface: four entry points, one `Plan`

```python
# 1. Zero-API default — unchanged
bench.plot_sweep(...)

# 2. Pinning — lazy View, string kwargs; typed objects accepted in the same slots
res.view()                                      # planner's choice
res.view(mark="box")                            # pin mark
res.view(x="voltage", overlay="algo")           # pin channels by dim name
res.view(agg="mean over lidar_id", tabs="scenario", backend="rerun")
# View = frozen plan + dataset ref; .show(), .save(path), .explain(), .plan

# 3. Declarative pre-run — frozen, picklable, rides BenchCfg through the split
bench.plot_sweep(..., views=[View(mark="curve"), View(mark="box", tabs="algo")])

# 4. Ad-hoc composition — Law 4, no sweep required
bn.compose([img_a, img_b, img_c], along="facet_col").show()
bn.compose(recordings, along="overlay", opacity=0.3).materialize("out.rrd")
```

Commitments: dims addressed by name, channels are the parameter names (reserved words,
acceptable because the vocabulary is closed); **`View` supersedes both
`bench.add(ResultClass, ...)` and `plot_callbacks`**, which become deprecated shims
constructing `View`s internally. Operator sugar (`/`, `|`) deferred to v2.
Natural join with plan 18: `SweepSpec` composes the sweep declaration, `views=` the
rendition declaration; both frozen and diffable (`diff_specs` extends to plans).

### Law 9 — Plan at collect, stored, never a lock

`collect()` = sample + materialize blobs (Law 1) + **plan** + pickle — still zero
render objects, so the segfault-avoidance property of the split is untouched. The
stored plans make re-rendering an old pickle pixel-stable regardless of planner
evolution; `replan=True` (API and render-CLI flag) recomputes with current policy.
A stored plan is validated against the dataset at render; on mismatch, fall back to
replanning with a logged notice (same defensive posture as the `getattr`-for-old-
pickles pattern in PR #994). Live `res.view(...)` always plans fresh.

**Collect once, re-render forever** — the three layers:
1. The sample cache is untouched; **nothing in a `Plan`/`View` ever enters a cache
   key** (extends the `_hash_exclude` discipline of PRs #989/#994 into a law).
2. The pickled result is renderable from any process (Law 1).
3. Stored plans are only the defaults; new pins always win, no re-collection.

### Law 10 — Migration: five-phase strangler, stacked PRs, hard cutover

Shipped as a five-PR stack, reviewed/merged bottom-up (the #1010–#1014 discipline):
each phase its own plan doc + implementation, independently CI-green.

1. **Data model** (Law 1). Pure data-layer, no visual changes.
2. **`Plan` type + planner in shadow mode**: runs alongside existing filters,
   asserting agreement across the whole gallery, modulo the 24 documented findings —
   each divergence recorded as an intended, reviewed exception. Golden-plan corpus is
   born here, before any renderer changes.
3. **Panel/holoviews lowered end-to-end**: `_to_panes_da` + `map_plot_panes` rewritten
   as plan execution; marks migrate one at a time behind the registry (name-keyed
   replacement is its documented override mechanism); `to_auto` flips to the planner;
   old filters become assertions, then die.
4. **Rerun and video backends** as lowerings — the two hand-synced rerun recursions
   and the video peel-order bug are deleted, not fixed.
5. **API surface** (Law 8) + shims + docs rewrite. Last, because it's the public
   promise and everything under it must already be true.

**Hard cutover per phase; no runtime legacy flag** (two-brains maintenance is the
`BENCHER_FORCE_SPLIT_RENDER` cost times every pathway). Shadow mode exists only inside
phase 2's test suite. **The acceptance artifact is the regenerated gallery: each
phase's PR includes before/after generated docs for owner visual review**, every diff
traceable to a numbered §6 finding. Exception: phase-5 API shims get a normal
deprecation cycle with warnings — API compatibility and rendering compatibility are
different promises.

---

## 3. Rerun parity (the motivating question)

Under this design, parity stops being undefined and becomes a capability-table
checklist. Both rerun recursions derive from the plan: the channel assignment *is* the
entity-path tree and *is* the Blueprint layout.

| Plan concept | holoviews lowering | rerun lowering | status |
|---|---|---|---|
| `X` + line mark | hvplot line | `SeriesLines` on a timeline | native |
| `Overlay` | hv Overlay + legend | sibling entity paths, shared view | native |
| `FacetRow/Col/Tabs` | nested Row/Column/Tabs | `rrb.Vertical/Horizontal/Tabs` | native |
| `Time` | HoloMap slider | **a named timeline per Time dim** — removes today's "over_time and a float sweep compete for `log_tick`" conflict | native |
| heatmap/volume marks | hvplot / plotly | `rr.Tensor` views | native/approx |
| image/video kinds | panes | `EncodedImage` / `AssetVideo` | native |
| `Spread(mean_std)` | `hv.Spread` band | no native band view: three series (mean, mean±std), or `Spread→Overlay` fallback | **declared gap** |
| box/violin marks | hv box/violin | fallback: jittered points or facet | **declared gap** |

Gaps are declared fallbacks visible in `explain()`, upgraded by a one-cell change when
rerun ships the missing view. Out of scope for the grammar (transport problems, keep on
a separate list): iframe embedding fragility (`inline_rrd_iframes` regex), the
`cachedir/rrd/` serving constraint, post-render opacity of `.rrd` files.

---

## 4. Feature-parity audit (migration checklist)

Everything maps; four items need explicit homes; one deliberate loss.

| Current feature | Home |
|---|---|
| All 16 chart types | Marks with capability-table lowerings |
| Auto-plot deduction | Planner (same inputs, inspectable output) |
| Five `over_time` mechanisms | `Time` channel, four lowerings; "Per Time Point / All Time Points" tabs pair becomes holoviews' native `Time` lowering |
| `ReduceType`, bool binomial SE, MINMAX | `Spread` + `Squeeze` transform (Law 2) |
| `aggregate=`, subsampling, levels | Transforms — picklable, in `explain()` |
| `pane_layout` | Planner preference knob (facet-vs-tabs chain order) |
| Declared containers (PRs #989/#994/#1007) | Per-result-var **sample mark**; precedence chain survives as mark resolution order |
| Worker-side composable containers | Law 4 `Compose` (materialize mode) — same vocabulary as render-side |
| `share_axis`, plot_size, depth colors, label widths | Backend lowering details |
| `bench.add`, `plot_list`/`remove_plots`, backend pin | `View` construction / planner filters over the registry |
| `explain_selection` | Planner `explain()` — strictly richer |
| Collect/render split, caching, sweep summary, regression overlays, optuna, `extra_panels` | Report layer — `to_auto_plots`'s hardcoded sequence becomes a default report recipe composed of plans + non-plan panels |

Explicit homes: (1) **tap/linked plots** — kept as named opt-in marks; principled
`LinkedViews` deferred to grammar v2; (2) **`plot_callbacks` with live callables** —
legacy escape hatch, same-process tier, own deprecation schedule; (3) **explorer,
latex, sparkline, scorecard** — named-only marks / report panels; (4) **deprecated
scatter + unfiltered table** — folded into the mark set with real declarations.
Deliberate loss: **`ResultHmap`** (Law 1).

---

## 5. Current dimension-assignment rules (empirical baseline)

Verified against source and by executing hand-built results. Canonical dim order:
`input_vars` declaration order + `repeat` (+ `over_time`); nothing reorders it except
`hmap_kdims = sorted(...)` (`bencher.py:1059`, legacy hmap path only).
`SampleOrder.REVERSED` permutes traversal only, never dims.

Effective policy for the main numeric pathway (`target_dimension=2`): `over_time` (>1)
→ slider; remaining dims peeled `pane_dims[-1]` first, so **last-declared = outermost
facet** (vertical, label left), innermost facet level horizontal (label above); leaf
gets first-declared dims: x = `float_vars[0]` (classification) or `non_time_dims[0]`
(position — bar/band), overlay = `cat_vars[0]`. Panes/video/dataset use
`target_dimension=0` (every dim a nesting level); box/violin use `cat_cnt+1`; band
never recurses. Video reverses only its outermost level (bug); rerun peels
`cat_dims[-1]` → entity branches, then floats to ≤3, leaf by shape (0D scalars / 1-cat
BarChart / 1-float timeline / 2–3D tensor). Full tables with file:line evidence live in
the audit transcript; the durable outputs are the Law 7 policy and the findings below.

## 6. The 24 verified findings and their dispositions

Each phase-3/4 visual diff must cite one of these. (V) = verified by execution.

1. Two rival role sources — classification (`plt_cnt_cfg.float_vars`) vs leaf position
   (`dims[0]`/`dims[-1]`) — can name different dims. → One plan, bound to the actual
   leaf dataset.
2. (V) Interleaved declaration `[f1, c1, f2]` breaks heatmap/surface: `_pick_xy_axes`
   picks a dim the peel already removed → 1-row heatmap + spurious dropdown. → Plans
   bind post-transform.
3. (V) 1-sample float dim + `squeeze(drop=True)` → hard `DataError`, swallowed by
   `to_auto`'s broad except. → Squeezed dim = constant annotation.
4. (V) bar's two-scenario loop returns the rejection Markdown as the plot when
   `print_debug=True`. → Typed `Match | Reject`.
5. `override=True` default on every direct `to_*()` bypasses all shape guards. →
   No escape hatch; pinned plan + typed error.
6. (V) Surviving `repeat` is peeled as outermost facet (line/bar under override,
   video with repeats>1). → `repeat` has a reserved role, never positional.
7. Distribution's `target_dimension = cat_cnt + 1` hard-codes "the extra dim is
   repeat"; one stray float destroys the distribution. → Leaf contract = named dim
   set, not arity.
8. (V) `horizontal` computed from hv dim count (kdims **+ data vars**) at top level vs
   xarray dim count in recursion — adding a `_std` var or second result var flips
   report orientation. → Orientation = f(facet depth).
9. No cardinality guard anywhere; curve overlay takes a Cartesian product over all
   groupby dims. → Law 7 budgets.
10. `plt_cnt_cfg.vector_len`/`.result_vars` permanently 1 (dead filter axes);
    `ResultVec` unrenderable. → Delete axes; vector index becomes a dim.
11. `ScatterResult` gates on deprecated `ResultVar` subclass — can never fire. →
    Gates over `result_kind`; unmatchable gate = construction error.
12. (V) Histogram's over_time snapshot aliases the parent's `_to_dataset_cache`: its
    `isel(over_time=-1)` is discarded, and it poisons the `NONE` entry for band. →
    Pure views; dataset-keyed caches.
13. Hidden `ResultBool` re-reduce inside `map_plot_panes` overrides `reduce=NONE`
    plots; bool box-plots degenerate. → Reduction decided once, in the plan.
14. `hmap_kdims` alphabetically sorted; everything else declaration order. → One rule;
    dies with `ResultHmap`.
15. (V) Size-1 `over_time` leaks as a one-option dropdown or redundant facet on every
    first over_time run. → Size-1 time = absent for planning.
16. Histogram declares `cat_range=(0,None)` but `input_range=(0,0)` — self-
    contradictory filter. → Contradictions unrepresentable in mark declarations.
17. Surface filters twice, inner check against pre-peel shape → facet trees of empty
    debug panes at 3 floats. → One filter, post-peel.
18. Volume indexes `input_vars[0..2]` positionally; `VarRange(-1, 0)` bound. → Roles
    by name; non-negative bounds by construction.
19. `IntSweep` fully conflated with `FloatSweep`. → Keep merged for axes; record
    discreteness in the plan (annotation only in v1).
20. (V) video_summary's `reverse` not propagated into recursion → actual peel order
    `first, last, second-to-last, …`. → Ordered peel list computed once in the plan.
21. (V) Three pathways nest the same `[c1, c2]` differently (panel `c2⊃c1`, video
    `c1⊃c2`, rerun `c2⊃c1`). → Single ordered `(dim, channel)` list, all backends.
22. `has_time`, `time_steps`, `samples_per_point` computed but read by nothing. →
    Planner inputs (Law 7) or deleted.
23. Repeats gating uses configured `repeats`, not observed samples — `repeats=3` with
    one valid sample still selects curve/box over line. → Gate on
    `samples_per_point`.
24. (V) hvplot's implicit groupby widget renders any unassigned leaf dim as a
    dropdown — an unplanned sixth mechanism. → Unassigned dim = planner error.

---

## 7. Deferred (explicitly v2, not forgotten)

- `LinkedViews` (principled tap/linked interactivity across plans).
- Operator sugar (`view_a / view_b`, `|`).
- Discreteness-aware mark preference for small integer axes (metadata recorded in v1).
- Any new channel (requires a grammar version bump by Law 5).
