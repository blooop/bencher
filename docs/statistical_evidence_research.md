# Statistical evidence layer for A/B benchmark PR reports — research notes

Date: 2026-10-19. Context: bencher/holobench (Python, xarray). Base vs PR, 5–30 repeats per sweep point, shared noisy CI runners, report goes into a GitHub PR body.

Legend: [V] = verified against the cited page during this research; [K] = standard reference cited from known literature (not re-fetched).

---

## A. Statistical methods

### A1. Continuous metrics (latency, time-to-goal)

Recommended default: **effect = ratio PR/base on the log scale** (geometric-mean ratio or ratio of medians), with a **bootstrap CI**, plus a rank test as a secondary check.

| Method | Use when | Notes |
|---|---|---|
| Ratio of geometric means (log-transform, then mean diff, exponentiate) with t or bootstrap CI | Positive, right-skewed timings; the reviewer thinks in "% faster" | Symmetric on log scale: 0.8x and 1.25x are the same distance. Kalibera & Jones recommend ratio-of-means CIs for benchmarks [K] https://doi.org/10.1145/2464157.2464160 |
| Ratio of medians, bootstrap CI | Heavy tails / outliers (CI hiccups) | Robust; percentile bootstrap of the median is coarse at n<15. |
| Bootstrap percentile vs **BCa** | BCa corrects bias and skew; second-order accurate (Efron 1987) [K] https://doi.org/10.1080/01621459.1987.10478410 | `scipy.stats.bootstrap` default `method='BCa'`; supports paired (`paired=True`) and multi-sample statistics [K] https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html . At n=5 any bootstrap under-covers; prefer t on log scale or exact rank intervals. |
| **Hodges–Lehmann shift** + Mann–Whitney U | Non-normal, unpaired; want "typical shift" with a distribution-free CI | HL = median of all pairwise differences (on log scale gives ratio). MWU tests stochastic dominance, not medians. `scipy.stats.mannwhitneyu` [K] https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html |
| Welch t-test | Means matter (throughput totals), roughly normal after log | Never use pooled-variance Student t when base/PR variances differ. |
| **Paired design** + Wilcoxon signed-rank / paired bootstrap | Interleaved runs (ABAB… or round-robin), same seed, same runner per pair | Pairing cancels runner drift and machine heterogeneity — the single biggest variance reduction available on shared CI. `scipy.stats.wilcoxon`. Chromium Pinpoint has a pairwise Wilcoxon signed-rank comparator [V] https://pkg.go.dev/go.skia.org/infra/pinpoint/go/compare |
| Tail metrics (p95/p99) | Latency SLOs, worst-case time-to-goal | Need many samples: a p99 from 30 runs is the max. Use Harrell–Davis quantile + bootstrap CI, or report p90 at small n. Rousselet/Wilcox shift function compares deciles with CIs [K] https://doi.org/10.1111/ejn.13610 |

Design advice: interleave base and PR on the **same runner** within one job (randomized or ABBA order), not "base job yesterday, PR job today". Measurement bias from environment (link order, env size) can exceed the effect being measured (Mytkowicz et al. 2009) [K] https://doi.org/10.1145/1508244.1508275 .

### A2. Binary metrics (success rate, flake rate)

- **Single proportion CI: Wilson** (good coverage, cheap) or **Clopper–Pearson** (exact, conservative). Wald interval is unacceptable at small n or p near 0/1 (Brown, Cai & DasGupta 2001) [K] https://doi.org/10.1214/ss/1009213286 . `statsmodels.stats.proportion.proportion_confint(method='wilson'|'beta')` [K] https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.proportion_confint.html
- **Difference of two proportions: Newcombe hybrid score CI** (Newcombe 1998) [K] https://doi.org/10.1002/(SICI)1097-0258(19980430)17:8%3C873::AID-SIM779%3E3.0.CO;2-I ; `statsmodels.stats.proportion.confint_proportions_2indep(method='newcomb')`.
- **Tests:** `scipy.stats.fisher_exact` (conditional, conservative), `scipy.stats.barnard_exact` (unconditional, more powerful at small n), `scipy.stats.binomtest` for one rate vs a target [K] https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.barnard_exact.html
- **Rule of three:** 0 failures in n runs → 95% upper bound on failure rate ≈ 3/n (Hanley & Lippman-Hand 1983) [K] https://doi.org/10.1001/jama.1983.03330370053031
- **Runs needed to claim "flake fixed":** to reject "rate is still ≥ p0" at α with zero failures, need (1−p0)^n ≤ α → n ≥ ln α / ln(1−p0). p0=5%, α=0.05 → **59 clean runs**; p0=10% → 29; p0=1% → 299. One failure raises the count a lot (use Clopper–Pearson upper bound). Report this as "N more clean runs needed".

