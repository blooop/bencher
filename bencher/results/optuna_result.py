from __future__ import annotations
from copy import deepcopy
from itertools import product as iter_product

import numpy as np
import optuna
import panel as pn


from optuna.visualization import (
    plot_param_importances,
    plot_pareto_front,
    plot_optimization_history,
)
from bencher.utils import hmap_canonical_input
from bencher.variables.time import TimeSnapshot, TimeEvent
from bencher.variables.inputs import BoolSweep
from bencher.results.bench_result_base import BenchResultBase, ReduceType

# from bencher.results.bench_result_base import BenchResultBase
from bencher.optuna_conversions import (
    _append_safe,
    sweep_var_to_optuna_dist,
    summarise_trial,
    param_importance,
    optuna_grid_search,
    summarise_optuna_study,
    sweep_var_to_suggest,
)


def _evaluate_over_non_optimized(worker, opt_kwargs, non_opt_vars, result_vars):
    """Evaluate worker across all combinations of non-optimized vars and return mean results."""
    non_opt_value_lists = [iv.values() for iv in non_opt_vars]
    all_results = []
    for combo in iter_product(*non_opt_value_lists):
        call_kwargs = dict(opt_kwargs)
        for iv, val in zip(non_opt_vars, combo):
            call_kwargs[iv.name] = val
        all_results.append(worker(**call_kwargs))

    aggregated = []
    for rv in result_vars:
        values = [res[rv.name] for res in all_results]
        arr = np.asarray(values)
        if not np.issubdtype(arr.dtype, np.number):
            raise TypeError(
                f"Result variable '{rv.name}' must be numeric to aggregate over "
                f"non-optimized variable combinations, but got dtype {arr.dtype}"
            )
        aggregated.append(float(np.mean(arr)))
    return tuple(aggregated)


def _aggregate_non_optimized(df, opt_vars, non_opt_vars, target_names):
    """Group DataFrame by optimized vars and average target columns over non-optimized vars."""
    if not (non_opt_vars and opt_vars and target_names):
        return df
    group_cols = [v.name for v in opt_vars if v.name in df.columns]
    if not group_cols:
        return df
    agg_cols = [t for t in target_names if t in df.columns]
    if not agg_cols:
        return df
    return df.groupby(group_cols, as_index=False)[agg_cols].mean()


