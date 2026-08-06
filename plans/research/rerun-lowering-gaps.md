# Rerun lowering gaps — evidence dossier for ticket #1110

AFK groundwork for the grilling ticket "What happens to a report item with no rerun
lowering?" (blooop/bencher#1110). This is **input to the owner's decision session, not a
decision**. Every repo claim is cited `file:line` against this branch
(`research/rerun-lowering-gaps-1110`, forked from main at `cfd551a3`); every measurement
names the command that produced it. Prototype scripts live in
`plans/research/prototypes_1110/`, their outputs in `plans/research/prototypes_1110/out/`
(the `.rrd` recordings are gitignored — `.gitignore:192` — regenerate them with the
commands at the bottom; the PNGs are committed).

Rerun view vocabulary used below (rerun-sdk 0.35.0, the version pinned in
`pyproject.toml:93`): `SeriesLines`/`SeriesPoints` (time-series), `BarChart`, `Tensor`,
`TextDocument` (renders markdown), `EncodedImage`, `AssetVideo`, `Points2D/3D`,
`LineStrips2D`, `Mesh3D`, `DataframeView`, and Blueprint containers
(`Vertical/Horizontal/Tabs/Grid`).

---

## A. The full no-lowering set, measured not guessed

Sources walked: `_builtin_specs()` (`bencher/plugins/builtins.py:81-90`),
`_named_only_specs()` (`bencher/plugins/builtins.py:120-139`), the `to_auto_plots`
report sequence (`bencher/results/bench_result.py:444-564`), `BenchReport`
(`bencher/bench_report.py:173-200`), optuna (`bencher/results/optuna_result.py:233-367`,
`bencher/optuna_conversions.py:53-73`), `ExplorerResult`
(`bencher/results/explorer_result.py:10`), `report_render_failure`
(`bencher/results/render_failure.py:34`).

A structural note that applies to every `filter()`-based plugin: the outer return is
always a `pn.Row` of per-result-var panes (`bencher/results/bench_result_base.py:785`,
`:714`, `:731`); the leaf element cited below is what sits inside. Recursion for extra
dims wraps leaves in `pn.Row/Column/Tabs`
(`bencher/results/composable_container/composable_container_panel.py:43-49`) — those
containers lower natively to `rrb.Vertical/Horizontal/Tabs` (A6 §3,
`plans/architecture/A6-grammar-of-nd-data.md:277`).

### A.1 Auto-selected plugins (`builtins.py:82-89`)

| item | current output type | plausible rerun lowering | fidelity | what's lost |
|---|---|---|---|---|
| `bar` | `hv.Bars` via hvplot (`bencher/results/holoview_results/bar_result.py:138`) | `rr.BarChart` | approx | categorical tick labels (BarChart is index-labelled), grouped-bar layout, hover |
| `box_whisker` | `hv.Overlay` of `hv.BoxWhisker` (`.../distribution_result/box_whisker_result.py:78`, built `.../distribution_result.py:66-80`) | none native (A6 §3 declared gap, `A6-grammar-of-nd-data.md:283`); jittered `Points2D` or rasterize | **none**/approx | quartile-box semantics; jitter shows samples, not the five-number summary |
| `curve` | `hv.Curve` **overlaid with `hv.Spread`** when `<var>_std` exists (`.../holoview_result.py:298,302` and `:313,317`) | mean → `SeriesLines` native; band → the Spread gap (see §C) | approx | the filled ±σ band (A6 §3 declared gap, `A6-grammar-of-nd-data.md:282`) |
| `line` | `hv.Curve` via hvplot (`.../line_result.py:168`); tap variant returns `pn.Row` driven by `hv.streams.PointerXY` (`.../holoview_result.py:518,526`) | `SeriesLines` | native (plain) / approx (tap) | the pointer-linked image/video preview pane; rerun's own selection linking is a different interaction |
| `heatmap` | `hv.HeatMap` (`.../heatmap_result.py:130`, HoloMap path `:124`); tap variants `:163-166` and `hv.streams.Tap` + `hv.DynamicMap` at `:202-211` | `rr.Tensor` (A6 §3 "native/approx", `A6-grammar-of-nd-data.md:281`) | approx | real coordinate axes (Tensor is index-addressed), colorbar-with-units, tap-to-detail linking |
| `histogram` | `hv.Histogram` via `hvplot(kind="hist")` (`bencher/results/histogram_result.py:57`) | `rr.BarChart` over binned counts | approx | bin-edge x axis (indices instead of values), hover counts |
| `volume` (plotly, **auto-selected**) | `pn.pane.Plotly` wrapping `go.Volume` (`bencher/results/volume_result.py:88-115`) | `rr.Tensor` (3D, slice navigation) or `Points3D` colored by value | approx | isosurface/opacity volume *rendering* and free 3D rotation of the rendered cloud; Tensor gives slices, not the gestalt. Rasterize keeps the gestalt but freezes one camera (see §B) |
| `panes` (`PaneResult.to_panes`, `bencher/results/pane_result.py:21-30`) | per result type, leaf from `ds_to_container` (`bencher/results/bench_result_base.py:1374-1441`) | see breakdown below | mixed | — |

