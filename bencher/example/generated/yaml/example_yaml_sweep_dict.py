import bencher as bn
from bencher.example.example_utils import resolve_example_path

_YAML_PATH = resolve_example_path("yaml_sweep_dict.yaml")


class YamlDictConfig(bn.ParametrizedSweep):
    """Example sweep that loads YAML dictionaries and summarizes them."""

    plan = bn.YamlSweep(_YAML_PATH, doc="Dictionary-based configurations stored in YAML")

    plan_summary = bn.ResultContainer(doc="Captured dictionary for the selected plan")
    total_duration = bn.ResultFloat(units="min", doc="Sum of all scheduled durations")
    average_duration = bn.ResultFloat(units="min", doc="Average scheduled duration")

    def benchmark(self):
        key, config = self.plan
        durations = config.get("durations", [])
        total = sum(durations)
        count = len(durations) or 1

        self.total_duration = total
        self.average_duration = total / count
        self.plan_summary = {
            "plan": key,
            "label": config.get("label", ""),
            "durations": list(durations),
            "resources": dict(config.get("resources", {})),
        }


def example_yaml_sweep_dict(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = YamlDictConfig().to_bench(run_cfg)
    bench.plot_sweep()
    return bench


if __name__ == "__main__":
    bn.run(example_yaml_sweep_dict, level=7)
