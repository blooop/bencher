"""Dummy version of PlannerSettingsSweep to reproduce shaded-area-instead-of-boxwhisker issue."""

from __future__ import annotations

import math
import random

import bencher as bch


class DummyPlannerSweep(bch.ParametrizedSweep):
    """Mimics PlannerSettingsSweep: StringSweep + FloatSweep, returns float results."""

    transition_id = bch.StringSweep(
        [
            "whole_body/Home -> whole_body/ReadyToPick",
            "whole_body/TransportTall -> whole_body/Home",
            "whole_body/Home -> whole_body/MovingWithItem",
            "torso/Bottom -> torso/Top",
        ],
        doc="Transition to benchmark.",
    )

    max_planning_time = bch.FloatSweep(
        default=0.1,
        bounds=[0.1, 5.0],
        units="s",
        samples=9,
        doc="Maximum time allowed for planning (seconds).",
    )

    # Constants (not swept)
    planning_attempts = bch.IntSweep(default=1, bounds=[1, 10], doc="Number of planning attempts.")
    goal_bias = bch.FloatSweep(default=0.05, bounds=[0.0, 1.0], doc="OMPL goal bias.")
    ompl_range = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="OMPL sampling step size.")

    # Result variables
    planning_success = bch.ResultVar(units="ratio", doc="Whether planning succeeded (1/0).")
    planning_time = bch.ResultVar(units="s", doc="Time taken for motion planning.")
    path_length = bch.ResultVar(units="rad", doc="Total L1 joint-space distance.")
    smoothness = bch.ResultVar(units="ul", doc="Trajectory smoothness (lower is smoother).")

    def __call__(self, **kwargs) -> DummyPlannerSweep:
        self.update_params_from_kwargs(**kwargs)

        # Fake different planning characteristics per transition
        base_times = {
            "whole_body/Home -> whole_body/ReadyToPick": 1.2,
            "whole_body/TransportTall -> whole_body/Home": 2.5,
            "whole_body/Home -> whole_body/MovingWithItem": 1.8,
            "torso/Bottom -> torso/Top": 0.4,
        }
        base = base_times.get(self.transition_id, 1.0)

        # Success depends on max_planning_time relative to base difficulty
        success_prob = min(1.0, self.max_planning_time / (base * 2))
        self.planning_success = 1.0 if random.random() < success_prob else 0.0

        if self.planning_success:
            self.planning_time = min(
                self.max_planning_time,
                base * random.lognormvariate(0, 0.3),
            )
            self.path_length = base * 0.5 + random.gauss(0, 0.1)
            self.smoothness = 0.1 + random.expovariate(1 / 0.05)
        else:
            self.planning_time = self.max_planning_time
            self.path_length = math.nan
            self.smoothness = math.nan

        return super().__call__()


def example_dummy_planner(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.over_time = True

    sweep = DummyPlannerSweep()
    bench = bch.Bench("dummy_planner_settings", sweep)

    bench.plot_sweep(
        title="Planner Settings Sweep (dummy)",
        input_vars=["max_planning_time", "transition_id"],
        result_vars=["planning_success", "planning_time", "path_length", "smoothness"],
        const_vars=sweep.get_input_defaults(),
        run_cfg=run_cfg,
        time_src=bch.git_time_event(),
    )
    bench.report.append(bench.get_result().to_optuna_plots())

    return bench


if __name__ == "__main__":
    bch.run(example_dummy_planner, level=4, repeats=20, show=False, save=True)
