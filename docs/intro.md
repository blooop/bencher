## Intro

Bencher is a tool to make it easy to benchmark the interactions between the input parameters
to your algorithm and its resulting performance on a set of metrics. It calculates the
[Cartesian product](https://en.wikipedia.org/wiki/Cartesian_product) of a set of variables,
evaluates your function at every combination, and automatically selects appropriate
visualizations based on the types of your parameters.

For the design philosophy behind Bencher, see [Concepts](concepts.md).

## How It Works

Parameters are defined using the [param](https://param.holoviz.org/) library as a config class
with metadata describing the bounds of the search space. You define a benchmarking function that
accepts an instance of the config class and returns a dictionary with string metric names and
float values.

Pass in a list of N parameters and an N-dimensional tensor is returned. You can optionally
sample each point multiple times to get a statistical distribution and track values over time.
By default, data is plotted automatically based on parameter types (continuous, discrete), but
you can also pass in a callback to customize plotting.

Results are stored in a persistent cache so that past evaluations are reused automatically.

## Assumptions

Input types should be one of the basic datatypes (bool, int, float, str, enum, datetime) so
that the data can be hashed, cached, and processed with xarray and plotting functions. You can
use class inheritance to define hierarchical parameter configuration classes that are reused
in larger configurations.

Bencher is designed to work with stochastic pure functions with no side effects. It assumes that
when the objective function is given the same inputs, it will return the same output +/- random
noise. This is because the function must be called multiple times to get a good statistical
distribution, and each call must not be influenced by external state.

### Pseudocode

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

## Demo

If you have [pixi](https://github.com/prefix-dev/pixi/) installed you can run a demo example:

```bash
pixi run demo
```

Example output can be seen here: <https://blooop.github.io/bencher/>

## Composable Containers

Bencher includes a composable container system for combining visual outputs (images, videos, datasets) using four composition strategies defined by `ComposeType`:

- **right** — place items side by side in a row
- **down** — stack items vertically in a column
- **sequence** — display items one after another (e.g. video frames, tabs)
- **overlay** — blend items on top of each other (alpha compositing or averaging)

Three backends are available: `ComposableContainerVideo` (moviepy), `ComposableContainerPanel` (Panel widgets), and `ComposableContainerDataset` (xarray). See `example_composable_backends.py` for a demonstration, and the "Composable Containers" section in the reference gallery for auto-generated examples of each backend and compose type.

## Examples

Most features are demonstrated in the examples folder.

Start with `example_simple_float.py` and explore other examples based on your data types:

- `example_float.py`: More complex float operations
- `example_float2D.py`: 2D float sweeps
- `example_float3D.py`: 3D float sweeps
- `example_categorical.py`: Sweeping categorical values (enums)
- `example_strings.py`: Sweeping categorical string values
- `example_float_cat.py`: Mixing float and categorical values
- `example_image.py`: Output images as part of the sweep
- `example_video.py`: Output videos as part of the sweep
- `example_filepath.py`: Output arbitrary files as part of the sweep
- `example_yaml_sweep_dict.py`: Loads sweeps from a YAML file
- And many others in `bencher/example/`
