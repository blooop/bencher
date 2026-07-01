# Plot plugin system — design and migration plan

This document captures the design that was settled before tier-0 infrastructure
landed (PR #932 / branch `feature/plugin-system`). It exists so that contributors
or agents continuing the work have the full context — the alternatives that were
considered, the tensions surfaced, the pivotal moments, and the reasoning —
without needing to reconstruct it from the code alone.

## Table of contents

1. [Goal and motivation](#goal-and-motivation)
2. [Resolved design at a glance](#resolved-design-at-a-glance)
3. [Decision walkthrough (the grilling)](#decision-walkthrough-the-grilling)
4. [Contract surfaces](#contract-surfaces)
5. [Runtime model](#runtime-model)
6. [Migration plan](#migration-plan)
7. [Tier-0 status (this branch)](#tier-0-status-this-branch)
8. [Open tactical questions](#open-tactical-questions)
9. [Handoff guide](#handoff-guide)

## Goal and motivation

Replace the inheritance-based rendering system in `bencher/results/` with a
plugin registry, so that:

1. Third parties can ship plot backends in their own repos (`pip install`-able,
   discovered via entry points).
2. Users can write one-off plot plugins inline in their benchmark scripts
   without touching upstream bencher.
3. The current tight coupling to Holoviews/Panel/xarray at the top of
   `bencher/results/bench_result_base.py` is replaced with a pluggable
   contract.

The existing TODO at `bench_result_base.py:50-52` flagged this gap explicitly:

```python
# todo add plugins
# https://gist.github.com/dorneanu/cce1cd6711969d581873a88e0257e312
# https://kaleidoescape.github.io/decorated-plugins/
```

The current code's pain points the design has to address:

- **Massive multiple-inheritance** — `BenchResult` in `bench_result.py:42-60`
  inherits from every concrete result type, baking all backends into one class.
- **Top-level imports of optional backends** — `bench_result_base.py:8-12`
  imports holoviews/panel/xarray unconditionally; `volume_result.py:9` and
  `surface_result.py:4` import plotly without any try/except even though they
  are 3D-only. `import bencher` therefore pulls every backend into memory.
- **No central dispatch table** — each result type hardcodes a `PlotFilter` in
  its `to_plot()` method (`line_result.py:56-78` style). Adding a renderer
  means inheriting and editing the god-class.
- **Per-backend composer split that fights itself** — `ComposableContainerPanel`
  (`composable_container_panel.py:13`) and `ComposableContainerRerun`
  (`composable_container_rerun.py:13`) duplicate the layout logic per backend
  because cross-backend native composition is awkward.

## Resolved design at a glance

| Decision | Choice | One-line reason |
|---|---|---|
| Plugin granularity | Hybrid: (chart × backend) pair, backend = namespace string | Backends without natural chart decomposition (Rerun/Vedo/Taichi) can register coarse plugins without changing the contract |
| Composition | Plugin owns internal; bencher does Panel-level outer | "Anything you want welded together natively, you put in one plugin" — eliminates per-backend composer split |
| Output target | Single — `pn.viewable.Viewable` | Vedo/Taichi/Holoviews/Plotly/Matplotlib/Rerun-via-iframe all collapse to Panel; non-HTML consumers use the data API |
| Plugin contract | `(name, backend, match, priority, requires, render(BenchData)→Viewable)` | One contract, frozen public surface, function/class form via decorator |
| `BenchData` | Frozen value type, fat (chart + meta-view fields) | One mental model; meta-views gate via `requires` instead of plugin kinds |
| Discovery | Hybrid: entry points + `register_plugin(...)`, lazy | Entry points handle distributed plugins; explicit registration handles in-script plugins |
| Selection | One implementation per matching chart type, ordered by priority; `backend` = preference | Same plotters, swappable rendering library — `include`/`exclude`/`only` for filtering |
| Override | By (name, backend) — same pair replaces; other backends of the same name coexist as alternatives | No flags, no monkey-patching |
| Built-in chart types | Migrate onto the same plugin mechanism | Bencher itself is a consumer of the public API; contract is forced to be good |
| Loading | Lazy module imports | `import bencher` no longer pulls Plotly/Holoviews/Rerun |
| Missing deps | Skip with logged warning | Other plugins continue working |
| Render errors | Substitute error pane (`strict=True` re-raises) | Default-tolerant for users; loud-by-default for developers |
| Plugin instances | Stateless | Per-render state flows through `BenchData` |
| Migration | Gradual, no flag, six tiers | Each PR is reviewable and behaviourally observable |
| Backwards compat | Preserve-surface-swap-internals | `to_<type>()` family stays as one-line shims; zero user-visible breakage |

## Decision walkthrough (the grilling)

The design was reached by walking down a decision tree, one branch at a time,
with every fork explicitly resolved before moving on. This section preserves
the structure of that walk — the alternatives considered, the tensions
surfaced, and the pivotal moments where the design changed direction. It is
written for someone who needs to understand *why* a decision was made and
when to revisit it.

### Q1: Plugin granularity

**Alternatives:**

- **Coarse** — one plugin = one rendering library. A "Plotly backend" plugin
  contributes whatever Plotly can do. Bencher dispatches *plot type* to the
  active backend. Loses the auto-dispatch by data shape that bencher already
  has.
- **Fine** — one plugin = one chart type for one backend. Matches today's
  granularity (`LineResult`, `HeatmapResult`, etc.). Loses the ability to
  say "prefer the plotly backend when both can render."
- **Hybrid** (chosen) — fine-grained plugins, with `backend` as a string
  namespace for grouping, optional-dep gating, and user-facing selection.

**Tension surfaced when Rerun/Vedo/Taichi entered the picture:** these
backends do not naturally chart-decompose. Rerun is an entity logger with a
Blueprint; Vedo is a 3D scene/Plotter; Taichi is essentially an
immediate-mode canvas. The hybrid model accommodates them — they can register
*coarse* plugins (one plugin = whole-backend output) under the same
contract. So "backend = namespace" cleanly admits both fine (Holoviews,
Plotly) and coarse (Rerun, Vedo, Taichi) styles within one mechanism.

### Q2: Composition

**The pivotal question:** where does composition live? The design conflicts
the user worried about almost all came from bencher trying to compose
*across* plugins natively — taking an `hv.Curve` from plugin A and an
`hv.HeatMap` from plugin B and welding them into one `hv.Layout`. That
forces the per-backend `ComposableContainer` split, the "promote to HTML
when mixing backends" rule, and the awkwardness around Rerun's iframe
(commits `ba7f09bd` / `c858ee24` base64-inlining `.rrd` data into HTML to
make it embeddable).

**Alternatives:**

- **Bencher composes across plugins natively** — keep the per-backend
  `ComposableContainerPanel` / `ComposableContainerRerun` split forever.
- **Plugin owns internal composition** (chosen) — a plugin returns one
  Panel-embeddable view. It is free to do whatever native composition it
  likes *inside* (linked `hv.Layout`, `plotly.subplots`, full Rerun
  blueprints, multi-cell Vedo scenes). Bencher does only Panel-level outer
  composition.

**What the user gives up:** bencher cannot *automatically* link plots from
two separate plugins. If you want linked brushing across `LineResult` and
`HeatmapResult` of the same data, you write *one* plugin that produces the
`hv.Layout`. The user verified explicitly: "linking happens in a single
plot" — cross-plugin native composition is not in use today, so the
collapse is free.

**The principle that falls out:** *the plugin is the composition unit.*
Anything you want welded together natively, you put in one plugin. Bencher
does dashboard-level composition (rows / columns / tabs / pages) only. This
collapses a meaningful amount of the existing complexity.

### Q3: Output target

**The user raised a meaningful constraint mid-walk:** "I was considering
making a full rerun backend, ie everything is viewable as a rerun file and
not even use html at all." That breaks the implicit assumption that "the
report is HTML."

**Alternatives:**

- **(a)** HTML/Panel as the only first-class target. Full-Rerun mode is a
  parallel code path outside the plugin system.
- **(b)** Target as a first-class concept. Plugins declare which targets
  they support; bencher dispatches per target. `panel-html`, `rerun-rrd`,
  optionally `pdf`, `static-png-dir`, `live-panel`, `live-rerun`,
  `notebook`. Per-target composition (Panel rows for HTML, Rerun
  Blueprint for Rerun).
- **(c)** Two hardcoded targets only — HTML and Rerun. Pragmatic middle.

**The pivot:** the user clarified that Vedo and Taichi can both be
expressed as Panel objects, weakening the "we need native non-HTML
output" argument substantially. The only target that genuinely wanted a
non-HTML output channel was Rerun, and Rerun's HTML-iframe path already
works (the recent base64-inlined `.rrd` work).

The argument crystallised: **multi-target is shipping a general extension
mechanism for exactly one specialised use case that has a thin direct
solution.** That's the wrong shape of complexity.

**Chosen: (a)** — single-target HTML/Panel. The plugin contract returns
`pn.viewable.Viewable`. Non-HTML consumers (full Rerun `.rrd` export,
future PDF, etc.) consume `bench.dataset` / `BenchData` outside the plugin
system. The data API is the integration point for alternative output
systems.

**What's given up:** a third party cannot add a *new output target* (PDF,
Three.js, Quarto) in their own repo. New targets require an upstream PR.
The user accepted this — the *plugins* (chart catalog) are extensible
without upstream changes, the *output targets* are not. Acceptable trade.

A standalone Rerun export, if needed later, lives outside the plugin
system as a finite exporter — `bench.export_rrd(dataset, blueprint_strategy)`
— consuming `BenchData` via the public data API.

### Q4: Plugin contract

The user accepted `BenchData` as the **stable public hand-off type**. The
contract is:

```python
class PlotPlugin(Protocol):
    name: str
    match: PlotFilter
    priority: int = 0
    def render(self, data: BenchData) -> pn.viewable.Viewable: ...
```

The pivotal commitment: internal bencher refactors must preserve the shape
of `BenchData`. Plugin authors' world is `(BenchData, PlotFilter, returns
pn.viewable.Viewable)` and nothing else. This breaks the inheritance-MRO
mess in `bench_result.py:42-60` because plugins consume `BenchData` as a
value, not by inheriting from a base class.

### Q5: Discovery, registration, selection — and the migration commitment

**Three sub-decisions:**

- **Discovery:** hybrid. Entry points (`bencher.plot_plugins` group) for
  distributed packages + `bencher.register_plugin(...)` for in-script.
  Both feed one registry. Entry-point-only would not help the in-script
  case (requires a packaged distribution). Explicit-only would mean a
  third-party plugin package can't "just work after pip install."
- **Backend grouping:** just a string namespace on each plugin. Exists for
  optional-dependency gating ("the whole plotly group fails if plotly is
  missing without breaking other plugins") and user-facing selection
  (`backend="plotly"`). No code complexity beyond a field.
- **Selection:** filter-and-order, not pick-one-winner. Today's
  `to_auto_plots()` runs many matching renderers. Default: run all plugins
  whose `match` accepts the data, in `priority` order. Filters:
  `include=[...]`, `exclude=[...]`, `backend="..."`, `only="name"` for
  single-plugin invocation. Override-by-name (a user-registered plugin with
  the same `name` as a built-in *replaces* the built-in).

**The big commitment in this question — built-in chart types migrate onto
the plugin mechanism.** The alternative was to keep built-ins on the
inheritance path and ship the plugin system alongside as a parallel path
("plugins are second-class — they run alongside built-ins but aren't
structurally identical"). That was rejected because:

1. Two mental models forever.
2. The plugin contract ages without internal pressure to keep it clean.
3. "Easily extensible by the user" becomes partly a lie — user plugins
   live in a side-system.
4. It's exactly the kind of decision you regret in a year — the same
   situation that produced the existing TODO in `bench_result_base.py:50-52`.

The migrate-onto-plugins decision is the bigger commitment but it's the
one that actually delivers the stated goals. Bencher itself becomes a
consumer of the public API — if the contract isn't clean enough for
first-party plugins, it's wrong.

### Q6: Does the plugin contract cover meta-views?

**The bite:** bencher today renders things that aren't really "a chart of
the dataset" — Optuna optimisation reports (`optuna_result.py`), the
Explorer (`explorer_result.py`), regression / aggregation reports, the
raw-xarray view (`dataset_result.py`), multi-cell video summaries
(`video_summary.py`). These need context beyond the dataset (the optimiser
study, baseline runs, widget wiring, ordering across the sweep).

**Alternatives:**

- **(a)** Single contract, fat `BenchData` (chosen). `BenchData` carries
  the dataset + var metadata + a set of *optional* fields:
  `optimizer_study`, `baseline_runs`, `cache`. A plugin's `match` filter
  handles availability via `requires={"optimizer_study"}`.
- **(b)** Plugin kinds — `chart` vs `report`. Two contracts, plugin
  authors must pick one. Cleaner separation; cost is two APIs and a
  "which kind do I write?" decision.
- **(c)** Single contract, capabilities registry. `data.require(OptimizerStudy)`
  raises if not present; capabilities themselves are registered (third
  parties can invent new context kinds). Most powerful; most upfront
  design.

**Why (a):**

1. The user just committed to one mental model in Q5 by migrating
   built-ins. Splitting into kinds undoes that decision two questions
   later.
2. (c) is over-engineered. The set of "context beyond the dataset" —
   optimiser study, baselines, run metadata — is small and slow-moving.
   A capabilities registry is YAGNI.
3. The kitchen-sink concern in (a) is solvable with discipline: optional
   fields are clearly typed `Optional[X]`, the `match` filter
   idiomatically checks them, and `BenchData` stays a frozen value type
   with no behaviour beyond accessors. It's a record, not a class
   hierarchy.
4. `PlotFilter` extends naturally: today it's `VarRange`-based on
   input/result var counts. Add `requires: frozenset[str]` (e.g.
   `{"optimizer_study"}`) to express "this plugin needs optimiser
   context." One-line extension.

**Cost:** every plugin sees the full `BenchData` whether it needs the
optional fields or not. Mitigated by: `BenchData` is small (six fields,
not sixty); the `match.requires` set makes "I depend on field X"
explicit; plugin examples in tree show idiomatic patterns.

**What's given up vs (b):** a slightly purer chart contract.
**What's given up vs (c):** the ability for a third party to extend
`BenchData`'s shape without an upstream PR. Probably acceptable — the
*plugins* are extensible without upstream changes, the *data context*
changes are slow enough that going through bencher is fine.

### Q7: Lifecycle, optional dependencies, failure modes

Five tightly-linked sub-decisions, accepted as a package:

- **(7a) Lazy module loading.** Entry points discovered at `import bencher`;
  plugin modules imported on first access. `import bencher` should not
  import plotly / holoviews / rerun. This is the load-time fix the current
  code badly needs anyway.
- **(7b) Skip-with-warning on missing deps.** A plugin that fails to
  import is dropped from the registry with a logged warning naming the
  plugin and the failing import. Matches the pattern that already works
  for Rerun (`rerun_result.py:68-74`). Hard-fail is too punitive when the
  user installed multiple optional plugin packages and only needs some.
- **(7c) Substitute an error pane during render.** Wrap each plugin's
  `render()` call in a try/except at the top level; on exception, replace
  that pane with a visible traceback pane. Add an opt-in `strict=True`
  flag on `bench.plot()` for development that re-raises instead. The
  default-tolerant path keeps reports shipping; the strict mode lets
  developers chase regressions.
- **(7d) Accept both class and function forms.** Decorator generates a
  class internally. Document the class form as canonical, function form
  as ergonomic shortcut.
- **(7e) Stateless plugin instances.** All per-render state goes through
  `BenchData`, including the optional `cache` handle.

**Non-obvious cost:** lazy loading + skip-on-missing-dep + tolerant render
combine to a system that *quietly degrades*. A plugin author who
introduces a syntax error or missing dep may not notice until a user
reports "this plot stopped showing up." Mitigations: a `bencher plugins
doctor` CLI subcommand (deferred — see open questions) that loads every
registered plugin eagerly and prints what's broken; CI guidance for
plugin repos to import-test their entry points.

### Q8: Migration phasing and the fate of the existing API

**Phasing alternatives:**

- **Big bang.** One PR landing infrastructure + every built-in migration +
  inheritance-tree deletion. Cleanest end state. Massive review surface;
  hard to bisect when something subtle breaks.
- **Gradual, no flag** (chosen). Land infrastructure first (it doesn't
  conflict — registry is empty, nobody queries it). Then migrate one
  result type per PR. The dispatcher in `bench_result.py` is updated to
  query the registry first, fall back to the inheritance method second.
  When all built-ins are migrated, one final cleanup PR removes the MRO
  and the fallback. Each PR is reviewable; behaviour is observable
  end-to-end at every step.
- **Gradual, behind a feature flag.** Same but gated on
  `bencher_use_plugins=True`. Rejected — flags become forever.

**Backwards-compat alternatives:**

- **(i) Preserve the surface, swap the internals** (chosen). `BenchResult`
  becomes a thin façade over `BenchData` + the plugin registry.
  `result.to_line()` looks up the `line` plugin and calls it.
  `result.to_auto_plots()` runs all matching plugins.
  `bench.add_plot_callback(callback)` becomes a sugar wrapper around
  `register_plugin`. **Zero user-visible breakage.**
- **(ii) Soft-deprecate the old surface.** Keep `to_<type>()` working with
  a `DeprecationWarning` pointing to `result.plot(name=...)`. Clean end
  state; breaks third parties who never upgrade.
- **(iii) Hard break.** Remove `to_<type>()` entirely. Smallest end
  state; biggest user disruption.

**Why (i):** the `to_<type>()` shims are tiny — each is one line that
looks up a plugin by name and calls `render`. The bencher codebase has
`to_<type>()` calls all over its own examples, docs, and tests;
preserving them is dramatically cheaper than rewriting all that.
Third-party benchmark code that calls `result.to_line()` keeps working
forever. The new `result.plot()` / `bench.plot()` API ships *alongside*
as the recommended forward path; nothing forces deprecation. If you ever
decide to deprecate, it's a separate decision — *not now*, while the
plugin system is still settling.

**Cost of (i):** carry the shim layer indefinitely. ~30 thin methods.
Acceptable. If a year from now the shims have rotted, revisit deprecation
*then* with usage data, not now.

**Migration order — six tiers, simplest first:**

The order matters because `BenchData`'s optional fields aren't fully
right on day one. Migrate in order of how much each one stresses the
schema:

1. **Trivial Holoviews charts** — Line, Heatmap, Curve, Bar, Scatter,
   Band, Table. All take `(input_vars, result_vars, dataset)` and produce
   a Holoviews chart. **Validates the basic contract.**
2. **3D / Plotly** — Surface (HoloViews + Plotly variants), Volume
   (Plotly only). Confirms the contract works across multiple backends
   and that lazy plotly imports are clean.
3. **Distribution and aggregation** — BoxWhisker, Violin, ScatterJitter,
   Histogram. Confirms statistical/aggregation cases.
4. **Data and media** — Dataset (raw xarray), Video, VideoSummary.
   Confirms non-chart panes go through fine.
5. **Schema-stretching** — Optuna (forces `optimizer_study`), Regression
   reports (forces `baseline_runs`), Explorer (may force a new field).
   Each likely lands with a `BenchData` schema bump.
6. **Embedded native viewer** — Rerun. The current iframe + base64-inlined
   `.rrd` (`ba7f09bd`, `c858ee24`) becomes one plugin. Confirms the
   "plugin is the composition unit" rule under a stress test.

After all six tiers land, the cleanup PR removes the inheritance tree
(`bench_result.py:42-60` MRO collapses, `bench_result_base.py` top-level
imports get reduced or moved).

**Don't migrate Rerun first.** Too much complexity at once.

A small additional piece for tier 1: introduce a single coordinator
helper `BenchResult._render_via_registry(plugin_name, **kwargs)` that all
the shim methods delegate to. That way the shims stay one-liners and any
policy change (error handling, caching) lives in one place.

## Contract surfaces

### `BenchData`

```python
@dataclass(frozen=True)
class BenchData:
    dataset: xr.Dataset
    input_vars: tuple = ()
    result_vars: tuple = ()
    plt_cnt_cfg: Optional[PltCntCfg] = None
    run_meta: RunMeta = field(default_factory=RunMeta)
    optimizer_study: Optional[Any] = None
    baseline_runs: tuple["BenchData", ...] = ()
    cache: Optional[CacheHandle] = None

    def has(self, capability: str) -> bool: ...
    def with_changes(self, **kwargs) -> "BenchData": ...

    @classmethod
    def fake(cls, *, dataset=None, input_vars=(), result_vars=(),
             plt_cnt_cfg=None, **overrides) -> "BenchData": ...
```

`BenchData.fake()` is the test constructor for plugin authors: defaults
`dataset` to an empty `xr.Dataset` and `plt_cnt_cfg` to a zero-counted
config so a plugin can be unit-tested in one line.

### `PlotPlugin`

```python
@runtime_checkable
class PlotPlugin(Protocol):
    name: str
    backend: str
    match: PlotFilter
    priority: int
    requires: frozenset[str]
    def render(self, data: BenchData) -> pn.viewable.Viewable: ...
```

Function form via decorator (sugar — synthesises a `_FunctionPlugin`
internally):

```python
@bencher.plot_plugin(name="my.line", backend="user",
                     match=PlotFilter(float_range=VarRange(1, 1)),
                     priority=10,
                     requires={"optimizer_study"})  # optional
def my_line(data: BenchData) -> pn.viewable.Viewable:
    ...
```

### `PluginRegistry`

```python
class PluginRegistry:
    def register(self, plugin: PlotPlugin) -> None: ...
    def unregister(self, name: str) -> None: ...
    def clear(self) -> None: ...
    def get(self, name: str) -> Optional[PlotPlugin]: ...
    def all(self) -> tuple[PlotPlugin, ...]: ...
    def select(self, data: BenchData, *,
               include=None, exclude=None,
               backend=None, only=None) -> tuple[PlotPlugin, ...]: ...
    def render(self, data: BenchData, *,
               include=None, exclude=None,
               backend=None, only=None,
               strict: bool = False) -> tuple[tuple[str, pn.viewable.Viewable], ...]: ...
```

Module-level helpers: `register_plugin(plugin)`, `unregister_plugin(name)`,
`get_registry()`. All re-exported at the top level (`bencher.register_plugin`,
etc.).

## Runtime model

### Discovery

- **Entry-point group:** `bencher.plot_plugins`. Discovered lazily on first
  registry lookup. The metadata scan is cheap; module import only happens
  on access.
- **Three resolution shapes** accepted from an entry point:
  1. A single `PlotPlugin` instance.
  2. A no-arg callable returning a `PlotPlugin`.
  3. A no-arg callable returning an iterable of `PlotPlugin` (factory style
     — useful for shipping a whole backend's worth of plugins from one
     entry point).
- **Failure mode:** broken plugin (missing dep, import error, factory
  exception) is logged at WARNING level and dropped. Other plugins
  unaffected.

### Selection

```python
plugins = registry.select(data,
                          include=None,        # whitelist by chart-type name
                          exclude=None,        # blacklist by chart-type name
                          backend=None,        # PREFERRED backend (not a hard filter)
                          only=None)           # short-circuit to a single chart type
```

- `only` short-circuits the match filter (explicit by-name selection
  bypasses dimension-shape checking — the user said they want this one).
- Otherwise, candidates are filtered by `include`/`exclude`,
  capability-gated (every name in `plugin.requires` must satisfy
  `data.has(name)`), and matched against `data.plt_cnt_cfg` via the
  existing `PlotFilter.matches_result(...)` rule.
- **Backend resolution**: matched plugins are grouped by chart-type name and
  each group resolves to ONE implementation — the `backend` param's when it
  provides one, otherwise the highest-priority. A chart type the preferred
  backend does not implement still renders through its best other backend.
  This is the mechanism that swaps the rendering library under an unchanged
  set of plotters: `select(data, backend="holoviews")` and
  `select(data, backend="rerun")` return the same chart types, differently
  implemented.
- Chosen plugins sorted by `(-priority, name)`. Higher priority first;
  alphabetical tiebreak.

### Render

```python
panes = registry.render(data, ..., strict=False)
# returns ((name, pane), ...) in priority order
```

- Each plugin's `render()` runs in a `try/except`; on exception, log at
  ERROR level and substitute a Markdown traceback pane. `strict=True`
  re-raises immediately.
- Plugins returning `None` are dropped silently from the output (this is
  the intentional "plugin examined the data and decided not to render"
  path; it is **not** an error).

### Override semantics

The registry is keyed by `(name, backend)`. Re-registering the same pair
replaces the prior entry — a user-supplied plugin replaces a built-in by
sharing its name and backend. Registering the same chart-type name under a
*different* backend coexists instead: it becomes an alternative
implementation, reachable via priority, the `backend` preference, or
`get(name, backend)`. No flags, no monkey-patching.

## Migration plan

### Phasing principles

- **Gradual, no flag.** Each tier is one PR, mechanical, isolated, easy to
  revert. Behaviour is observable end-to-end at every step.
- **Preserve-surface-swap-internals.** The `to_<type>()` family lives on
  as one-line shims dispatching through
  `BenchResult._render_via_registry(name, **kwargs)`. Zero user-visible
  breakage. New `result.plot()` / `result.plot(name=...)` ships alongside.
- **Inheritance fallback during transition.** Until the cleanup PR, the
  dispatcher queries the registry first, falls back to the inheritance
  method second. This means tiers can land in any order without being
  blocked on each other (although the recommended order minimises schema
  churn — see below).

### Tier order

1. **Trivial Holoviews charts** — `LineResult`, `HeatmapResult`,
   `CurveResult`, `BarResult`, `ScatterResult`, `BandResult`,
   `TableResult`. Validates the contract on the simplest cases.
2. **3D / Plotly** — `SurfaceResult` (HV + Plotly variants), `VolumeResult`.
   Confirms contract works across multiple backends; cleans up the
   unguarded plotly imports in `volume_result.py:9` and
   `surface_result.py:4`.
3. **Distribution and aggregation** — `BoxWhiskerResult`, `ViolinResult`,
   `ScatterJitterResult`, `HistogramResult`, `TabulatorResult`.
4. **Data and media** — `DataSetResult`, `VideoResult`, `VideoSummary`.
   Confirms non-chart panes pass through cleanly.
5. **Schema-stretching** — `OptunaResult` (forces `BenchData.optimizer_study`),
   `RegressionReport` / `RegressionResult` (forces `BenchData.baseline_runs`),
   `ExplorerResult` (may force a new field). Each likely lands with a
   `BenchData` schema bump. Schema additions ship *with* the tier PR, not
   as a separate refactor.
6. **Embedded native viewer** — `RerunResult`. The current iframe +
   base64-inlined `.rrd` path becomes one plugin. Stress test for the
   "plugin is the composition unit" rule.
7. **Cleanup** — collapse the `BenchResult` MRO in
   `bench_result.py:42-60`, lift the top-level imports out of
   `bench_result_base.py:8-12`, optionally rename
   `bencher/results/<...>` → `bencher/plugins/<backend>/<name>.py`.

## Tier-0 status (this branch)

What's in the tier-0 PR (`feature/plugin-system`, PR #932):

| File | Purpose |
|---|---|
| `bencher/plugins/bench_data.py` | `BenchData` (frozen), `RunMeta`, `CacheHandle` protocol, `BenchData.fake()` test constructor |
| `bencher/plugins/plugin.py` | `PlotPlugin` protocol + `@plot_plugin` decorator |
| `bencher/plugins/registry.py` | `PluginRegistry` — register, override-by-name, lazy entry-point discovery, `select(...)` with priority/include/exclude/backend/only filters, `render(...)` with error-pane substitution and `strict=True` opt-in |
| `bencher/plugins/__init__.py` | Public surface |
| `bencher/__init__.py` | Top-level re-exports of the plugin API |
| `test/test_plugins.py` | 23 unit tests covering registration, override semantics, selection, capability gating, render happy/error paths, `strict=True` re-raise, lazy entry-point loading, factory loading |
| `docs/plot_plugin_design.md` | This document |

What is **not** changed:

- No existing result class (`LineResult`, `HeatmapResult`, etc.) is touched.
- The inheritance MRO in `bench_result.py` is unchanged.
- No existing call site queries the registry.
- No public API has changed shape; only new symbols are exposed.

Verification at tier-0:

- `pixi run format` — clean
- `pixi run ruff-lint` — clean
- `pixi run pylint` — 10.00/10
- `pixi run ty` — no diagnostics on new files
- Plugin tests: 23/23 pass
- Full test suite (1212 tests, excluding doc-generation): all pass
- `import bencher` smoke test: plugin API reachable at top level

## Open tactical questions

These were deferred to implementation time — they are not architectural and
can be answered when the first plugin actually needs the answer. They are
listed here so a continuing agent doesn't think they were forgotten.

- **Repo layout for migrated plugins** — `bencher/plugins/<backend>/<name>.py`
  vs keeping `bencher/results/` as the home? Recommendation: rename in the
  tier-7 cleanup PR, not earlier (avoids churn during migration).
- **`BenchResult` integration** — when tier 1 starts, `BenchResult` needs a
  helper like `_render_via_registry(plugin_name, **kwargs)` that the
  `to_<type>()` shims delegate to. Single place for policy (error
  handling, caching, etc.). The dispatcher should fall back to the
  inheritance method if no plugin is registered for that name, until the
  cleanup PR removes the fallback.
- **Plugin doctor CLI** — `bencher plugins list` / `bencher plugins doctor`
  to eagerly load every registered plugin and report what's broken.
  Compensates for the silent-degradation property of lazy loading +
  skip-on-missing-dep. Useful, not blocking.
- **`PlotFilter` extensions beyond `requires`** — predicate functions for
  cases like "match if a var named `time` exists." Add only when a real
  plugin needs it; don't pre-design.
- **External plugin template repo** — `bencher-plugin-template` with a
  one-plugin example, entry-point declaration, CI that runs the doctor
  command. Useful for third-party adoption; not blocking.
- **`add_plot_callback` reconciliation** — today's `Bench.add_plot_callback`
  appends a callable to `self.plot_callbacks` (`bencher.py:149-164`). The
  shim layer should make this a thin wrapper around `register_plugin` so
  the callback list and the registry don't drift.

## Handoff guide

To start tier 1:

1. **Pick a target.** `LineResult` is the cleanest first migration. Read
   `bencher/results/holoview_results/line_result.py`. Note its existing
   `to_line()` method and its `PlotFilter` usage.

2. **Decide where the plugin module lives.** For tier 1, recommended path:
   create `bencher/plugins/builtin/line.py`. (The folder rename across all
   backends is deferred to tier 7 to avoid churn during migration.)

3. **Register the plugin.** Inside the new module:

   ```python
   from bencher.plugins import BenchData, PlotFilter, VarRange, plot_plugin

   @plot_plugin(name="holoviews.line", backend="holoviews",
                match=PlotFilter(float_range=VarRange(1, 1), ...))
   def render_line(data: BenchData) -> pn.viewable.Viewable:
       # Move the rendering logic out of LineResult.to_line() into here.
       ...
   ```

   Make sure the plugin module is imported during `import bencher` so the
   built-in is available without entry-point machinery (built-ins ship
   in-tree). The cleanest hook is `bencher/plugins/builtin/__init__.py`
   importing every built-in plugin module, with `bencher/plugins/__init__.py`
   importing the `builtin` package.

4. **Add the dispatcher helper.** Tier 1 introduces
   `BenchResult._render_via_registry(name, **kwargs)`:

   ```python
   def _render_via_registry(self, name: str, **kwargs):
       data = self._to_bench_data()  # adapter from BenchResultBase to BenchData
       picked = get_registry().select(data, only=name)
       if picked:
           return picked[0].render(data)
       # Fallback to the inheritance method during migration; remove in cleanup PR.
       return getattr(self, f"_legacy_to_{name.split('.')[-1]}")(**kwargs)
   ```

5. **Replace the legacy method with a shim.** Rename
   `LineResult.to_line()` to `LineResult._legacy_to_line()` (kept as the
   inheritance fallback during migration). Add a new shim:

   ```python
   def to_line(self, **kwargs):
       return self._render_via_registry("holoviews.line", **kwargs)
   ```

6. **Add a unit test** under `test/` that constructs a `BenchData.fake(...)`
   and asserts the registered plugin renders a `pn.viewable.Viewable`.
   Existing `test_line_result.py` should continue to pass without
   modification — that's the point of the preserve-surface design.

7. **Run `pixi run ci`.** Tier 1 should not change any existing test's
   behaviour beyond the new plugin tests. Every other test still goes
   through the same `to_line()` entry point and gets the same output.

The contract surfaces (`BenchData`, `PlotPlugin`, `PluginRegistry`) are
considered stable. If a tier discovers a need to change `BenchData`'s
shape (e.g. tier 5 adding `optimizer_study` semantics), that change ships
*with* the tier PR — it is part of the schema evolution this design
accepts.

When in doubt about a decision: re-read the [decision walkthrough](#decision-walkthrough-the-grilling)
above. The design was reached deliberately, and the tradeoffs that look
suboptimal in isolation often have a load-bearing reason in another
question's resolution.
