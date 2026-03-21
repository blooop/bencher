"""OptimizeResult — first-class container for optimization results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import optuna
import panel as pn

from bencher.optuna_conversions import summarise_optuna_study


@dataclass
class OptimizeResult:
    """Wraps an ``optuna.Study`` with bencher-friendly accessors.

    Attributes:
        study: The underlying optuna study.
        n_warm_start_trials: Number of trials seeded from cache / prior results.
        n_new_trials: Number of new trials evaluated during optimization.
        target_names: Names of the optimization target variables.
    """

    study: optuna.Study
    n_warm_start_trials: int = 0
    n_new_trials: int = 0
    target_names: list[str] = field(default_factory=list)

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
        """Panel visualization reusing the existing ``summarise_optuna_study`` helper."""
        return summarise_optuna_study(self.study, target_names=self.target_names)

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
