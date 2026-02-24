# 09 - Configuration System

## Inheritance Chain

```
param.Parameterized → BenchPlotSrvCfg → BenchRunCfg → BenchCfg
                       (bench_cfg.py:22)  (bench_cfg.py:43)  (bench_cfg.py:305)
```

## BenchPlotSrvCfg (`bench_cfg.py:22`)

| Parameter | Default | Effect |
|-----------|---------|--------|
| `port` | `None` | Panel web server port (None = auto) |
| `allow_ws_origin` | `False` | Add port to WebSocket origin whitelist |
| `show` | `True` | Auto-open browser on serve |

## BenchRunCfg (`bench_cfg.py:43`) — Execution Configuration

### Execution
| Parameter | Default | Effect |
|-----------|---------|--------|
| `repeats` | `1` | Times to repeat each parameter combination |
| `level` | `2` | Sampling level (controls samples per sweep variable) |
| `executor` | `SERIAL` | Execution strategy: SERIAL, MULTIPROCESSING, SCOOP |
| `headless` | `False` | Headless mode (no UI) |

### Caching
| Parameter | Default | Effect |
|-----------|---------|--------|
| `cache_results` | `True` | Enable benchmark-level result caching |
| `cache_samples` | `True` | Enable sample-level function call caching |
| `clear_cache` | `False` | Clear benchmark cache before run |
| `clear_sample_cache` | `False` | Clear sample cache before run |
| `overwrite_sample_cache` | `False` | Force re-execution, overwrite cached samples |
| `only_hash_tag` | `False` | Use tag-only hashing for sample cache keys |
| `only_plot` | `False` | Skip execution if cached, just re-plot |

### Visualization
| Parameter | Default | Effect |
|-----------|---------|--------|
| `auto_plot` | `True` | Auto-generate plots based on data shape |
| `use_optuna` | `False` | Include Optuna optimization plots |
| `render_plotly` | `True` | Enable Plotly for 3D plots |

### Time/History
| Parameter | Default | Effect |
|-----------|---------|--------|
| `over_time` | `False` | Track results over time |
| `clear_history` | `False` | Clear historical data before run |
| `time_event` | `None` | Discrete time event label (e.g., git commit hash) |
| `run_tag` | `""` | Tag for grouping related runs |

Methods: `from_cmd_line()` (static, parses CLI args), `deep()` (deep copy).

## BenchCfg (`bench_cfg.py:305`) — Full Benchmark Protocol

Extends `BenchRunCfg` with sweep parameters:

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `input_vars` | `[]` | Input variables to sweep |
| `result_vars` | `[]` | Result variables to collect |
| `const_vars` | `[]` | Constant variable values (list of tuples) |
| `meta_vars` | `[]` | Meta variables (repeat count, timestamps) |
| `name` | `""` | Benchmark name |
| `tag` | `""` | Tag for cache partitioning |
| `pass_repeat` | `False` | Pass repeat index to worker function |
| `plot_callbacks` | `None` | Custom plot callback functions |

### hash_persistent() (`bench_cfg.py:429-467`)
Core of the caching system. Computes SHA1 hash from: input_vars hashes + result_vars hashes + const_vars + name + tag. If `pass_repeat=False`, excludes repeat count so different repeat counts share cache.

### DimsCfg (`bench_cfg.py:659`)
Extracts dimensionality info from a BenchCfg: dimension names, value ranges, sizes, coordinates. Created during `ResultCollector.setup_dataset()` for xarray construction.
