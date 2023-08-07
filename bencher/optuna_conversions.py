from typing import List

import numpy as np
import optuna
import panel as pn
import param
from optuna.visualization import (
    plot_param_importances,
    plot_pareto_front,
    plot_optimization_history,
)

from bencher.bench_cfg import BenchCfg


from bencher.variables.inputs import IntSweep, FloatSweep, StringSweep, EnumSweep, BoolSweep
from bencher.variables.time import TimeSnapshot, TimeEvent
from bencher.variables.results import OptDir

from bencher.variables.parametrised_sweep import ParametrizedSweep


def optuna_grid_search(bench_cfg: BenchCfg) -> optuna.Study:
    """use optuna to perform a grid search

    Args:
        bench_cfg (BenchCfg): setting for grid search

    Returns:
        optuna.Study: results of grid search
    """
    search_space = {}
    for iv in bench_cfg.all_vars:
        search_space[iv.name] = iv.values(bench_cfg.debug)
    directions = []
    for rv in bench_cfg.result_vars:
        if rv.direction != OptDir.none:
            directions.append(rv.direction)

    study = optuna.create_study(
        sampler=optuna.samplers.GridSampler(search_space),
        directions=directions,
        study_name=bench_cfg.title,
    )
    return study


# def bench_results_to_optuna(bench_cfg: BenchCfg):


def to_optuna(worker, bench_cfg: BenchCfg, n_trials=100, sampler=optuna.samplers.TPESampler()):
    directions = []
    for rv in bench_cfg.result_vars:
        if rv.direction != OptDir.none:
            directions.append(rv.direction)

    study = optuna.create_study(sampler=sampler, directions=directions, study_name=bench_cfg.title)

    # add already calculated results
    if len(bench_cfg.ds.sizes) > 0:
        study.add_trials(bench_results_to_optuna_trials(bench_cfg, True))

    def wrapped(trial):
        kwargs = {}
        for iv in bench_cfg.input_vars:
            kwargs[iv.name] = sweep_var_to_suggest(iv, trial)
        result = worker(**kwargs)
        output = []
        for rv in bench_cfg.result_vars:
            output.append(result[rv.name])
        return tuple(output)

    study.optimize(wrapped, n_trials=n_trials)
    return study


def extract_study_to_dataset(study: optuna.Study, bench_cfg: BenchCfg) -> BenchCfg:
    """Extract an optuna study into an xarray dataset for easy plotting

    Args:
        study (optuna.Study): The result of a gridsearch
        bench_cfg (BenchCfg): Options for the grid search

    Returns:
        BenchCfg: An updated config with the results included
    """
    for t in study.trials:
        for it, rv in enumerate(bench_cfg.result_vars):
            bench_cfg.ds[rv.name].loc[t.params] = t.values[it]
    return bench_cfg


