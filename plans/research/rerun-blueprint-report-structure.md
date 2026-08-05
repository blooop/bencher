# What a rerun Blueprint can express about report-level structure

Research findings for [#1106](https://github.com/blooop/bencher/issues/1106), under map
[#1103](https://github.com/blooop/bencher/issues/1103) ("make rerun a native report backend
— the whole report as one rerun window").

**Anchored against:** bencher `main` @ `98503c84` (v1.119.0); `rerun-sdk` / `rerun-cli`
**0.35.0** (released 2026-07-23, per the
[CHANGELOG](https://github.com/rerun-io/rerun/blob/main/CHANGELOG.md)) — the top of
bencher's pinned range `rerun-sdk>=0.32.0,<=0.35.0`.

Every claim below is tagged:

- **VERIFIED** — an experiment in this document that I ran on this machine against the
  installed 0.35.0 SDK / CLI / viewer. Scripts are throwaway; the commands are given so
  they can be re-run.
- **DOCUMENTED** — stated by a rerun primary source (rerun.io docs, `rerun-io/rerun`
  source or changelog) but not independently executed here.
- **UNKNOWN** — could not be established from either.

> Per `plans/README.md` rule 7, every bencher citation below was re-checked against
> `98503c84` while writing this file.

---

## TL;DR — the answers

| Ticket question | Answer | Confidence |
|---|---|---|
| `rrb.Tabs` nesting / naming / can tabs hold containers / depth limit | Yes to containers; `name=` is the tab label; no depth limit in rerun | VERIFIED |
| Arbitrary `Horizontal`/`Vertical`/`Tabs` nesting + sizing | Usable to ≥500 deep; `row_shares`/`column_shares`/`grid_columns` exist, `Tabs` has none | VERIFIED |
| `rrb.TextDocumentView` renders Markdown | Yes — `rr.TextDocument(md, media_type=MediaType.MARKDOWN)` | VERIFIED |
| Practical ceiling on view count | **No engine ceiling** (1000 views load in ~1.9 s). The ceiling is **pixels** — ~48 legible views per 1600×1000 viewport | VERIFIED |
| **Can one Blueprint span multiple recordings?** | **NO. Everything must be in ONE recording store.** | VERIFIED + DOCUMENTED |
| Does `make_active`/`make_default` survive a cold `.rrd` open? | **Yes** — persisted verbatim as a `BlueprintActivationCommand` message | VERIFIED |

**The load-bearing answer (bullet 5) is a hard NO**, so bencher's merge into one recording
is *not* avoidable. But the *chunk-level decode* it uses today is not the expensive part —
see [§5.3](#53-so-is-bencher_read_items-cost-avoidable) and [§7](#7-what-this-means-for-bencher).

---

## 1. `rrb.Tabs` — nesting, naming, containers, depth

### 1.1 Tabs can hold containers, not just views — VERIFIED

The signature is typed `Container | View`, and it works at runtime:

```
Tabs(self, *args: 'Container | View', contents: 'Iterable[Container | View] | None' = None,
     active_tab: 'int | str | None' = None, name: 'Utf8Like | None' = None,
     visible: 'BoolLike | None' = None) -> 'None'
```
<sub>`pixi run python -c "import inspect, rerun.blueprint as rrb; print(inspect.signature(rrb.Tabs.__init__))"`</sub>

Built and saved a `Tabs` whose four children are a `Horizontal`, a `Vertical`, a nested
`Tabs` and a `Grid`; all four round-tripped:

```
built OK: Tabs kind= Tabs n children= 4
child kinds: [ContainerKind.Horizontal, ContainerKind.Vertical, ContainerKind.Tabs, ContainerKind.Grid]
```

DOCUMENTED corroboration: all four container classes take `*args: Container | View`
([`rerun_py/.../blueprint/containers.py`](https://github.com/rerun-io/rerun/blob/main/rerun_py/rerun_sdk/rerun/blueprint/containers.py)),
and the docs list "Containers come in four types: Horizontal, Vertical, Grid, and Tabs"
([configure-viewer-through-code](https://rerun.io/docs/howto/configure-viewer-through-code)).

### 1.2 Naming — `name=` is the tab label — VERIFIED

`Container.name` is serialized as `ContainerBlueprint:display_name`, and the viewer paints
it as the tab caption. Confirmed visually in [§4.2](#42-visual-proof-a-report-shaped-blueprint):
the tab strip reads `result var 0 … result var 7` from `rrb.Tabs(..., name=f"result var {rv}")`.

`View.name` becomes `ViewBlueprint:display_name`, dumped straight out of a saved blueprint:

```
bp chunk path=/view/966a92c7-…
    ViewBlueprint:class_identifier = [['TimeSeries']]
    ViewBlueprint:display_name     = [['from A']]
    ViewBlueprint:space_origin     = [['/from_a']]
```

DOCUMENTED: the first-party blueprint skill says "**Always set an explicit `origin` and
`name`** — `origin` defaults to `/`, which dumps the whole tree into one view (the usual
cause of an unreadable blob)"
([`skills/rerun-blueprint/SKILL.md`](https://github.com/rerun-io/rerun/blob/main/skills/rerun-blueprint/SKILL.md)).

### 1.3 `active_tab` — a real trap for a report — VERIFIED

`active_tab` accepts an index or a name, but **name resolution only matches `View`
children**. Naming a *container* tab never resolves:

| case | result |
|---|---|
| `active_tab=0`, view children | OK |
| `active_tab="B"`, view children | OK |
| `active_tab="nope"` | `ValueError: Active tab 'nope' not found in the container contents.` |
| `active_tab=1`, **container** children | OK |
| `active_tab="B"`, **container** children named `"B"` | **`ValueError: Active tab 'B' not found`** |
| `active_tab=5`, 1 child (out of range) | `ValueError: Active tab '5' not found` |

The cause is in the installed SDK — the name branch is gated on `isinstance(sub, View)`:

```python
# .pixi/envs/default/.../rerun/blueprint/api.py:331  (Container._log_to_stream)
if i == self.active_tab or (isinstance(sub, View) and sub.name == self.active_tab):
```
<sub>Same line on `main`: [`blueprint/api.py`](https://github.com/rerun-io/rerun/blob/main/rerun_py/rerun_sdk/rerun/blueprint/api.py)</sub>

**Consequence for bencher:** a report's tabs are containers (each tab holds a markdown pane
plus a plot grid), so bencher must select the default tab **by integer index**. Passing the
tab's human name — the obvious thing to write — raises at render time, not construction
time (the check runs in `_log_to_stream`, i.e. during `send_blueprint`/`save`).

Also note the validation is *only* this reachability check. There is no bounds check;
`active_tab=5` fails with "not found" rather than an index error.

### 1.4 Depth limit — none in rerun; Python recursion is the only wall — VERIFIED

Alternating `Horizontal`→`Vertical`→`Tabs` around one leaf view, saved to `.rbl`:

| depth | result |
|---|---|
| 5 | OK, 34,876 bytes |
| 10 | OK, 52,147 bytes |
| 20 | OK, 86,221 bytes |
| 50 | OK, 188,287 bytes |
| 100 | OK, 359,852 bytes |
| 200 | OK, 702,454 bytes |
| 500 | OK, 1,732,574 bytes |
| 1000 | `RecursionError: maximum recursion depth exceeded` |

The 1000 failure is **Python's** limit in the recursive `Container._log_to_stream`, not a
rerun constraint — with `sys.setrecursionlimit(20000)`:

```
depth 1000 with recursionlimit=20000 -> OK, 3,443,236 bytes
depth 2000 with recursionlimit=20000 -> OK, 6,870,233 bytes
```

Cost is linear at **~3.4 KB of blueprint per nesting level**.

DOCUMENTED: no depth limit, clamp or assertion exists in the viewer's container/viewport
implementation
([`container.rs`](https://github.com/rerun-io/rerun/blob/main/crates/viewer/re_viewport_blueprint/src/container.rs),
[`viewport_blueprint.rs`](https://github.com/rerun-io/rerun/blob/main/crates/viewer/re_viewport_blueprint/src/viewport_blueprint.rs)),
and rerun's own shipped OCR example nests to depth 5
(`Blueprint → Tabs → Vertical → Horizontal → Tabs → Spatial2DView`,
[`examples/python/ocr/ocr.py`](https://github.com/rerun-io/rerun/blob/main/examples/python/ocr/ocr.py)).

**One caveat, DOCUMENTED:** the viewport runs `egui_tiles` simplification
(`ViewportCommand::SimplifyContainer`) and has an explicit code path for a "'Trivial Tab',
which egui_tiles adds to all views during simplification"
([`viewport_blueprint.rs`](https://github.com/rerun-io/rerun/blob/main/crates/viewer/re_viewport_blueprint/src/viewport_blueprint.rs)).
Single-child containers may therefore be collapsed by the viewer. This is visible in
§4.2's screenshot: a deliberate `rrb.Tabs(rrb.Vertical(...))` renders as a lone tab captioned
*"Vertical container"* — a wasted chrome row. **Don't emit single-child containers.**

---

## 2. Nesting `Horizontal`/`Vertical`/`Tabs` in practice + sizing controls

### 2.1 The sizing controls a report layout needs exist — VERIFIED

| container | sizing params |
|---|---|
| `Horizontal` | `column_shares` |
| `Vertical` | `row_shares` |
| `Grid` | `column_shares`, `row_shares`, `grid_columns` |
| **`Tabs`** | **none** |

```
Tabs.__init__ params: ['self', 'args', 'contents', 'active_tab', 'name', 'visible']
Tabs(row_shares=...) -> TypeError: Tabs.__init__() got an unexpected keyword argument 'row_shares'
```

Semantics, DOCUMENTED: "The share is used to determine what fraction of the total width each
column should take up. The column with index `i` will take up the fraction
`shares[i] / total_shares`"
([`containers.py`](https://github.com/rerun-io/rerun/blob/main/rerun_py/rerun_sdk/rerun/blueprint/containers.py));
they are "relative weights on a container's children, equal by default"
([`SKILL.md`](https://github.com/rerun-io/rerun/blob/main/skills/rerun-blueprint/SKILL.md)).

`Vertical(row_shares=[1, 6])` demonstrably works — §4.2's screenshot shows the README
markdown pane as a thin top strip above the tab tree.

### 2.2 Shares are NOT validated — VERIFIED

Every one of these was accepted and written without complaint, on a container with 2 children:

```
row_shares=[1]            -> accepted, NO validation
row_shares=[1, 2, 3, 4]   -> accepted, NO validation
row_shares=[]             -> accepted, NO validation
row_shares=[0, 0]         -> accepted, NO validation
row_shares=[-1, 2]        -> accepted, NO validation
row_shares=[0.5, 0.5]     -> accepted, NO validation
```

DOCUMENTED expectation that this violates: "For Horizontal containers, the length of this
list should always match the number of contents. **Ignored** for Vertical containers"
([`container_blueprint.fbs`](https://github.com/rerun-io/rerun/blob/main/crates/store/re_sdk_types/definitions/rerun/blueprint/archetypes/container_blueprint.fbs)).
Also per that schema, `col_shares` is ignored on `Vertical`, `row_shares` ignored on
`Horizontal`, `active_tab` applies only to `Tabs`, and `grid_columns` is ignored on
`Horizontal`/`Vertical`. **Nothing enforces any of this** — a shares/children mismatch is
a silent layout bug bencher has to prevent itself.

### 2.3 The root container is implicit — VERIFIED / DOCUMENTED

`Blueprint(*parts)` with more than one container **silently wraps them in a `Tabs`**:

```python
# .pixi/envs/default/.../rerun/blueprint/api.py  (Blueprint.__init__)
elif len(contents) == 1:
    self.root_container = contents[0].to_container()
else:
    self.root_container = Tabs(contents=contents)
```

DOCUMENTED, verbatim: "Blueprints only have a single top-level 'root' container that defines
the viewport. If you provide multiple `ContainerLike` instances, they will be combined under
a single root `Tab` container"
([`api.py`](https://github.com/rerun-io/rerun/blob/main/rerun_py/rerun_sdk/rerun/blueprint/api.py)).

So a report should pass exactly **one** root container and be explicit about it.

---

## 3. `rrb.TextDocumentView` for the report's markdown / title panes

### 3.1 It renders Markdown — VERIFIED

Logging and round-tripping the media type:

```python
rec.log("/report/title",
        rr.TextDocument(MD, media_type=rr.components.MediaType.MARKDOWN), static=True)
```
```
store=recording/203807af path=/report/title cols=3 media=['TextDocument:media_type']
   value: [['text/markdown']]
```

And it *renders*: §4.2's screenshot shows `# Bencher report` painted as an H1 heading and
`## result var 0 / plot type 0` as an H2 — not as literal `#` characters.

```
MediaType.MARKDOWN = MediaType(value='text/markdown')
MediaType.TEXT     = MediaType(value='text/plain')
```

### 3.2 How the text is logged — VERIFIED + DOCUMENTED

```
rr.TextDocument(text: Utf8Like, *, media_type: Utf8Like | None = None)
```

- `text` is **required**; `media_type` is optional and "**If omitted, `text/plain` is
  assumed**"
  ([`text_document.fbs`](https://github.com/rerun-io/rerun/blob/main/crates/store/re_sdk_types/definitions/rerun/archetypes/text_document.fbs),
  [docs](https://rerun.io/docs/reference/types/archetypes/text_document)). Verified: the
  `/report/plain` entity logged without `media_type` has no `media_type` column at all.
- Canonical call, DOCUMENTED
  ([`docs/snippets/all/archetypes/text_document.py`](https://github.com/rerun-io/rerun/blob/main/docs/snippets/all/archetypes/text_document.py)):
  `rr.log("markdown", rr.TextDocument("""# Hello Markdown!…""", media_type=rr.MediaType.MARKDOWN))`
- For a static report pane, log it `static=True` (as above) so it is not tied to a
  timeline — relevant because a bencher report's markdown must be visible at every sweep index.

### 3.3 Markdown feature set — DOCUMENTED

From rerun's own feature checklist
([`docs/snippets/all/views/text_document.py`](https://github.com/rerun-io/rerun/blob/main/docs/snippets/all/views/text_document.py)):
Commonmark; GitHub-style strikethrough, **tables** and checkboxes; italics/bold/inline code;
`----` rules; images via `![](url)`; https links; rerun-internal links
(`recording://markdown`, `recording://markdown[#0]`, `recording://markdown:Text`); and
basic syntax highlighting for **C/C++, Python and Rust only**.

Tables matter for bencher — `BenchReport.append_markdown` output and dataset summaries can
be Markdown tables rather than needing a `DataframeView`. (I verified a Markdown table
round-trips; I did not visually confirm table *rendering*, so treat "tables render" as
DOCUMENTED, not VERIFIED.)

### 3.4 The `format_options` trap — DOCUMENTED

`TextDocumentView(format_options=rrb.archetypes.TextDocumentFormat(monospace=…, word_wrap=…))`
exists (verified in the signature), but those options "only apply to plain text documents and
have **no effect on Markdown documents**"
([`text_document_format.fbs`](https://github.com/rerun-io/rerun/blob/main/crates/store/re_sdk_types/definitions/rerun/blueprint/archetypes/text_document_format.fbs)).
So there is no knob to control Markdown pane presentation — layout must come from
`row_shares` on the enclosing container.

### 3.5 `BenchReport.append_markdown` maps cleanly

`bencher/bench_report.py:177` `BenchReport.append_markdown` is the panel-side source. A
rerun-native equivalent is one `rr.TextDocument(..., MARKDOWN)` log plus one
`rrb.TextDocumentView` — a 1:1 mapping with no expressiveness gap. `RerunViewKind`
(`composable_container_rerun.py:16`) **already has** a `text_document` member, so the view
kind is present; what is missing is any code path that produces it from markdown.

---

## 4. Practical ceiling on view count

### 4.1 There is no engine ceiling — VERIFIED

Building one recording plus one `Grid` blueprint of N `TimeSeriesView`s, then draining to
bytes:

| views | `.rrd` bytes | log | send_blueprint | drain |
|---|---|---|---|---|
| 10 | 85,489 | 0.00 s | 0.00 s | 0.00 s |
| 50 | 356,637 | 0.00 s | 0.00 s | 0.00 s |
| 200 | 1,371,231 | 0.00 s | 0.02 s | 0.02 s |
| 500 | 3,406,005 | 0.01 s | 0.03 s | 0.05 s |
| 1000 | 6,804,127 | 0.01 s | 0.05 s | 0.10 s |
| 2000 | 13,650,598 | 0.03 s | 0.12 s | 0.20 s |

Linear, ~**6.8 KB per view** (blueprint + trivial data), and nothing rejects any size.
Opening the 1000-view file in the real viewer: **1.9 s wall clock**, all 1000 views present
and enumerated in the blueprint panel.

The one hard numeric limit in rerun's codebase does **not** apply here:
`DEFAULT_MAX_VIEWS_SPAWNED: usize = 8`
([`spawn_heuristics.rs`](https://github.com/rerun-io/rerun/blob/main/crates/viewer/re_viewer_context/src/view/spawn_heuristics.rs))
gates the **auto-spawn heuristic** per view class, i.e. `auto_views=True`. An explicit
`rrb.Blueprint(..., auto_views=False)` — which bencher already passes
(`composable_container_rerun.py:467` `render`) — is unaffected. No documented view-count
maximum or perf-degradation threshold exists anywhere in the docs, changelog or issues.

### 4.2 The real ceiling is pixels — VERIFIED

The ceiling is **legibility, not throughput**. Screenshots taken with
`rerun --window-size 1600x1000 --screenshot-to …` (software/Vulkan under `xvfb-run`):

- **200 views, flat `Grid`, 1600×1000:** all render, ~1.7 s — but each tile is ~85×70 px.
  Titles truncate to `w 0`, `w 1:`; axes show a bare `0`; **no plot content is visible**.
- **1000 views, flat `Grid`:** all render, ~1.9 s — each cell is nothing but a
  "maximize view" icon. Completely unreadable.
- **~200 views behind nested `Tabs`** (§4.2 report shape): perfectly legible, because only
  the active tab's ~4 views are laid out.

A view needs roughly **200×150 px** to show a title, axes and a trace. A 1600×1000 viewport
therefore holds about **8×6 ≈ 48 legible views**.

**This is the argument for `rrb.Tabs`, and it is a stronger one than "a report is a tab
tree".** Tabs are the only container that makes view count independent of viewport area: an
inactive tab's views cost bytes but no pixels. A report of hundreds of views is fine *if and
only if* it is behind tabs.

### 4.3 Visual proof: a report-shaped blueprint

I built 8 result vars × 5 plot types × 4 plots = **~201 views at nesting depth 5**, shaped
like `BenchReport`:

```
Blueprint(
  Vertical(
    TextDocumentView(origin="/report/readme"),          # markdown header
    Tabs(  *[ Tabs( *[ Tabs(Vertical(TextDocumentView(notes),
                                     Grid(plots, grid_columns=2),
                                     row_shares=[1, 4]),
                            name=f"plot type {pt}") ...],
                    name=f"result var {rv}", active_tab=0) ...],
         name="Report", active_tab=0),
    row_shares=[1, 6]),
  BlueprintPanel(state="collapsed"), SelectionPanel(state="collapsed"),
  auto_layout=False, auto_views=False)
```

Built and saved in **0.10 s**, `report.rrd` = **2,020,218 bytes**, reading back as
`recordings=1 blueprints=1` with 535 blueprint entities (402 view, 130 container).

Opened cold in the viewer, the screenshot showed **all of the following working at once**:

- nested tab strips: `result var 0…7`, then `plot type 0…4`
- Markdown rendered as headings (`Bencher report` H1, `result var 0 / plot type 0` H2)
- `Grid(grid_columns=2)` laying out `plot 0…3` as a legible 2×2 of real sine traces
- `row_shares=[1, 6]` honoured (thin markdown strip on top)
- `active_tab=0` honoured at both tab levels
- blueprint + selection panels collapsed exactly as specified
- the `sweep` timeline in the time panel

Two practical costs were also visible, and both are layout advice rather than limits:

1. **Every tab nesting level spends a full chrome row.** Four stacked strips
   (`result var` / `plot type` / `Vertical container` / `notes`) ate ~230 px of the 1000 px
   height before any content. Keep the tab tree shallow — 2 levels, not 4.
2. **`row_shares=[1, 6]` clipped the markdown pane** — "Generated sweep" was cut off. Markdown
   panes need a generous share or their own tab; there is no auto-height.

---

## 5. Can one Blueprint span multiple recordings? — **NO**

This is the load-bearing question, and the answer is unambiguous.

### 5.1 Structural proof — VERIFIED

`ViewBlueprint` carries **no recording qualifier**. Dumping a saved blueprint's chunks, the
only addressing field is a bare entity path:

```
ViewBlueprint:class_identifier = [['TimeSeries']]
ViewBlueprint:display_name     = [['from A']]
ViewBlueprint:space_origin     = [['/from_a']]     <-- bare path, no store/recording
ViewContents:query             = [['$origin/**']]  <-- bare glob, no store/recording
```

No class in `rerun.blueprint` exposes any `recording`/`dataset`/`store` parameter (swept every
class's `__init__`; the only hits were `TensorView.scalar_mapping` and `Visualizer.mappings`).
`grep recording_id` across the installed `rerun/blueprint/**.py`: **0 hits**.

And the blueprint is bound to the data by **`application_id` alone**:

```python
# .pixi/envs/default/.../rerun/sinks.py  (send_blueprint)
application_id = get_application_id(recording=recording)
blueprint_storage = create_in_memory_blueprint(application_id=application_id, blueprint=blueprint).storage
```

### 5.2 Behavioural proof — VERIFIED (this is the decisive one)

I built two recordings sharing one `application_id` (`multi_app`) with different
`recording_id`s (`AAA` with `/from_a/scalar`, `BBB` with `/from_b/scalar`), plus one blueprint
with one view per path, and merged all three into a single `.rrd` with
`rerun rrd merge`. The file is legitimately multi-store:

```
merged_bp.rrd  recordings=2 blueprints=1
    [recording] app='multi_app' rec='AAA'  entities=['/__properties', '/from_a/scalar']
    [recording] app='multi_app' rec='BBB'  entities=['/__properties', '/from_b/scalar']
    [blueprint] app='multi_app' rec='rec_6fc0e48b…'
```

Opened cold in the real viewer:

- the Sources panel lists **both** recordings under `multi_app`; exactly **one is active**
- the blueprint **did** apply — the panel shows `Viewport (Horizontal cont…)` with views
  `from A` and `from B`
- **both views are empty.** The Streams panel lists only `from_b/scalar` — the active
  recording's entities. `from A` has nothing to draw because `/from_a` does not exist in the
  active recording.

So: **a `.rrd` may contain multiple recording stores, and a blueprint applies across them by
app id — but its views only ever resolve against the single active recording.** Two
recordings means the user toggles between them and sees half a report at a time. A
one-window report therefore requires **one recording store**.

### 5.2.1 DOCUMENTED corroboration

Five independent primary sources agree:

1. "The Viewer stores blueprints **per application ID**"; recordings sharing an app id "share
   the same blueprint" — [apps-and-recordings](https://rerun.io/docs/concepts/apps-and-recordings)
2. "**All recordings that share the same Application ID will use the same blueprint.**" —
   [blueprints](https://rerun.io/docs/concepts/visualization/blueprints)
3. The viewer keys blueprints by `ApplicationId`, one active + one default each:
   `default_blueprint_by_app_id: HashMap<ApplicationId, StoreId>`,
   `active_blueprint_by_app_id: HashMap<ApplicationId, StoreId>` —
   [`store_hub.rs`](https://github.com/rerun-io/rerun/blob/main/crates/viewer/re_viewer_context/src/store_hub.rs)
4. `ViewBlueprint` has only `class_identifier`, `display_name`, `space_origin`, `visible` —
   no recording field —
   [`view_blueprint.fbs`](https://github.com/rerun-io/rerun/blob/main/crates/store/re_sdk_types/definitions/rerun/blueprint/archetypes/view_blueprint.fbs)
5. Open upstream bug **[#8287 "Support per-recording blueprints (as opposed to
   per-application)"](https://github.com/rerun-io/rerun/issues/8287)** (filed 2024-12-03,
   still open, labelled `🪳 bug` + `user-request`): "it looks like **both recordings receive
   the same blueprint**… If the two recordings are both in a different application it works
   correctly."

Related open issues: [#5640](https://github.com/rerun-io/rerun/issues/5640) (switch between
app/recording blueprint), [#9766](https://github.com/rerun-io/rerun/issues/9766) (sync
timelines across recordings), [#7927](https://github.com/rerun-io/rerun/issues/7927)
("Introduce an actual Rerun Archive format (`.rra`), banish multi-recordings RRD"). Searching
`rerun-io/rerun` for "cross-recording", "view multiple recordings simultaneously" and
"compare two recordings" found **no feature and no open request** for cross-recording views
in one layout. This is not on rerun's roadmap; bencher cannot wait for it.

### 5.3 So is bencher's `_read_item` cost avoidable?

**The merge is not avoidable. The chunk-level decode mostly is — but it is also not the
problem people assume.**

`ComposableContainerRerun._read_item` (`composable_container_rerun.py:269`) decodes every
chunk of every input `.rrd` via `RrdReader.stream`, rewrites each entity path with
`chunk.with_entity_path`, and re-emits with `send_chunks`. Measured against the two CLI
alternatives, on 60 inputs (128×128 RGB image + 50 scalars each, 3.6 MB total):

| approach | time | output | stores | entity paths |
|---|---|---|---|---|
| (a) bencher's Python chunk decode + re-root | **0.02 s** | 3,408,139 B | 1 | **181 (prefixed)** |
| (b) `rerun rrd route --recording-id ONE` | 0.11 s | 3,279,286 B | 1 | **3 (collided!)** |
| (c) `rerun rrd merge` | 0.14 s | 3,592,537 B | **60** | 3 |

Three findings, all VERIFIED:

1. **Bencher's approach is already the fastest of the three** at this scale, and it scales
   benignly: 240 items / 192 MB in **0.37 s**. `chunk.with_entity_path` is an Arrow metadata
   rewrite, not a re-encode. The real cost is **memory**, not CPU — peak RSS was 1,782 MB for
   a 192 MB report, because `memory_recording().drain_as_bytes()` materialises the whole
   report as one `bytes`. **~9× the report size in RAM is the ceiling to worry about, not
   time.**

   | items | input | output | merge | peak RSS |
   |---|---|---|---|---|
   | 60 | 3.6 MB | 3.4 MB | 0.02 s | 177 MB |
   | 120 | 25.0 MB | 24.6 MB | 0.07 s | 398 MB |
   | 240 | 50.0 MB | 49.2 MB | 0.13 s | 784 MB |
   | 240 | 192.2 MB | 191.4 MB | 0.37 s | 1,782 MB |

2. **`rrd route` is not a drop-in replacement**, despite advertising exactly the right thing
   ("This can be used to combine multiple .rrd files into a single recording… Because the
   payload of the messages is never decoded, no migration or verification will be performed").
   It rewrites *store ids only* — it does **not** re-root entity paths. All 60 items collapsed
   onto 3 paths (`/__properties`, `/img`, `/y`), silently overwriting each other. Route is only
   usable if bencher logs each item under its final `item{i}/…` prefix **at source**, which is
   the actually interesting refactor: it would make the merge a metadata-only concatenation and
   remove the decode *and* the RSS spike.

3. **`rrd merge` is wrong for this purpose** — it preserves 60 separate recording stores, which
   §5.2 proves yields 60 half-empty windows.

Two further `route` caveats, VERIFIED:

- With multiple inputs, `route --recording-id` **drops blueprint activation**:
  `Processed 17 messages, dropped 1 blueprint activations`. Confirmed absent afterwards.
  The docs say so: "When this flag is set and multiple input .rrd files are specified,
  blueprint activation commands will be dropped." So the blueprint must be sent/appended
  *after* routing.
- `route` **panics** on a single input that contains both a recording and a blueprint store:
  `assertion left == right failed … rerun/src/commands/rrd/route.rs:253`. That is an upstream
  bug in rerun-cli 0.35.0 worth reporting; it means `route` cannot be applied to bencher's
  current per-plot `.rrd` files, which already embed blueprints.

---

## 6. Does `make_active` / `make_default` survive a cold `.rrd` open? — **YES**

### 6.1 A blueprint *is* embedded in a saved `.rrd` — VERIFIED

This resolves an UNKNOWN: the rerun docs only ever describe saving blueprints to `.rbl`, and
never state that a blueprint can live inside an `.rrd`. Empirically it can, and bencher
already relies on it. A `.rrd` produced by `send_blueprint` then `drain_as_bytes` contains
**two stores**:

```
md.rrd  recordings=1 blueprints=1
    [recording] app='exp_md'  rec='203807af2a2e449ebddd6c94854b843e'
    [blueprint] app='exp_md'  rec='rec_7ff4bcdcde75469e8d9e6d9fcb2db7cb'
```

### 6.2 The activation flags are persisted verbatim — VERIFIED

`rerun rrd print` on the saved file shows an explicit activation *message*:

```
BlueprintActivationCommand(StoreId(Blueprint, "exp_md", "rec_7ff4bcdc…"),
                           make_active: true, make_default: true)
```

All four flag combinations round-trip exactly:

```
flags_False_False.rrd   make_active: false, make_default: false
flags_False_True.rrd    make_active: false, make_default: true
flags_True_False.rrd    make_active: true,  make_default: false
flags_True_True.rrd     make_active: true,  make_default: true
```

**So `composable_container_rerun.py:501`'s
`recording.send_blueprint(blueprint, make_active=True, make_default=True)` does survive a cold
open.** Independently confirmed end-to-end: every screenshot in §4 and §5.2 is a cold
`rerun <file>.rrd` with no prior viewer state, and the blueprint was applied each time.

`Blueprint.save()` also writes an activation command into the `.rbl`
(`make_active: true, make_default: true`), so a `.rbl` merged into an `.rrd` stays active
(verified on `merged_bp.rrd`).

### 6.3 Semantics and the one gotcha

DOCUMENTED, verbatim
([`sinks.py`](https://github.com/rerun-io/rerun/blob/main/rerun_py/rerun_sdk/rerun/sinks.py)):

- `make_active` — "Immediately make this the active blueprint for the associated `app_id`.
  Note that setting this to `false` does not mean the blueprint may not still end up becoming
  active. In particular, if `make_default` is true and there is no other currently active
  blueprint."
- `make_default` — "Make this the default blueprint for the `app_id`. The default blueprint
  will be used as the template when the user resets the blueprint for the app. It will also
  become the active blueprint if no other blueprint is currently active."

Keeping both `True`, as bencher does, is correct for a self-contained report artifact.

**Resolving an apparent contradiction in rerun's own sources.** The first-party skill claims a
blueprint "binds to the data by store identity, **both application id and recording id**…
Mismatch either and the viewer keeps blueprint and data as separate recordings and never
applies the blueprint"
([`SKILL.md`](https://github.com/rerun-io/rerun/blob/main/skills/rerun-blueprint/SKILL.md)),
which contradicts the app-id-only keying in `store_hub.rs`. **The skill is wrong on this
point, and I can show it:** in every working case above the blueprint store's `recording_id`
(`rec_7ff4bcdc…`) *differs* from the data recording's (`203807af…`) — `send_blueprint` always
mints a fresh uuid for the blueprint store — and the blueprint applied anyway. Binding is by
`application_id`; the blueprint's own `recording_id` is just its store identity and is never
expected to match. (The skill's advice is presumably about the *data* stream you build when
re-logging against an already-loaded `.rrd`, not about the blueprint store.)

One caveat worth carrying: `rrd route --application-id X --recording-id Y` rewrites **all**
stores including the blueprint's, so both ended up as `ONE_APP/ONE_REPORT` (verified). Harmless
because `kind` still distinguishes them, but it means route is not identity-preserving.

---

## 7. What this means for bencher

Answering the map's framing — "where does a Blueprint run out?" — the honest answer is
**it doesn't run out at report scale.** Every structural thing a `BenchReport` does has a
Blueprint counterpart, verified working together in one window at ~200 views (§4.3). A6 §3's
parity table is indeed pessimistic, as #1103 suspected.

The binding constraint is **one recording store**, not blueprint expressiveness.

### Confirmed capability map

| `BenchReport` (panel) | rerun Blueprint equivalent | status |
|---|---|---|
| `self.pane = pn.Tabs(...)` (`bench_report.py:145`) | `rrb.Tabs(name=…, active_tab=<int>)` | VERIFIED works, nests arbitrarily |
| `append_markdown` (`bench_report.py:177`) | `rr.TextDocument(md, MARKDOWN)` + `rrb.TextDocumentView` | VERIFIED renders |
| `ComposeType.right` → `Horizontal` (`:152`) | unchanged | already correct |
| `ComposeType.down` → `Vertical` (`:152`) | unchanged | already correct |
| *(missing)* tab composition | **`rrb.Tabs` — exists in 0.35.0, unused by `_rerun_compose_spec`** | the actual gap |
| *(missing)* proportional sizing | `row_shares` / `column_shares` / `grid_columns` | available, unused |

`RerunViewKind` (`composable_container_rerun.py:16`) already contains `text_document`, so the
markdown pane needs no new view kind — only a producer.

### Concrete constraints any rerun-native report design must respect

1. **One recording store, mandatory** (§5.2). Not a perf choice — a correctness one.
2. **Select default tabs by integer index, never by name** (§1.3) — container-named
   `active_tab` raises at render time.
3. **Never emit single-child containers** (§1.4) — the viewer collapses them into a wasted
   "Trivial Tab" chrome row.
4. **Keep the tab tree ~2 levels deep** (§4.3) — each level costs a full chrome row of height.
5. **Validate `row_shares`/`column_shares` length against child count yourself** (§2.2) —
   rerun silently accepts mismatched, empty, zero and negative shares.
6. **Pass exactly one root container** (§2.3) — multiple parts are silently wrapped in `Tabs`.
7. **Budget ~48 legible views per visible tab**, not per report (§4.2). Total view count is
   effectively unbounded *behind tabs*.
8. **The RSS ceiling is ~9× report size** (§5.3), from `drain_as_bytes`. This, not merge CPU,
   is the scaling risk the map lists as "the merge-cost ceiling for a whole-report recording".

### The one cheap win this research uncovered

Bencher's per-plot `.rrd` files are produced by bencher itself. If each were logged under its
final `item{i}/…` entity prefix **at source**, the whole-report merge becomes a metadata-only
concatenation (`rrd route --recording-id`, or `send_chunks` without `with_entity_path`),
eliminating both the chunk decode and the peak-RSS spike. Today the prefix is applied
*after the fact* in `_read_item` (`:269`), which is the only reason a decode is needed at all.

### Incidental bugs found (not bencher's, but worth knowing)

- **rerun-cli 0.35.0 `rrd route` panics** on a single input containing both a recording and a
  blueprint store (`route.rs:253` assertion). Blocks using `route` on bencher's current
  per-plot files, which embed blueprints.
- **`active_tab` by name silently cannot address container children** (`api.py:331`) — arguably
  an upstream bug, since `Container.name` exists and is displayed.
- **A bencher latent bug:** `_read_item` (`:269`) iterates `RrdReader.recordings()`, which
  returns **only** `kind='recording'` stores. Any blueprint embedded in an input `.rrd` — and
  bencher's own `render()` at `:467` embeds one in every artifact it writes — is silently
  dropped on re-composition. Harmless today (the composer builds a fresh blueprint anyway) but
  it means nested compositions cannot inherit child layout, and it will bite the moment
  sub-reports are composed.

---

## Appendix: reproducing this

Experiments were throwaway scripts, not committed. To re-derive:

```bash
# SDK surface
pixi run python -c "import inspect, rerun.blueprint as rrb; print(inspect.signature(rrb.Tabs.__init__))"
pixi run python -c "import rerun as rr; print(rr.components.MediaType.MARKDOWN)"

# blueprint + activation inside a saved .rrd
pixi run rerun rrd print report.rrd | grep BlueprintActivationCommand

# store kinds in a file
pixi run python -c "
from rerun.experimental import RrdReader
r = RrdReader('report.rrd'); print(r.recordings()); print(r.blueprints())"

# multi-recording merge, and the cheap metadata-only route
pixi run rerun rrd merge a.rrd b.rrd -o merged.rrd
pixi run rerun rrd route --recording-id ONE a.rrd b.rrd -o routed.rrd

# cold-open screenshots (headless)
WGPU_BACKEND=vulkan xvfb-run -a -s "-screen 0 1600x1000x24" \
  pixi run rerun --window-size 1600x1000 --screenshot-to shot.png report.rrd
```

Note `--screenshot-to` grabs a frame and quits; on a large file it can fire mid-load (the
2000-view capture did), so check the blueprint panel is populated before trusting a shot.

### Source index

**Primary — rerun docs:**
[views reference](https://rerun.io/docs/reference/types/views) ·
[TextDocumentView](https://rerun.io/docs/reference/types/views/text_document_view) ·
[TextDocument archetype](https://rerun.io/docs/reference/types/archetypes/text_document) ·
[blueprints concept](https://rerun.io/docs/concepts/visualization/blueprints) ·
[apps and recordings](https://rerun.io/docs/concepts/apps-and-recordings) ·
[configure viewer through code](https://rerun.io/docs/howto/configure-viewer-through-code) ·
[build a blueprint programmatically](https://rerun.io/docs/howto/visualization/build-a-blueprint-programmatically) ·
[0.21 migration (SpaceView→View)](https://rerun.io/docs/reference/migration/migration-0-21)

**Primary — `rerun-io/rerun`:**
[CHANGELOG](https://github.com/rerun-io/rerun/blob/main/CHANGELOG.md) ·
[`blueprint/api.py`](https://github.com/rerun-io/rerun/blob/main/rerun_py/rerun_sdk/rerun/blueprint/api.py) ·
[`blueprint/containers.py`](https://github.com/rerun-io/rerun/blob/main/rerun_py/rerun_sdk/rerun/blueprint/containers.py) ·
[`sinks.py`](https://github.com/rerun-io/rerun/blob/main/rerun_py/rerun_sdk/rerun/sinks.py) ·
[`container_blueprint.fbs`](https://github.com/rerun-io/rerun/blob/main/crates/store/re_sdk_types/definitions/rerun/blueprint/archetypes/container_blueprint.fbs) ·
[`view_blueprint.fbs`](https://github.com/rerun-io/rerun/blob/main/crates/store/re_sdk_types/definitions/rerun/blueprint/archetypes/view_blueprint.fbs) ·
[`text_document.fbs`](https://github.com/rerun-io/rerun/blob/main/crates/store/re_sdk_types/definitions/rerun/archetypes/text_document.fbs) ·
[`text_document_format.fbs`](https://github.com/rerun-io/rerun/blob/main/crates/store/re_sdk_types/definitions/rerun/blueprint/archetypes/text_document_format.fbs) ·
[`store_hub.rs`](https://github.com/rerun-io/rerun/blob/main/crates/viewer/re_viewer_context/src/store_hub.rs) ·
[`viewport_blueprint.rs`](https://github.com/rerun-io/rerun/blob/main/crates/viewer/re_viewport_blueprint/src/viewport_blueprint.rs) ·
[`spawn_heuristics.rs`](https://github.com/rerun-io/rerun/blob/main/crates/viewer/re_viewer_context/src/view/spawn_heuristics.rs) ·
[`skills/rerun-blueprint/SKILL.md`](https://github.com/rerun-io/rerun/blob/main/skills/rerun-blueprint/SKILL.md) ·
[snippet: text_document view](https://github.com/rerun-io/rerun/blob/main/docs/snippets/all/views/text_document.py) ·
[issue #8287](https://github.com/rerun-io/rerun/issues/8287) ·
[issue #7927](https://github.com/rerun-io/rerun/issues/7927)

**Primary — installed SDK (`.pixi/envs/default/lib/python3.13/site-packages/rerun_sdk/`),
rerun 0.35.0.**

**Bencher, verified against `98503c84`:**
`bencher/bench_report.py:145` `BenchReport.pane` ·
`bencher/bench_report.py:177` `BenchReport.append_markdown` ·
`bencher/results/composable_container/composable_container_rerun.py:16` `RerunViewKind` ·
`:152` `_rerun_compose_spec` ·
`:269` `_read_item` ·
`:411` `ComposableContainerRerun._layout` ·
`:467` `ComposableContainerRerun.render` ·
`:501` `send_blueprint(make_active=True, make_default=True)`
