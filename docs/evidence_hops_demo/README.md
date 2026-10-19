# Literature statistics animations (demo, do not merge)

`make_svgs.py` (stdlib only, seeded) writes the animated SVGs in this folder. It reuses the
synthetic data, palette and dot style of `docs/evidence_svg_demo` (PR #1188), so the two
demos can be compared side by side. Here the animation is the method, not ambient emphasis.

```
python docs/evidence_hops_demo/make_svgs.py
```

## Notes on the sources

### Hypothetical outcome plots (HOPs)

- Hullman, Resnick & Adar 2015, "Hypothetical Outcome Plots Outperform Error Bars and
  Violin Plots for Inferences about Reliability of Variable Ordering", PLOS ONE 10(11):
  e0142444. <https://doi.org/10.1371/journal.pone.0142444>
  - Each frame shows one draw from the distribution, a horizontal bar per variable, with a
    frame number in the corner. The frame changes every 400 ms. Viewers could pause and
    step. The y-axis stays fixed.
  - 5000 draws per distribution; viewers watched a median of 89 frames.
  - For "how often is B larger than A" (2 and 3 variables), HOPs had much lower absolute
    error than error bars and violin plots (p < 0.001). With error bars and violins, the
    mean absolute error was never under 36 percentage points on those tasks. For the mean
    of one variable with high variance, HOPs were worse.
- Kale, Nguyen, Kay & Hullman 2019, "Hypothetical Outcome Plots Help Untrained Observers
  Judge Trends in Ambiguous Data", IEEE TVCG 25(1) (InfoVis 2018).
  <https://idl.uw.edu/papers/hops-trends>,
  PDF <https://mucollective.northwestern.edu/files/2018-HOPsTrends-InfoVis.pdf>
  - Experiment 1: each sample showed for 1500 ms with 500 ms cubic-eased transitions
    (the NYT parameters). Experiment 2: 400 ms per sample ("regular HOPs", chosen to match
    Hullman et al.) and 100 ms ("fast HOPs").
  - HOPs at 400 ms gave lower just-noticeable differences than a static ensemble of 50
    lines (est. −1.22 log-likelihood units, 95 % CI −2.18 to −0.26). At 100 ms the gain
    was small and unreliable. Guidance: not so fast that a viewer cannot take in one
    outcome, not so slow that the viewer gets impatient; 400 ms per sample.
- Kale, Kay & Hullman 2021, "Visual Reasoning Strategies for Effect Size Judgments and
  Decisions", IEEE TVCG (VIS 2020). <https://idl.uw.edu/papers/effect-size-judgments>
  - Compared intervals, HOPs, densities and quantile dotplots, with and without means.
    Adding a mean biased users toward ignoring the uncertainty; the best design for
    estimating effect size was not the best for decisions.

What the plates take from this: 400 ms per frame, a hard cut between frames (no tween,
no trail), the frame number on screen, 40 draws in a loop of 16 s, the axes and the data
fixed, only the outcome changing. No mean is drawn on the animated panel.

### Quantile dotplots

- Kay, Kola, Hullman & Munson 2016, "When (ish) is My Bus? User-centered Visualizations of
  Uncertainty in Everyday, Mobile Predictive Systems", CHI 2016.
  <https://doi.org/10.1145/2858036.2858558>, <https://idl.uw.edu/papers/when-ish-is-my-bus>
  - A dotplot of n quantiles of the distribution (20 or 100), so each dot is a 1-in-n
    outcome you can count. With few dots, probability estimates had about 1.15 times lower
    variance than with a density plot.
- Fernandes, Walls, Munson, Hullman & Kay 2018, "Uncertainty Displays Using Quantile
  Dotplots or CDFs Improve Transit Decision-Making", CHI 2018.
  <https://idl.uw.edu/papers/uncertainty-bus>
  - Quantile dotplots (and CDFs) also gave better decisions, not only better estimates.

I found no published animated variant of the quantile dotplot. The plates use the static
20-dot quantile dotplot as the companion of the HOPs in H1 and H2: the same distribution,
counted instead of watched.

### Dance of the confidence intervals and the p values (Cumming)

- Cumming 2006, "Understanding replication: confidence intervals, p values, and what's
  likely to happen next time", ICOTS-7.
  <https://www.stat.auckland.ac.nz/~iase/publications/17/7D3_CUMM.pdf>
  - Figure 1: 20 replications, independent samples of n = 20 from one population, each
    drawn as a mean and 95 % CI, with the population mean μ as a horizontal line. A 95 %
    CI captures on average 83.4 % of replication means, not 95 %.
- Cumming 2008, "Replication and p Intervals", Perspectives on Psychological Science 3(4).
  <https://doi.org/10.1111/j.1745-6924.2008.00079.x>
  - In 25 simulated replications of a typical experiment, p ran from < .001 to .76. Given
    an initial p = .05, the 80 % interval for the next p is about .00008 to .44.
- The "dance of the p values" videos (2009, 2014, 2018) run the simulation live: a new
  replication appears, its CI and p value join the column, and the p values jump.
  <https://www.psychologicalscience.org/video/understanding-replication-confidence-intervals-much-better-than-p-values.html>

What H4 takes from this: 20 replications of one experiment against a fixed true effect, a
new replication every 0.6 s that stays (the column builds up), the p value beside each
CI, and n = 6 against n = 20 side by side.

### Bootstrap build-up (teaching animations)

- Wild, Pfannkuch, Regan & Parsonage 2017, "Accessible Conceptions of Statistical
  Inference: Pulling Ourselves Up by the Bootstraps", International Statistical Review
  85(1): 84–107. <https://doi.org/10.1111/insr.12117>, preprint
  <https://www.stat.auckland.ac.nz/~wild/TEMP/bootstrap.pdf>
  - The VIT animations have three panels on one axis: the data, the resample, and the
    sampling distribution. The data rows chosen with replacement move into the resample;
    the statistic is marked; it drops into the third panel and becomes a dot of a stacked
    dotplot. The first 1 to 5 repetitions play slowly; after that, 20 or 1000 play fast.
  - When the distribution is built, the tails are trimmed to form the percentile interval,
    and the interval is moved up onto the data. Then the construction fades.
  - Design rules they cite: change only a few elements at a time, show the structures
    before the animation starts, let the user control the pace.
- Hesterberg 2015, "What Teachers Should Know About the Bootstrap", The American
  Statistician 69(4). <https://doi.org/10.1080/00031305.2015.1089789>

What H5 takes from this: the three panels on one axis, 6 slow resamples (1.6 s each, the
chosen dots ringed once per pick, the unchosen dimmed, the mean dropping into place), 94
fast ones (0.12 s), then the 5 % tails dimmed, the 90 % interval drawn, and the interval
carried up onto the data.

### Animated transitions

- Heer & Robertson 2007, "Animated Transitions in Statistical Data Graphics", IEEE TVCG
  13(6). <https://homes.cs.washington.edu/~jheer/files/2007-AnimatedTrans-InfoVis.pdf>
  - Animated transitions beat static cuts for tracking changes; staging helps complex
    changes; transitions of about 1 s (the study used 1.25 s).

This applies to a base-to-candidate morph. The plates here do not morph base into
candidate; HOPs papers cut between frames on purpose, so no transition is used.

## Plates

| file | method | each frame | static companion |
|---|---|---|---|
| `h1_hops_shift.svg` | HOPs | one bootstrap draw of the planning_time shift, as a candidate median | 20-dot quantile dotplot and 90 % CI |
| `h2_hops_inconclusive.svg` | HOPs | one t draw of the shift, n = 6 | same |
| `h3_hops_rates.svg` | HOPs | one pair of Jeffreys posterior rates, 17/18 and 18/18 | observed waffles, Newcombe 90 % CI |
| `h4_dance_of_cis.svg` | Cumming's dance | one more replication (CI and p) | the full column at the end |
| `h5_bootstrap_buildup.svg` | VIT bootstrap | one resample, its mean dropping into the distribution | final 90 % interval on the data |
| `h6_hops_forest.svg` | HOPs | one draw per metric for 12 metrics | 90 % CI forest |
| `h7_hops_sweep.svg` | HOPs (Kale et al. trends) | one plausible effect curve over 8 speeds | 90 % CI per speed |

`prefers-reduced-motion` stops the animation and shows the static companion and the final
state.

## Departures

- The Newcombe interval in H3 is the 90 % hybrid score interval computed here, −8.2 to
  +21.5 pp. The #1188 caption gives −8.9 to +25.8 pp.
- Draws per metric in H6 and per speed in H7 are independent; the real runs would share
  VMs, so a joint bootstrap would draw correlated curves.