class OptunaResult(BenchResultBase):
    def to_optuna_plots(self, **kwargs) -> list[pn.pane.panel]:
        """Create an optuna summary from the benchmark results

        Returns:
            list[pn.pane.panel]: A list of optuna plot summarising the benchmark process
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
        extra_results: list[OptunaResult] | None = None,
        sampler=None,
    ):
        directions = []
        for rv in self.bench_cfg.optuna_targets(True):
            directions.append(rv.direction)

        if sampler is None:
            sampler = optuna.samplers.TPESampler()

        study = optuna.create_study(
            sampler=sampler, directions=directions, study_name=self.bench_cfg.title
        )

        # add already calculated results
        results_list = extra_results if extra_results is not None else [self]
        for res in results_list:
            if len(res.ds.sizes) > 0:
                study.add_trials(res.bench_results_to_optuna_trials(False))

        opt_vars, non_opt_vars = self.bench_cfg.partition_input_vars(self.bench_cfg.input_vars)

        if not opt_vars:
            raise ValueError(
                "At least one input variable must have optimize=True for Optuna optimization."
            )

        def wrapped(trial) -> tuple:
            kwargs = {iv.name: sweep_var_to_suggest(iv, trial) for iv in opt_vars}

            if not non_opt_vars:
                result = worker(**kwargs)
                return tuple(result[rv.name] for rv in self.bench_cfg.result_vars)

            return _evaluate_over_non_optimized(
                worker, kwargs, non_opt_vars, self.bench_cfg.result_vars
            )

        study.optimize(wrapped, n_trials=n_trials)
        return study

    def bench_results_to_optuna_trials(self, include_meta: bool = True) -> list:
        """Convert an xarray dataset to optuna trials so optuna can further optimise or plot.

        Args:
            include_meta (bool): When True, include all variables (inputs + meta like repeat
                and over_time) as trial parameters for importance analysis. When False, use
                only input variables with partition/aggregation via the optimize flag.

        Returns:
            list[optuna.trial.FrozenTrial]: Optuna trials derived from benchmark results.
        """
        target_names = self.bench_cfg.optuna_targets()

        if include_meta:
            # Importance analysis: every raw data point becomes a trial with all vars
            df = self.to_dataset(reduce=ReduceType.NONE).to_dataframe().reset_index()
            trial_vars = list(self.bench_cfg.all_vars)
        else:
            # Optimization mode: partition by optimize flag, aggregate non-optimized
            input_vars = self.bench_cfg.input_vars
            df = self.to_dataset(reduce=ReduceType.AUTO).to_dataframe().reset_index()
            opt_vars, non_opt_vars = self.bench_cfg.partition_input_vars(input_vars)

            if not opt_vars:
                raise ValueError(
                    "At least one input variable must have optimize=True for Optuna optimization."
                )

            df = _aggregate_non_optimized(df, opt_vars, non_opt_vars, target_names)
            trial_vars = opt_vars

        df.dropna(inplace=True)

        distributions = {}
        for i in trial_vars:
            distributions[i.name] = sweep_var_to_optuna_dist(i)

        trials = []
        for row in df.iterrows():
            params = {}
            values = []
            for i in trial_vars:
                if isinstance(i, TimeSnapshot):
                    val = row[1][i.name]
                    if hasattr(val, "timestamp") and not (hasattr(val, "isnull") and val.isnull()):
                        params[i.name] = val.timestamp()
                    elif isinstance(val, np.datetime64) and not np.isnat(val):
                        params[i.name] = val.astype("datetime64[s]").astype(float)
                    else:
                        continue
                elif isinstance(i, TimeEvent):
                    params[i.name] = str(row[1][i.name])
                elif isinstance(i, BoolSweep):
                    val = row[1][i.name]
                    if isinstance(val, str):
                        params[i.name] = val.lower() == "true"
                    else:
                        params[i.name] = bool(val)
                else:
                    params[i.name] = row[1][i.name]

            for r in target_names:
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
        trial_vars = list(self.bench_cfg.all_vars) if include_meta else None
        study = optuna_grid_search(self.bench_cfg, trial_vars=trial_vars)
        optuna.logging.set_verbosity(optuna.logging.CRITICAL)
        import warnings

        # /usr/local/lib/python3.10/dist-packages/optuna/samplers/_grid.py:224: UserWarning: over_time contains a value with the type of <class 'pandas._libs.tslibs.timestamps.Timestamp'>, which is not supported by `GridSampler`. Please make sure a value is `str`, `int`, `float`, `bool` or `None` for persistent storage.

        # this is not disabling the warning
        warnings.filterwarnings(action="ignore", category=UserWarning)
        # remove optuna gridsearch warning as we are not using their gridsearch because it has the most inexplicably terrible performance I have ever seen in my life. How can a for loop of 400 iterations start out with 100ms per loop and increase to greater than a 1000ms after 250ish iterations!?!?!??!!??!
        study.add_trials(trials)
        return study

    def get_best_trial_params(self, canonical=False):
        studies = self.bench_result_to_study(False)
        out = studies.best_trials[0].params
        if canonical:
            return hmap_canonical_input(out)
        return out

    def get_pareto_front_params(self):
        return [p.params for p in self.studies[0].trials]

    def collect_optuna_plots(
        self, pareto_width: float | None = None, pareto_height: float | None = None
    ) -> list[pn.pane.panel]:
        """Use optuna to plot various summaries of the optimisation

        Args:
            study (optuna.Study): The study to plot
            bench_cfg (BenchCfg): Benchmark config with options used to generate the study

        Returns:
            list[pn.pane.Pane]: A list of plots
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

            # --- Optimization History ---
            if len(target_names) > 1:
                for idx, tgt in enumerate(target_names):

                    def _target(t, i=idx):
                        return t.values[i]

                    _append_safe(
                        study_pane,
                        plot_optimization_history,
                        study,
                        target=_target,
                        target_name=tgt,
                    )
            else:
                _append_safe(study_pane, plot_optimization_history, study)

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

    def get_best_holomap(self, name: str | None = None):
        return self.get_hmap(name)[self.get_best_trial_params(True)]
