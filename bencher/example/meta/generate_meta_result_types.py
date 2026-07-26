"""Meta-generator: Result Type Showcase.

Demonstrates each result type at different input dimensionalities.
Each generated example is self-contained with an inline class definition.
"""

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "result_types"

RESULT_TYPES = [
    "result_var",
    "result_bool",
    "result_vec",
    "result_string",
    "result_path",
    "result_dataset",
]

VALID_COMBOS = {
    "result_var": [0, 1, 2],
    "result_bool": [0, 1, 2],
    "result_vec": [1, 2],
    "result_string": [0, 1],
    "result_path": [0, 1],
    "result_dataset": [1, 2],
}


def _build_response_timer_code():
    """ResponseTimer: measures request latency."""
    return (
        "import math",
        "ResponseTimer",
        '["latency"]',
        {
            0: '["endpoint"]',
            1: '["concurrency"]',
            2: '["endpoint", "concurrency"]',
        },
        'class ResponseTimer(bn.ParametrizedSweep):\n    """Measures HTTP request latency across endpoints and concurrency levels."""\n\n    endpoint = bn.StringSweep(["api/users", "api/orders"], doc="API endpoint")\n    concurrency = bn.FloatSweep(default=50, bounds=[1, 100], doc="Concurrent requests")\n\n    latency = bn.ResultFloat(units="ms", doc="Response latency")\n\n    def benchmark(self):\n        base = {"api/users": 12.0, "api/orders": 25.0}[self.endpoint]\n        self.latency = base + 0.5 * math.log1p(self.concurrency)',
    )


def _build_health_checker_code():
    """HealthChecker: checks if service is healthy."""
    return (
        "import math",
        "HealthChecker",
        '["healthy"]',
        {
            0: '["difficulty"]',
            1: '["threshold"]',
            2: '["threshold", "difficulty"]',
        },
        'class HealthChecker(bn.ParametrizedSweep):\n    """Checks whether a service passes its health threshold."""\n\n    threshold = bn.FloatSweep(default=0.5, bounds=[0.1, 0.9], doc="Decision threshold")\n    difficulty = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Problem difficulty")\n\n    healthy = bn.ResultBool(doc="Whether the service is healthy")\n\n    def benchmark(self):\n        score = math.sin(math.pi * self.threshold) * (1.0 - 0.5 * self.difficulty)\n        self.healthy = score > 0.5',
    )


def _build_system_metrics_code():
    """SystemMetrics: returns [cpu, mem, disk] vector."""
    return (
        "import math",
        "SystemMetrics",
        '["metrics"]',
        {
            1: '["load"]',
            2: '["load", "instances"]',
        },
        'class SystemMetrics(bn.ParametrizedSweep):\n    """Returns a [cpu, mem, disk] utilization vector."""\n\n    load = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="System load factor")\n    instances = bn.FloatSweep(default=5.0, bounds=[1.0, 10.0], doc="Number of instances")\n\n    metrics = bn.ResultVec(3, "%", doc="CPU, memory, disk utilization")\n\n    def benchmark(self):\n        cpu = 20.0 + 70.0 * math.sin(math.pi * self.load / 2.0)\n        mem = 30.0 + 50.0 * self.load * math.log1p(self.instances)\n        disk = 10.0 + 40.0 * math.sqrt(self.load * self.instances / 10.0)\n        self.metrics = [cpu, mem, disk]',
    )


def _build_log_formatter_code():
    """LogFormatter: formats a log report."""
    return (
        "import math",
        "LogFormatter",
        '["report"]',
        {
            0: '["level"]',
            1: '["level", "verbosity"]',
        },
        'class LogFormatter(bn.ParametrizedSweep):\n    """Formats a structured log report string."""\n\n    level = bn.StringSweep(["info", "warn", "error"], doc="Log severity level")\n    verbosity = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Output verbosity")\n\n    report = bn.ResultString(doc="Formatted log report")\n\n    def benchmark(self):\n        detail = int(math.ceil(self.verbosity * 5))\n        text = (\n            f"Level: {self.level}\\n"\n            f"\\tVerbosity: {self.verbosity:.2f}\\n"\n            f"\\tDetail depth: {detail}"\n        )\n        self.report = bn.tabs_in_markdown(text)',
    )


