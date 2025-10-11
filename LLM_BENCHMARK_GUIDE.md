
# LLM Guide to Benchmarking with `bencher`

This guide provides a comprehensive overview of how to create and run benchmarks using the `bencher` library. It is designed to be used by an LLM to automate the process of creating benchmarks for various functions and scenarios.

## Core Concepts

The `bencher` library is built around a few core concepts:

- **`ParametrizedSweep`:** A class that defines the input parameters and result variables for a benchmark.
- **Sweeps:** These define the input parameters for a benchmark. `bencher` provides several types of sweeps, including:
    - `bch.FloatSweep`: For sweeping over a range of floating-point numbers.
    - `bch.IntSweep`: For sweeping over a range of integers.
    - `bch.StringSweep`: For sweeping over a list of strings.
    - `bch.EnumSweep`: For sweeping over the members of an enum.
- **`ResultVar`:** A class that defines the result variables for a benchmark.
- **`__call__` method:** The method that contains the actual benchmarking logic. It takes the input parameters as arguments and returns a dictionary of the results.
- **`to_bench` method:** A method that converts the `ParametrizedSweep` class into a `bch.Bench` object.
- **`Bench` object:** An object that represents a benchmark and provides methods for running it and plotting the results.
- **`BenchRunner`:** A class that is used to run multiple benchmarks.
- **`BenchRunCfg`:** A class that is used to configure a benchmark run.

## Steps to Create a Benchmark

1.  **Define the Benchmark Function:**
    - Create a class that inherits from `bch.ParametrizedSweep`.
    - Define the input parameters as class attributes using the appropriate sweep classes (e.g., `bch.FloatSweep`, `bch.StringSweep`).
    - Define the result variables as class attributes using `bch.ResultVar`.
    - Implement the `__call__` method. This method should:
        - Take the input parameters as arguments.
        - Run the code that you want to benchmark.
        - Return a dictionary of the results.

2.  **Create a Benchmark Factory Function:**
    - Create a function that takes an optional `run_cfg: bch.BenchRunCfg | None = None` argument.
    - Inside the function, create an instance of your `ParametrizedSweep` class.
    - Call the `to_bench()` method on the instance to create a `bch.Bench` object.
    - Optionally, call the `plot_sweep()` method on the `bch.Bench` object to configure the plot.
    - Return the `bch.Bench` object.

3.  **Run the Benchmark:**
    - Create an instance of `bch.BenchRunner`.
    - Add your benchmark factory function to the runner using the `add()` method.
    - Call the `run()` method on the runner to execute the benchmark.

## Complete Example

Here is a complete example of how to create and run a benchmark using `bencher`:

```python
import bencher as bch
import math
import random

# 1. Define the Benchmark Function
class MyBenchmark(bch.ParametrizedSweep):
    # Input Parameters
    input_float = bch.FloatSweep(default=1.0, bounds=[0.0, 10.0])
    input_string = bch.StringSweep(["a", "b", "c"])

    # Result Variables
    result_sin = bch.ResultVar(units="radians")
    result_cos = bch.ResultVar(units="radians")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        # Benchmark logic
        self.result_sin = math.sin(self.input_float) + random.uniform(0, 0.1)
        self.result_cos = math.cos(self.input_float) + random.uniform(0, 0.1)

        return super().__call__()

# 2. Create a Benchmark Factory Function
def benchmark_factory(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = MyBenchmark().to_bench(run_cfg)
    bench.plot_sweep(
        title="My Benchmark",
        description="A simple benchmark example",
        post_description="This benchmark demonstrates how to use `bencher` to benchmark a simple function.",
    )
    return bench

# 3. Run the Benchmark
if __name__ == "__main__":
    br = bch.BenchRunner(run_tag="my_benchmark_run")
    br.add(benchmark_factory)
    br.run(repeats=2, level=2, save=True)
```

## How to Use This Guide

When you are asked to create a benchmark for a function or scenario, follow these steps:

1.  **Identify the input parameters:** Determine the input parameters for the benchmark and their types (e.g., float, int, string).
2.  **Identify the result variables:** Determine the result variables for the benchmark and their units.
3.  **Create the `ParametrizedSweep` class:** Create a class that inherits from `bch.ParametrizedSweep` and define the input parameters and result variables.
4.  **Implement the `__call__` method:** Implement the `__call__` method to run the benchmark and calculate the results.
5.  **Create the benchmark factory function:** Create a function that creates an instance of your `ParametrizedSweep` class and returns a `bch.Bench` object.
6.  **Create a new file:** Create a new file in the `bencher/example` directory to store your benchmark. The filename should be descriptive of the benchmark.
7.  **Add the benchmark to the `BenchRunner`:** If you want to run the benchmark as part of a larger suite of benchmarks, you can add it to a `BenchRunner` in a file like `bencher/example/example_benchrunner.py`.
8.  **Run the benchmark:** Run the benchmark and analyze the results.

By following these steps, you can create and run benchmarks for a wide variety of functions and scenarios using the `bencher` library.
