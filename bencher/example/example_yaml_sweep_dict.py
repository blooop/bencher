import bencher as bch
from bencher.example.example_utils import resolve_example_path

_YAML_PATH = resolve_example_path("example_yaml_sweep_dict.yaml")


class YamlDictConfig(bch.ParametrizedSweep):
    """Example sweep that loads YAML dictionaries and summarizes them."""

    plan = bch.YamlSweep(_YAML_PATH, doc="Dictionary-based configurations stored in YAML")

    plan_summary = bch.ResultContainer(doc="Captured dictionary for the selected plan")
    total_duration = bch.ResultVar(units="min", doc="Sum of all scheduled durations")
    average_duration = bch.ResultVar(units="min", doc="Average scheduled duration")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

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

        return super().__call__()


def example_yaml_sweep_dict(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    bench = YamlDictConfig().to_bench(name="yaml_dict_sweep", run_cfg=run_cfg, report=report)
    bench.plot_sweep()
    return bench


if __name__ == "__main__":
    bench_runner = bch.BenchRunner()
    bench_runner.add(example_yaml_sweep_dict).run(level=7, show=True)
