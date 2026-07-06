# Benchmark Health Scorecard

The scorecard renders a set of benchmark result summaries into a single grouped
HTML page. Every scalar metric shows, at a glance:

- a **verdict** — the latest value, its Δ, and a color from the regression report
  (`regressed` / `improved` / `passed`, or an uncolored `trend` when a metric has
  no regression gate yet); and
- a **noise sparkline** — the per-time-event mean with a ±std band and a node per
  run, plus a right-margin distribution column (one alpha-blended dot per run) and
  the μ mean, so both the trend and the spread of a jittering metric are visible
  without opening each benchmark's full report.

It reads the machine-readable `*.summary.json` written by
{func}`bencher.result_to_json` (with `include_series=True`) for every benchmark
under a reports directory and groups them by category.

## Producing the input

Each benchmark writes its summary with the over-time series attached:

```python
import bencher as bn

result = bench.plot_sweep(...)              # a collected BenchResult
bn.result_to_json(
    result,
    f"reports/benchmarks/{tag}/{result.bench_cfg.bench_name}.summary.json",
    include_series=True,                     # attach the per-event mean/std/n trend
)
```

## Rendering the page

Everything project-specific is injected via
{class}`~bencher.scorecard.ScorecardConfig`, and every field defaults — so the
zero-config path still produces a page:

```python
from bencher.scorecard import Chrome, ReportLayout, ScorecardConfig, generate_scorecard

config = ScorecardConfig(
    registry={"latency_bench": ("Performance", "Latency", "Request latency sweep.")},
    aliases={"wall_time": "duration"},        # equivalent metrics share one column
    percent_metrics=frozenset({"completion"}),  # 0..1 fractions shown as percentages
    layout=ReportLayout(root="benchmarks"),   # <reports_dir>/benchmarks/<tag>/*.summary.json
)
generate_scorecard("reports", config, chrome=Chrome(title="My Health Page"))
```

| `ScorecardConfig` field | purpose |
|---|---|
| `registry` | `tag -> (category, name, description)` for known benchmarks; unknown tags auto-name into `other_category` |
| `aliases` | `raw -> canonical` metric names so equivalent metrics from different benchmarks share a column |
| `percent_metrics` | metric names whose `0..1` value renders as a percentage |
| `layout` | on-disk {class}`~bencher.scorecard.ReportLayout` (root subdir + link pattern) |

## Live example

The example below fabricates benchmark summaries with hand-shaped distributions —
stable, noisy, improving, regressing, converging, spiky — so the sparkline
rendering and verdict colors can be evaluated in isolation. Every distribution
archetype shares one `value` column, so the shapes line up for direct comparison.

```{raw} html
<a class="bencher-report-link" href="scorecard_example/index.html" target="_blank">Open the example scorecard in a new tab &#8599;</a>
<div class="bencher-report-region">
<div class="bencher-report-wrap">
<iframe class="bencher-report" src="scorecard_example/index.html"
        scrolling="no" allowfullscreen
        style="width:100%; min-height:600px; border:none; overflow:hidden;"></iframe>
</div>
<div class="bencher-hscroll"><div class="bencher-hscroll-inner"></div></div>
</div>
```

Source for the example:

```{literalinclude} ../bencher/example/example_scorecard.py
:language: python
```
