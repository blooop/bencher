# Usage

## Minimal Example

Define a `ParametrizedSweep` class with typed input parameters and result variables, then call `plot_sweep()`:

```python
import math
import bencher as bch

class SimpleFloat(bch.ParametrizedSweep):
    theta = bch.FloatSweep(default=0, bounds=[0, math.pi], units="rad", samples=30)
    out_sin = bch.ResultVar(units="v", doc="sin of theta")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out_sin = math.sin(self.theta)
        return super().__call__(**kwargs)

bench = SimpleFloat().to_bench()
bench.plot_sweep()
```

Bencher computes the Cartesian product of all input parameters, evaluates your function at every combination, caches the results, and automatically selects appropriate visualizations based on parameter types.

## Input Types

Define your search space with typed sweep classes:

- `FloatSweep` — continuous float range with bounds
- `IntSweep` — discrete integer range with bounds
- `EnumSweep` — Python enum members
- `BoolSweep` — True/False
- `StringSweep` — categorical string values
- `YamlSweep` — configurations loaded from a YAML file

Input types should be basic datatypes so that the data can be hashed, cached, and processed with xarray. See the [Parameters](concepts.md#parameters-input-space) section in A Grammar of Benchmarking for details.

## Result Types

Declare what your benchmark function returns:

- `ResultVar` — a numeric scalar with units and an optimization direction (minimize/maximize)
- `ResultBool` — a boolean result
- `ResultVec` — a fixed-size numeric vector
- `ResultImage`, `ResultVideo`, `ResultPath` — file outputs
- `ResultString`, `ResultDataSet` — structured outputs

See the [Result Types](reference/meta/result_types/index) gallery for examples of each type.

## Adding Dimensions

As you add input parameters, Bencher automatically adapts the visualization:

| Inputs | Visualization |
|--------|---------------|
| 1 float | [Line plot](reference/meta/1_float/no_repeats/index) |
| 1 float + categories | [Line plot with color/facets](reference/meta/1_float/no_repeats/index) |
| 2 floats | [Heatmap](reference/meta/2_float/no_repeats/index) |
| Categories only | [Bar chart](reference/meta/0_float/no_repeats/index) |

No code changes to plotting logic are needed — the type signature of your parameters drives the selection. See [Automatic Plot Selection](concepts.md#automatic-plot-selection) for how this works.

## Repeats and Statistics

Sample each point multiple times to get a statistical distribution:

```python
bench.plot_sweep(run_cfg=bch.BenchRunCfg(repeats=10))
```

With repeats, plots automatically show mean +/- standard deviation. See the [Repeated](reference/meta/0_float/with_repeats/index) gallery sections for examples.

Bencher assumes your function is a stochastic pure function — given the same inputs it returns the same output +/- random noise. Each call must not be influenced by external state.

## Tracking Over Time

Track how results change across successive runs:

```python
run_cfg = bch.BenchRunCfg(over_time=True, repeats=3)
bench.plot_sweep(run_cfg=run_cfg, time_src=bch.git_time_event())
```

Each run adds a time slider to the plots. See the [Over Time](reference/meta/0_float/over_time/index) and [Over Time + Repeated](reference/meta/0_float/over_time_repeats/index) gallery sections.

## Optimisation

### Automatic Importance Analysis

When `use_optuna=True`, Bencher integrates with [Optuna](https://optuna.org/) for parameter importance analysis and optimisation:

```python
run_cfg = bch.BenchRunCfg(use_optuna=True, repeats=3)
res = bench.plot_sweep(run_cfg=run_cfg)
res.to_optuna_plots()  # parameter importance, Pareto fronts
```

See the [Optimisation](reference/meta/optimisation/index) gallery section.

### Aggregated Optimisation

Mark a variable with `optimize=False` to sweep it without optimising — Optuna averages results across its values:

```python
algorithm = bch.StringSweep(["adam", "sgd", "rmsprop"], optimize=False)
learning_rate = bch.FloatSweep(default=0.01, bounds=[0.001, 1.0])
```

Optuna only suggests `learning_rate` and reports the mean loss across all algorithms. See the [Aggregated](reference/meta/optimization_aggregated/index) examples.

### Direct Optimisation API

Use `bench.optimize()` or the one-liner `to_optimize()` for direct optimisation:

```python
result = MyBench().to_optimize(n_trials=50)
print(result.summary())
```

## Composable Containers

Bencher includes a composable container system for combining visual outputs. See the [Composition](concepts.md#composition) section in A Grammar of Benchmarking and the [Composable Containers](reference/meta/composable_containers/index) gallery.

## Sampling and Level System

The `level` parameter controls sampling density across all dimensions with a single knob. Higher levels are strict supersets of lower ones, so cached results are reused automatically. See [The Level System](concepts.md#the-level-system) for details and the [Sampling Strategies](reference/meta/sampling/index) gallery.

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
