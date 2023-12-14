from typing import List

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


# BENCH_CFG
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


# BENCH_CFG


def to_optuna(worker, bench_cfg: BenchCfg, n_trials=100, sampler=optuna.samplers.TPESampler()):
    directions = []
    for rv in bench_cfg.result_vars:
        if rv.direction != OptDir.none:
            directions.append(rv.direction)

    study = optuna.create_study(sampler=sampler, directions=directions, study_name=bench_cfg.title)

    # add already calculated results
    # if len(bench_cfg.ds.sizes) > 0:
    # study.add_trials(bench_results_to_optuna_trials(bench_cfg, True))

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


# BENCH_CFG
def param_importance(bench_cfg: BenchCfg, study: optuna.Study) -> pn.Row:
    col_importance = pn.Column()
    for tgt in bench_cfg.optuna_targets():
        col_importance.append(
            pn.Column(
                pn.pane.Markdown(f"## Parameter importance for: {tgt}"),
                plot_param_importances(study, target=lambda t: t.values[0], target_name=tgt),
            )
        )
    return col_importance


# BENCH_CFG
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


def summarise_study(study: optuna.study.Study) -> pn.pane.panel:
    """Summarise an optuna study in a panel format"""
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
