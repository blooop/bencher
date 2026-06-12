# A1 — Rendering Backend Unification (resolving #830 vs #932)

**Status:** Proposal — needs owner sign-off on the target architecture before any code.
**Scope:** How plots are *produced and saved*. Plot *selection* is A2; the data contract
both depend on is A3. Read A3 first — `BenchData` is the keystone.

---

## 1. Current architecture (verified against the code)

- Every plot type is a **base class of `BenchResult`** — a 17-way multiple inheritance
  in `bencher/results/bench_result.py:42-63` (`VolumeResult`, `BoxWhiskerResult`,
  `LineResult`, ..., `HoloviewResult`, `OptunaResult`). The class both *holds the data*
  (`self.ds`, `self.bench_cfg`, `self.plt_cnt_cfg`) and *is* every renderer.
- Renderers build HoloViews objects wrapped in Panel; `BenchReport.save()` uses Panel's
  embed pipeline, which pre-computes widget states (~16s for over_time reports).
- The collect/render split (`bencher/render.py`) pickles the whole `BenchResult` to move
  it across processes.

**Consequences:** third parties cannot add a plot type without subclassing the god
class; a backend swap (HoloViews→Plotly) means rewriting methods *inside* the
hierarchy (which is exactly what PR #830 does, hence its 2,195 deleted lines and
conflict surface); renderer crashes are handled by scattered broad excepts.

## 2. What the two open PRs actually contain

**PR #932 (plugin infra, tier 0, additive — CI green):**
- `PlotPlugin` protocol: `name`, `backend`, `match: PlotFilter`, `priority`,
  `requires: frozenset[str]`, `render(data: BenchData) -> pn.viewable.Viewable`.
- Frozen `BenchData` value type: `dataset` (xr.Dataset), `input_vars`, `result_vars`,
  `plt_cnt_cfg`, `run_meta`, optional `optimizer_study`/`baseline_runs`, `cache` handle.
- `PluginRegistry`: idempotent registration, entry-point discovery
  (`bencher.plot_plugins` group), `select(data, include/exclude/backend/only)`,
  `render(...)` with per-plugin error panes. `@plot_plugin` decorator for functions.
- **Zero integration** — nothing calls the registry yet. Its design doc already plans
  "tier 1: migrate built-in chart types onto the registry."

**PR #830 (Plotly port — CI red, 2.5 months stale):** two separable things:
1. **Fast save path** (`bench_report.py`): `_extract_plotly_figures` /
   `_save_tab_plotly` walk the Panel tree, serialize `go.Figure`s as JSON-in-HTML via
   `plotly.io.to_html` instead of Panel embed → 16s → 0.13s. Falls back to
   `Panel.save(embed=True)` when Bokeh panes are present.
2. **Renderer rewrites**: every result class rebuilt on `go.Figure`
   (`_build_time_dropdown_fig` replaces HoloMap+slider with a Plotly dropdown,
   `DatasetWrapper` shims `hv.Dataset`), HoloViews imports deleted.

## 3. The decision, reframed

The PR-triage framing ("pick #830 or #932") was too coarse. The components compose:

| Component | Verdict |
|---|---|
| #932 plugin contract + registry | **Adopt as the skeleton.** It is additive, tested, and CI-green today. |
| #830 fast save path | **Land independently and early.** It keys off pane *types*, not the renderer architecture. Most of the 120x is here. |
| #830 Plotly renderers | **Re-land as plugins** (`backend="plotly"`), not as in-place rewrites of the mixin hierarchy. |
| #830's deletion of HoloViews | **Defer.** HoloViews renderers become a parallel plugin set; delete only after Plotly plugins reach parity and a deprecation cycle passes. |

This converts an irreversible either/or into a reversible migration: both backends
coexist behind one contract, the default flips when Plotly is ready, and HoloViews
removal becomes a dependency-trim at the end instead of a big-bang rewrite.

