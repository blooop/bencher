import bencher as bn
from bencher.example.example_utils import resolve_example_path

_YAML_PATH = resolve_example_path("yaml_sweep_list.yaml")


class YamlConfigSweep(bn.ParametrizedSweep):
    """Example sweep that aggregates YAML list entries into a single metric."""

    workload = bn.YamlSweep(_YAML_PATH, doc="Workload lists stored in yaml_sweep_list.yaml")

    total_workload = bn.ResultVar(units="tasks", doc="Total workload summed from the YAML list")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        self.total_workload = sum(self.workload.value())

        return super().__call__()


def example_yaml_sweep_list(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = YamlConfigSweep().to_bench(run_cfg)
    bench.plot_sweep(
        title="YAML workload sweep",
        input_vars=["workload"],
        result_vars=["total_workload"],
    )
    return bench


if __name__ == "__main__":
    bn.run(example_yaml_sweep_list)
