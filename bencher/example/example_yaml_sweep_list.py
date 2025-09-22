import bencher as bch
from bencher.example.example_utils import resolve_example_path

_YAML_PATH = resolve_example_path("example_yaml_sweep_list.yaml")


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


def example_yaml_sweep_list(
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
    example_yaml_sweep_list().report.show()
