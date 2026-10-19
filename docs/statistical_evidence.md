# Statistical evidence for a change

This page is the design for the statistics and the graphics that `bencher compare`
and `bencher ab` put in a pull request. A reviewer reads the report once, at the top
of the PR, and must come away with three facts for each claim the PR makes:

1. **How big** the change is, in the metric's own terms (−18 %, +2 pp, 0.3 s).
2. **How sure** the data are, as an interval, never as a bare p-value.
3. **What it means** against a margin the author set before the run: improved,
   regressed, equivalent, too small to matter, or not yet known.

Research notes with sources are in `docs/statistical_evidence_research.md`.

## 1. What a PR claims

Every benchmark claim a PR makes is one of seven kinds. The kind picks the test.

| Claim | Example | Question the test answers | Test |
|---|---|---|---|
| Improvement | "planning is faster" | Is the change real, and how big? | CI of the effect vs 0 and vs margin |
| No regression | "refactor, no slowdown" | Is it at worst Δ worse? | Non-inferiority: one-sided bound vs −Δ |
| Same behaviour | "tooling change, 13 metrics unchanged" | Is every metric within ±Δ? | Equivalence (TOST): 90 % CI inside ±Δ |
| Reliability | "success 17/18 → 18/18" | Did the rate move, and where is it now? | Wilson per arm, Newcombe difference, Barnard |
| Flake fixed | "no failures in 30 runs" | What failure rate is still possible? | Rule of three / exact upper bound, runs needed |
| Absolute bound | "p95 latency < 0.7 s" | Does the quantile sit under the bound? | Order-statistic CI of the quantile |
| Less noise / tails | "p99 cut", "less jitter" | Did the spread or the tail move? | Shift function (decile differences), SD ratio |

"No significant change" is **not** evidence of "no change". A test that fails to reject
only says the data cannot tell. The report must never print "unchanged" unless the
equivalence test passed.

## 2. Metric kinds and the effect each one uses

| Kind | Examples (kbench `METRICS.md`) | Effect | Margin unit |
|---|---|---|---|
| Positive continuous | `task_duration`, `planning_time`, `tracking_error_rms` | ratio cand/base, as log ratio | relative, ±5 % default |
| Signed continuous | `com_margin_min`, `zmp_margin_min` | difference cand − base | absolute, in the metric's units |
| Bounded fraction | `task_completion`, `plan_request_success` | difference | absolute, percentage points |
| Binary | `task_success`, `clean_exit`, `required_sigkill` | difference of proportions | absolute, percentage points |
| Count | `orphan_count`, `plan_requests` | rate ratio | relative |

A positive metric uses the log scale because timings are skewed and multiplicative
noise is the norm: a 2× slowdown and a 2× speedup are the same distance from 1.
The effect is the ratio of geometric means; the ratio of medians is the robust
cross-check.

## 3. The design of the run

The design decides how much noise reaches the effect. Bencher must record the design
and pick the analysis that matches it.

* **Unpaired** — base runs, then candidate runs. Machine drift between the two blocks
  lands on the effect. Default for `bencher compare` of two old pickles.