**OWNER DECISION required:** confirm this synthesis, or explicitly choose #830's
big-bang path (faster to the perf win, but re-conflicts with main and forecloses the
plugin contract validating against two backends — the strongest test a contract can get).

## 4. Target architecture

```
Bench.collect() ──► BenchData (frozen: dataset + vars + meta)        [A3]
                         │
            PluginRegistry.select(BenchData)                          [A2 decides how]
                         │
        ┌────────────────┼─────────────────┐
   holoviews backend   plotly backend   user plugins (entry points)
   (existing renderers) (from #830)
                         │
            list[(name, Viewable | go.Figure)]
                         │
            BenchReport.save()  ── fast path: plotly figures → static HTML
                                ── fallback: Panel embed for Bokeh/widget panes
```

- `BenchResult` survives as a **facade**: `.to(HeatmapResult)`, `.to_auto()` etc. keep
  working by delegating to the registry (plugin looked up by name). The 17-class MRO
  shrinks over time but no user-facing API breaks.
- A renderer crash produces an error pane (registry behavior in #932), replacing the
  scattered `try/except Exception` blocks in `to_auto` (`bench_result.py:214-217`).

## 5. Migration phases (each independently shippable & revertable)

**Phase 0 — land the skeleton.** Rebase and merge #932 as-is (it is additive).
Verify: `pixi run ci`, plugin tests pass, no behavior change.

**Phase 1 — fast save path.** Extract ONLY `bench_report.py`'s
`_extract_plotly_figures` / `_extract_markdown` / `_has_bokeh_panes` /
`_save_tab_plotly` from #830 into a fresh PR. Today only `SurfaceResult`/`VolumeResult`
emit Plotly, so initial benefit is small — that's fine; it's the highway later phases
drive on. Verify: `pixi run test-split` plus a visual diff of one saved report per
result type (`plans/architecture/` should gain a checklist of golden examples).

**Phase 2 — wrap built-ins as plugins.** For each existing result class, register a
thin plugin whose `render(data)` constructs the class from `data` and calls its
`to_plot`. `match` comes from the class's existing `PlotFilter`; `backend="holoviews"`.
`to_auto` switches from `default_plot_callbacks()` to `registry.select()`. This is the
contract-validation phase — **no renderer logic changes**. Verify: report output
byte-comparable (or visually identical) before/after; full `ci` + `test-split`.

**Phase 3 — port renderers to Plotly as plugins.** Cherry-pick #830's trace-building
logic (`_build_time_dropdown_fig`, per-type `make_traces` functions) into
`bencher/plugins/plotly/` one plot type at a time, `backend="plotly"`,
same `match` filters, *lower* priority than holoviews initially. A
`BenchCfg.plot_backend: str = "holoviews"` flag flips priority. Each type lands as its
own PR with a side-by-side example in the gallery. Verify per type: the generated
example for that type renders, plus the over_time variant.

**Phase 4 — flip the default & deprecate.** Set `plot_backend="plotly"` default; one
minor release later, move HoloViews plugins behind an extra (`holobench[holoviews]`);
later still, delete. Each step is a one-line revert if users object.

## 6. Risks & open questions

- **Widget-dependent features** (image/video sliders, explorer/dataset viewers) are
  Panel/Bokeh-native; they stay on the embed save path indefinitely. The plugin
  contract returns `pn.viewable.Viewable`, which covers them — but document that
  reports mixing them lose the fast-save benefit for that tab.
- **`BenchResult.to()` semantics**: `.to(ResultType)` passes class objects. Facade must
  map class → plugin name; new code should pass names (A2 makes them serializable).
- **Plugin cache handle** (#932's `CacheHandle`) overlaps with A4's caching redesign —
  keep it a Protocol so A4 can swap the implementation under it.
- **Performance regression guard**: the Performance Tracking CI job should gain a
  `report.save()` timing benchmark before Phase 3, so the 120x claim is continuously
  measured rather than asserted.
