# Research: what can `rerun.blueprint.DataframeView` display, and what must bencher log to get a table?

Resolves [#1105](https://github.com/blooop/bencher/issues/1105) (child of the rerun-native
report map [#1103](https://github.com/blooop/bencher/issues/1103)).

- **Researched against:** `rerun-sdk` / `rerun-cli` **0.35.0** as installed in this repo's pixi
  env (`.pixi/envs/default`), plus rerun's own docs, `rerun-io/rerun` source at tag `0.35.0`,
  and the GitHub release notes.
- **Bencher tree:** `main` @ `98503c84` (v1.119.0).
- **Evidence classes used below:** **VERIFIED** = I ran it in this repo's pixi env and observed
  the result (SDK introspection, a saved `.rrd`, or a real viewer screenshot rendered headlessly
  via `rerun --screenshot-to`). **DOCUMENTED** = a primary source says so but I did not
  independently execute it. **UNKNOWN** = not established; do not rely on it.

Version banner reproduced by `pixi run python -c "import rerun; print(rerun.__version__)"`
→ `0.35.0`; `rerun-cli 0.35.0 … prepare-release-0.35.0 bb8284e, built 2026-07-23`.

---

## TL;DR

1. **`DataframeView` is a query view, not a table sink.** You cannot hand it a table. It renders
   the result of a query over entities/components **already logged into the recording**.
2. **A timeline is mandatory.** A purely static (non-temporal) recording renders an **"Unknown
   timeline"** error panel and **zero rows** — VERIFIED. Bencher's Cartesian sweeps are not
   temporal, so bencher must **synthesise a row-index timeline**.
3. **With a synthesised row index it works, today, in 0.35.0.** A real bencher 4x3x2 sweep
   renders as a usable 24-row table — VERIFIED by screenshot.
4. **Nothing needed is above the `<=0.35.0` pin.** 0.35.0 *is* the newest rerun release
   (2026-07-23). The last DataframeView features (`entity_order`, `auto_scroll`) landed in
   **0.30.0**, below the pin's `>=0.32.0` floor. The pin costs nothing.
5. **The sharp edges are cosmetic-but-real:** no column renaming, no sorting at all, no
   units/precision control, and column order is only controllable at *entity-group* granularity.
   Everything is still marked **unstable** by rerun.

---

## 1. Query view, or arbitrary table? — a query view. (ticket bullet 1)

**DOCUMENTED.** The view's own reference page says it displays "any data in a tabular form … Any
data from the store can be shown, using a flexible, user-configurable query", and under
*Visualized archetypes*: "Any data can be displayed by the Dataframe view."
<https://rerun.io/docs/reference/types/views/dataframe_view>

**DOCUMENTED (source).** The viewer builds a `QueryExpression` against the *recording's* storage
engine, with the column set derived from the view's entity-path contents —
`crates/viewer/re_view_dataframe/src/view_class.rs` @ tag 0.35.0:

```rust
let query_engine = QueryEngine { engine: ctx.recording().storage_engine_arc() };
let query_results = ctx.lookup_query_result(query.view_id);
let view_contents = query_results.tree.iter_data_results()
    .map(|data_result| (data_result.entity_path.clone(), None)).collect();
```

The in-app help string is blunt: *"This view displays **entity content** in a tabular form."*
<https://raw.githubusercontent.com/rerun-io/rerun/0.35.0/crates/viewer/re_view_dataframe/src/view_class.rs>

**DOCUMENTED.** The row/column model —
<https://rerun.io/docs/concepts/query-and-transform/dataframe-queries>:

> "A row is produced for each distinct index (or timeline) value for which there is at least one
> value in the filtered content."

Columns are one per `(entity_path, component)` pair in the view contents. Column *identity* is
therefore the pair — there is no free-floating "column name" concept.

**VERIFIED — the blueprint really is just these seven knobs.** `DataframeQuery` in the installed
SDK has exactly `timeline`, `filter_by_range`, `filter_is_not_null`, `apply_latest_at`, `select`,
`entity_order`, `auto_scroll`
(`.pixi/envs/default/lib/python3.13/site-packages/rerun_sdk/rerun/blueprint/archetypes/dataframe_query.py`).
Nothing accepts a dataframe.

### There *is* an arbitrary-table API — but it is a different feature

**VERIFIED.** `rerun.experimental.ViewerClient` exists in 0.35.0 with a `send_table` method:

```
ViewerClient methods: ['close', 'connect', 'save_screenshot', 'send_table', 'spawn', 'url']
send_table: "Send a table to the viewer. A table is represented as a dataframe defined by an
Arrow record batch." … "The table name serves as an identifier."
```

**DOCUMENTED.** Rerun explicitly separates the two — 0.23.0 release notes:
"Please note that this is distinct from our current `send_dataframe` API and dataframe query
view." <https://github.com/rerun-io/rerun/releases/tag/0.23.0>

**DOCUMENTED limitations** that disqualify it for the #1103 destination (a single saved `.rrd`) —
<https://raw.githubusercontent.com/rerun-io/rerun/0.35.0/docs/content/howto/logging-and-ingestion/send-table.md>:

> - Only a single record batch is supported per table
> - **Tables can't be saved/loaded from files yet (unlike `.rrd` files for recordings)**
> - Integration with the rest of the Rerun API is still in progress
> - The API may undergo significant changes as we iterate based on user feedback

**Consequence for #1103:** `send_table` requires a *live viewer connection* and cannot be
persisted into the report `.rrd`. For a saved single-window report, `DataframeView` is the only
option. (It does get interactive filtering that `DataframeView` lacks — see §4.)

---

## 2. Index/timeline columns, `latest_at` vs `range`, and the non-temporal case (ticket bullet 2)

### 2a. How the index is chosen

**VERIFIED (SDK docstring).** `timeline`: *"The timeline for this query. If unset, the timeline
currently active on the time panel is used."*

**DOCUMENTED (source).** The viewer resolves the name against the recording's timelines and
**hard-fails to an error panel** if absent — `view_class.rs` @0.35.0:

```rust
let timeline = view_query.timeline(ctx)?;
let Some(timeline) = timeline else {
    timeline_not_found_ui(ctx, ui, query.view_id);
    return Ok(());
};
```

There is **no code path in the view** that issues `filtered_index: None` (the static-only mode).

### 2b. `latest_at` vs `range` — precise row/cell semantics

Mapping from blueprint field to the store's `QueryExpression`
(`crates/store/re_chunk_store/src/dataframe.rs` @0.35.0). The mental model, verbatim:

> The filters filter out _rows_ of data from the view contents. **A filter cannot possibly
> introduce new rows, it can only remove existing ones**. … The selection applies last and
> samples _columns_.
> `SELECT <selection> FROM <view_contents> WHERE <filtered_*>`

| Blueprint field | Affects | Semantics |
|---|---|---|
| `timeline` | **rows** | Row per distinct index value with ≥1 non-null column. "If left unspecified, the results will only contain static data." |
| `filter_by_range` | **rows** | Keeps rows whose index is within `[start, end]` — **`end` inclusive** ([docs.rs `FilterByRange` 0.35.0](https://docs.rs/rerun/0.35.0/rerun/blueprint/datatypes/struct.FilterByRange.html)). Blueprint note: "will be unset as soon as `timeline` is changed." |
| `filter_is_not_null` | **rows** | Keeps only rows where the named component column is non-null. |
| `apply_latest_at` | **cells only** | `SparseFillStrategy::LatestAtGlobal` vs `None`. Never changes the row set. |

**Critical caveat, DOCUMENTED**, for `apply_latest_at=True` (`dataframe.rs` @0.35.0):

> "Fill null values using global-scope latest-at semantics. The latest-at semantics are applied
> on the **entire dataset** as opposed to just the current view contents: **it is possible to end
> up with values from outside the view!**"

**VERIFIED empirically — all three, side by side in one screenshot.** Logged a 6-row sequence on
timeline `row` where `dense` was logged every row and `sparse` only at rows 0 and 3:

| view config | rendered rows | `sparse` column |
|---|---|---|
| `apply_latest_at=False` (default) | 6 rows (#0–#5) | `0`, `-`, `-`, `30`, `-`, `-` (nulls shown as `-`) |
| `apply_latest_at=True` | 6 rows (#0–#5) | `0, 0, 0, 30, 30, 30` (forward-filled) |
| `filter_is_not_null="/sp:sparse"` | **2 rows (#0, #3 only)** | `0`, `30` |

This confirms exactly the documented split: `apply_latest_at` fills cells, `filter_is_not_null`
removes rows.

**DOCUMENTED — deliberately *not* wired up in the view** (`view_class.rs`, comment typo theirs):

```rust
// not yet unsupported by the dataframe view
filtered_index_values: None,
using_index_values: None,
```

So **no resampling and no explicit index-value list** from a blueprint. Those exist only in the
programmatic catalog SDK.

**UNKNOWN:** whether latest-at fill is applied before or after the not-null row filter. No source
states the ordering.

### 2c. Can a NON-TEMPORAL sweep be tabled? — **No. This is the crux.**

**VERIFIED — the decisive experiment.** I logged a 6-row bencher-shaped table as purely static
(`rr.send_dataframe(table, index=None)`), attached a `DataframeView`, saved the `.rrd`, and
rendered it in the real viewer headlessly. The view shows:

> ⚠ **Unknown timeline**
> "The timeline currently configured for this view does not exist in the current recording.
> Select another timeline in the view properties found in the selection panel."

**No table. Zero rows.** The data is definitely in the store — the same file reports
`/sweep rows=6 static=True timelines=[] cols=['cat','energy','x']` — but with **zero timelines**
the view has no index to generate rows from.

**DOCUMENTED — rerun says the same thing** (<https://rerun.io/docs/concepts/query-and-transform/dataframe-queries>):

> "The consequence of this is that **static data cannot, by itself, generate rows.** However, for
> rows that are generated by other (temporal) data, static data will show up in their respective
> columns provided they are part of the filtered content."

The single-row static escape (`dataset.reader(index=None)`) is a **catalog-SDK-only** capability
and is not expressible in a blueprint (§2a).

**Is there a fallback index?** Two near-misses, both unusable:

- **`RowID`** is a selectable *column* in the view's Columns list, but does **not** drive rows
  (DOCUMENTED, `view_query/ui.rs` @0.35.0).
- **`log_time`/`log_tick`** are auto-created (`log_time` on by default) — but their granularity is
  **per `rr.log` call**. VERIFIED: `rr.log("/sweep", rr.AnyValues(...))` in a loop yields
  `timelines=['log_time','row']`. So if you log a sweep sample's columns in N separate `rr.log`
  calls, you get **N different rows**, not one. They cannot serve as a sample index.

**⇒ Bencher must synthesise an explicit row index.** One sweep sample = one index value = one
table row.

---

## 3. Does a bencher N-D dataset work? — **Yes, VERIFIED end to end**

**VERIFIED.** I ran a real bencher sweep (`bch.ParametrizedSweep`, 3 input vars 4x3x2, result
vars `energy: ResultVar(units="J")` and `ok: ResultBool`), took `res.to_dataset()`, and bridged it:

```python
df = ds.to_dataframe().reset_index()      # N-D xarray -> flat table; 24 rows
cols = {"row": pa.array(range(len(df)), pa.int64())}
for c in df.columns:
    cols[f"/sweep:{c}"] = pa.array(df[c].astype(str) if df[c].dtype == object else df[c])
rr.send_dataframe(pa.table(cols), index="row")   # "row" becomes a sequence timeline
rr.send_blueprint(rrb.Blueprint(rrb.DataframeView(origin="/sweep",
    query=rrb.archetypes.DataframeQuery(timeline="row"))))
```

Observed dataset: `dims {'theta': 4, 'offset': 3, 'mode': 2}`, `data_vars ['energy','ok']`,
`coords ['theta','offset','mode']` → flattened to **24 rows x 5 cols**. The viewer screenshot
shows all 24 rows correctly populated. **`xarray.Dataset.to_dataframe().reset_index()` is the
whole bridge** — the Cartesian product is already the row set.

Three warts VERIFIED in that screenshot:

1. **Columns came out alphabetical — inputs and results interleaved**: `row | energy | mode |
   offset | ok | theta`. Unreadable for a report. Fix: log inputs and results to *separate
   entities* and use `entity_order` (§4).
2. **Full float precision with digit grouping**: `0.865 759 839 492 344`. No precision control.
3. **`ok` renders as `0`/`1`, not `true`/`false`** — because bencher's xarray stores `ResultBool`
   as float. That is a bencher-side coercion, not a rerun limitation (a genuine
   `pa.bool_()` column VERIFIED renders as `true`/`false`).

### The logging shapes, compared (VERIFIED)

| shape | resulting columns | verdict |
|---|---|---|
| `rr.send_dataframe(tbl, index="row")` with `"/ent:name"` column names | one clean column per name, no archetype tier | **best** — one call, whole table |
| `rr.log(ent, rr.AnyValues(a=…, b=…))` per row | one clean column per kwarg | good; per-row, adds `log_time` |
| `rr.log(ent, rr.Scalars(v))` one entity per column | header tier `Scalars` / `scalars` | verbose headers |
| a full archetype, e.g. `rr.Image(img)` | **explodes into several columns** (`buffer`, `format`) | pollutes the table |

**VERIFIED — the column-name convention** that makes `send_dataframe` work (from
`Chunk.from_record_batch` docstring): "if the name starts with `/` and contains a `:`, the first
part of the column name is interpreted as the entity path and the rest as the component
identifier."

**VERIFIED — `send_dataframe` forces you to be explicit about temporality:**

```
ValueError: The record batch carries no index column, so it cannot be unambiguously interpreted
as temporal or static. Pass `index=<column>` for temporal data or `index=None` for static data.
```

`index="row"` on an `int64` column creates a **sequence** timeline (VERIFIED:
`Index(timeline:row)`, `/sweep rows=6 static=False timelines=['row']`). Per the docstring, time
type follows Arrow dtype: `int64` → sequence, `timestamp(ns)` → timestamp, `duration(ns)` →
duration.

**DOCUMENTED caveat if you use `send_columns` instead:** "`send_columns` does **NOT** add any
other timelines to the data. Neither the built-in timelines `log_time` and `log_tick`, nor any
user timelines." — which is actually what you want here.

### What exotic bencher result types look like in a cell (VERIFIED)

Rendered a recording with an image, tensor, markdown doc, multi-value scalar and plain values:

| logged | cell renders as |
|---|---|
| `rr.Image(8x8x3)` | raw bytes `[162, 68, 10, 4, 207, 232, …]` + separate `format` col `RGB U8 8×8` — **no thumbnail** |
| `rr.Tensor(2x3)` | `float32, 2×3` — a shape summary, **not the data** |
| `rr.TextDocument("# md", text/markdown)` | raw quoted string `"# md 0"` — **markdown not rendered** |
| `rr.Scalars([a,b,c])` (multi-value) | `3 instances` — **values not shown** |
| `rr.AnyValues(label=…, n=…)` | clean `"row-0"` / `0` — **the good case** |

**⇒ `DataframeView` is for scalar/string/bool cells only.** `ResultImage` / `ResultVideo` /
`ResultPath` cannot be previewed in a table cell; they need their own spatial/tensor views. Header
structure is **three tiers**: entity path → archetype → field name.

---

## 4. Column selection, ordering, naming, sorting, units (ticket bullet 3)

### Expressible

- **Column visibility — YES.** VERIFIED: `select=["/s:c","/s:a"]` on a 4-column entity rendered
  only `a` and `c`; `b` and `d` were gone.
- **Entity-group order — YES.** VERIFIED: `entity_order=["/results","/inputs"]` put the
  `/results` group (`energy`, `ok`) *before* the `/inputs` group (`cat`, `x`). SDK docstring:
  "This affects the order of component columns, which are always grouped by entity path.
  **Timeline columns always come first.** Entities not listed here are appended at the end."
- **Row filtering by index range / not-null — YES.** §2b.
- **Units, by smuggling them into the component identifier — YES (workaround).** VERIFIED:
  columns named `/sweep:energy [J]` and `/sweep:duration (ms)` render verbatim as headers
  `energy [J]` and `duration (ms)`. Spaces, brackets and parens are all accepted. Caveat: that
  string *becomes* the component identifier, so any `select` / `filter_is_not_null` spec must use
  the identical string.

### NOT expressible

- **❌ Rename a column header.** VERIFIED: no `rename`/`unit`/`precision`/`sort` component exists
  anywhere under `rerun/blueprint/{components,datatypes,archetypes}` (grepped the installed SDK —
  the only hits are unrelated: `grid_spacing`, `line_grid3d`, `near_clip_plane`, `view_contents`).
  `SelectedColumns` carries only `time_columns` and `component_columns`, and
  `ComponentColumnSelector` only `entity_path` + `component` — no display-name field.
  DOCUMENTED: headers are derived mechanically from `archetype_field_name()` in
  `dataframe_ui.rs` @0.35.0. **The component identifier IS the header** — hence the units
  workaround above.
- **❌ Arbitrary column order.** VERIFIED, and this is the one that will bite: `select` is a
  **set, not a permutation**. I passed `select=["row","/sweep:energy","/sweep:x","/sweep:cat"]`
  and the viewer rendered **`row | cat | energy | x`** — alphabetical, select order ignored.
  Reproduced twice (`select=["/s:c","/s:a"]` → rendered `a` then `c`). DOCUMENTED confirmation in
  `view_query/blueprint.rs` @0.35.0: `// Step 1: Reorder columns by entity if an order is set,
  otherwise keep as-is. // Step 2: Apply column visibility.` — order is entity-granular, `select`
  is only visibility.
- **❌ Hide the index column.** VERIFIED: `select=["/s:c","/s:a"]` (no time column) still rendered
  `row` as the first column. DOCUMENTED: the selection panel string is *"The query timeline must
  always be visible"*.
- **❌ Sorting — neither blueprint nor interactive.** No sort field in `DataframeQuery`
  (VERIFIED), no sort in `QueryExpression` (DOCUMENTED). Rows always come out in index order.
  DOCUMENTED, 0.25.0 release notes: "We are busy working on a powerful filtering feature for our
  arrow dataframe widget used for tables (sent with `ViewerClient.send_table()`) … **(Note that
  the text log views and dataframe views are using a different widget which does not support
  filtering.)**" <https://github.com/rerun-io/rerun/releases/tag/0.25.0>
- **❌ Units / display precision as first-class fields.** No component exists (VERIFIED above).
- **❌ Client-side validation of any of it.** VERIFIED: constructing
  `DataframeQuery(timeline="no_such_timeline", select=["no_such_timeline","/nope:AlsoNope"],
  entity_order=["/does/not/exist"])` raises **nothing**. A typo in a bencher-generated blueprint
  fails silently at *render* time (an empty column, or the "Unknown timeline" panel). Bencher
  should validate entity/component/timeline names against the dataset before emitting a
  blueprint.

**⇒ Practical rule for bencher:** because within-entity column order is uncontrollable and
alphabetical, the only lever for a readable report table is **entity partitioning** — e.g.
`/sweep/inputs:*` and `/sweep/results:*` with `entity_order=["/sweep/inputs","/sweep/results"]`.
Within a group, prefix names to force the desired alphabetical order if it matters.

---

## 5. Scale limits (ticket bullet 4)

**VERIFIED — no practical wall for realistic sweeps.**

| rows x cols | `.rrd` size | result |
|---|---|---|
| 20,000 x 8 | 1.4 MB | renders fully, virtualized scroll, no warning, no truncation |
| 200,000 x 8 | 13.8 MB | renders fully (screenshot confirms rows #0–#21 populated, scrollbar reflects full extent) |
| 1,000,000 x 8 | 70.2 MB | **UNVERIFIED visually** — `--screenshot-to` fires on the first frame and raced the async loader (snapshot showed `Rows 1` mid-load). Not a failure, just a measurement artifact. |

Log+save cost was trivial (`send_dataframe`: 0.3 s for 200k rows, 0.9 s for 1M rows). Viewer peak
RSS 467 MB / 710 MB respectively for the (partial) loads.

**DOCUMENTED — no hard limit is published.** What exists instead:

- Dataframe queries are streamed since 0.20.0 ("Dataframe queries are now streamed, reducing
  memory usage") <https://github.com/rerun-io/rerun/releases/tag/0.20.0>
- Row virtualization with an explicit perf note in `dataframe_ui.rs` @0.35.0: "Empirical testing
  shows that iterating over all instances can take multiple tens of ms when the instance count is
  very large … So we use the clip rectangle to determine exactly which instances are visible."
- A **static-data** warning that matters if bencher puts constants on every row
  (<https://rerun.io/docs/concepts/query-and-transform/dataframe-queries>): "In practice, this can
  cause performance and/or memory issues when the same large static data is yielded in every row.
  For this reason, it may be preferable to filter static columns out … and query the static data
  separately."
- The viewer reported `Compaction config 4096 rows (1024 if unsorted)` for a generated recording
  (VERIFIED, from the recording-info panel) — a chunk-store batching parameter, not a view limit.

**UNKNOWN:** any documented max row/column count or per-view size cap. I found none in the docs,
the release notes, or the view source. The real constraint for #1103 is the **whole-report merge
cost** already flagged in #1103's "Not yet specified", not the `DataframeView` itself.

---

## 6. Version history and the `<=0.35.0` pin (ticket bullet 5)

| Version | Event | Source |
|---|---|---|
| **0.19.0** (2024-10-17) | **`DataframeView` introduced**, with the dataframe query API: "We now have an API for querying the contents of an .rrd file… We have also **added a matching dataframe view inside the Rerun Viewer**." | [releases/0.19.0](https://github.com/rerun-io/rerun/releases/tag/0.19.0), [rerun.io/blog/dataframe](https://rerun.io/blog/dataframe) |
| 0.20.0 | Dataframe queries streamed | [releases/0.20.0](https://github.com/rerun-io/rerun/releases/tag/0.20.0) |
| ≤0.22.0 | `DataframeQuery` blueprint archetype present with `timeline`, `filter_by_range`, `filter_is_not_null`, `apply_latest_at`, `select` — but **no** `entity_order`, **no** `auto_scroll` | [ref.rerun.io 0.22.0](https://ref.rerun.io/docs/python/0.22.0/common/blueprint_archetypes/) |
| 0.23.0 | Experimental `send_table` — explicitly distinct from the dataframe query view | [releases/0.23.0](https://github.com/rerun-io/rerun/releases/tag/0.23.0) |
| 0.24.0 | "Group dataframe table by archetype and use new table design [#10149]" — explains the 3-tier header I VERIFIED in §3 | [releases/0.24.0](https://github.com/rerun-io/rerun/releases/tag/0.24.0) |
| 0.25.0 | Filtering added to the **table widget only**; dataframe views use a different widget that does not support filtering | [releases/0.25.0](https://github.com/rerun-io/rerun/releases/tag/0.25.0) |
| **0.30.0** | **`entity_order` + `auto_scroll` landed**: "Make columns reorderable by entity in the dataframe view" (commit 2026-02-19), "Add auto-scroll feature and time indicator to the dataframe view" (commit 2026-02-23) | [releases/0.30.0](https://github.com/rerun-io/rerun/releases/tag/0.30.0); commit dates via `gh api search/commits` |
| 0.31–0.35.0 | **No further DataframeView/DataframeQuery changes found** in the CHANGELOG span | [CHANGELOG @main](https://raw.githubusercontent.com/rerun-io/rerun/main/CHANGELOG.md) |

### Answers to the pin question

- **Is anything needed only above `<=0.35.0`? — No, and it cannot be.** **0.35.0 is the newest
  rerun release**, published 2026-07-23; the newest heading in `main`'s CHANGELOG is
  `0.35.0 (2026-07-23)`. There is nothing above the pin to want.
  <https://github.com/rerun-io/rerun/releases>
- **Is anything needed only above the pin's `>=0.32.0` *floor*? — No.** The newest DataframeView
  features (`entity_order`, `auto_scroll`) landed in **0.30.0**, two minors *below* the floor. So
  every knob in this document is available across the **entire** pinned range `>=0.32.0,<=0.35.0`.
- **It is still marked unstable, at 0.35.0.** VERIFIED in the installed SDK — the docstrings of
  `DataframeView`, `DataframeQuery`, `ApplyLatestAt`, `FilterIsNotNull`, `SelectedColumns`,
  `ColumnName` and `ComponentColumnSelector` all carry:
  "⚠️ **This type is _unstable_ and may change significantly in a way that the data won't be
  backwards compatible.**" It never graduated. Any bencher blueprint emitting `DataframeQuery`
  should expect to be rewritten on a rerun minor bump.

### Two 0.35.0-specific SDK facts worth recording

- **VERIFIED: there is no `rerun.dataframe` module in 0.35.0.** `import rerun; rerun.dataframe`
  raises `AttributeError`, and `grep -rn "load_recording"` across the installed `rerun_sdk`
  returns **nothing**. Most rerun "get data out" documentation describes
  `rr.dataframe.load_recording(...)`, which **no longer exists**. Corroborated by the 0.26.0
  changelog: the Python `DataframeQueryView` was removed and replaced by the catalog
  `filter_segments()` / `filter_contents()` / `reader()` API, which requires a server.
  **⇒ bencher cannot use rerun as a local query engine to read a table back in 0.35.0.** The
  *view* is unaffected; only the programmatic read-back path is gone. The local read APIs that do
  exist are chunk-level: `rerun.experimental.RrdReader` / `ChunkStore` / `Chunk`.
- **VERIFIED: `rrb.Tabs` exists**, and rerun 0.35.0 ships exactly 11 view types: `BarChartView`,
  **`DataframeView`**, `GraphView`, `MapView`, `Spatial2DView`, `Spatial3DView`,
  `StateTimelineView`, `TensorView`, `TextDocumentView`, `TextLogView`, `TimeSeriesView`.
  Bencher's `RerunViewKind`
  (`bencher/results/composable_container/composable_container_rerun.py:16`, symbol
  `RerunViewKind`) has 10 members — the **exactly one** missing kind is `dataframe`. Confirms the
  ticket's premise precisely.

---

## 7. What this means for bencher (#1103 / #1110)

**A bencher N-D dataset CAN be shown as a usable table in a `DataframeView`** — VERIFIED with a
real sweep. The required logging shape:

1. **Flatten the N-D dataset to one row per sweep sample**:
   `ds.to_dataframe().reset_index()`. The Cartesian product already *is* the row set.
2. **Synthesise a row-index timeline** — non-negotiable, per §2c. Either an `int64` `"row"` column
   passed as `send_dataframe(..., index="row")`, or `rr.set_time("row", sequence=i)` before
   logging each sample's components. **Never** log the table `static=True`, and never rely on
   `log_time`/`log_tick`.
3. **Partition columns into entities to control order**, e.g. `/table/inputs:<name>` and
   `/table/results:<name>`, with
   `entity_order=["/table/inputs","/table/results"]`. Within-entity order is alphabetical and
   uncontrollable, so bake ordering into names if it matters.
4. **Bake units into the component identifier** (`energy [J]`) — there is no unit field.
5. **Keep cells scalar/string/bool.** Route `ResultImage`/`ResultVideo`/`ResultPath` to spatial
   views; in a table they degrade to raw byte arrays. Prefer `AnyValues`-style flat components
   over full archetypes, which explode into multiple columns.
6. **Choose `apply_latest_at` deliberately.** Bencher's dense Cartesian products have no holes, so
   the default `False` is right; `True` risks pulling in values from outside the view. It becomes
   relevant for ragged `over_time` history data.
7. **Validate names before emitting the blueprint** — the SDK validates nothing (§4), so a typo
   silently yields an empty column or an "Unknown timeline" panel.

Two constraints to carry into the plan doc:

- **`DataframeView` cannot sort or filter interactively**, and cannot rename columns. If the
  report needs a sortable table, `DataframeView` will not deliver it at any rerun version ≤0.35.0
  — and the alternative (`send_table`) **cannot be saved to a `.rrd`**, so it is incompatible with
  the "one saved rerun window" destination. This is a real, non-negotiable capability gap versus
  the incumbent `("tabulator","panel")` plugin, and #1110 should record it as an accepted loss
  rather than assume parity.
- **A11 note for A6 §3's parity table:** the ticket is right that A6 §3 is *pessimistic* on
  tables. Tables are achievable — but only for scalar-valued cells, only with a synthesised index,
  and without sorting or renaming.

---

## Appendix: how to reproduce

Experiments were run with `pixi run python` against `rerun-sdk` 0.35.0; screenshots were rendered
headlessly with the pixi-env viewer binary:

```bash
pixi run python <script.py>            # writes a .rrd containing data + blueprint
.pixi/envs/default/bin/rerun --screenshot-to out.png --window-size 1500x600 file.rrd
```

`--screenshot-to` captures the first rendered frame and quits (it panics on exit *after* writing
the PNG — the image is still valid). It races the async loader on large files, so for
multi-10-MB recordings the snapshot may show a partially loaded store; that is a measurement
artifact, not a rendering limit.

Key SDK introspections used:

```bash
pixi run python -c "import rerun, inspect, rerun.blueprint as rrb; print(inspect.getsource(rrb.DataframeView))"
pixi run python -c "from rerun.experimental import Chunk; print(Chunk.from_record_batch.__doc__)"
pixi run python -c "from rerun.experimental import RrdReader; print(RrdReader('f.rrd').store().summary())"
```