def collect_optuna_plots(bench_cfg: BenchCfg) -> List[pn.pane.panel]:
    """Use optuna to plot various summaries of the optimisation

    Args:
        study (optuna.Study): The study to plot
        bench_cfg (BenchCfg): Benchmark config with options used to generate the study

    Returns:
        List[pn.pane.Pane]: A list of plots
    """

    # plot_cols.extend(collect_optuna_plots(bench_cfg, False))

    studies = [bench_cfg_to_study(bench_cfg, True)]
    bench_cfg.studies = studies
    titles = ["# Analysis"]
    if bench_cfg.repeats > 1:
        studies.append(bench_cfg_to_study(bench_cfg, False))
        titles = ["# Parameter Importance With Repeats", "## Parameter Importance Without Repeats"]

    cols = pn.Row()
    for study, title in zip(studies, titles):
        rows = pn.Column()
        target_names = []
        for rv in bench_cfg.result_vars:
            if rv.direction != OptDir.none:
                target_names.append(rv.name)
        param_str = []

        print("tgtnam", target_names)

        rows.append(pn.pane.Markdown(title))

        if len(target_names) > 1:
            if len(target_names) <= 3:
                # rows.append(plot_param_importances(study, target_name=target_names))
                # rows.append(target_names)

                # for tgt in target_names:
                #     rows.append(
                #         plot_param_importances(study, target=lambda t: t.values[0], target_name=tgt)
                #     )

                rows.append(
                    plot_pareto_front(
                        study, target_names=target_names, include_dominated_trials=False
                    )
                )
            else:
                print("plotting pareto front of first 3 result variables")
                rows.append(
                    plot_pareto_front(
                        study,
                        targets=lambda t: (t.values[0], t.values[1], t.values[2]),
                        target_names=target_names[:3],
                        include_dominated_trials=False,
                    )
                )
            if bench_cfg.repeats > 1:
                rows.append("repeats>1")
                for tgt in target_names:
                    rows.append(
                        plot_param_importances(study, target=lambda t: t.values[0], target_name=tgt)
                    )

            param_str.append(f"    Number of trials on the Pareto front: {len(study.best_trials)}")
            for t in study.best_trials:
                param_str.extend(summarise_trial(t, bench_cfg))

        else:
            # cols.append(plot_optimization_history(study)) #TODO, maybe more clever when this is plotted?

            # If there is only 1 parameter then there is no point is plotting relative importance.  Only worth plotting if there are multiple repeats of the same value so that you can compare the parameter vs to repeat to get a sense of the how much chance affects the results
            if bench_cfg.repeats > 1 and len(bench_cfg.input_vars) > 1:
                rows.append(plot_param_importances(study, target_name=target_names[0]))
            param_str.extend(summarise_trial(study.best_trial, bench_cfg))

        kwargs = {"height": 500, "scroll": True} if len(param_str) > 30 else {}

        param_str = "\n    ".join(param_str)
        rows.append(
            pn.Row(pn.pane.Markdown(f"## Best Parameters\n    {param_str}"), **kwargs),
        )

        cols.append(rows)

    return [cols]


def summarise_trial(trial: optuna.trial, bench_cfg: BenchCfg) -> List[str]:
    """Given a trial produce a string summary of the best results

    Args:
        trial (optuna.trial): trial to summarise
        bench_cfg (BenchCfg): info about the trial

    Returns:
        List[str]: Summary of trial
    """
    sep = "    "
    output = []
    output.append(f"Trial id:{trial.number}:")
    output.append(f"{sep}Inputs:")
    for k, v in trial.params.items():
        output.append(f"{sep}{sep}{k}:{v}")
    output.append(f"{sep}Results:")
    for it, rv in enumerate(bench_cfg.result_vars):
        if rv.direction != OptDir.none:
            output.append(f"{sep}{sep}{rv.name}:{trial.values[it]}")
    return output


def sweep_var_to_optuna_dist(var: param.Parameter) -> optuna.distributions.BaseDistribution:
    """Convert a sweep var to an optuna distribution

    Args:
        var (param.Parameter): A sweep var

    Raises:
        ValueError: Unsupported var type

    Returns:
        optuna.distributions.BaseDistribution: Optuna representation of a sweep var
    """

    iv_type = type(var)
    if iv_type == IntSweep:
        return optuna.distributions.IntDistribution(var.bounds[0], var.bounds[1])
    if iv_type == FloatSweep:
        return optuna.distributions.FloatDistribution(var.bounds[0], var.bounds[1])
    if iv_type in (EnumSweep, StringSweep):
        return optuna.distributions.CategoricalDistribution(var.objects)
    if iv_type == BoolSweep:
        return optuna.distributions.CategoricalDistribution([False, True])
    if iv_type == TimeSnapshot:
        # return optuna.distributions.IntDistribution(0, sys.maxsize)
        return optuna.distributions.FloatDistribution(0, 1e20)
        # return optuna.distributions.CategoricalDistribution([])
    # elif iv_type == TimeEvent:
    #     pass
    # return optuna.distributions.CategoricalDistribution(["now"])

    raise ValueError(f"This input type {iv_type} is not supported")


