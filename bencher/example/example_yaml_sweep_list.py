from pathlib import Path

import bencher as bch


def _resolve_example_path(filename: str) -> Path:
    """Locate example assets when running as a script, notebook, or installed package."""

    module_file = globals().get("__file__")
    search_roots = []
    if module_file:
        search_roots.append(Path(module_file).resolve().parent)

    search_roots.append(Path.cwd())
    search_roots.append(Path(bch.__file__).resolve().parent / "example")

    for root in search_roots:
        candidate = Path(root) / filename
        if candidate.exists():
            return candidate

    searched = ", ".join(str(Path(root)) for root in search_roots)
    raise FileNotFoundError(f"Unable to locate {filename}. Searched: {searched}")


_YAML_PATH = _resolve_example_path("example_yaml_sweep_list.yaml")


class YamlConfigSweep(bch.ParametrizedSweep):
    """Example sweep that aggregates YAML list entries into a single metric."""

    workload = bch.YamlSweep(
        _YAML_PATH, doc="Workload lists stored in example_yaml_sweep_list.yaml"
    )

    total_workload = bch.ResultVar(units="tasks", doc="Total workload summed from the YAML list")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        self.total_workload = sum(self.workload.value())

        return super().__call__()


def example_yaml_sweep(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    bench = YamlConfigSweep().to_bench(name="yaml_sweep", run_cfg=run_cfg, report=report)
    bench.plot_sweep(
        title="YAML workload sweep",
        input_vars=[YamlConfigSweep.param.workload],
        result_vars=[YamlConfigSweep.param.total_workload],
    )
    return bench


if __name__ == "__main__":
    example_yaml_sweep().report.show()