`panes` breakdown (the per-type leaves):

| result type | current leaf | rerun lowering | fidelity | what's lost |
|---|---|---|---|---|
| `ResultImage` | raw path auto-resolved to image pane (`bench_result_base.py:1441`, no `to_container` at `variables/results.py:345`) | `rr.EncodedImage` | native | nothing material |
| `ResultVideo` | raw path → video pane; explicit `pn.pane.Video` on video paths (`bencher/results/video_controls.py:18`) | `rr.AssetVideo` | native* | *codec caveat: AssetVideo is MP4-container; whatever bencher writes must stay in the supported set |
| `ResultString` | markdown-ish raw string (`bench_result_base.py:1441`) | `rr.TextDocument` (markdown) | native | nothing material |
| `ResultPath` / `ResultContainer` | `pn.widgets.FileDownload(embed=True)` (`variables/results.py:326-328`) / raw value | none — no download affordance in a rerun viewer; a `TextDocument` path listing at best | **none** | the click-to-download artifact |
| `ResultRerun` | `pn.pane.HTML` iframe viewer per sample (`variables/results.py:458-463`, `bencher/utils_rrd.py:128-132`) | merge into the report recording (what `rerun_summary` already does, `bencher/results/rerun_summary.py:195-255`) | native | nothing — this is the destination working as intended |
| `ResultDataSet` | stored object via declared container (`bench_result_base.py:1263-1350`) | `DataframeView` *(pending the blocked-by research ticket)* or `TextDocument` table | approx/unknown | depends on the DataframeView findings #1110 is blocked by |
| over_time image/video slider | base64 `<img>`/`<video>` swapped by a bokeh `CustomJS` slider (`bench_result_base.py:1026-1101`) | a rerun **timeline** | native — *better than today* | nothing; the slider hack exists because panel lacks what rerun has natively |

### A.2 Named-only plugins (`builtins.py:120-139`)