def sweep_var_to_suggest(iv: ParametrizedSweep, trial: optuna.trial) -> object:
    """Converts from a sweep var to an optuna

    Args:
        iv (ParametrizedSweep): A parametrized sweep input variable
        trial (optuna.trial): Optuna trial used to define the sample

    Raises:
        ValueError: Unsupported var type

    Returns:
        Any: A sampled variable (can be any type)
    """
    iv_type = type(iv)

    if iv_type == IntSweep:
        return trial.suggest_int(iv.name, iv.bounds[0], iv.bounds[1])
    if iv_type == FloatSweep:
        return trial.suggest_float(iv.name, iv.bounds[0], iv.bounds[1])
    if iv_type in (EnumSweep, StringSweep):
        return trial.suggest_categorical(iv.name, iv.objects)
    if iv_type in (TimeSnapshot, TimeEvent):
        pass  # optuna does not like time
    if iv_type == BoolSweep:
        return trial.suggest_categorical(iv.name, [True, False])
    raise ValueError(f"This input type {iv_type} is not supported")


def cfg_from_optuna_trial(
    trial: optuna.trial, bench_cfg: BenchCfg, cfg_type: ParametrizedSweep
) -> ParametrizedSweep:
    cfg = cfg_type()
    for iv in bench_cfg.input_vars:
        cfg.param.set_param(iv.name, sweep_var_to_suggest(iv, trial))
    for mv in bench_cfg.meta_vars:
        sweep_var_to_suggest(mv, trial)
    return cfg


def bench_results_to_optuna_trials(bench_cfg: BenchCfg, include_meta: bool = True) -> optuna.Study:
    """Convert an xarray dataset to an optuna study so optuna can further optimise or plot the statespace

    Args:
        bench_cfg (BenchCfg): benchmark config to convert

    Returns:
        optuna.Study: optuna description of the study
    """
    if include_meta:
        df = bench_cfg.get_dataframe()
        all_vars = []
        for v in bench_cfg.all_vars:
            if type(v) != TimeEvent:
                all_vars.append(v)

        print("All vars", all_vars)
    else:
        all_vars = bench_cfg.input_vars
        df = bench_cfg.ds.mean("repeat").to_dataframe().reset_index()
    # df = bench_cfg.ds.mean("repeat").to_dataframe.reset_index()
    # bench_cfg.all_vars
    # del bench_cfg.meta_vars[1]

    trials = []
    distributions = {}
    for i in all_vars:
        distributions[i.name] = sweep_var_to_optuna_dist(i)

    for row in df.iterrows():
        params = {}
        values = []
        for i in all_vars:
            if type(i) == TimeSnapshot:
                if type(row[1][i.name]) == np.datetime64:
                    params[i.name] = row[1][i.name].timestamp()
            else:
                params[i.name] = row[1][i.name]

        for r in bench_cfg.result_vars:
            if r.direction != OptDir.none:
                values.append(row[1][r.name])

        trials.append(
            optuna.trial.create_trial(
                params=params,
                distributions=distributions,
                values=values,
            )
        )
    return trials


def bench_cfg_to_study(bench_cfg: BenchCfg, include_meta: bool) -> optuna.Study:
    trials = bench_results_to_optuna_trials(bench_cfg, include_meta)
    study = optuna_grid_search(bench_cfg)
    optuna.logging.set_verbosity(optuna.logging.CRITICAL)
    import warnings

    # /usr/local/lib/python3.10/dist-packages/optuna/samplers/_grid.py:224: UserWarning: over_time contains a value with the type of <class 'pandas._libs.tslibs.timestamps.Timestamp'>, which is not supported by `GridSampler`. Please make sure a value is `str`, `int`, `float`, `bool` or `None` for persistent storage.

    # this is not disabling the warning
    warnings.filterwarnings(action="ignore", category=UserWarning)
    # remove optuna gridsearch warning as we are not using their gridsearch because it has the most inexplicably terrible performance I have ever seen in my life. How can a for loop of 400 iterations start out with 100ms per loop and increase to greater than a 1000ms after 250ish iterations!?!?!??!!??!
    study.add_trials(trials)
    return study


def summarise_study(study: optuna.study.Study) -> None:
    row = pn.Column(name="Optimisation Results")
    row.append(plot_optimization_history(study))
    row.append(plot_param_importances(study))
    try:
        row.append(plot_pareto_front(study))
    except Exception:
        pass

    row.append(
        pn.pane.Markdown(f"```\nBest value: {study.best_value}\nParams: {study.best_params}```")
    )

    return row
