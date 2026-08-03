from __future__ import annotations

import logging

import optuna
import panel as pn
import param

# NOTE: `optuna.visualization` pulls in sklearn's fANOVA evaluator (~3s at
# import). It is only needed by param_importance(), so import it lazily there.
from bencher.bench_cfg import BenchCfg
from bencher.results.render_failure import report_render_failure
from bencher.variables.inputs import BoolSweep, EnumSweep, FloatSweep, IntSweep, StringSweep
from bencher.variables.parametrised_sweep import ParametrizedSweep
from bencher.variables.time import TimeEvent, TimeSnapshot

logger = logging.getLogger(__name__)


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
def param_importance(
    bench_cfg: BenchCfg, study: optuna.Study, plot_width: int | None = None
) -> pn.Column:
    from optuna.visualization import plot_param_importances

    col_importance = pn.Column()
    for idx, tgt in enumerate(bench_cfg.optuna_targets()):

        def _target(t, i=idx):
            return t.values[i]

        fig = plot_param_importances(study, target=_target, target_name=tgt)
        if plot_width and hasattr(fig, "update_layout"):
            fig.update_layout(width=plot_width)
        col_importance.append(
            pn.Column(
                pn.pane.Markdown(f"## Parameter importance for: {tgt}"),
                fig,
            )
        )
    return col_importance


# BENCH_CFG
def summarise_trial(trial: optuna.trial, bench_cfg: BenchCfg) -> list[str]:
    """Given a trial produce a string summary of the best results

    Args:
        trial (optuna.trial): trial to summarise
        bench_cfg (BenchCfg): info about the trial

    Returns:
        list[str]: Summary of trial
    """
    sep = "    "
    output = []
    output.append(f"Trial id:{trial.number}:")
    output.append(f"{sep}Inputs:")
    for k, v in trial.params.items():
        output.append(f"{sep}{sep}{k}:{v}")
    output.append(f"{sep}Results:")
    for it, rv in enumerate(bench_cfg.optuna_targets()):
        output.append(f"{sep}{sep}{rv}:{trial.values[it]}")
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

    if isinstance(var, IntSweep):
        return optuna.distributions.IntDistribution(var.sweep_bounds[0], var.sweep_bounds[1])
    if isinstance(var, FloatSweep):
        return optuna.distributions.FloatDistribution(var.sweep_bounds[0], var.sweep_bounds[1])
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
        return trial.suggest_int(iv.name, iv.sweep_bounds[0], iv.sweep_bounds[1])
    if iv_type == FloatSweep:
        return trial.suggest_float(iv.name, iv.sweep_bounds[0], iv.sweep_bounds[1])
    if iv_type in (EnumSweep, StringSweep):
        return trial.suggest_categorical(iv.name, iv.objects)
    if iv_type in (TimeSnapshot, TimeEvent):
        return None  # optuna does not like time
    if iv_type == BoolSweep:
        return trial.suggest_categorical(iv.name, [True, False])
    raise ValueError(f"This input type {iv_type} is not supported")


def cfg_from_optuna_trial(
    trial: optuna.trial, bench_cfg: BenchCfg, cfg_type: type[ParametrizedSweep]
) -> ParametrizedSweep:
    """Build a worker config from an optuna trial's suggested values.

    ``cfg_type`` is the worker *class*, not an instance -- it is called here to construct
    one. Annotating it ``ParametrizedSweep`` makes a checker resolve ``cfg_type()``
    through ``Parameterized.__call__`` and infer a ``dict``.
    """
    cfg = cfg_type()
    for iv in bench_cfg.input_vars:
        if getattr(iv, "optimize", True):
            cfg.param.set_param(iv.name, sweep_var_to_suggest(iv, trial))
    for mv in bench_cfg.meta_vars:
        if getattr(mv, "optimize", True):
            sweep_var_to_suggest(mv, trial)
    return cfg


# The failure modes optuna's plotting functions are known to raise: a bad or
# empty study (ValueError), a plotly/optuna version mismatch (AttributeError,
# TypeError), or a backend that refuses to render (RuntimeError). These get an
# error pane and nothing more -- report_render_failure already logs at ERROR
# and warns.
_EXPECTED_PLOT_FAILURES = (RuntimeError, ValueError, TypeError, AttributeError)


def _plot_failure_pane(plot_fn, exc: Exception, *, unexpected: bool = False):
    """Build the error pane that replaces a plot that failed to render.

    *unexpected* marks an exception outside ``_EXPECTED_PLOT_FAILURES``; it gets
    an extra ERROR log naming the type, because an unanticipated type here is a
    signal that the expected-failure tuple has fallen out of date.
    """
    fn_name = getattr(plot_fn, "__name__", str(plot_fn))
    if unexpected:
        logger.error(
            "Unexpected %s while rendering optuna plot '%s'; rendering an error pane instead",
            type(exc).__name__,
            fn_name,
            exc_info=exc,
        )
    return report_render_failure(f"Optuna plot '{fn_name}'", exc)


def _append_safe(row, plot_fn, *args, **kwargs):
    """Append a plot to *row*, surfacing any exception instead of propagating.

    Nothing is ever re-raised: this runs while the report is being built, after
    the sweep has already paid for every sample, so a crash here would throw
    away the whole run's results to report one missing plot. A visible error
    pane costs nothing and keeps the rest of the report.
    """
    try:
        row.append(plot_fn(*args, **kwargs))
    except _EXPECTED_PLOT_FAILURES as exc:
        row.append(_plot_failure_pane(plot_fn, exc))
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        row.append(_plot_failure_pane(plot_fn, exc, unexpected=True))


def _append_safe_sized(row, plot_fn, width, *args, **kwargs):
    """Like _append_safe but sets a consistent width on the resulting plotly figure."""
    try:
        fig = plot_fn(*args, **kwargs)
        if hasattr(fig, "update_layout"):
            fig.update_layout(width=width)
        row.append(fig)
    except _EXPECTED_PLOT_FAILURES as exc:
        row.append(_plot_failure_pane(plot_fn, exc))
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        row.append(_plot_failure_pane(plot_fn, exc, unexpected=True))
