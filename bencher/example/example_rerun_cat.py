"""Rerun backend: categorical-only example.

Demonstrates a single categorical dimension logged as a BarChart.
The blueprint arranges one BarChartView per result variable in a
Vertical container.
"""

import random
import bencher as bch

random.seed(0)


class RerunCat(bch.ParametrizedSweep):
    data_structure = bch.StringSweep(["list", "dict", "set"], doc="Type of data structure")
    execution_time = bch.ResultVar(units="ms", doc="Execution time")
    memory_usage = bch.ResultVar(units="KB", doc="Memory usage")

    def __call__(self, **kwargs) -> dict:
        self.update_params_from_kwargs(**kwargs)
        base = {"list": (28.0, 960.0), "dict": (42.0, 720.0), "set": (35.0, 680.0)}
        bt, bm = base[self.data_structure]
        self.execution_time = bt * random.uniform(0.9, 1.1)
        self.memory_usage = bm * random.uniform(0.95, 1.05)
        return super().__call__(**kwargs)


def example_rerun_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Categorical sweep → rerun: logged as BarChart."""
    bench = RerunCat().to_bench(run_cfg)
    bench.plot_sweep(title="Rerun Categorical Example")
    return bench


if __name__ == "__main__":
    bch.run_flask_in_thread()
    bench = example_rerun_cat()
    bench.get_result().to_rerun().show()
