# Prototype results — #1117: over_time history and regression views under named timelines

Prototype evidence, not a resolution. Branch `prototype/history-regression-1117`,
built on `task/grammar-foundation-1108` @ `2a96bf00` (the grammar landing — remote
`main` @ `cfd551a3` does not yet contain `bencher/grammar/`). rerun-sdk 0.35.0.

Reproduce:

```
pixi run python plans/prototypes/history_regression_1117/history_regression.py   # 11/11 checks
pixi run python plans/prototypes/history_regression_1117/screenshot.py           # 3 screenshots
pixi run rerun rrd verify plans/prototypes/history_regression_1117/out/history_regression.rrd
```

Everything below comes from a **real bencher run**: `TrainBenchmark`
(`batch_size` IntSweep ×3, 5 repeats) executed 8 times through
`plot_sweep(..., over_time=True, time_src=<daily datetimes>)` with
`regression_detection=True, regression_method="percentage", regression_percentage=10`.
Runs 0–6 carry mild sub-threshold drift; run 7 is a +30% `train_time` step (fires:
+27.97% vs ±10%) and a −6.6% `accuracy` dip (does not fire on a maximize var).
The recording is lowered from `res.ds` and `res.regression_report` — the same
objects the panel report consumes.

## What the current machinery actually is (read + measured, not guessed)

- `over_time=True` appends a `TimeSnapshot` (continuous → `np.datetime64`; string
  `time_src` → `TimeEvent`, discrete) input var literally named `over_time` as the
  **last dataset dim**: `dims = input_vars + [repeat, over_time]` (measured:
  `('batch_size', 'repeat', 'over_time')`, dtype `datetime64[us]`, one coordinate
  per run). History is `xr.concat(..., "over_time")` from the diskcache record
  (`result_collector.py:840`, `history.py:reconcile`), schema-reconciled per
  column (dormant/retired/birth) with the birth marker feeding
  `regression_min_history`.
- The over-time band at `bench_result.py:559` is `self.to(BandResult,
  aggregate=input_names)`: over_time on x, and per time point it pools **all
  input dims + repeat** into one sample pool, drawing nested `hv.Area` percentile
  bands (10–90 outer, 25–75 inner) + median `hv.Curve` + raw scatter.
- `detect_regressions` (`bencher.py:917`, after history merge) splits `over_time`
  at the last index: **reference = per-time means of all-but-last** (every
  non-time dim collapsed to one scalar per historical run), **current = last**.
  Detectors: percentage / adaptive (MAD step + Theil–Sen drift, dual-band) /
  delta / absolute → `RegressionResult` with `baseline_value`,
  `band_lower/upper` (acceptance band), verdict, direction. Displayed as a
  markdown table + an `hv.Overlay` per variable (acceptance-band Area, dashed
  baseline Curve, history line + scatter, verdict-coloured current marker,
  dotted connector); `regression_fail` raises on mature-baseline regressions.

## A. History as a TIME channel assignment — yes, natively

- `rr.set_time("over_time", timestamp=<datetime64>)` gives a **named,
  timestamp-typed timeline** (verified in the file: index column `over_time` of
  arrow type `timestamp[ns]`). History is exactly a TIME assignment over the
  `over_time` dim; the wall-clock axis needs no encoding tricks.
- The ±σ spread per run (from `repeat`) lowers per the #1110 single-series
  ruling: **three SeriesLines** (mean full-colour w=2.5, ±1σ edges lighter tint
  w=0.75). Screenshot `out/screens/s1_blueprint_layout.png` row 1: envelope and
  the +30% step read clearly.
