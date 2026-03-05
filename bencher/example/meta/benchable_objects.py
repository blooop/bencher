"""Benchable classes demonstrating each result type.

Each class is a minimal ``ParametrizedSweep`` that exercises one result type.
They are used by the meta generators to produce notebook code and can also be
imported directly in notebooks.
"""

import math
import random

import bencher as bch


class BenchableBoolResult(bch.ParametrizedSweep):
    """Demonstrates ResultBool — a boolean pass/fail metric."""

    threshold = bch.FloatSweep(default=0.5, bounds=[0.1, 0.9], doc="Decision threshold")
    difficulty = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Problem difficulty")

    pass_rate = bch.ResultBool(doc="Whether the score exceeded the threshold")

    noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Noise scale")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        score = math.sin(math.pi * self.threshold) * (1.0 - 0.5 * self.difficulty)
        if self.noise_scale > 0:
            score += random.gauss(0, self.noise_scale)
        self.pass_rate = score > 0.5
        return super().__call__()


class BenchableVecResult(bch.ParametrizedSweep):
    """Demonstrates ResultVec — a fixed-size vector output."""

    x = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="X coordinate")
    y = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Y coordinate")

    position = bch.ResultVec(3, "m", doc="3D position vector")

    noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Noise scale")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        vals = [
            math.sin(math.pi * self.x),
            math.cos(math.pi * self.y),
            math.sin(math.pi * (self.x + self.y)),
        ]
        if self.noise_scale > 0:
            vals = [v + random.gauss(0, self.noise_scale) for v in vals]
        self.position = vals
        return super().__call__()


class BenchableStringResult(bch.ParametrizedSweep):
    """Demonstrates ResultString — a markdown string output."""

    label = bch.StringSweep(["alpha", "beta", "gamma"], doc="Label category")
    value = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Numeric value")

    report = bch.ResultString(doc="Formatted report string")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        text = (
            f"Label: {self.label}\n\tValue: {self.value:.3f}\n\tScore: {math.sin(self.value):.3f}"
        )
        self.report = bch.tabs_in_markdown(text)
        return super().__call__()


class BenchablePathResult(bch.ParametrizedSweep):
    """Demonstrates ResultPath — a file download output."""

    content = bch.StringSweep(["report_a", "report_b", "report_c"], doc="Report content variant")

    file_result = bch.ResultPath(doc="Generated report file")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        filename = bch.gen_path(self.content, suffix=".txt")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"content: {self.content}\ntimestamp: deterministic")
        self.file_result = filename
        return super().__call__()


class BenchableDataSetResult(bch.ParametrizedSweep):
    """Demonstrates ResultDataSet — an xarray dataset output."""

    value = bch.FloatSweep(default=5.0, bounds=[0, 10], doc="Base value")
    scale = bch.FloatSweep(default=1.0, bounds=[0.5, 2.0], doc="Scale factor")

    result_ds = bch.ResultDataSet(doc="Generated dataset")

    def __call__(self, **kwargs):
        import numpy as np
        import xarray as xr

        self.update_params_from_kwargs(**kwargs)
        vector = [self.scale * (v + self.value) for v in range(1, 5)]
        data_array = xr.DataArray(vector, dims=["index"], coords={"index": np.arange(len(vector))})
        result_df = xr.Dataset({"result_ds": data_array})
        self.result_ds = bch.ResultDataSet(result_df.to_pandas())
        return super().__call__()


class BenchableMultiObjective(bch.ParametrizedSweep):
    """Demonstrates multi-objective optimization with competing objectives."""

    x = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Design parameter X")
    y = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Design parameter Y")

    performance = bch.ResultVar("score", bch.OptDir.maximize, doc="Performance (maximize)")
    cost = bch.ResultVar("$", bch.OptDir.minimize, doc="Cost (minimize)")

    noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Noise scale")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.performance = math.sin(math.pi * self.x) * math.cos(0.5 * math.pi * self.y) + 0.5
        self.cost = 0.3 + 0.7 * self.x + 0.5 * self.y**2
        if self.noise_scale > 0:
            self.performance += random.gauss(0, self.noise_scale)
            self.cost += random.gauss(0, self.noise_scale * 0.5)
        return super().__call__()


class BenchableIntFloat(bch.ParametrizedSweep):
    """Demonstrates integer vs float sweep comparison."""

    int_input = bch.IntSweep(default=5, bounds=[0, 10], doc="Discrete integer input")
    float_input = bch.FloatSweep(default=5.0, bounds=[0.0, 10.0], doc="Continuous float input")

    output = bch.ResultVar("ul", doc="Computed output")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.output = math.sin(self.int_input * 0.3) + math.cos(self.float_input * 0.2)
        return super().__call__()