| item | current output type | plausible rerun lowering | fidelity | what's lost |
|---|---|---|---|---|
| `violin` | `hv.Overlay` of `hv.Violin` (`.../distribution_result/violin_result.py:75`) | none native (A6 §3 gap, `A6-grammar-of-nd-data.md:283`) | **none**/approx | density silhouette; jittered points ≠ KDE shape |
| `scatter_jitter` | jittered `hv.Scatter` (`.../scatter_jitter_result.py:100`) | `Points2D` | approx | categorical x tick labels |
| `scatter` | `hv.Scatter` via hvplot (`.../scatter_result.py:73`) | `Points2D`/`SeriesPoints` | approx | categorical axes labels, hover |
| `band` | **`hv.Area` ×2** (p10-p90 `:272`, p25-p75 `:280`) + median `hv.Curve` (`:288`) + samples `hv.Scatter` (`:300`), composed `.../band_result.py:295-309` | the Spread gap, doubled: 4 edge lines + median | **none** native; approx via lines | *two* nested filled bands — the worst case of §C's finding; also used by `to_auto_plots`'s over-time section (`bench_result.py:559`) |
| `surface` (plotly) | `pn.pane.Plotly`: `go.Surface` mean (`.../surface_result.py:132`) **plus ±1σ surfaces when repeats>1** (`:148`), pane at `:172` | `rr.Tensor` (A6 §3) or a real `Mesh3D` triangulation | approx | 3D relief under Tensor; the ±1σ companion surfaces have no Tensor expression at all |
| `table` | `hv.Table` (`.../table_result.py:16`) | `DataframeView` (pending) or `TextDocument` markdown table | approx | nothing much (static today) |
| `tabulator` | `pn.widgets.Tabulator` (`.../tabulator_result.py:78`) | `DataframeView` (pending) | approx/**none** | widget interactivity: sorting, paging, filtering (A1 §6 already flagged panel-native, per ticket) |
| `dataset` | arbitrary stored object via renderer (`bencher/results/dataset_result.py:33`, `bench_result_base.py:1417`) | none in general | **none** | whatever the arbitrary container renders |
| `video_summary` | composed grid written to one video, `pn.pane.Video` (`bencher/results/video_summary.py:141-146`) | `rr.AssetVideo` | native* | play-speed/loop button row (`video_controls.py:61-75`) — the viewer has its own transport, arguably no loss |
| `rerun`, `rerun_summary`, `rerun_grid` | `.rrd` + iframe (`bencher/results/rerun_result.py:142-144`, `rerun_summary.py:189`) | identity | native | — |
| `xy_scatter` | `hv.Points` (`.../xy_scatter_result.py:71`) | `Points2D` | native | — |
| `xy_curve` | `hv.Overlay` of `hv.Curve` + marker `hv.Scatter` (`.../xy_curve_result.py:99,104`) | `LineStrips2D` (x non-monotonic ⇒ not SeriesLines) | native | — |
| `xy_histogram` | `hv.Overlay` of `hv.Histogram` (`.../xy_histogram_result.py:79`) | `rr.BarChart` | approx | bin-edge axis |
| `xy_hexbin` | `hv.HexTiles` (`.../xy_hexbin_result.py:64`) | none native; density-colored `Points2D` or rasterize | **none**/approx | hexagonal binning gestalt |

### A.3 Non-plugin report items

| item | current output type | plausible rerun lowering | fidelity | what's lost |
|---|---|---|---|---|
| sweep summary | `pn.Column` of `pn.pane.Markdown` (`bencher/bench_cfg.py:1225-1233`), **a `pn.pane.LaTeX`** (`bencher/results/laxtex_result.py:78`, wired in at `bench_cfg.py:1081,1089-1090`), a `pn.Accordion` (`:1082-1084`), optional `pn.pane.Image` (`:1098`) | markdown → `TextDocument` native; **LaTeX → none** (TextDocument has no MathJax); Accordion → always-expanded text; Image → `EncodedImage` | native except LaTeX (**none**/rasterize) and Accordion (approx) | rendered math for the sweep-equation pane; collapse/expand |
| failed-samples pane | `pn.pane.Markdown` (`bench_result.py:469-475`) | `TextDocument` | native | — |
| regression report + overlays | `pn.pane.Markdown` (`bench_result.py:482-488`) + hv overlay plots (`:494`) | `TextDocument` + `SeriesLines` | native/approx | overlay's band styling if any |
| aggregated view | `pn.pane.Markdown` header + markdown table (`bench_result.py:524-527`, `:566-590`) | `TextDocument` | native | — |
| over-time band | `BandResult` (`bench_result.py:559`) | see `band` above | **none** native | double filled band |
| post description | `pn.pane.Markdown` (`bench_cfg.py:1188-1197`) | `TextDocument` | native | — |
| `BenchReport.append_markdown` / tabs | `pn.pane.Markdown` in `pn.Tabs` (`bencher/bench_report.py:178-193`) | `TextDocument` in `rrb.Tabs` | native | — |
| optuna figures | plotly `go.Figure`s appended raw (Panel resolves to Plotly panes): optimization history (`optuna_result.py:283-290,334-339`), param importances (`optuna_conversions.py:64`), pareto front (`optuna_result.py:305-325`); plus text panes | not bencher's figures to re-render (per ticket) ⇒ rasterize (`EncodedImage`) or omit-visibly; data-level relog would be `SeriesPoints`/`BarChart`/`Points2D/3D` approx | approx (rasterize) / **none** (as-is) | hover trial metadata either way |
| `ExplorerResult` | live hvplot explorer app (`bencher/results/explorer_result.py:20,24`) | none — it is a UI, not a plot; **rasterizing is meaningless** | **none** | everything; the only honest options are panel-fallback or omit-visibly |
| `report_render_failure` | `pn.pane.Markdown` (`bencher/results/render_failure.py:52-58`) | `TextDocument` | native | — (and it is the in-repo precedent for "degrade visibly") |
| `extra_panels` / live `plot_callbacks` | arbitrary user Viewables (`bench_result.py:500-514`, `bencher/bencher.py:654-655`) | none in general | **none** | arbitrary; same tier as A6 §4's "legacy escape hatch" |

