"""Meta-generator: Result Type Showcase.

Demonstrates each result type at different input dimensionalities.
Each generated example is self-contained with an inline class definition.
"""

from typing import Any

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
        "\n".join(
            [
                "class ResponseTimer(bn.ParametrizedSweep):",
                '    """Measures HTTP request latency across endpoints and concurrency levels."""',
                "",
                '    endpoint = bn.StringSweep(["api/users", "api/orders"], doc="API endpoint")',
                '    concurrency = bn.FloatSweep(default=50, bounds=[1, 100], doc="Concurrent requests")',
                "",
                '    latency = bn.ResultVar(units="ms", doc="Response latency")',
                "",
                "    def __call__(self, **kwargs):",
                "        self.update_params_from_kwargs(**kwargs)",
                '        base = {"api/users": 12.0, "api/orders": 25.0}[self.endpoint]',
                "        self.latency = base + 0.5 * math.log1p(self.concurrency)",
                "        return super().__call__()",
            ]
        ),
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
        "\n".join(
            [
                "class HealthChecker(bn.ParametrizedSweep):",
                '    """Checks whether a service passes its health threshold."""',
                "",
                '    threshold = bn.FloatSweep(default=0.5, bounds=[0.1, 0.9], doc="Decision threshold")',
                '    difficulty = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Problem difficulty")',
                "",
                '    healthy = bn.ResultBool(doc="Whether the service is healthy")',
                "",
                "    def __call__(self, **kwargs):",
                "        self.update_params_from_kwargs(**kwargs)",
                "        score = math.sin(math.pi * self.threshold) * (1.0 - 0.5 * self.difficulty)",
                "        self.healthy = score > 0.5",
                "        return super().__call__()",
            ]
        ),
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
        "\n".join(
            [
                "class SystemMetrics(bn.ParametrizedSweep):",
                '    """Returns a [cpu, mem, disk] utilization vector."""',
                "",
                '    load = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="System load factor")',
                '    instances = bn.FloatSweep(default=5.0, bounds=[1.0, 10.0], doc="Number of instances")',
                "",
                '    metrics = bn.ResultVec(3, "%", doc="CPU, memory, disk utilization")',
                "",
                "    def __call__(self, **kwargs):",
                "        self.update_params_from_kwargs(**kwargs)",
                "        cpu = 20.0 + 70.0 * math.sin(math.pi * self.load / 2.0)",
                "        mem = 30.0 + 50.0 * self.load * math.log1p(self.instances)",
                "        disk = 10.0 + 40.0 * math.sqrt(self.load * self.instances / 10.0)",
                "        self.metrics = [cpu, mem, disk]",
                "        return super().__call__()",
            ]
        ),
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
        "\n".join(
            [
                "class LogFormatter(bn.ParametrizedSweep):",
                '    """Formats a structured log report string."""',
                "",
                '    level = bn.StringSweep(["info", "warn", "error"], doc="Log severity level")',
                '    verbosity = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Output verbosity")',
                "",
                '    report = bn.ResultString(doc="Formatted log report")',
                "",
                "    def __call__(self, **kwargs):",
                "        self.update_params_from_kwargs(**kwargs)",
                "        detail = int(math.ceil(self.verbosity * 5))",
                "        text = (",
                '            f"Level: {self.level}\\n"',
                '            f"\\tVerbosity: {self.verbosity:.2f}\\n"',
                '            f"\\tDetail depth: {detail}"',
                "        )",
                "        self.report = bn.tabs_in_markdown(text)",
                "        return super().__call__()",
            ]
        ),
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
        "\n".join(
            [
                "class ReportExporter(bn.ParametrizedSweep):",
                '    """Writes a text report file in the requested format."""',
                "",
                '    format_type = bn.StringSweep(["summary", "detailed", "raw"], doc="Report format")',
                "",
                '    file_result = bn.ResultPath(doc="Generated report file")',
                "",
                "    def __call__(self, **kwargs):",
                "        self.update_params_from_kwargs(**kwargs)",
                '        filename = bn.gen_path(self.format_type, suffix=".txt")',
                '        line_count = {"summary": 5, "detailed": 20, "raw": 50}[self.format_type]',
                '        with open(filename, "w", encoding="utf-8") as f:',
                "            for i in range(line_count):",
                '                f.write(f"[{self.format_type}] line {i + 1}: value={math.sin(i):.4f}\\n")',
                "        self.file_result = filename",
                "        return super().__call__()",
            ]
        ),
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
        "\n".join(
            [
                "class TimeseriesCollector(bn.ParametrizedSweep):",
                '    """Collects a timeseries and returns it as an xarray dataset."""',
                "",
                '    duration = bn.FloatSweep(default=5.0, bounds=[1.0, 10.0], doc="Collection duration")',
                '    sample_rate = bn.FloatSweep(default=1.0, bounds=[0.5, 2.0], doc="Samples per second")',
                "",
                '    result_ds = bn.ResultDataSet(doc="Collected timeseries dataset")',
                "",
                "    def __call__(self, **kwargs):",
                "        import xarray as xr",
                "",
                "        self.update_params_from_kwargs(**kwargs)",
                "        n_samples = max(1, int(self.duration * self.sample_rate))",
                "        values = [math.sin(2 * math.pi * i / max(n_samples, 1)) * self.duration for i in range(n_samples)]",
                '        data_array = xr.DataArray(values, dims=["time"], coords={"time": list(range(n_samples))})',
                '        ds = xr.Dataset({"result_ds": data_array})',
                "        self.result_ds = bn.ResultDataSet(ds.to_pandas())",
                "        return super().__call__()",
            ]
        ),
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

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        if self.input_dims not in VALID_COMBOS.get(self.result_type, []):
            return super().__call__()

        imports, class_name, result_vars, input_vars_map, class_code = BENCHABLE_MAP[
            self.result_type
        ]()
        input_vars_code = input_vars_map[self.input_dims]

        sub_dir = f"{OUTPUT_DIR}/{self.result_type}"
        filename = f"{self.result_type}_{self.input_dims}d"
        function_name = f"example_{self.result_type}_{self.input_dims}d"
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

        level = 2 if self.input_dims >= 2 else 3
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
            run_kwargs={"level": level},
        )

        return super().__call__()


def example_meta_result_types(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = MetaResultTypes().to_bench(run_cfg)

    bench.plot_sweep(
        title="Result Types",
        input_vars=[
            bn.p("result_type", RESULT_TYPES),
            bn.p("input_dims", [0, 1, 2]),
        ],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_result_types)