def _build_report_exporter_code():
    """ReportExporter: writes a text report file."""
    return (
        "import math",
        "ReportExporter",
        '["file_result"]',
        {
            0: '["format_type"]',
            1: '["format_type"]',
        },
        'class ReportExporter(bn.ParametrizedSweep):\n    """Writes a text report file in the requested format."""\n\n    format_type = bn.StringSweep(["summary", "detailed", "raw"], doc="Report format")\n\n    file_result = bn.ResultPath(doc="Generated report file")\n\n    def benchmark(self):\n        filename = bn.gen_path(self.format_type, suffix=".txt")\n        line_count = {"summary": 5, "detailed": 20, "raw": 50}[self.format_type]\n        with open(filename, "w", encoding="utf-8") as f:\n            for i in range(line_count):\n                f.write(f"[{self.format_type}] line {i + 1}: value={math.sin(i):.4f}\\n")\n        self.file_result = filename',
    )


def _build_timeseries_collector_code():
    """TimeseriesCollector: returns xarray dataset."""
    return (
        "import math",
        "TimeseriesCollector",
        '["result_ds"]',
        {
            1: '["duration"]',
            2: '["duration", "sample_rate"]',
        },
        'class TimeseriesCollector(bn.ParametrizedSweep):\n    """Collects a timeseries and returns it as an xarray dataset."""\n\n    duration = bn.FloatSweep(default=5.0, bounds=[1.0, 10.0], doc="Collection duration")\n    sample_rate = bn.FloatSweep(default=1.0, bounds=[0.5, 2.0], doc="Samples per second")\n\n    result_ds = bn.ResultDataSet(doc="Collected timeseries dataset")\n\n    def benchmark(self):\n        import xarray as xr\n\n        n_samples = max(1, int(self.duration * self.sample_rate))\n        values = [math.sin(2 * math.pi * i / max(n_samples, 1)) * self.duration for i in range(n_samples)]\n        data_array = xr.DataArray(values, dims=["time"], coords={"time": list(range(n_samples))})\n        ds = xr.Dataset({"result_ds": data_array})\n        self.result_ds = bn.ResultDataSet(ds.to_pandas())',
    )


BENCHABLE_MAP = {
    "result_var": _build_response_timer_code,
    "result_bool": _build_health_checker_code,
    "result_vec": _build_system_metrics_code,
    "result_string": _build_log_formatter_code,
    "result_path": _build_report_exporter_code,
    "result_dataset": _build_timeseries_collector_code,
}


class MetaResultTypes(MetaGeneratorBase):
    """Generate Python examples demonstrating each result type."""

    result_type = bn.StringSweep(RESULT_TYPES, doc="Result type to demonstrate")
    input_dims = bn.IntSweep(default=0, bounds=(0, 2), doc="Number of input dimensions")

    def benchmark(self):
        if self.input_dims not in VALID_COMBOS.get(self.result_type, []):
            return

        imports, class_name, result_vars, input_vars_map, class_code = BENCHABLE_MAP[
            self.result_type
        ]()
        input_vars_code = input_vars_map[self.input_dims]

        sub_dir = f"{OUTPUT_DIR}/{self.result_type}"
        function_name = f"example_{self.result_type}_{self.input_dims}d"
        filename = function_name
        title = f"{self.result_type.replace('_', ' ').title()}: {self.input_dims}D input"

        desc_map = {
            "result_var": "a scalar numeric metric with units",
            "result_bool": "a boolean pass/fail outcome",
            "result_vec": "a fixed-size numeric vector",
            "result_string": "a formatted markdown string",
            "result_path": "a downloadable file output",
            "result_dataset": "an xarray/pandas dataset",
        }
        description = (
            f"Demonstrates {desc_map.get(self.result_type, self.result_type)} "
            f"with {self.input_dims}D input sweep."
        )

        sd = 2 if self.input_dims >= 2 else 3
        self.generate_sweep_example(
            title=title,
            output_dir=sub_dir,
            filename=filename,
            function_name=function_name,
            benchable_class=class_name,
            benchable_module=None,
            input_vars=input_vars_code,
            result_vars=result_vars,
            class_code=class_code,
            extra_imports=[imports],
            description=description,
            run_kwargs={"subsampling_divisions": sd},
        )


def example_meta_result_types(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = MetaResultTypes().to_bench(run_cfg)

    bench.plot_sweep(
        title="Result Types",
        input_vars=[
            bn.sweep("result_type", RESULT_TYPES),
            bn.sweep("input_dims", [0, 1, 2]),
        ],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_result_types)
