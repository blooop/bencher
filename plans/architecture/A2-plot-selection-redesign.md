# A2 — Plot Selection Redesign

**Status:** Proposal. Depends on A1 phases 0–2 (registry in place, built-ins wrapped).
**Scope:** How bencher decides *which* plots to show for a given sweep, and how users
override that. A1 covers how plots are produced; A3 covers the data they receive.

---

## 1. How selection works today (verified)

1. `PltCntCfg` (`bencher/plotting/plt_cnt_cfg.py`, 83 lines) counts the sweep shape:
   `float_cnt`, `cat_cnt`, `vector_len`, `result_vars`, `panel_cnt`, `repeats`,
   `inputs_cnt`.
2. Each result class declares a `PlotFilter` of `VarRange`s over those counts
   (`bencher/plotting/plot_filter.py:66-91`) and checks it inside its own `to_plot`.
3. `BenchResult.to_auto()` (`bench_result.py:169-222`) iterates a **hard-coded list**
   (`default_plot_callbacks()`: Bar, BoxWhisker, Curve, Line, Heatmap, Histogram,
   Volume, Panes) and appends *every* callback that doesn't filter itself out or throw.
4. User control is via `plot_callbacks` in `BenchCfg` — a list of **callables** — or
   `plot_list`/`remove_plots` kwargs, also callables.

### What's good (keep it)

The `VarRange`/`PlotFilter` shape-matching DSL is a genuinely sound idea — declarative,
testable, and already the matching language of #932's plugin protocol. The failure
diagnostics (`PlotMatchesResult.matches_info`) are a great debugging affordance.

### The problems

| # | Problem | Evidence |
|---|---|---|
| P1 | **No ranking — all matches render.** A 2-float/1-cat sweep with repeats can produce bar + box + curve + line + heatmap, mostly redundant. Reports are slow and noisy; users scroll. | `to_auto` loop appends every success |
| P2 | **Selection knowledge is scattered.** Which plot handles which shape lives in 17 class bodies; the candidate list lives in `default_plot_callbacks()`; nothing can answer "what would render for this sweep?" without executing renderers. | `bench_result.py:132-145` |
| P3 | **Plot choices aren't serializable.** `plot_callbacks` holds function objects — fragile for the collect/render split (pickled through `BenchResult`), impossible to express in the YAML sweep format, and unusable from a CLI. | `bench_cfg.py` plot_callbacks |
| P4 | **Counts are too coarse a signature.** `float_cnt/cat_cnt` can't express "temporal axis present", "result is an image", "data is monotonic", "categorical with >20 levels (heatmap unreadable)". Hence special-case branches in `to_auto_plots` (over_time band plot, aggregation views are hand-wired, `bench_result.py:279-322`). | read of to_auto_plots |
| P5 | **Failure = silent log line.** A plot that matched but threw is logged and dropped (`bench_result.py:216-217`); the user sees fewer plots with no explanation (registry error panes in #932 fix the rendering half; selection still can't say *why* something didn't appear). | |

## 2. Target design

### 2.1 One selection function, three stages

```
candidates = registry.plugins(backend=cfg.plot_backend)        # A1
eligible   = [p for p in candidates if p.match.matches(signature)]   # hard constraints
chosen     = rank(eligible, signature, intent)                  # soft scoring
```

All selection logic lives in one module (`bencher/plugins/selection.py`), and a public
`explain_selection(bench_result) -> str` renders the full eligible/chosen/rejected
table with reasons — turning P2 and P5 into a feature (append it to the report's
sweep-summary tab when `print_debug` is on).

### 2.2 Richer signature: extend `PltCntCfg` into `DataSignature`

Add derived, *cheaply computable* facts alongside the existing counts (keep the counts —
backward compatible):

- `has_time: bool`, `time_steps: int` (kills the hand-wired over_time branch)
- `result_kinds: dict[name, Kind]` where Kind ∈ {float, bool, vec, image, video, path,
  container, dataset} (replaces `panel_cnt` special-casing)
- `cat_levels: dict[name, int]` (lets heatmap demote itself for 50-level categoricals)
- `samples_per_point: int` (true repeats actually present, not configured repeats —
  matters now that missing values are NaN)

`PlotFilter` grows optional predicates over these (`requires: {"time"}` already exists
in #932's plugin protocol — reuse it rather than inventing a second mechanism).

### 2.3 Ranking instead of render-everything

Each plugin declares `specificity` (how narrow its filter is — computable from the
`VarRange` widths, no manual numbers) and an `intent` tag:
`overview | distribution | relationship | detail | diagnostic`.

Default policy: pick the highest-specificity plugin **per intent**, drop the rest.
That yields e.g. {overview: heatmap, distribution: box-whisker, detail: line} instead
of seven near-duplicates. Policies are data, not code:

```python
cfg.plot_policy = "best_per_intent"   # default
cfg.plot_policy = "all_matching"      # today's behavior, kept for compatibility
cfg.plot_policy = "minimal"           # single best plot
```

**Migration safety:** ship with `all_matching` as default for one release, emit the
`explain_selection` table, and flip the default only after gallery review.

### 2.4 Serializable plot specs (fixes P3)

Replace callables with specs everywhere user-facing:

```python
bench.plot_sweep(..., plots=["heatmap", {"name": "curve", "agg_fn": "median"}])
```

- Spec = plugin name + kwargs → trivially picklable, YAML-able, CLI-able
  (`bencher render result.pkl --plots heatmap,curve`).
- `plot_callbacks` (callables) keeps working via a shim plugin wrapper, deprecated
  through the existing `__getattr__` alias mechanism.
- This is what makes the collect/render split clean: the render process receives
  data + *names*, never live function objects (see A3).

## 3. Migration phases

**Phase S1 — signature enrichment.** Extend `PltCntCfg` with the new fields (additive,
computed in one place from the dataset). Verify: all existing `PlotFilter` matches are
unchanged (`pixi run ci`); add unit tests asserting each new field on small synthetic
sweeps.

**Phase S2 — centralize matching.** Move the match check out of each `to_plot` into the
registry-driven `to_auto` (A1 Phase 2 does most of this). Add `explain_selection()` and
a test asserting its output for 3 canonical sweep shapes. Behavior must be identical.

**Phase S3 — plot specs.** Implement name+kwargs specs, registry lookup by name,
deprecation shim for callables. Update YAML sweep format and docs. Verify: round-trip
a spec through save→load→render (`pixi run test-split`).

**Phase S4 — ranking.** Add `specificity`/`intent`, implement `best_per_intent` behind
`plot_policy` (default still `all_matching`). Regenerate the full gallery
(`pixi run generate-docs`) with the new policy on a branch; owner reviews the visual
diff before the default flips.

**OWNER DECISION points:** the intent taxonomy (2.3), and when/whether to flip the
default policy (Phase S4) — that changes every user's default report.

## 4. Interactions

- **A1**: phases S2+ assume plugins exist; `specificity`/`intent` are plugin fields.
- **A3**: specs (names+kwargs) are part of the serialized run manifest.
- **PR #923 / plans/08** (BenchCfg split): `plot_policy`, `plot_backend`, `plots` form
  a natural `PlotCfg` group — coordinate so the flags land in the grouped layout.
