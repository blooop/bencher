from __future__ import annotations
from typing import List
from copy import deepcopy

import numpy as np
import optuna
import panel as pn


from optuna.visualization import (
    plot_param_importances,
    plot_pareto_front,
)
from bencher.utils import hmap_canonical_input
from bencher.variables.time import TimeSnapshot, TimeEvent
from bencher.results.bench_result_base import BenchResultBase, ReduceType

# from bencher.results.bench_result_base import BenchResultBase
from bencher.optuna_conversions import (
    sweep_var_to_optuna_dist,
    summarise_trial,
    param_importance,
    optuna_grid_search,
    summarise_optuna_study,
    sweep_var_to_suggest,
)


class OptunaResult(BenchResultBase):
    def to_optuna_plots(self, **kwargs) -> List[pn.pane.panel]:
        """Create an optuna summary from the benchmark results

        Returns:
            List[pn.pane.panel]: A list of optuna plot summarising the benchmark process
        """

        return self.collect_optuna_plots(**kwargs)

    def to_optuna_from_sweep(self, bench, n_trials=30):
        optu = self.to_optuna_from_results(
            bench.worker, n_trials=n_trials, extra_results=bench.results
        )
        return summarise_optuna_study(optu)

    def to_optuna_from_results(
        self,
        worker,
        n_trials=100,
        extra_results: List[OptunaResult] = None,
        sampler=optuna.samplers.TPESampler(),
    ):
        directions = []
        for rv in self.bench_cfg.optuna_targets(True):
            directions.append(rv.direction)

        study = optuna.create_study(
            sampler=sampler, directions=directions, study_name=self.bench_cfg.title
        )

        # add already calculated results
        results_list = extra_results if extra_results is not None else [self]
        for res in results_list:
            if len(res.ds.sizes) > 0:
                study.add_trials(res.bench_results_to_optuna_trials(True))

        def wrapped(trial) -> tuple:
            kwargs = {}
            for iv in self.bench_cfg.input_vars:
                kwargs[iv.name] = sweep_var_to_suggest(iv, trial)
            result = worker(**kwargs)
            output = []
            for rv in self.bench_cfg.result_vars:
                output.append(result[rv.name])
            return tuple(output)

        study.optimize(wrapped, n_trials=n_trials)
        return study

    def bench_results_to_optuna_trials(self, include_meta: bool = True) -> optuna.Study:
        """Convert an xarray dataset to an optuna study so optuna can further optimise or plot the statespace

        Args:
            bench_cfg (BenchCfg): benchmark config to convert

        Returns:
            optuna.Study: optuna description of the study
        """
        if include_meta:
            # df = self.to_pandas()
            df = self.to_dataset(reduce=ReduceType.NONE).to_dataframe().reset_index()
            all_vars = []
            for v in self.bench_cfg.all_vars:
                if type(v) is not TimeEvent:
                    all_vars.append(v)

            print("All vars", all_vars)
        else:
            all_vars = self.bench_cfg.input_vars
            # df = self.ds.
            # if "repeat" in self.
            # if self.bench_cfg.repeats>1:
            # df = self.bench_cfg.ds.mean("repeat").to_dataframe().reset_index()
            # else:
            # df = self.to_pandas().reset_index()
            df = self.to_dataset(reduce=ReduceType.AUTO).to_dataframe().reset_index()
        # df = self.bench_cfg.ds.mean("repeat").to_dataframe.reset_index()
        # self.bench_cfg.all_vars
        # del self.bench_cfg.meta_vars[1]

        # optuna does not like the nan values so remove them.
        df.dropna(inplace=True)

        trials = []
        distributions = {}
        for i in all_vars:
            distributions[i.name] = sweep_var_to_optuna_dist(i)

        for row in df.iterrows():
            params = {}
            values = []
            for i in all_vars:
                if type(i) is TimeSnapshot:
                    if type(row[1][i.name]) is np.datetime64:
                        params[i.name] = row[1][i.name].timestamp()
                else:
                    params[i.name] = row[1][i.name]

            for r in self.bench_cfg.optuna_targets():
                # print(row[1][r])
                # print(np.isnan(row[1][r]))
                # if not np.isnan(row[1][r]):
                values.append(row[1][r])

            trials.append(
                optuna.trial.create_trial(
                    params=params,
                    distributions=distributions,
                    values=values,
                )
            )
        return trials

    def bench_result_to_study(self, include_meta: bool) -> optuna.Study:
        trials = self.bench_results_to_optuna_trials(include_meta)
        study = optuna_grid_search(self.bench_cfg)
        optuna.logging.set_verbosity(optuna.logging.CRITICAL)
        import warnings

        # /usr/local/lib/python3.10/dist-packages/optuna/samplers/_grid.py:224: UserWarning: over_time contains a value with the type of <class 'pandas._libs.tslibs.timestamps.Timestamp'>, which is not supported by `GridSampler`. Please make sure a value is `str`, `int`, `float`, `bool` or `None` for persistent storage.

        # this is not disabling the warning
        warnings.filterwarnings(action="ignore", category=UserWarning)
        # remove optuna gridsearch warning as we are not using their gridsearch because it has the most inexplicably terrible performance I have ever seen in my life. How can a for loop of 400 iterations start out with 100ms per loop and increase to greater than a 1000ms after 250ish iterations!?!?!??!!??!
        study.add_trials(trials)
        return study

    def get_best_trial_params(self, canonical=False):
        studies = self.bench_result_to_study(True)
        out = studies.best_trials[0].params
        if canonical:
            return hmap_canonical_input(out)
        return out

    def get_pareto_front_params(self):
        return [p.params for p in self.studies[0].trials]

    def collect_optuna_plots(
        self, pareto_width: float = None, pareto_height: float = None
    ) -> List[pn.pane.panel]:
        """Use optuna to plot various summaries of the optimisation

        Args:
            study (optuna.Study): The study to plot
            bench_cfg (BenchCfg): Benchmark config with options used to generate the study

        Returns:
            List[pn.pane.Pane]: A list of plots
        """

        self.studies = [self.bench_result_to_study(True)]
        titles = ["# Analysis"]
        if self.bench_cfg.repeats > 1:
            self.studies.append(self.bench_result_to_study(False))
            titles = [
                "# Parameter Importance With Repeats",
                "# Parameter Importance Without Repeats",
            ]

        study_repeats_pane = pn.Row()
        for study, title in zip(self.studies, titles):
            study_pane = pn.Column()
            target_names = self.bench_cfg.optuna_targets()
            param_str = []

            study_pane.append(pn.pane.Markdown(title))

            if len(target_names) > 1:
                if len(target_names) <= 3:
                    study_pane.append(
                        plot_pareto_front(
                            study,
                            target_names=target_names,
                            include_dominated_trials=False,
                        )
                    )
                else:
                    print("plotting pareto front of first 3 result variables")
                    study_pane.append(
                        plot_pareto_front(
                            study,
                            targets=lambda t: (t.values[0], t.values[1], t.values[2]),
                            target_names=target_names[:3],
                            include_dominated_trials=False,
                        )
                    )
                    if pareto_width is not None:
                        study_pane[-1].width = pareto_width
                    if pareto_height is not None:
                        study_pane[-1].height = pareto_height
                try:
                    study_pane.append(param_importance(self.bench_cfg, study))
                    param_str.append(
                        f"    Number of trials on the Pareto front: {len(study.best_trials)}"
                    )
                except RuntimeError as e:
                    study_pane.append(f"Error generating parameter importance: {str(e)}")

                for t in study.best_trials:
                    param_str.extend(summarise_trial(t, self.bench_cfg))

            else:
                # cols.append(plot_optimization_history(study)) #TODO, maybe more clever when this is plotted?

                # If there is only 1 parameter then there is no point is plotting relative importance.  Only worth plotting if there are multiple repeats of the same value so that you can compare the parameter vs to repeat to get a sense of the how much chance affects the results
                # if bench_cfg.repeats > 1 and len(bench_cfg.input_vars) > 1:  #old code, not sure if its right
                if len(self.bench_cfg.input_vars) > 1:
                    study_pane.append(plot_param_importances(study, target_name=target_names[0]))

                param_str.extend(summarise_trial(study.best_trial, self.bench_cfg))

            kwargs = {"height": 500, "scroll": True} if len(param_str) > 30 else {}

            param_str = "\n".join(param_str)
            study_pane.append(
                pn.Row(
                    pn.pane.Markdown(f"## Best Parameters\n```text\n{param_str}"),
                    **kwargs,
                ),
            )

            study_repeats_pane.append(study_pane)

        return study_repeats_pane

    # def extract_study_to_dataset(study: optuna.Study, bench_cfg: BenchCfg) -> BenchCfg:
    #     """Extract an optuna study into an xarray dataset for easy plotting

    #     Args:
    #         study (optuna.Study): The result of a gridsearch
    #         bench_cfg (BenchCfg): Options for the grid search

    #     Returns:
    #         BenchCfg: An updated config with the results included
    #     """
    #     for t in study.trials:
    #         for it, rv in enumerate(bench_cfg.result_vars):
    #             bench_cfg.ds[rv.name].loc[t.params] = t.values[it]
    #     return bench_cfg

    def deep(self) -> OptunaResult:  # pragma: no cover
        """Return a deep copy of these results"""
        return deepcopy(self)

    def get_best_holomap(self, name: str = None):
        return self.get_hmap(name)[self.get_best_trial_params(True)]
