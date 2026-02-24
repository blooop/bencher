# 10 - Integrations

## Optuna Integration

**Files**: `bencher/optuna_conversions.py`, `bencher/results/optuna_result.py`

Converts bencher sweep parameters to Optuna distributions for hyperparameter optimization. Supports single-objective (minimize/maximize one ResultVar) and multi-objective (Pareto front for multiple ResultVars with OptDir).

| Bencher Type | Optuna Distribution |
|-------------|---------------------|
| `IntSweep` | `IntDistribution(low, high)` |
| `FloatSweep` | `FloatDistribution(low, high)` |
| `EnumSweep`/`StringSweep` | `CategoricalDistribution(choices)` |
| `BoolSweep` | `CategoricalDistribution([False, True])` |

Key entry points: `optuna_grid_search()` (creates GridSampler study), `cfg_from_optuna_trial()` (creates ParametrizedSweep from trial), `OptunaResult.collect_optuna_plots()` (generates visualization suite: history, importance, Pareto, contour).

## Rerun Integration

**Files**: `bencher/utils_rerun.py`, `bencher/flask_server.py`

Optional dependency (guarded by `try/except` in `__init__.py`). Integrates the Rerun 3D/2D visualization SDK.

Key functions: `rerun_to_pane()` (render recording as Panel widget), `rrd_to_pane()` (display `.rrd` via web viewer iframe), `publish_and_view_rrd()` (publish to git branch), `run_flask_in_thread()` (local file server on port 8001).

## Panel Server & Reports

**Files**: `bencher/bench_plot_server.py`, `bencher/bench_report.py`

`BenchPlotServer` loads cached BenchResults from diskcache and serves them via Panel web server (two-level index: `bench_name` → `bench_cfg_hash` → `BenchResult`).

`BenchReport` extends `BenchPlotServer` with HTML report generation:
- `save()` → static HTML with embedded JS/CSS
- `show()` → interactive Panel server
- `publish_gh_pages()` → pushes to gh-pages branch via `GithubPagesCfg`

## Video Generation

**Files**: `bencher/video_writer.py`

`VideoWriter` composes image sequences into video using moviepy (H.264 codec, 30fps, CRF 23). Helper functions: `create_label()`, `label_image()`, `extract_frame()`, `convert_to_compatible_format()`.