### A3. Equivalence / no-regression

- "p > 0.05" = **no evidence of difference**, *not* evidence of no difference. A wide CI that spans both "+20% regression" and "−20% improvement" must read "inconclusive".
- **TOST** (two one-sided tests) against margins [−Δ, +Δ]: equivalent iff the (1−2α) CI (i.e. 90% for α=0.05) lies wholly inside the margins (Lakens 2017) [K] https://doi.org/10.1177/1948550617697177 . `statsmodels.stats.weightstats.ttost_ind` / `ttost_paired` [K] https://www.statsmodels.org/stable/generated/statsmodels.stats.weightstats.ttost_ind.html
- **Non-inferiority** (the usual PR question: "not slower by more than Δ"): one-sided; CI upper bound for the ratio < 1+Δ. Margins must be declared per metric *before* the run (e.g. latency +3%, success −2 pp).
- **Four-way verdict from CI vs margin** (maps directly to a glyph): improved (CI wholly beyond −Δ... or beyond 0 in the good direction), regressed (CI beyond 0 in bad direction and crosses +Δ), equivalent (CI inside ±Δ), inconclusive (CI straddles a margin). Distinguish "statistically significant but inside margin" = "trivial change".

### A4. Multiple comparisons

A sweep of 20 points × 4 metrics = 80 tests → ~4 false alarms at α=0.05 with no correction.
- **Holm** (FWER, uniformly better than Bonferroni) [K] https://www.jstor.org/stable/4615733 — use for gating ("fail the PR").
- **Benjamini–Hochberg FDR** [K] https://doi.org/10.1111/j.2517-6161.1995.tb02031.x — use for "flag for review" across a heatmap. `scipy.stats.false_discovery_control(ps, method='bh'|'by')` (SciPy ≥1.11) [K] https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.false_discovery_control.html ; `statsmodels.stats.multitest.multipletests(method='holm'|'fdr_bh')`.
- Alternative that reads better: pre-declare 1–3 **primary** metrics (gated, Holm) and treat the rest as **exploratory** (FDR, shown but not gating).

### A5. Power, minimum detectable effect, sequential testing