* **Paired** — each repeat runs base and candidate on the same machine, same seed,
  back to back (kbench `--paired`, a future `bencher ab --interleave`). Analyse the
  per-pair log differences. This cuts the CI 5–15× on CI runners (kinisi_ros #13739).
  Alternate the order (ABBA) so that a warm-cache order effect cancels.
* **Clustered** — repeats share a shard or VM. The unit of replication is the shard,
  not the repeat. Resample shards, not repeats (cluster bootstrap).
* **Sweep** — sweep points are a fixed design, not a random sample. Each point gets
  its own effect and CI. The headline pools points only when the author asks for it.

## 4. The test set

All decisions run at one-sided α = 0.05, which is the **90 % two-sided CI**. The
report draws the 90 % CI thick and the 95 % CI thin.

### 4.1 Continuous

* Estimate: mean of log values per arm (or of paired log differences), back to %.
* CI: BCa bootstrap with 10 000 resamples and a fixed seed when n ≥ 10 per arm;
  Welch t on the logs when n < 10 (the bootstrap is too narrow there).
* Robust check: Hodges–Lehmann shift with Mann–Whitney (unpaired) or Wilcoxon
  signed-rank (paired). When the robust check disagrees with the main verdict, the
  report says so and shows the distribution plot.
* Tails: the shift function — the difference at each decile with a bootstrap CI.

### 4.2 Binary

* Per arm: Wilson score interval.
* Difference: Newcombe hybrid score interval.
* Exact test: Barnard (more power than Fisher at small n). Paired outcomes (same seeds)
  use McNemar exact on the discordant pairs.
* Zero events in n: the 95 % upper bound is 3/n (rule of three); exact is
  1 − 0.05^(1/n).
* Runs needed to claim a flake rate p₀ is gone: n = ⌈ln α / ln(1 − p₀)⌉.
  5 % → 59 runs, 10 % → 29, 1 % → 299.

### 4.3 Verdict

Orient the CI so that positive is better. With margin Δ > 0 and CI [L, U]:

| Verdict | Rule | Glyph | Reads as |
|---|---|---|---|
| Improved | L > 0 and U > Δ | ▲ | real gain, may matter |
| Regressed | U < 0 and L < −Δ | ▼ | real loss, may matter |
| Equivalent | −Δ < L and U < Δ | ≈ | the same within the margin |
| Inconclusive | L ≤ 0 ≤ U and the CI crosses a margin | ? | the data cannot tell yet |

Equivalent splits into "≈ no change" (CI holds 0) and "≈ small gain / small loss"
(CI excludes 0 but stays inside ±Δ). Non-inferiority passes when L > −Δ. The margin
is the author's, set on the result variable before the run
(`bn.ResultFloat(margin=0.05)`); the default is the larger of 5 % and twice the A/A
noise floor of that metric.

### 4.4 Many metrics, many sweep points

* **Primary** metrics (the claim the PR makes; 1–3 of them): Holm across them. The
  report widens their CIs to match the adjusted α.
* **Secondary** metrics and sweep cells: Benjamini–Hochberg at q = 0.05. These flag;
  they do not gate. A cell that fails FDR draws hollow.

### 4.5 Enough runs

* Minimum detectable effect at 80 % power: MDE = (z₀.₉₅ + z₀.₈₀) · SE.
* When MDE > Δ the verdict carries "underpowered" and the runs needed to reach Δ:
  n ≈ n · (MDE / Δ)².
* Peeking at a fixed-n test inflates false positives. "Add runs until decided" is a
  later phase that uses a confidence sequence; until then the report states n was
  fixed in advance.

### 4.6 Noise checks

* A/A: `bencher ab --base HEAD` runs the same tree twice. Its effect CIs give the
  noise floor of each metric and the real false-positive rate. Store it next to the
  history and use it for the default margin.
* Drift: plot value against run order, coloured by arm. A slope inside one arm says
  the machine drifted.
* Shard outliers: one-way test by shard (kbench `judge_shards`), Holm.
* Bimodality: when the two arms have more than one mode, the ECDF goes in the
  report, and no single number speaks for the metric.

## 5. Graphics

The graphics follow estimation statistics (Gardner & Altman, Cumming, DABEST): show
every sample, show the effect on its own axis, show its uncertainty. They avoid bars
of means, dual axes and radar charts: area and axis order in a radar distort the
values, and directions mix on one polygon. The radar stays behind an explicit flag.

Common rules:

* Okabe–Ito colours. Base is grey `#8C8C8C`; candidate is blue `#0072B2`. Better is
  bluish green `#009E73`, worse is vermillion `#D55E00`, inconclusive is amber
  `#E69F00`. A glyph and a word always back the colour.
* One shared axis for every effect: % change on a log-ratio scale, 0 in the centre,
  the ±Δ band shaded.
* Every image ships in light and dark, as PNG at 2× (1600 px wide, shown at 800), plus
  SVG. The Markdown uses `<picture>` with `prefers-color-scheme`; the `#gh-dark-mode-only`
  fragment is deprecated.
* Alt text carries the verdict and the numbers, so a screen reader and a broken image
  still give the result.
* The title of a chart is its finding ("Planning is 18 % faster"), not its axes.

The catalogue:

| # | Graphic | Use | Content |
|---|---|---|---|
| G1 | Scorecard | top of every report | one tile per primary metric: big effect, CI, mini effect bar with ±Δ band, glyph + word, footer `n=20 paired · BCa · MDE 4 %` |
| G2 | Forest plot | many metrics or sweep points | rows sorted by effect, point + 90 %/95 % CI on the shared axis, ±Δ band, verdict column, hollow when FDR fails |
| G3 | Estimation plot | each primary continuous metric | left: every sample per arm (swarm), median tick; slope lines when paired; right: bootstrap distribution of the effect with CI and ±Δ band |
| G4 | Raincloud + shift | tails, bimodal data | half-violin, box, raw points per arm; under it the decile shift function with CIs |
| G5 | Waffle | binary metrics | one square per run per arm, success / failure; Wilson CI bar; difference CI; rule-of-three note at 0 failures |
| G6 | Sweep panel | one swept input | top: both arms, median + CI ribbon; bottom: effect per point with CI and ±Δ band |
| G7 | Effect heatmap | two swept inputs | diverging blue–orange centred on 0 %, cells whose CI crosses the margin hatched, glyph in each cell |
| G8 | Power bar | under any underpowered verdict | MDE against Δ, "add ~N runs" |
| G9 | Diagnostics | in `<details>` | value vs run order by arm and shard; A/A null band |

### Video

A video earns its place only when the claim is spatial or temporal and a still cannot
show it: two trajectories side by side, a gripper that now closes in time, a planner
that stops oscillating. Then: an H.264 MP4 under 10 MB, base and candidate side by side
and in sync, a still frame and the numbers next to it, attached to the PR as an upload.
A video never carries a statistical claim on its own; it shows the mechanism behind
one.

## 6. Report layout in the PR

```markdown
## Evidence

<picture>  scorecard (G1)  </picture>

**2 improved · 0 regressed · 9 equivalent · 1 inconclusive** — paired, n=20,
margin ±5 %, Holm over 3 primary metrics.

<picture>  forest plot (G2)  </picture>

### Planning is 18 % faster ▲
<picture>  estimation plot (G3)  </picture>
`planning_time` −18.4 % [90 % CI −22.0, −14.6], BCa bootstrap of paired log
differences, n=20 pairs. Wilcoxon agrees (p < 0.001).

<details><summary>Method, diagnostics and data</summary> … G9, CSV … </details>
```

The text-only charts of `evidence.py` stay as the fallback when images are off.

## 7. Modules

* `bencher/evidence_stats.py` — the tests. Pure functions on numpy arrays; no xarray,
  no plotting. Returns frozen dataclasses (`Effect`, `ProportionEffect`, `Verdict`).
* `bencher/infographic.py` — the graphics G1–G9, matplotlib `Figure` without pyplot,
  one theme object for light and dark.
* `bencher/evidence_report.py` — turns two recordings (or two kbench `repeats.json`
  row files) into the Markdown above plus the image files.
* CLI: `bencher compare BASE CAND --report DIR`, and `bencher evidence-rows BASE.json
  CAND.json --report DIR` for the kbench row format.
