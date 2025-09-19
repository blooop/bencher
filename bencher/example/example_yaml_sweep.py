from pathlib import Path

import bencher as bch


_YAML_PATH = Path(__file__).with_name("example_yaml_sweep.yaml")


class YamlConfigSweep(bch.ParametrizedSweep):
    """Example sweep that drives configurations defined in a YAML file."""

    config = bch.YamlSweep(_YAML_PATH, doc="Configurations stored in example_yaml_sweep.yaml")

    iterations = bch.ResultVar(units="iterations", doc="Iteration budget for the configuration")
    learning_rate = bch.ResultVar(
        units="ratio", doc="Learning rate associated with the configuration"
    )
    config_name = bch.ResultString(doc="Name of the active YAML configuration")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        selected = self.config
        key = self.param.config.key_for_value(selected)
        self.config_name = key or "unknown"
        self.iterations = selected.get("iterations", 0)
        self.learning_rate = selected.get("learning_rate", 0.0)
        return super().__call__()


def example_yaml_sweep(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    bench = YamlConfigSweep().to_bench(name="yaml_sweep", run_cfg=run_cfg, report=report)
    bench.plot_sweep(
        title="YAML configuration sweep",
        input_vars=[YamlConfigSweep.param.config],
        result_vars=[YamlConfigSweep.param.iterations, YamlConfigSweep.param.learning_rate],
    )
    return bench


if __name__ == "__main__":
    example_yaml_sweep().report.show()
