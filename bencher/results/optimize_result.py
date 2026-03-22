"""OptimizeResult — first-class container for optimization results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

import optuna
import panel as pn

from optuna.visualization import (
    plot_param_importances,
    plot_pareto_front,
    plot_optimization_history,
)
from bencher.optuna_conversions import (
    _append_safe,
    _append_safe_sized,
    summarise_optuna_study,
    summarise_trial,
    param_importance,
)

if TYPE_CHECKING:
    from bencher.bench_cfg import BenchCfg


@dataclass
class OptimizeResult:
    """Wraps an ``optuna.Study`` with bencher-friendly accessors.

    Attributes:
        study: The underlying optuna study.
        n_warm_start_trials: Number of trials seeded from cache / prior results.
        n_new_trials: Number of new trials evaluated during optimization.
        target_names: Names of the optimization target variables.
        bench_cfg: Optional BenchCfg for rich report generation.
    """

    study: optuna.Study
    n_warm_start_trials: int = 0
    n_new_trials: int = 0
    target_names: list[str] = field(default_factory=list)
    bench_cfg: BenchCfg | None = None

    # ------------------------------------------------------------------
    # Single-objective helpers
    # ------------------------------------------------------------------

    def _ensure_single_objective(self) -> None:
        """Raise if study is multi-objective."""
        if len(self.study.directions) != 1:
            raise RuntimeError(
                "best_params/best_value are only defined for single-objective studies. "
                "For multi-objective studies use best_trials instead."
            )

    @property
    def best_params(self) -> dict[str, Any]:
        """Best parameters found (single-objective only)."""
        self._ensure_single_objective()
        return self.study.best_params

    @property
    def best_value(self) -> float:
        """Best objective value (single-objective only)."""
        self._ensure_single_objective()
        return self.study.best_value

    # ------------------------------------------------------------------
    # Multi-objective helpers
    # ------------------------------------------------------------------

    @property
    def best_trials(self) -> list[optuna.trial.FrozenTrial]:
        """Pareto-optimal trials (multi-objective)."""
        return self.study.best_trials

    # ------------------------------------------------------------------
    # Visualization
    # ------------------------------------------------------------------

    def to_panel(self) -> pn.pane.panel:
        """Panel visualization matching the collect_optuna_plots report layout."""
        if self.bench_cfg is not None:
            return self._collect_optuna_plots()
        return summarise_optuna_study(self.study)

    def _collect_optuna_plots(self) -> pn.pane.panel:
        """Produce the same report layout as OptunaResult.collect_optuna_plots."""
        study = self.study
        bench_cfg = self.bench_cfg
        target_names = bench_cfg.optuna_targets()
        plot_w = bench_cfg.plot_width or bench_cfg.plot_size or 600

        study_pane = pn.Column()
        param_str = []

        study_pane.append(pn.pane.Markdown("# Analysis"))

        if len(target_names) > 1:
            # --- Per-objective columns aligned with sweep result vars ---
            obj_row = pn.Row()
            for idx, tgt in enumerate(target_names):

                def _target(t, i=idx):
                    return t.values[i]

                col = pn.Column(pn.pane.Markdown(f"## {tgt}"))
                _append_safe_sized(
                    col, plot_optimization_history, plot_w,
                    study, target=_target, target_name=tgt,
                )
                _append_safe_sized(
                    col, plot_param_importances, plot_w,
                    study, target=_target, target_name=tgt,
                )
                obj_row.append(col)
            study_pane.append(obj_row)

            # --- Pareto Front ---
            if len(target_names) <= 3:
                _append_safe(
                    study_pane,
                    plot_pareto_front,
                    study,
                    target_names=target_names,
                    include_dominated_trials=False,
                )
            else:
                print("plotting pareto front of first 3 result variables")
                _append_safe(
                    study_pane,
                    plot_pareto_front,
                    study,
                    targets=lambda t: (t.values[0], t.values[1], t.values[2]),
                    target_names=target_names[:3],
                    include_dominated_trials=False,
                )

            param_str.append(
                f"    Number of trials on the Pareto front: {len(study.best_trials)}"
            )
            for t in study.best_trials:
                param_str.extend(summarise_trial(t, bench_cfg))

        else:
            _append_safe_sized(study_pane, plot_optimization_history, plot_w, study)

            if len(bench_cfg.input_vars) > 1:
                _append_safe_sized(
                    study_pane, plot_param_importances, plot_w,
                    study, target_name=target_names[0],
                )

            param_str.extend(summarise_trial(study.best_trial, bench_cfg))

        kwargs = {"height": 500, "scroll": True} if len(param_str) > 30 else {}

        param_str = "\n".join(param_str)
        study_pane.append(
            pn.Row(
                pn.pane.Markdown(f"## Best Parameters\n```text\n{param_str}"),
                **kwargs,
            ),
        )

        return pn.Row(study_pane)

    # ------------------------------------------------------------------
    # Text summary
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Return a human-readable summary of the optimization."""
        lines = [
            f"Study: {self.study.study_name}",
            f"  warm-start trials: {self.n_warm_start_trials}",
            f"  new trials:        {self.n_new_trials}",
            f"  total trials:      {len(self.study.trials)}",
        ]
        directions = self.study.directions
        if len(directions) == 1:
            lines.append(f"  best value:  {self.study.best_value}")
            lines.append(f"  best params: {self.study.best_params}")
        else:
            lines.append(f"  Pareto-front size: {len(self.study.best_trials)}")
        return "\n".join(lines)