### A.4 What the measurement says about the Law-3 question

The distribution is not binary. Counting the tables above: **~10 items are cleanly
native, ~14 are approx with a nameable loss, and the hard "none" set is small and
specific** — box/violin marks, hexbin, every *filled band* (Spread, Band's double band,
surface's ±1σ companions), LaTeX, FileDownload artifacts, Tabulator/dataset widgets, the
hvplot explorer, and arbitrary user panels. That shape is exactly a three-valued
`native | approx | none` column: the "none" rows are few enough to enumerate in a
capability table and each needs a *per-row* policy anyway (rasterize is meaningless for
the explorer, natural for a plotly figure; omit-visibly is natural for FileDownload).
A single global policy would be wrong for at least one row in each direction.

---

## B. Rasterize-fallback prototype (measured)

Script: `plans/research/prototypes_1110/proto_b_rasterize.py`
(`pixi run python plans/research/prototypes_1110/proto_b_rasterize.py`).
Takes the real `CurveResult` overlay from `bencher/example/example_simple_float.py`
(30 samples × 5 repeats), a `go.Volume` built exactly as `VolumeResult.to_volume_ds`
builds it (`volume_result.py:88-99`), and an optuna-style 2D figure; renders each to PNG
headlessly; logs all of them plus a `TextDocument` omission note into one recording.
Recording verified with `pixi run rerun rrd print` — entities
`report/{holoviews_curve,plotly_volume,plotly_history,omissions}` all present.

**Headline: yes, it works end-to-end, but holoviews and plotly are in different
dependency worlds.**

| measurement | holoviews → PNG | plotly → PNG |
|---|---|---|
| works headless today (stock pixi env)? | **yes**, via the matplotlib backend | **no** — `fig.to_image()` raises `ValueError: ... requires the Kaleido package` |
| dependency status | matplotlib already a direct dep (`pyproject.toml:26`); **zero new deps**. bokeh-native export instead needs selenium + a webdriver — `pixi list` shows **neither installed** | kaleido **not** in `pixi list`; new dep. kaleido 1.3.0 additionally needs a **Chrome binary** — it used the machine's `/usr/bin/google-chrome`; a CI image without Chrome needs a browser download step too |
| wall time per plot | **~0.3 s** (327 ms first run, 303 ms warm) | **~14–16 s per figure** via `fig.to_image()` (Chrome spawn+teardown per call, incl. an "unclean kill browser" timeout). Batched via `kaleido.write_fig_sync(figs, ...)`: 5 figures in **15.4 s** with one browser ⇒ ~11 s fixed + **~1 s marginal** per figure |
| PNG size at report-typical dims | 18 KB at ~700×400 | volume 150 KB at 600×600; 2D figure 20–23 KB at 700×400 |
| quality | legible: curve, spread band, legend, axis labels all present (`out/holoviews_curve_mpl.png`) | legible: volume gestalt, colorbar, axis titles — but **one fixed camera**; the rotate-to-understand affordance of a 3D volume is the main casualty (`out/plotly_volume.png`) |
| `rr.EncodedImage` logging | 2–10 ms for all images; `.rrd` ≈ sum of PNG sizes (209 KB) | same |

kaleido timings measured after `pixi run python -m pip install kaleido` (kaleido 1.3.0 +
choreographer 1.3.0) into this branch's throwaway env; the numbers are in the script
output and `scratchpad` timing runs (`fig.to_image` ×3: 16.1/14.3/14.6 s; 5×
`pio.to_image` sequential: 75.5 s; `write_fig_sync` batch: 15.4 s).

**Bug found while prototyping** (would bite any holoviews rasterizer): bencher labels
curves with the vdim name (`label=var`, `holoview_result.py:298`); holoviews' matplotlib
backend treats a legend label equal to a dimension name as a *style dim() mapping* and
vectorizes it, crashing with `ValueError: label must be scalar or have the same length
as the input data, but found 30 for 1 datasets`. The bokeh backend is unaffected, which
is why nobody has seen it. Workaround in the prototype: relabel colliding elements
(zero-width-space suffix) before `hv.render(obj, backend="matplotlib")`. A real
rasterizer needs this normalization pass (or bencher stops label/dim-name collisions at
the source).

---

## C. Spread-gap prototype: three SeriesLines vs a filled band

Script: `plans/research/prototypes_1110/proto_c_spread_gap.py`
(`pixi run python plans/research/prototypes_1110/proto_c_spread_gap.py`).
Builds `out/spread_fallback.rrd`: three sibling entities
`curve/out_sin/{mean,upper,lower}` so one TimeSeriesView shows all three, styled via
static `rr.SeriesLines` — mean at width 2.5 in full color, ±1σ edges at width 0.75 in a
lighter same-hue tint, legend names `out_sin (mean)` / `out_sin ±1σ`. Verified with
`pixi run rerun rrd print`. Side-by-side legibility mock (same data, same styling
choices): `out/spread_band_vs_three_lines.png`.

Assessment from the side-by-side:

- **Single series: acceptable.** The envelope shape reads clearly; width-and-tint
  contrast keeps the mean dominant. Nobody would misread the plot.
- **What is genuinely lost:** (1) the *filled* gestalt — area-as-uncertainty-mass is
  preread by anyone who has seen a confidence band; hollow edges read as "three
  measurements" until the legend is consulted; (2) legend economy — every result var
  gains two extra legend entries; (3) **scaling** — at N overlaid result vars the view
  has 3N lines and edge-to-mean pairing relies entirely on hue families; the `band`
  plugin's *double* band (p10-p90 + p25-p75 + median, `band_result.py:272-288`) becomes
  5 lines per var and is the first place this fallback will stop being legible.
- **A lowering detail the grammar will hit:** SeriesLines are indexed by a rerun
  *timeline*. The prototype uses `rr.set_time("theta", sequence=i)` — integer sample
  index, not the float `theta` value. A float x axis needs encoding as a duration/
  timestamp timeline; plain `sequence` silently turns a non-uniform float sweep into a
  uniform index axis. Worth a row in the capability table on its own.

---

## D. Auto-selection blast radius of `("volume","plotly")`

Trigger (all conditions required, from the auto path `to_auto` with `override=False`,
`bench_result.py:313,353`):

- registry match is wide open (`PlotFilter()` at `builtins.py:159`); the real gate is
  inside `VolumeResult.to_volume` (`volume_result.py:64-74`);
- `plt_cnt_cfg.float_cnt == 3` and `cat_cnt == 0` (`VarRange.exactly`, matched at
  `bencher/plotting/plot_filter.py:113-114`, wired `:227-228`). **IntSweep, FloatSweep,
  TimeSnapshot, TimeEvent all count as float** (`bencher/plotting/plt_cnt_cfg.py:95-98`);
  Enum/Bool/String/Yaml count as cat (`:99-102`) — so 3 int sweeps also trigger it, and
  any bool input kills it;
- ≥1 result var isinstance `ResultFloat` (`result_types=(ResultFloat,)`,
  `volume_result.py:71`, filtered at `bench_result_base.py:738-740`) — **`ResultBool`
  qualifies** (subclass, `variables/results.py:160`);
- not `over_time` — hard early `return None` (`volume_result.py:61-63`);
- `repeats >= 1`, `input_vars >= 1` (inherited defaults, `bench_result_base.py:59-60`);
- aggregation shrinks the counted dims first (`bench_result_base.py:817-842`), so a
  3-float sweep with `aggregate=` over one dim does *not* trigger it;
- on mismatch the auto path returns silently — `to_auto` sets `print_debug=False`
  (`bench_result.py:346`; silent-None behavior `plot_filter.py:239-243`).

**How often it actually fires in the repo:** an AST scan of every sweep call under
`bencher/example/` found **2 of 171 generated examples plus 3 hand-written/meta sites**:

- `bencher/example/generated/3_float/no_repeats/example_sweep_3_float_0_cat_no_repeats.py:30` (3 FloatSweeps `:11-13`, ResultFloat `:15`);
- `bencher/example/generated/3_float/with_repeats/example_sweep_3_float_0_cat_with_repeats.py:32` (`:12-14`, `:16`);
- `bencher/example/example_workflow.py:106` (`example_floats3D_workflow`, `:94`; `__main__`-only `:134` — not in the gallery or tests);
- `bencher/example/meta/example_meta.py:205-215` ("3 Float Inputs", nested via `res.to_auto()` at `:155`) and `bencher/example/meta/example_meta_float.py:8-12` (the `float_vars=3` cell);
- `bencher/example/generated/plot_types/example_plot_volume.py:10-11` — volume appears **twice** there: once auto, once via explicit `res.to_volume()` (generated by `bencher/example/meta/generate_meta_plot_types.py:355-361`).

**Gallery pages that would lose a plot if a rerun report silently dropped volume**
(registrations at `bencher/example/meta/generate_examples.py:697-704,717`; docs index
`docs/examples_index.md:91,94`):

- "3 Float Inputs → No Repeats" and "3 Float Inputs → Repeated" — lose their *only* 3D
  plot;
- "Plot Types → volume" — loses the auto half but keeps the explicit `to_volume()`
  render, i.e. the page silently halves rather than blanks;
- "3 Float Inputs → Over Time" never had it (over_time guard).

**Test-coverage fact for the "silent drop" concern:** no test asserts volume is
*auto*-selected. `test/test_volume_result.py` exercises explicit `to_volume()`
(`:66-99`) and rejection paths (`:104-125`); `test/test_plugins_builtins.py:21` checks
registration order only; the generated 3_float examples run as smoke tests without
inspecting panes (`test/test_generated_examples.py:39-59`). **A regression that silently
stopped auto-selecting volume would pass the entire suite today** — the ticket's "an
auto path that silently drops a plot is worse than one that never had it" concern is
already unguarded in the panel world, not just a rerun-future risk.

---

## Reproduction commands

```
pixi run python plans/research/prototypes_1110/proto_b_rasterize.py   # §B measurements
pixi run python -m pip install kaleido                                # for the plotly rows of §B
pixi run python plans/research/prototypes_1110/proto_c_spread_gap.py  # §C recording + mock
pixi run rerun plans/research/prototypes_1110/out/spread_fallback.rrd # view §C
pixi run rerun plans/research/prototypes_1110/out/rasterized_report.rrd # view §B
```
