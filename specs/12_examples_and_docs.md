# 12 - Examples & Documentation Generation

## Gallery Organization

Examples are organized by input dimensionality:

| Gallery Directory | Description |
|------------------|-------------|
| `docs/reference/0D/` | No input parameters |
| `docs/reference/1D/` | 1 input parameter |
| `docs/reference/2D/` | 2 input parameters |
| `docs/reference/inputs_0_float/` | 0 float + N categorical |
| `docs/reference/inputs_1_float/` | 1 float + N categorical |
| `docs/reference/inputs_2_float/` | 2 float + N categorical |
| `docs/reference/inputs_3_float/` | 3 float + N categorical |
| `docs/reference/meta/` | Meta-generated examples |
| `docs/reference/levels/` | Level-based sampling |
| `docs/reference/pareto/` | Optimization examples |

Naming convention: `example_{N}_float_{M}_cat_in_{K}_out.py`

## Doc Generation Pipeline

```
Python examples (bencher/example/*.py)
  → generate_examples.py (pixi run generate-docs)
    → Jupyter notebooks (docs/reference/*/*.ipynb)
      → sphinx-build (pixi run docs)
        → HTML (docs/builtdocs/) → ReadTheDocs
```

`convert_example_to_jupyter_notebook()` in `bencher/example/meta/generate_examples.py` reads a `.py` file and creates a 3-cell notebook (title markdown, setup code with `%%capture`, plotting code).

Examples are registered manually as `convert_example_to_jupyter_notebook()` calls in the `__main__` block of `generate_examples.py`.

## Example File Pattern

```python
import bencher as bch

class MyBenchmark(bch.ParametrizedSweep):
    x = bch.FloatSweep(default=0, bounds=(0, 10))
    y = bch.ResultVar(units="m")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(kwargs)
        self.y = self.x ** 2
        return super().__call__()

def example_my_benchmark(run_cfg=None, report=None):
    bench = MyBenchmark().to_bench(run_cfg)
    bench.plot_sweep("x", "y")
    return bench

if __name__ == "__main__":
    example_my_benchmark().report.show()
```

## How to Add a New Example

1. Create the example file in `bencher/example/` (or appropriate subdirectory)
2. Subclass `ParametrizedSweep`, implement `__call__()`, create a top-level function
3. Register in `generate_examples.py` with `convert_example_to_jupyter_notebook()` call
4. Run `pixi run generate-docs` to create the notebook
5. Update `docs/conf.py` and relevant `.rst` files if adding a new gallery section
6. Run `pixi run ci` to verify
