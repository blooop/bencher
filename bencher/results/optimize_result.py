"""OptimizeResult — first-class container for optimization results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import optuna

from bencher.utils import AggFn

if TYPE_CHECKING:
    from bencher.bench_cfg import BenchCfg


@dataclass(frozen=True)
class Aggregation:
    """How a study reduced several evaluations of one design to the value it ranked.

    A study aggregates whenever it evaluated a design more than once: over the
    dimensions ``Bench.optimize(aggregate=...)`` looped inside each trial, over the
    repeats, or both. So ``dims`` is empty for a study that only had ``repeats > 1``,
    and the presence of an ``Aggregation`` is the separate — and, for a reader of the
    front, the load-bearing — fact that a trial's value is a different number from
    any one sample of it.

    Attributes:
        fn: What combined them.
        dims: The input variables looped inside each trial rather than suggested by
            optuna, in the study's order. Empty when only the repeats were reduced.
    """

    fn: AggFn
    dims: tuple[str, ...] = ()


@dataclass
class OptimizeResult:
    """Wraps an ``optuna.Study`` with bencher-friendly accessors.

    Attributes:
        study: The underlying optuna study.
        n_warm_start_trials: Number of trials seeded from cache / prior results.
        n_new_trials: Number of new trials evaluated during optimization.
        target_names: Names of the optimization target variables.
        bench_cfg: Optional BenchCfg for rich report generation.
        aggregation: How several evaluations of one design became the value the study
            ranked, or None when a trial's value is one sample — see
            :class:`Aggregation`.
    """

    study: optuna.Study
    n_warm_start_trials: int = 0
    n_new_trials: int = 0
    target_names: list[str] = field(default_factory=list)
    bench_cfg: BenchCfg | None = None
    aggregation: Aggregation | None = None

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

    def pareto_trials(self, objective: str | None = None) -> list[optuna.trial.FrozenTrial]:
        """The Pareto front ordered along one objective, best first.

        ``best_trials`` is a set in trial order, which is the order optuna happened
        to find them in. Sorting the front along *objective* — the first target by
        default — turns it into a walk: the trial that is best on that objective
        first, then each trade-off in turn, ending at the one that gave the most of
        it away. That is the order a slider through the front should take. A
        single-objective study has a front of one, its best trial.

        Raises:
            ValueError: if *objective* is not one of ``target_names``.
        """
        index = 0 if objective is None else self._target_index(objective)
        descending = self.study.directions[index] == optuna.study.StudyDirection.MAXIMIZE
        return sorted(
            self.study.best_trials,
            key=lambda trial: trial.values[index],
            reverse=descending,
        )

    def _target_index(self, objective: str) -> int:
        if objective not in self.target_names:
            raise ValueError(
                f"{objective!r} is not an objective of this study; "
                f"its targets are {self.target_names}"
            )
        return self.target_names.index(objective)

    @property
    def searched(self) -> list[str]:
        """Names of the input variables optuna suggested, in the study's order.

        The complement of ``aggregation.dims`` within the study's inputs, so it is
        empty without a ``bench_cfg``.
        """
        if self.bench_cfg is None:
            return []
        looped = self.aggregation.dims if self.aggregation else ()
        return [iv.name for iv in self.bench_cfg.input_vars if iv.name not in looped]

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
