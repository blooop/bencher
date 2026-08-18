from __future__ import annotations

import param

from bencher.job import Executors
from bencher.variables.sweep_base import SUBSAMPLING_DIVISIONS_SAMPLES


class ExecutionCfg(param.Parameterized):
    """Configuration for how the benchmark function is executed.

    Controls sampling density, repeats, execution strategy and the
    error-tolerance behaviour of a sweep.

    Quick-start examples::

        # Use defaults — each variable uses its own ``samples`` setting:
        run_cfg = BenchRunCfg()

        # Set a sampling subsampling_divisions (geometrically increasing sample counts):
        run_cfg = BenchRunCfg(execution=ExecutionCfg(subsampling_divisions=5))  # 9 samples
        run_cfg = BenchRunCfg(execution=ExecutionCfg(subsampling_divisions=8))  # 65 samples

        # Or set an exact sample count directly:
        run_cfg = BenchRunCfg(execution=ExecutionCfg(samples_per_var=20))

    Subsampling Divisions-to-samples mapping
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ========= ======= ========= ======= ========= =======
    Divisions Samples Divisions Samples Divisions Samples
    ========= ======= ========= ======= ========= =======
    1         1       5         9       9         129
    2         2       6         17      10        257
    3         3       7         33      11        513
    4         5       8         65      12        1025
    ========= ======= ========= ======= ========= =======
    """

    repeats: int = param.Integer(1, doc="The number of times to sample the inputs")

    catch: tuple[type[BaseException], ...] = param.Parameter(
        (),
        doc="Exception types a single sample may raise without aborting the sweep. "
        "Default () keeps today's fail-fast behaviour. Spelled exactly as on "
        "Bench.optimize(catch=...), which has had this knob since #962. A caught "
        "sample leaves the missing-value sentinel at its coordinate, is logged at "
        "WARNING, and is recorded in BenchResult.failed_samples; nothing is written "
        "to the sample cache for it, so a transient flake cannot become permanent. "
        "A bare exception type is accepted and wrapped, so catch=RuntimeError and "
        "catch=(RuntimeError,) are the same; anything that is not an exception type "
        "raises TypeError at the start of the run rather than from inside the "
        "sampling loop. Use with fail_on_sample_error -- they are a pair, not "
        "independent "
        "knobs: catch alone turns real breakage into a green run over an "
        "all-sentinel dataset.",
    )

    fail_on_sample_error: bool | float = param.Parameter(
        False,
        doc="Fail the run after the fact if samples were caught. True raises when "
        "any sample failed; a float in (0, 1] raises when the failed *fraction* "
        "reaches it, so a flake is tolerated but a run made of flakes is not. The "
        "fraction is over samples this run *executed*, not over every coordinate: "
        "a cache hit never reached the worker and so could not have failed, and "
        "counting it would make one threshold mean different things on a cold and a "
        "warm cache. A truthy integer is rejected rather than guessed at: 1 could "
        "mean True or 100%, so write True or 1.0. Falsy values (False, 0, 0.0) mean "
        "off; out-of-range thresholds are rejected before sampling starts. The "
        "raise happens after the dataset and report are assembled, so the partial "
        "results survive it -- losing the artifact would defeat catching in the "
        "first place. It fires only for a run that actually sampled: on a "
        "benchmark-result cache hit the loaded result carries a previous run's "
        "failure counts, which are not this run's errors (read n_failed for that).",
    )

    subsampling_divisions: int = param.Integer(
        default=0,
        bounds=(0, 12),
        doc="Controls sample count for every sweep variable at once. "
        "Subsampling Divisions 0 (default) uses each variable's own `samples` setting. "
        "Subsampling Divisions 1-12 override with geometrically increasing counts: "
        "1→1, 2→2, 3→3, 4→5, 5→9, 6→17, 7→33, 8→65, 9→129, 10→257, 11→513, 12→1025. "
        "Use `ExecutionCfg.subsampling_divisions_to_samples(subsampling_divisions)` to query "
        "programmatically, or set `samples_per_var` for a direct sample count.",
    )

    samples_per_var: int | None = param.Integer(
        default=None,
        allow_None=True,
        bounds=(1, None),
        doc="Explicit number of samples per sweep variable. "
        "When set, takes precedence over `subsampling_divisions`. "
        "Example: samples_per_var=20 gives exactly 20 samples for every input variable.",
    )

    executor = param.Selector(
        objects=list(Executors),
        doc="The function can be run serially or in parallel with different futures executors",
    )

    nightly: bool = param.Boolean(
        False, doc="Run a more extensive set of tests for a nightly benchmark"
    )

    headless: bool = param.Boolean(False, doc="Run the benchmarks headlessly")

    dry_run: bool = param.Boolean(
        False,
        doc="When True, plot_sweep() computes the sweep grid and logs a summary "
        "(total combinations, parameter ranges, evaluation count) without "
        "executing the benchmark function.",
    )

    only_plot: bool = param.Boolean(
        False, doc="Do not attempt to calculate benchmarks if no results are found in the cache"
    )

    @staticmethod
    def subsampling_divisions_to_samples(
        subsampling_divisions: int, max_subsampling_divisions: int = 12
    ) -> int:
        """Return the number of samples-per-variable for a given *subsampling_divisions*.

        Args:
            subsampling_divisions: Sampling subsampling_divisions (1-12).
            max_subsampling_divisions: Cap applied before lookup. Defaults to 12.

        Returns:
            The sample count for this subsampling_divisions.

        Raises:
            ValueError: If *subsampling_divisions* is out of range.

        Example::

            >>> ExecutionCfg.subsampling_divisions_to_samples(5)
            9
        """
        if subsampling_divisions < 1 or subsampling_divisions >= len(SUBSAMPLING_DIVISIONS_SAMPLES):
            raise ValueError(
                f"subsampling_divisions must be between 1 and {len(SUBSAMPLING_DIVISIONS_SAMPLES) - 1}, got {subsampling_divisions}"
            )
        return SUBSAMPLING_DIVISIONS_SAMPLES[min(max_subsampling_divisions, subsampling_divisions)]