- `batch_size` coexists as FACET_COL (one view per value, row 1) **and** as its
  own `batch_size` sequence timeline in the same recording (checked in-file:
  timelines `{over_time: timestamp[ns], batch_size: int64}`; the sweep entity is
  indexed on `batch_size` and **not** on `over_time`). `log_tick` is absent;
  `log_time` is present as always (#1109's finding). No collision — the #1109
  result holds with a datetime timeline in the mix.
- **New viewer facts (0.35) the lowering must know:**
  1. A TimeSeriesView's default x view does **not** fit a sparse timestamp
     timeline — it opened on a ~1-minute window around the cursor, flattening 7
     days of history into invisible lines. The blueprint must pin
     `axis_x=TimeAxis(view_range=...)`. `time_ranges=VisibleTimeRanges` is the
     wrong knob (tested: no effect on the axis — it controls per-cursor visible
     history). An `infinite` view range half-clips the newest mark at the right
     plot edge, so pin absolute bounds with a margin.
  2. **One active timeline per viewer.** `rrb.TimeAxis` has no per-view timeline
     selector; every TimeSeriesView's x-axis follows the time panel's active
     timeline (pinnable via `rrb.TimePanel(timeline=...)`). A view whose
     entities live on a different timeline renders empty with an error badge
     (`s3_sweep_timeline_mode.png`, right pane). So per-dim timelines coexist in
     the *data*, but as *views* they are a mode switch, not side-by-side panes:
     a sweep dim that must appear next to wall-time history should be FACET (or
     the leaf's X), and TIME is best reserved for the dim the report scrubs.

## B. Regression views

- **The comparison is an OVERLAY on the history timeline** — s1 row 2 right:
  blue history-mean line, grey baseline (reference) line, green acceptance-band
  edge lines (`band_lower/upper` from the real `RegressionResult`), red current
  point clearly outside the band. All sibling entities in one TimeSeriesView;
  nothing about it needed a new channel. The acceptance *band* hits the same
  SPREAD gap as ±σ (edge lines instead of fill) — same row of the table.
- **Pass/fail-over-history**, replayed honestly (`detect_regressions` re-run on
  every history prefix; verdict sequence PASS×6 → FAIL, matching the +30% step),
  built three ways (s1 row 3):
  1. **0/1 SeriesLines in its own view** — misleading: SeriesLines interpolates
     between sparse samples, so the 1→0 transition renders as a day-long ramp,
     reading as gradual degradation. Rerun 0.35 has no step-line mode. Worst.
  2. **SeriesPoints riding the history-mean value with per-timestep colours**
     (green/red) — works: per-timestep `rr.SeriesPoints(colors=...)` updates are
     honoured per point (6 green + 1 red in one view). Reads best as a chart
     mark, and can overlay the history line itself.
  3. **TextLog verdict stream** (level INFO/ERROR) on the same timeline — the
     TextLogView shows timestamped PASS/FAIL rows with the detector detail
     string, colour-coded by level, and clicking a row moves the time cursor.
     Best as the *report record* of verdicts; not a chart.
  **Verdict: (2) for the mark, (3) alongside it as the log; (1) rejected.**
  These are mark/item-table rows (per #1110's mark-level extension), not new
  channels.

## C. Report-wide timeline sharing + default blueprint

- Two result vars' histories under host-assigned prefixes `/item_0` (train_time)
  and `/item_1` (accuracy), logged onto the same `over_time` timeline name →
  **shared automatically**: one timeline in the file, one scrubber over both
  items' streams (s1 bottom panel), one time cursor moving over every view.
  Sharing is by timeline *name*; the #1104 host owns naming, so report-wide
  wall-time alignment is the host emitting one canonical name (e.g. `over_time`)
  for every item's history dim.
- **The viewer's default (no blueprint) is unusable as a report**
  (`s2_default_no_blueprint.png`): the heuristic makes **one view per leaf
  entity** — 28 tiny panes, the three-SeriesLines spread scattered into separate
  mean/hi/lo views, plus it happily mixes timelines (the sweep entity got its
  own broken pane). The blueprint must pin: (a) grouping mean/±σ (and
  overlay members) into one view per facet, (b) the facet/row structure, (c)
  `TimePanel(timeline="over_time")`, (d) per-view x view-range (A.1 above), and
  (e) y-range where a verdict mark must not clip. What falls out free: timeline
  sharing, the scrubber, per-point colours, TextLog↔cursor linking.

## SPREAD reconciliation (#1110 ruling vs the grammar seed on main)

- **#1110 resolution ruled (mark/item level):** `Spread`/band marks = **Approx →
  three-SeriesLines** (mean + ±1σ edges) for a single series; **rasterize** for
  multi-var / double-band where 3N/5N lines stop being legible.
- **The seed table** (`bencher/grammar/capability.py`) marks channel-level
  `SPREAD: Unsupported("no native band view (A6 §3 declared gap)")` with
  `SUBSTITUTION_CHAIN SPREAD→OVERLAY`.
- **Reconciliation:** not a contradiction, but the ruling's fidelity is only
  half-encoded. `substitute()` on SPREAD returns
  `Substituted(via=(SPREAD, OVERLAY), capability=Native(OVERLAY))` — the walk is
  recorded (visible substitution, Law 3) and the three-SeriesLines form *is*
  the OVERLAY landing, so the single-series arm is consistent. But (a) the
  landing reports `Native`, so the degradation statement ("filled gestalt lost,
  ±1σ edges") lives nowhere — #1110 called the row **Approx** with a `how`; and
  (b) the conditional arm (rasterize at multi-var/double-band) is
  unrepresentable in a channel-level static table — it is exactly the
  **mark/item-level table** #1110's resolution says arrives with the #1109
  implementation. This prototype's evidence: the three-SeriesLines landing is
  real and legible for single series (s1 rows 1–2), and the regression
  acceptance band consumed the same row. The seed needs either the mark-level
  rows, or the SPREAD row switched to `Approx(how="three SeriesLines via
  OVERLAY; filled band gestalt lost")` so the substitution's fidelity is stated.

## Recommendation (evidence-weighted, against "long-term correct, scales well")

1. **History = TIME assignment over the `over_time` dim, Native.** No special
   over_time machinery survives at the view layer: the datetime timeline
   replaces the slider hack, the ±σ band replaces `BandResult`'s over-time
   variant via the SPREAD row, `TimeEvent` (string labels) is the one case that
   cannot be a timestamp timeline (sequence timeline + label mapping — its own
   capability-row note).
2. **Regression = data, not new grammar.** Reference/band/current are OVERLAY
   members on the same timeline; pass/fail is a mark-table row
   (verdict-coloured SeriesPoints + TextLog stream). No new channel.
3. **The default blueprint is a hard dependency, not polish.** Four viewer
   facts (one-view-per-entity default, unfit default x-range, one active
   timeline, right-edge clipping) each independently break an unpinned report.
   The #1109 `lower()` already returns the view node per subtree — this
   prototype shows exactly which properties that node must carry
   (`TimeAxis.view_range`, `ScalarAxis.range`, `TimePanel.timeline`).
4. **Sweep dims should not default to TIME in a report that scrubs wall time.**
   One active timeline per viewer makes per-dim timelines mode switches; FACET
   keeps them simultaneous. TIME-per-dim remains correct at the data level
   (#1109) and for deliberate scrub-this-dim views.

## Files

- `history_regression.py` — build + 11 programmatic checks (all pass).
- `screenshot.py` — offline single-file viewer HTML (technique from
  `prototype/rerun-delivery-1107`) + headless-Chrome screenshots.
- `out/screens/s1_blueprint_layout.png` — pinned report layout (A, B, C).
- `out/screens/s2_default_no_blueprint.png` — viewer default: one view per
  entity, 28 panes.
- `out/screens/s3_sweep_timeline_mode.png` — batch_size-timeline mode; the
  wall-time history view errors on the same screen.
- `out/*.rrd` (gitignored, regenerated): `history_regression.rrd` 238 KB
  (data + blueprint, `rerun rrd verify` clean), `_noblueprint` 141 KB,
  `_sweepmode` 177 KB.
