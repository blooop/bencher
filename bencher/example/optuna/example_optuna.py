import bencher as bch
import numpy as np
import optuna
from optuna.samplers import TPESampler


def objective(trial):
    x = trial.suggest_float("x", -10, 10)
    return x**2


study = optuna.create_study(sampler=TPESampler())
study.optimize(objective, n_trials=10)

rast_range = 1.5

optimal_value = 0.1234


class ToyOptimisationProblem(bch.ParametrizedSweep):
    input1 = bch.FloatSweep(default=0, bounds=[-rast_range, rast_range], samples=10)
    input2 = bch.FloatSweep(default=0, bounds=[-rast_range, rast_range], samples=10)
    offset = bch.FloatSweep(default=0, bounds=[-rast_range, rast_range])

    bump_scale = bch.FloatSweep(default=1.5, bounds=[1, 10])

    # RESULTS
    output = bch.ResultVar("ul", bch.OptDir.minimize)

    def rastrigin(self, **kwargs) -> dict:
        """A modified version of the rastrigin function which is very difficult to find the global optimum
        https://en.wikipedia.org/wiki/Rastrigin_function

        Returns:
            dict: dictionary of return values
        """
        self.update_params_from_kwargs(**kwargs)
        x = np.array([self.input1 + optimal_value, self.input2 + optimal_value])

        self.output = (
            np.sum(x * x - self.bump_scale * np.cos(self.bump_scale * np.pi * x))
            + self.bump_scale * np.size(x)
            + self.offset
        )
        return self.get_results_values_as_dict()


def optuna_rastrigin(run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None):
    explorer = ToyOptimisationProblem()

    bench = bch.Bench("Rastrigin", explorer.rastrigin, run_cfg=run_cfg, report=report)

    # res = bench.to_optuna(
    #     input_vars=[explorer.param.input1, explorer.param.input2],
    #     result_vars=[explorer.param.output],
    #     n_trials=30
    # )

    # run_cfg.use_optuna = True
    res = bench.plot_sweep(
        "Rastrigin",
        input_vars=[explorer.param.input1, explorer.param.input2],
        result_vars=[explorer.param.output],
        run_cfg=run_cfg,
    )

    bench.report.append(res.to_optuna_plots())
    bench.report.append(res.to_optuna_from_sweep(bench))
    bench.report.append_markdown(
        f"The optimal value should be input1:{-optimal_value},input2:{-optimal_value} with a value of 0"
    )
    return bench


if __name__ == "__main__":
    optuna_rastrigin().report.show()
