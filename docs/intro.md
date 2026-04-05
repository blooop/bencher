# Feature Guide

A tour of bencher's capabilities — what happens as you add dimensions, repeats,
time-tracking, and optimization. For installation, quick-start code, and API tables,
see [Getting Started](how_to_use_bencher.md).

## Adding Dimensions

As you add input parameters, Bencher automatically adapts the visualization:

| Inputs | Visualization |
|--------|---------------|
| 1 float | [Line plot](reference/meta/1_float/no_repeats/index) |
| 1 float + categories | [Line plot with color/facets](reference/meta/1_float/no_repeats/index) |
| 2 floats | [Heatmap](reference/meta/2_float/no_repeats/index) |
| Categories only | [Bar chart](reference/meta/0_float/no_repeats/index) |

No code changes to plotting logic are needed — the type signature of your parameters drives the selection. See [Automatic Plot Selection](concepts.md#automatic-plot-selection) for how this works, and the [Cartesian Animation](reference/meta/cartesian_animation/index) gallery for an animated visualization of how each dimension builds on the last.

## Repeats and Statistics

Sample each point multiple times to get a statistical distribution:

```python
bn.run(SimpleFloat, level=3, repeats=10)
```

Or with the manual API:

```python
bench.plot_sweep(run_cfg=bn.BenchRunCfg(repeats=10))
```

With repeats, plots automatically show mean +/- standard deviation. See the
[Repeated](reference/meta/0_float/with_repeats/index) gallery for examples, and the
[Statistics gallery](reference/meta/statistics/index) for distributions, error bands, and
repeat-count comparisons.

Bencher assumes your function is a stochastic pure function — given the same inputs it returns the same output +/- random noise. Each call must not be influenced by external state.

## Tracking Over Time

Enable `over_time` to record time-series snapshots that can be scrubbed via a slider:

```python
bn.run(MyBench, level=3, repeats=3, over_time=True)
```

For multi-snapshot tracking (e.g. CI pipelines), call `plot_sweep()` in a loop with different `time_src` values:

```python
run_cfg = bn.BenchRunCfg(over_time=True, repeats=3)
benchable = MyBench()
bench = benchable.to_bench(run_cfg)

for i in range(5):
    bench.plot_sweep(
        input_vars=["param1"],
        result_vars=["metric"],
        run_cfg=run_cfg,
        time_src=bn.git_time_event(),  # or a datetime
    )
```

Each run adds a time slider to the plots. When combined with repeats, the Optuna importance analysis shows both `repeat` and `over_time` alongside input parameters — revealing whether measurement noise or temporal drift dominates. See the [Over Time](reference/meta/0_float/over_time/index) and [Over Time + Repeated](reference/meta/0_float/over_time_repeats/index) gallery sections, plus the [Time Event](reference/meta/advanced/example_advanced_time_event) and [Git Time Event](reference/meta/advanced/example_advanced_git_time_event) advanced examples.

## Optimisation

### Parameter Importance Analysis

When `use_optuna=True`, Bencher integrates with [Optuna](https://optuna.org/) for parameter importance analysis:

```python
bn.run(MyBench, level=3, repeats=3, optimise=30)
```

Or with the manual API:

```python
run_cfg = bn.BenchRunCfg(use_optuna=True, repeats=3)
res = bench.plot_sweep(run_cfg=run_cfg)
bench.report.append(res.to_optuna_plots())
```

The importance plots show which parameters matter most, including `repeat` (measurement noise) and `over_time` (temporal drift) when present. See the [Optimization gallery](reference/meta/optimization/index) for 1D and 2D examples with single and multi-objective optimization.

### Aggregated Optimisation

Mark a variable with `optimize=False` to sweep it without optimising — Optuna averages results across its values:

```python
class MyBench(bn.ParametrizedSweep):
    algorithm = bn.StringSweep(["adam", "sgd", "rmsprop"], optimize=False)
    learning_rate = bn.FloatSweep(default=0.01, bounds=[0.001, 1.0])
    loss = bn.ResultFloat("loss", bn.OptDir.minimize)
```

Optuna only suggests `learning_rate` and reports the mean loss across all algorithms. This finds settings that work best **across** categories rather than the best (category, setting) pair. See the [Aggregated](reference/meta/optimization_aggregated/index) examples.

### Direct Optimisation API

Use `bench.optimize()` or the one-liner `to_optimize()` for direct optimisation without a grid sweep:

```python
# One-liner
result = MyBench().to_optimize(n_trials=50)
print(result.summary())

# Or via bn.run() — runs a grid sweep then optimises with 30 extra trials
bn.run(MyBench, level=3, optimise=30)
```

## Composable Containers

Bencher includes a composable container system for combining visual outputs. See the [Composition](concepts.md#composition) section in A Grammar of Benchmarking and the [Composable Containers](reference/meta/composable_containers/index) gallery.

## Sampling and Level System

The `level` parameter controls sampling density across all dimensions with a single knob. Higher levels are strict supersets of lower ones, so cached results are reused automatically. See [The Level System](concepts.md#the-level-system) for the conceptual explanation, the [Level System](reference/meta/levels/index) gallery for an interactive demo, and the [Sampling Strategies](reference/meta/sampling/index) gallery for related sampling techniques.

## Running Examples

If you have [pixi](https://github.com/prefix-dev/pixi/) installed:

```bash
pixi run demo
```

Example output: <https://blooop.github.io/bencher/>

Browse the [Gallery Overview](reference/meta/gallery) to see all examples with interactive reports.

## Algorithm

    Enumerate all input parameter combinations (Cartesian product)
    for each set of input parameters:
        pass the inputs to the objective function and store results in the N-D array

        get unique hash for the set of input parameters
        look up previous results for that hash
        if it exists:
            load historical data
            combine latest data with historical data

        store the results using the input hash as a key
    deduce the type of plot based on the input and output types
    return data and plot
