from __future__ import annotations

import logging

import optuna
import panel as pn
import param
from optuna.visualization import (
    plot_param_importances,
    plot_pareto_front,
    plot_optimization_history,
    plot_parallel_coordinate,
    plot_slice,
)

from bencher.bench_cfg import BenchCfg


from bencher.variables.inputs import IntSweep, FloatSweep, StringSweep, EnumSweep, BoolSweep
from bencher.variables.time import TimeSnapshot, TimeEvent

from bencher.variables.parametrised_sweep import ParametrizedSweep


# BENCH_CFG
def optuna_grid_search(bench_cfg: BenchCfg, trial_vars: list | None = None) -> optuna.Study:
    """use optuna to perform a grid search

    Args:
        bench_cfg (BenchCfg): setting for grid search
        trial_vars (list | None): If provided, use these variables for the search space.
            Otherwise, filter bench_cfg.all_vars by optimize=True.

    Returns:
        optuna.Study: results of grid search
    """
    search_space = {}
    if trial_vars is not None:
        for iv in trial_vars:
            search_space[iv.name] = iv.values()
    else:
        for iv in bench_cfg.all_vars:
            if getattr(iv, "optimize", True):
                search_space[iv.name] = iv.values()
    directions = []
    for rv in bench_cfg.optuna_targets(True):
        directions.append(rv.direction)

    study = optuna.create_study(
        sampler=optuna.samplers.GridSampler(search_space),
        directions=directions,
        study_name=bench_cfg.title,
    )
    return study


# BENCH_CFG
def param_importance(bench_cfg: BenchCfg, study: optuna.Study) -> pn.Column:
    col_importance = pn.Column()
    for idx, tgt in enumerate(bench_cfg.optuna_targets()):

        def target(t, i=idx):
            return t.values[i]

        col_importance.append(
            pn.Column(
                pn.pane.Markdown(f"### Parameter importance for: {tgt}"),
                plot_param_importances(study, target=target, target_name=tgt),
            )
        )
    return col_importance


# BENCH_CFG
def summarise_trial(trial: optuna.trial, bench_cfg: BenchCfg) -> str:
    """Given a trial produce a markdown summary of the best results.

    Args:
        trial (optuna.trial): trial to summarise
        bench_cfg (BenchCfg): info about the trial

    Returns:
        str: Markdown-formatted summary of the trial
    """
    lines = [f"#### Trial {trial.number}", ""]
    lines.append("| Parameter | Value |")
    lines.append("|-----------|-------|")
    for k, v in trial.params.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("| Result | Value |")
    lines.append("|--------|-------|")
    for it, rv in enumerate(bench_cfg.optuna_targets()):
        val = trial.values[it]
        if isinstance(val, float):
            lines.append(f"| {rv} | {val:.6g} |")
        else:
            lines.append(f"| {rv} | {val} |")
    return "\n".join(lines)


def sweep_var_to_optuna_dist(var: param.Parameter) -> optuna.distributions.BaseDistribution:
    """Convert a sweep var to an optuna distribution

    Args:
        var (param.Parameter): A sweep var

    Raises:
        ValueError: Unsupported var type

    Returns:
        optuna.distributions.BaseDistribution: Optuna representation of a sweep var
    """

    if isinstance(var, IntSweep):
        return optuna.distributions.IntDistribution(var.bounds[0], var.bounds[1])
    if isinstance(var, FloatSweep):
        return optuna.distributions.FloatDistribution(var.bounds[0], var.bounds[1])
    if isinstance(var, (EnumSweep, StringSweep)):
        return optuna.distributions.CategoricalDistribution(var.objects)
    if isinstance(var, BoolSweep):
        return optuna.distributions.CategoricalDistribution([False, True])
    if isinstance(var, TimeSnapshot):
        return optuna.distributions.FloatDistribution(0, 1e20)
    if isinstance(var, TimeEvent):
        return optuna.distributions.CategoricalDistribution(var.values())

    raise ValueError(f"This input type {type(var)} is not supported")


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
        return None  # optuna does not like time
    if iv_type == BoolSweep:
        return trial.suggest_categorical(iv.name, [True, False])
    raise ValueError(f"This input type {iv_type} is not supported")


def cfg_from_optuna_trial(
    trial: optuna.trial, bench_cfg: BenchCfg, cfg_type: ParametrizedSweep
) -> ParametrizedSweep:
    cfg = cfg_type()
    for iv in bench_cfg.input_vars:
        if getattr(iv, "optimize", True):
            cfg.param.set_param(iv.name, sweep_var_to_suggest(iv, trial))
    for mv in bench_cfg.meta_vars:
        if getattr(mv, "optimize", True):
            sweep_var_to_suggest(mv, trial)
    return cfg


def _make_target(idx: int):
    """Create a target function that extracts the idx-th objective value from a trial."""

    def target(t):
        return t.values[idx]

    return target


def _append_safe(row, plot_fn, *args, **kwargs):
    """Append a plot to *row*, logging any exception instead of propagating."""
    try:
        row.append(plot_fn(*args, **kwargs))
    except Exception as e:  # pylint: disable=broad-except
        logging.exception(e)


def summarise_optuna_study(
    study: optuna.study.Study, target_names: list[str] | None = None
) -> pn.pane.panel:
    """Summarise an optuna study in a panel format.

    Args:
        study: The optuna study to summarise.
        target_names: Optional names for each objective. Falls back to "Objective N".
    """
    col = pn.Column(name="Optimisation Results")
    n_objectives = len(study.directions)
    is_multi = n_objectives >= 2

    col.append(pn.pane.Markdown("## Optimization History"))
    if is_multi:
        for idx in range(n_objectives):
            name = target_names[idx] if target_names and idx < len(target_names) else f"Obj {idx}"
            _append_safe(
                col, plot_optimization_history, study, target=_make_target(idx), target_name=name
            )
    else:
        _append_safe(col, plot_optimization_history, study)

    col.append(pn.pane.Markdown("## Parameter Importance"))
    if is_multi:
        for idx in range(n_objectives):
            name = target_names[idx] if target_names and idx < len(target_names) else f"Obj {idx}"
            _append_safe(
                col, plot_param_importances, study, target=_make_target(idx), target_name=name
            )
    else:
        _append_safe(col, plot_param_importances, study)

    # Parameter interactions
    n_params = len(study.trials[0].params) if study.trials else 0
    if n_params >= 2:
        col.append(pn.pane.Markdown("## Parameter Interactions"))
        if is_multi:
            for idx in range(n_objectives):
                name = (
                    target_names[idx] if target_names and idx < len(target_names) else f"Obj {idx}"
                )
                _append_safe(
                    col,
                    plot_parallel_coordinate,
                    study,
                    target=_make_target(idx),
                    target_name=name,
                )
                _append_safe(col, plot_slice, study, target=_make_target(idx), target_name=name)
        else:
            _append_safe(col, plot_parallel_coordinate, study)
            _append_safe(col, plot_slice, study)

    if is_multi:
        _append_safe(col, plot_pareto_front, study)

    # Summary section
    col.append(pn.pane.Markdown("## Summary"))
    if is_multi:
        col.append(pn.pane.Markdown(f"**Pareto-front size:** {len(study.best_trials)}"))
    else:
        summary_lines = [
            "| Parameter | Value |",
            "|-----------|-------|",
        ]
        for k, v in study.best_params.items():
            summary_lines.append(f"| {k} | {v} |")
        summary_lines.append("")
        summary_lines.append(f"**Best objective value:** {study.best_value}")
        col.append(pn.pane.Markdown("\n".join(summary_lines)))
    return col