- **MDE** for a two-sample log-ratio test: MDE ≈ (z₁₋α/₂ + z₁₋β)·σ_log·√(2/n). With CV 5% and n=10/arm at 80% power: ≈ 2.8·0.05·0.447 ≈ 6.3%. Print MDE in the report so "no change" is honest ("could not have seen < 6%").
- **Pilot → choose n:** estimate σ from an A/A run or historical base runs, then n = 2·((z_a+z_b)·σ/Δ)².
- **Sequential / adaptive:** peeking with fixed-n tests inflates false positives. Valid options: SPRT (Wald) for binary success; **always-valid p-values / confidence sequences** (Johari et al. 2017 [K] https://arxiv.org/abs/1512.04922 ; Howard et al. 2021 [K] https://doi.org/10.1214/20-AOS1991) — stop when the CS is clear of or inside the margin. Pinpoint's design is a practical pattern: two alpha thresholds; p < low → "Different", p > high → "Same", in between → "Unknown, need more runs" [V] https://pkg.go.dev/go.skia.org/infra/pinpoint/go/compare . Simple rule for holobench: run n₀=5, compute CI; if verdict inconclusive, add repeats in batches up to n_max, using a group-sequential (e.g. Pocock / O'Brien–Fleming or alpha-spending) correction or a confidence sequence.

### A6. Noise diagnostics

- **A/A test**: run base vs base on the same CI pool; the share of "significant" results calibrates the real false-positive rate and the noise floor (per metric). Use it to set Δ and to pick the noise threshold (criterion's ±2% default is a generic guess).
- **Drift**: plot value vs run index (interleaved order); Spearman of value vs index; a paired design absorbs slow drift.
- **Runner heterogeneity**: record runner id / CPU model / load; stratify or use a mixed model (random runner effect). Pair within runner.
- **Outliers**: report (don't silently drop) with Tukey 1.5·IQR or MAD; robust statistics (median, HL) handle them.
- **Bimodality**: dip test (Hartigan) or simply a dot/raincloud plot; a bimodal distribution invalidates a single "shift" number — show the ECDF / shift function instead.
- **Prior art on real sample tails**: bench noise is often non-normal and multimodal; Kalibera & Jones above.

### A7. What the established tools do

- **Google Benchmark `compare.py`**: Mann–Whitney U test, null = no difference; docs warn it needs "LARGE (no less than 9)" repetitions [V] https://github.com/google/benchmark/blob/main/docs/tools.md
- **pyperf `compare_to`**: Student's two-sample two-tailed t-test (docs say "alpha equals to 0.95", i.e. 95% confidence); `--min-speed` absolute % floor, default 0% [V] https://pyperf.readthedocs.io/en/latest/cli.html
- **airspeed velocity (asv)**: `compare` colour-codes changes beyond `--factor` (default 1.1 = 10%), marks non-significant with `~` [V] https://asv.readthedocs.io/en/stable/using.html ; significance via `is_different` = Mann–Whitney with p-threshold 0.002, falling back to a pessimistic CI-overlap check when samples are missing/small [V] https://asv.readthedocs.io/en/latest/autoapi/asv/_stats/index.html ; history step detection = piecewise-constant fit, weighted L1 deviations + penalty on segment count, penalty chosen by an information criterion [V] https://asv.readthedocs.io/en/stable/step_detection.html
- **Mozilla Perfherder**: Welch-form t statistic between back window (12–24 revisions) and fore window (12), with linear weights; `t_threshold=7`; plus a magnitude gate (default 2% for Talos/Browsertime, 0.25% AWSY, 5% Dromaeo) [V] https://raw.githubusercontent.com/mozilla/treeherder/master/treeherder/perfalert/perfalert/__init__.py , https://firefox-source-docs.mozilla.org/testing/perfdocs/perf-sheriffing.html
- **Chromium Pinpoint**: KS and Mann–Whitney p-values combined; low/high alpha thresholds give Same / Different / Unknown(need more data); magnitude-dependent thresholds; separate functional (failure-rate) comparison; pairwise Wilcoxon option [V] https://pkg.go.dev/go.skia.org/infra/pinpoint/go/compare
- **criterion.rs**: bootstrap CI of the change (100,000 resamples default), p-value vs 0.05, **noise threshold ±2%** default: "Change within noise threshold" when the CI overlaps ±2% [V] https://bheisler.github.io/criterion.rs/book/user_guide/command_line_output.html
- **hyperfine**: mean ± σ, min/max/median in exports, relative "x faster" factor; statistical outlier warnings; warmup runs; `scripts/` has extra analysis (incl. a Welch t-test script) [V/K] https://github.com/sharkdp/hyperfine
- **MongoDB**: E-Divisive means change-point detection over history; cut false positives drastically (useful notifications 1% → 67%) [V] https://arxiv.org/abs/2003.00584 , slides https://icpe2020.spec.org/slides/Daly_Use.pdf ; library https://github.com/mongodb/signal-processing-algorithms ; successor Apache Otava (Hunter) [V] https://arxiv.org/abs/2505.06758
- **Bencher.dev**: per-metric thresholds with tests percentage, z-score, t-test, log-normal, IQR, delta-IQR, static; min/max sample sizes and window configurable [V] https://bencher.dev/docs/explanation/thresholds/
- **Conbench**: "lookback z-score" of the contender against a distribution of up to 100 ancestor commits (`DISTRIBUTION_COMMITS`), baseline = fork point for PRs [V] https://conbench.github.io/conbench/pages/lookback_zscore.html (threshold value configurable; default not stated on that page).

Pattern across tools: (1) a significance test *and* (2) a magnitude/noise floor — significance alone flags trivial changes, magnitude alone flags noise. holobench should do both, with the floor calibrated from A/A data.

### A8. Bayesian alternative

Posterior P(PR faster), P(within ROPE ±Δ), and a 95% HDI read naturally to reviewers ("93% probability the PR is ≥2% faster"). Kruschke's HDI+ROPE rule gives the same three-way accept/reject/undecided as TOST [K] https://doi.org/10.1177/2515245918771304 . A cheap version: Bayesian bootstrap of the log ratio, or Beta-Binomial (Beta(1,1) prior) for success rates — P(p_PR > p_base) by Monte Carlo. Recommendation: keep frequentist CIs as the gating rule (easier to audit, matches tools above) and optionally print "P(improvement)" as a reading aid.

---

## B. Graphical representation

### B1. Plot types that are correct and readable

- **Estimation plots (Gardner–Altman for 2 groups, Cumming for many)**: raw data swarm + effect size with bootstrap CI on a floating/second axis. DABEST (Ho et al. 2019, *Nature Methods*) [K] https://doi.org/10.1038/s41592-019-0470-3 ; `dabest` Python https://github.com/ACCLAB/DABEST-python . Best single per-metric figure for base vs PR.
- **Raincloud plots** (half-violin + jittered points + box) (Allen et al. 2019) [K] https://doi.org/10.12688/wellcomeopenres.15191.2 — shows bimodality and outliers.
- **Forest plot**: one row per metric or sweep point, effect (log ratio) ± CI, vertical line at 1.0, shaded equivalence band ±Δ. Best "many comparisons" overview; sort by effect or group by metric.
- **Slope / dumbbell plot**: paired base→PR per seed or per sweep point; colour lines by direction.
- **ECDF overlay + shift function** (deciles difference with CIs) (Rousselet, Pernet, Wilcox 2017) [K] https://doi.org/10.1111/ejn.13610 — shows "tail got worse while median improved".
- **Verdict bar**: CI of the ratio drawn over a strip with the ±Δ region shaded; the glyph follows the A3 four-way rule.
- **Small multiples**: same axes per metric/sweep slice; avoid one overloaded chart.
- **History strip / sparkline**: base-branch history with change points (asv/E-divisive) to put the PR value in context.
- **Waffle chart** (10×10) for success rates: counts are concrete (e.g. 47/50 green, 3 red); add Wilson CI text.
- **2-D sweep heatmap**: diverging colour = log ratio centred on 1.0; mask/hatch cells whose CI crosses the margin or that fail FDR; annotate values.

### B2. What misleads

- **Bar-of-means ("dynamite plots")** hide n, distribution and outliers (Weissgerber et al. 2015) [K] https://doi.org/10.1371/journal.pbio.1002128 .
- **Error bars** are misread as hard boundaries; gradient / violin intervals do better (Correll & Gleicher 2014) [K] https://doi.org/10.1109/TVCG.2014.2346298 .
- **Radar charts**: area grows with the square of the values, and axis order changes the shape; the axes are not comparable [K] https://www.data-to-viz.com/caveat/spider.html .
- **Dual-axis charts**: readers infer false crossings and correlations from arbitrary scale choices (Isenberg et al. 2011) [K] https://doi.org/10.1109/TVCG.2011.160 .
- **Honest uncertainty**: **quantile dotplots** (Kay et al. 2016) [K] https://doi.org/10.1145/2858036.2858558 and Fernandes et al. 2018 [K] https://doi.org/10.1145/3173574.3173718 improve probability judgement; gradient/fan intervals (50/80/95%); hypothetical outcome plots (HOPs, animated) (Hullman et al. 2015) [K] https://doi.org/10.1371/journal.pone.0142444 .

### B3. Scorecard / verdict tile

One row of tiles, one per primary metric: metric name; big number "−8.3%" (or "47/50 → 50/50"); small CI "[−11.2, −5.1]% 95% CI"; mini verdict bar with ±Δ band; glyph + word (never colour alone): ▲ improved, ▼ regressed, ≈ equivalent, ? inconclusive; footer "n=20 paired, MDE 4%". In Markdown, a short list of the same content works where image tiles are not wanted.

Palettes: **Okabe–Ito** for categories (base vs PR) [K] https://jfly.uni-koeln.de/color/ ; **viridis/cividis** for sequential [K] https://bids.github.io/colormap/ ; for diverging good/bad use blue–orange (colourblind-safe), not red–green. Pair colour with shape/glyph.

### B4. GitHub rendering constraints

- **Uploads (user-attachments)**: images and GIFs up to 10 MB; video up to 10 MB on free plans, 100 MB on paid plans; formats PNG, GIF, JPEG, SVG, MP4, MOV, WebM; H.264 recommended [V] https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/attaching-files . Uploads need a browser session or an unofficial API path; the common CI pattern is to commit images to a branch/orphan branch or gist and link raw URLs, or publish via Pages/artifacts.
- **Images are proxied through Camo**; SVG is served as an image (`<img>`), so scripts, external fonts and interactivity do not run. Embed fonts as paths or use generic font families; keep text as `<text>` only with safe fonts.
- **Dark/light**: `<picture>` with `<source media="(prefers-color-scheme: dark)" srcset=...>` plus `<img>` fallback is the supported method; the `#gh-dark-mode-only` / `#gh-light-mode-only` fragments are **deprecated** and "will be removed" [V] https://github.blog/developer-skills/github/how-to-make-your-images-in-markdown-on-github-adjust-for-dark-mode-and-light-mode/ ; `<picture>` support listed in the formatting docs [V] https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax . Alternative: transparent PNG/SVG with mid-grey text that reads on both.
- **Mermaid**: rendered natively in ```mermaid blocks [K] https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams . `xychart-beta` supports only bar and line, numeric y, categorical or numeric x, horizontal option, multiple series; **no error bars or statistical overlays** [V] https://mermaid.js.org/syntax/xyChart.html . GitHub's Mermaid version can lag the upstream docs — test-render before relying on newer options (legend 11.17, data labels 11.14). Use Mermaid for flow (what ran where), not for evidence charts.
- **HTML subset**: `<details>/<summary>`, `<picture>`, `<table>`, `<sub>/<sup>`, `<kbd>`, `<img width>`, `align`; no `<style>`, no `style=` CSS, no JS (sanitized) [K] https://github.com/github/markup#github-markup . **Math**: `$...$` and `$$...$$` (MathJax) [K] https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/writing-mathematical-expressions . PR body limit is 65,536 characters [K].
- **Video earns its place** when the difference is spatial/temporal and a static plot loses it: robot trajectory base vs PR side by side or overlaid, a recovery manoeuvre, a stall. It does not earn its place for scalar metrics; an animated distribution build-up (HOPs) is a nice-to-have at most. Keep ≤10 MB H.264, a few seconds, loop-friendly; always give a static poster image plus the numbers, because video does not autoplay in all clients.

### B5. Python libraries

- Plotting/export: matplotlib (+ seaborn objects API) → SVG/PNG directly; plotnine (ggplot grammar) on matplotlib; plotly static via kaleido https://github.com/plotly/Kaleido ; altair via vl-convert https://github.com/vega/vl-convert (pure-Rust, no browser, good SVG).
- Estimation: `dabest` (bootstrap estimation plots; pandas-based).
- Stats: `scipy.stats.bootstrap` (BCa default, paired), `mannwhitneyu`, `wilcoxon`, `ttest_ind(equal_var=False)`, `false_discovery_control`, `binomtest`, `fisher_exact`, `barnard_exact`, `ks_2samp`, `permutation_test`; `statsmodels`: `proportion_confint`, `confint_proportions_2indep`, `test_proportions_2indep`, `ttost_ind/ttost_paired`, `multipletests`, `samplesize_confint_proportion`, power classes (`TTestIndPower`).
- Change points (history): `signal-processing-algorithms` (E-Divisive), `ruptures`.

---

## Recommended design for holobench (synthesis)

1. Default effect: log ratio PR/base (paired when runs interleave), BCa bootstrap CI (t on logs when n<8), HL + MWU/Wilcoxon as robustness cross-check.
2. Binary: Wilson per arm, Newcombe for the difference, Barnard exact test, "clean runs needed" via (1−p0)^n ≤ α.
3. Verdict from CI vs pre-declared per-metric margin Δ (non-inferiority / TOST): improved / regressed / equivalent / inconclusive / trivial. Print MDE.
4. Holm on primary metrics (gate), BH-FDR on sweep cells (flag).
5. Adaptive repeats with a confidence sequence or Pinpoint-style two-threshold "need more runs" state.
6. A/A calibration job sets noise floor per metric/runner class.
7. Report: verdict tiles (image + Markdown list) → forest plot with ±Δ band → per-metric estimation/raincloud plot in `<details>` → sweep heatmap with masking → ECDF/shift function for tails → optional video for trajectories. `<picture>` light/dark, Okabe–Ito, glyph + word for every colour.
