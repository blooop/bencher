import numpy as np

import bencher as bn

rast_range = 1.5

optimal_value = 0.1234


class ToyOptimisationProblem(bn.ParametrizedSweep):
    input1 = bn.FloatSweep(default=0, bounds=[-rast_range, rast_range], samples=10)
    input2 = bn.FloatSweep(default=0, bounds=[-rast_range, rast_range], samples=10)
    offset = bn.FloatSweep(default=0, bounds=[-rast_range, rast_range])

    bump_scale = bn.FloatSweep(default=1.5, bounds=[1, 10])

    # RESULTS
    output = bn.ResultFloat("ul", bn.OptDir.minimize)

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


def optuna_rastrigin(run_cfg: bn.BenchRunCfg | None = None):
    explorer = ToyOptimisationProblem()

    bench = bn.Bench("Rastrigin", explorer.rastrigin, run_cfg=run_cfg)

    bench.plot_sweep(
        "Rastrigin",
        input_vars=[explorer.param.input1, explorer.param.input2],
        result_vars=[explorer.param.output],
        run_cfg=run_cfg,
    )

    bench.report.append_markdown(
        f"The optimal value should be input1:{-optimal_value},input2:{-optimal_value} with a value of 0"
    )
    return bench


if __name__ == "__main__":
    bn.run(optuna_rastrigin, optimise=30)
