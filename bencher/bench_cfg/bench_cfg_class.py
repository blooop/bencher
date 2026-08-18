from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import panel as pn
import param

from bencher.bench_cfg.run_cfg import BenchRunCfg
from bencher.cache_management import CACHE_VERSION
from bencher.results.laxtex_result import to_latex
from bencher.utils import AggFn
from bencher.variables.results import OptDir
from bencher.variables.sweep_base import describe_variable, hash_sha1
from bencher.variables.time import TimeEvent, TimeSnapshot

if TYPE_CHECKING:
    # Runtime import would be circular: identity imports this module.
    from bencher.identity import SweepIdentity

logger = logging.getLogger(__name__)


class BenchCfg(BenchRunCfg):
    """Complete configuration for a benchmark protocol.

    This class extends BenchRunCfg and provides a comprehensive set of parameters
    for configuring benchmark runs. It maintains a unique hash value based on its
    configuration to ensure that benchmark results can be consistently referenced
    and that plots are uniquely identified across runs.

    The class handles input variables, result variables, constant values, meta variables,
    and various presentation options. It also provides methods for generating
    descriptive summaries and visualizations of the benchmark configuration.

    Attributes:
        input_vars (list): A list of ParameterizedSweep variables to perform a parameter sweep over
        result_vars (list): A list of ParameterizedSweep results to collect and plot
        const_vars (list): Variables to keep constant but are different from the default value
        result_hmaps (list): A list of holomap results
        meta_vars (list): Meta variables such as recording time and repeat id
        all_vars (list): Stores a list of both the input_vars and meta_vars
        iv_time (list[TimeSnapshot | TimeEvent]): Parameter for sampling the same inputs over time
        name (str): The name of the benchmarkCfg
        title (str): The title of the benchmark
        bench_name (str): The name of the benchmark and save folder
        description (str): A longer description of the benchmark function
        post_description (str): Comments on the output of the graphs
        has_results (bool): Whether this config has results
        pass_repeat (bool): Whether to pass the 'repeat' kwarg to the benchmark function
        tag (str): Tags for grouping different benchmarks
        hash_value (str): Stored hash value of the config
        plot_callbacks (list): Callables that take a BenchResult and return panel representation

    Parameter interactions:
        The caching and history knobs below live on ``BenchRunCfg`` sub-configs
        and are inherited here; the ``run_cfg`` passed to ``plot_sweep`` is
        merged onto the ``BenchCfg`` before the run, so a run_cfg value wins
        over the one stored on the config (except for parameters declared
        constant, which are skipped with a warning).

        Benchmark-level result cache (``cache.results``, ``cache.clear``):
            * The *write* is unconditional. Whenever a sweep actually runs, the
              finished ``BenchResult`` is stored under the config hash regardless
              of ``cache.results`` — so a later run with ``cache.results=True``
              can hit an entry left by a run that had it off.
            * ``cache.results`` controls only the *read*: with it True, a stored
              result under the same config hash is loaded and the entire sweep is
              skipped.
            * ``cache.clear=True`` takes precedence over ``cache.results``: the
              entry is deleted and no read is attempted, so the sweep always
              re-runs (and repopulates the entry at the end).
            * ``execution.only_plot=True`` forces ``cache.results=True``, and
              turns a cache miss into ``FileNotFoundError`` instead of a re-run.

        Per-sample cache (``cache.samples``, ``cache.overwrite_samples``,
        ``cache.clear_samples``):
            * Independent of the benchmark-level cache: this one caches individual
              benchmark-function calls rather than the finished result.
            * With ``cache.samples=False`` no sample cache is opened at all, so
              nothing is read or written per sample and the other two flags have
              nothing to act on — clearing a tag then logs a warning rather than
              letting "nothing happened" look like "the tag was cleared".
            * ``cache.overwrite_samples=True`` keeps writing but stops reading:
              every sample is recomputed and its stored value replaced.
            * ``cache.clear_samples=True`` evicts this benchmark's ``tag`` from
              the sample cache before any sampling starts.

        History and ``over_time`` (``time.clear_history``, ``time.max_events``):
            * History is only loaded, merged and written back when
              ``time.over_time=True``. With it False the run is a single snapshot
              and neither ``time.clear_history`` nor ``time.max_events`` does
              anything.
            * The history key deliberately excludes result variables, so adding or
              removing a metric reconciles per column instead of orphaning the
              whole series. The benchmark-level result cache above stays strict —
              a hit there requires the exact result-var set.
            * ``time.clear_history=True`` skips the load: a fresh series starts
              from this run and is written back.
            * ``time.max_events`` trims the merged dataset after reconciliation,
              keeping the newest N events and dropping older ones; ``None`` means
              unlimited. A result variable may additionally carry its own
              ``max_time_events``, which nulls that variable's older cells (and
              deletes any media files they owned) without shortening the shared
              ``over_time`` axis.
    """

    # These six declare *lists of variables*, and "no variables" is spelled `[]`, not
    # `None`. They defaulted to None until plan 23 P12b. That default is what obliged every
    # reader to carry an `or []`, and 26 iteration sites across eight modules did not, so
    # `BenchCfg()` built outside `plot_sweep` raised `TypeError: 'NoneType' object is not
    # iterable` from inside describe/plot code (the per-module breakdown is in plan 23 §10
    # P12b item 1). param.List instantiates mutable defaults per instance -- verified, not
    # assumed -- so `[]` is not shared state.
    input_vars = param.List(
        default=[],
        doc="A list of ParameterizedSweep variables to perform a parameter sweep over",
    )
    result_vars = param.List(
        default=[],
        doc="A list of ParameterizedSweep results collect and plot.",
    )

    const_vars = param.List(
        default=[],
        doc="Variables to keep constant but are different from the default value",
    )

    result_hmaps = param.List(default=[], doc="a list of holomap results")

    meta_vars = param.List(
        default=[],
        doc="Meta variables such as recording time and repeat id",
    )
    all_vars = param.List(
        default=[],
        doc="Stores a list of both the input_vars and meta_vars that are used to define a unique hash for the input",
    )
    iv_time = param.List(
        default=[],
        item_type=TimeSnapshot | TimeEvent,
        doc="A parameter to represent the sampling the same inputs over time as a scalar type",
    )

    name: str | None = param.String(None, doc="The name of the benchmarkCfg")
    title: str | None = param.String(None, doc="The title of the benchmark")
    bench_name: str | None = param.String(
        None, doc="The name of the benchmark and the name of the save folder"
    )
    description: str | None = param.String(
        None,
        doc="A place to store a longer description of the function of the benchmark",
    )
    post_description: str | None = param.String(
        None, doc="A place to comment on the output of the graphs"
    )

    has_results: bool = param.Boolean(
        False,
        doc="If this config has results, true, otherwise used to store titles and other bench metadata",
    )

    pass_repeat: bool = param.Boolean(
        False,
        doc="By default do not pass the kwarg 'repeat' to the benchmark function.  Set to true if you want the benchmark function to be passed the repeat number",
    )

    tag: str = param.String(
        "",
        doc="Use tags to group different benchmarks together. By default benchmarks are considered distinct from each other and are identified by the hash of their name and inputs, constants and results and tag, but you can optionally change the hash value to only depend on the tag.  This way you can have multiple unrelated benchmarks share values with each other based only on the tag value.",
    )

    series_id: str = param.String(
        None,
        allow_None=True,
        doc="Names the over_time *trend* this benchmark appends to, independently of "
        "what identifies its configuration. tag partitions storage; series_id names "
        "the trend. Deliberately NOT part of hash_persistent: two benchmarks with the "
        "same name, tag, inputs and consts stay one cache entry whatever their "
        "series_id, and folding it in would re-key every existing cache and history "
        "on upgrade. Declare it to keep a trend across a rename of the worker class "
        "or a change of cache tag; leave it unset and the series is bench_name:tag, "
        "exactly as before.",
    )

    hash_value: str = param.String(
        "",
        doc="store the hash value of the config to avoid having to hash multiple times",
    )

    plot_callbacks = param.List(
        None,
        doc="A callable that takes a BenchResult and returns panel representation of the results",
    )

    agg_over_dims = param.List(
        default=None,
        doc="Dimension names to aggregate over when auto-appending aggregated views. "
        "When set, run_sweep will automatically append CurveResult (mean +/- std) "
        "and BandResult (percentile bands) with these dims collapsed.",
    )
    # The objects derive from AggFn (the single source of the vocabulary, plan 23
    # C11/P11) but stay plain strings: param stores whatever the caller assigns, so
    # readers of this field must construct the enum at the boundary via
    # normalize_agg_fn before matching on it (plan 24 A2/A3).
    agg_fn = param.ObjectSelector(
        default=AggFn.MEAN.value,
        objects=[m.value for m in AggFn],
        doc="Aggregation function to use when agg_over_dims is set.",
    )

    def __init__(self, **params: Any) -> None:
        """Initialize a BenchCfg with the given parameters.

        Args:
            **params (Any): Parameters to set on the BenchCfg
        """
        super().__init__(**params)
        self.plot_lib = None
        self.hmap_kdims = None
        self.iv_repeat = None

    def hash_persistent(self, include_repeats: bool, include_result_vars: bool = True) -> str:
        """Generate a persistent hash for the benchmark configuration.

        Overrides the default hash function because the default hash function does not
        return the same value for the same inputs. This method references only stable
        variables that are consistent across instances of BenchCfg with the same
        configuration.

        ``input_vars`` are folded in list order because their order determines the
        dimension layout of the result arrays. ``result_vars`` and ``const_vars``
        contribute as an *unordered set* (their per-var digests are sorted before
        hashing): result vars become name-keyed xarray data variables and const
        order only affects the title string, so reordering either is a
        presentation change that must not move the cache key.

        Args:
            include_repeats (bool): Whether to include repeats as part of the hash
                                   (True by default except when using the sample cache)
            include_result_vars (bool): Whether result variables contribute to the
                hash. True for the benchmark-level result cache, where a cached
                result must match the exact result-var set. False for the
                over_time history key, so the history survives result-var
                changes and per-column reconciliation can retain, retire, or
                backfill individual columns (see ``bencher.history``).

        Returns:
            str: A persistent hash value for the benchmark configuration
        """

        if include_repeats:
            # needed so that the historical xarray arrays are the same size
            repeats_hash = hash_sha1(self.execution.repeats)
        else:
            repeats_hash = 0

        # NOTE: title is intentionally excluded from the hash so that renaming
        # a benchmark's display title does not invalidate cached results or
        # lose over_time history.  The benchmark is uniquely identified by
        # bench_name + input/result/const vars + tag + over_time + repeats.
        #
        # CACHE_VERSION is folded in so that bumping it atomically invalidates
        # every benchmark-level and over_time history key without relying
        # solely on the on-disk version-file check in ``ensure_cache_version``.
        hash_val = hash_sha1(
            (
                CACHE_VERSION,
                hash_sha1(str(self.bench_name)),
                hash_sha1(self.time.over_time),
                repeats_hash,
                hash_sha1(self.tag),
            )
        )
        # The three `or []` folds here and below are unreachable since plan 23 P12b gave
        # these fields `default=[]` -- param rejects None outright now. They are kept
        # deliberately, because they are *why* that change could not move a stored digest:
        # `[]` and `None` were already folded identically, so the pre- and post-change
        # digests match (measured, not argued). Deleting them is a provable no-op and is
        # logged as entry L7 of plans/27-cache-version-bump-ledger.md, to be swept with the
        # next CACHE_VERSION bump rather than as a drive-by that removes the evidence.
        for v in self.input_vars or []:
            hash_val = hash_sha1((hash_val, v.hash_persistent()))

        # Folded as sets -- sorted *unique* digests -- so that a variable appearing twice
        # cannot move the key, which is what "unordered set" above has always claimed.
        # A sorted tuple delivered the ordering half of that contract but not the
        # uniqueness half: a repeat appeared twice in the hashed sequence, while the
        # dataset's data_vars and history's per-column metadata are keyed by name and
        # collapsed it. That disagreement is the bug plan 20 documents.
        # validate_declared_vars rejects or dedupes duplicates before they reach here on
        # the plot_sweep path; deduping here too keeps identity correct on the paths that
        # bypass it -- a BenchCfg built or deserialized directly. Configurations without a
        # duplicate hash exactly as before, since sorted(set(xs)) == sorted(xs) when xs is
        # already unique.
        if include_result_vars:
            result_hashes = tuple(sorted({v.hash_persistent() for v in self.result_vars or []}))
        else:
            result_hashes = ()

        const_hashes = tuple(
            sorted(
                {
                    hash_sha1((v[0].hash_persistent(), hash_sha1(v[1])))
                    for v in self.const_vars or []
                }
            )
        )

        return hash_sha1((hash_val, result_hashes, const_hashes))

    def identity(self, run_cfg: BenchRunCfg | None = None) -> SweepIdentity:
        """This config's cache/history/sample keys as an inspectable value.

        *run_cfg* replays the merge :meth:`bencher.bencher.Bench.run_sweep`
        performs before hashing; pass it for a config that has not been run, whose
        ``repeats`` and ``over_time`` are still the class defaults. The replay runs
        against a copy, so asking for an identity never reconfigures *self*.
        """
        from bencher.identity import identity_of

        return identity_of(self, run_cfg)

    @property
    def series(self) -> str:
        """The series this run appends to: the declared ``series_id`` or the default."""
        from bencher.history import default_series_id

        return self.series_id or default_series_id(self.bench_name, self.tag)

    def inputs_as_str(self) -> list[str]:
        """Get a list of input variable names.

        Returns:
            list[str]: List of the names of input variables
        """
        return [i.name for i in self.input_vars]

    def to_latex(self) -> pn.pane.LaTeX | None:
        """Convert benchmark configuration to LaTeX representation.

        Returns:
            pn.pane.LaTeX | None: LaTeX representation of the benchmark configuration
        """
        return to_latex(self)

    def to_cartesian_animation(self) -> str | None:
        """Render an animation of the Cartesian product data collection.

        Delegates to :func:`bencher.results.manim_cartesian.render_animation`,
        which currently uses a PIL-based renderer. Returns the filesystem path
        to the generated animated PNG (or other format, depending on the
        renderer), or ``None`` on failure so callers can degrade gracefully.

        Returns:
            str | None: Path to the rendered animation file, or None on failure.
        """
        try:
            from bencher.results.manim_cartesian import from_bench_cfg, render_animation

            cfg = from_bench_cfg(self)
            return render_animation(cfg, width=350, height=250)
        except (ImportError, AttributeError, ValueError, RuntimeError, OSError):
            # Log the exception so failures remain diagnosable while preserving
            # the existing graceful fallback behavior.
            logger.exception("Failed to render Cartesian animation for bench config %r", self)
            return None

    def describe_sweep(
        self, width: int = 800, accordion: bool = True
    ) -> pn.pane.Markdown | pn.Column:
        """Produce a markdown summary of the sweep settings.

        Args:
            width (int): Width of the markdown panel in pixels. Defaults to 800.
            accordion (bool): Whether to wrap the description in an accordion. Defaults to True.

        Returns:
            pn.pane.Markdown | pn.Column: Panel containing the sweep description
        """

        latex = self.to_latex()
        desc = pn.pane.Markdown(self.describe_benchmark(), width=width)
        if accordion:
            desc = pn.Accordion(("Expand Full Data Collection Parameters", desc))

        sentence = self.sweep_sentence()

        parts = [sentence]
        if latex is not None:
            parts.append(latex)

        # Render Cartesian product animation (gracefully skipped on error)
        animation_path = self.to_cartesian_animation()
        if animation_path is not None:
            from pathlib import Path

            abs_path = str(Path(animation_path).resolve())
            parts.append(pn.pane.Image(abs_path, width=350))

        parts.append(desc)
        return pn.Column(*parts)

    def sweep_sentence(self) -> pn.pane.Markdown:
        """Generate a concise summary sentence of the sweep configuration.

        Returns:
            pn.pane.Markdown: A panel containing a markdown summary sentence
        """
        inputs = " by ".join([iv.name for iv in self.all_vars])

        all_vars_lens = [len(iv.values()) for iv in reversed(self.all_vars)]
        if len(all_vars_lens) == 1:
            all_vars_lens.append(1)
        result_sizes = "x".join([str(iv) for iv in all_vars_lens])
        results = ", ".join([rv.name for rv in self.result_vars])

        return pn.pane.Markdown(
            f"Sweeping {inputs} to generate a {result_sizes} result dataframe containing {results}. "
        )

    def describe_benchmark(self) -> str:
        """Generate a detailed string summary of the inputs and results from a BenchCfg.

        Returns:
            str: Comprehensive summary of BenchCfg
        """
        benchmark_sampling_str = ["```text"]
        benchmark_sampling_str.append("")

        benchmark_sampling_str.append("Input Variables:")
        for iv in self.input_vars:
            benchmark_sampling_str.extend(describe_variable(iv, True))

        if self.const_vars and (self.display.summarise_constant_inputs):
            benchmark_sampling_str.append("\nConstants:")
            for cv in self.const_vars:
                benchmark_sampling_str.extend(describe_variable(cv[0], False, cv[1]))

        benchmark_sampling_str.append("\nResult Variables:")
        for rv in self.result_vars:
            benchmark_sampling_str.extend(describe_variable(rv, False))

        benchmark_sampling_str.append("\nMeta Variables:")
        benchmark_sampling_str.append(f"    run date: {self.run_date}")
        if self.run_tag:
            benchmark_sampling_str.append(f"    run tag: {self.run_tag}")
        if self.execution.subsampling_divisions is not None:
            benchmark_sampling_str.append(
                f"    bench subsampling_divisions: {self.execution.subsampling_divisions}"
            )
        benchmark_sampling_str.append(f"    cache_results: {self.cache.results}")
        benchmark_sampling_str.append(f"    cache_samples {self.cache.samples}")
        benchmark_sampling_str.append(f"    only_hash_tag: {self.cache.only_hash_tag}")
        benchmark_sampling_str.append(f"    executor: {self.execution.executor}")

        for mv in self.meta_vars:
            benchmark_sampling_str.extend(describe_variable(mv, True))

        benchmark_sampling_str.append("```")

        benchmark_sampling_str = "\n".join(benchmark_sampling_str)
        return benchmark_sampling_str

    def to_title(self, panel_name: str | None = None) -> pn.pane.Markdown:
        """Create a markdown panel with the benchmark title.

        Args:
            panel_name (str | None): The name for the panel. Defaults to the benchmark title.

        Returns:
            pn.pane.Markdown: A panel with the benchmark title as a heading
        """
        if panel_name is None:
            panel_name = self.title
        return pn.pane.Markdown(f"# {self.title}", name=panel_name)

    def to_description(self, width: int = 800) -> pn.pane.Markdown:
        """Create a markdown panel with the benchmark description.

        Args:
            width (int): Width of the markdown panel in pixels. Defaults to 800.

        Returns:
            pn.pane.Markdown: A panel with the benchmark description
        """
        return pn.pane.Markdown(self.description or "", width=width)

    def to_post_description(self, width: int = 800) -> pn.pane.Markdown:
        """Create a markdown panel with the benchmark post-description.

        Args:
            width (int): Width of the markdown panel in pixels. Defaults to 800.

        Returns:
            pn.pane.Markdown: A panel with the benchmark post-description
        """
        return pn.pane.Markdown(self.post_description or "", width=width)

    def to_sweep_summary(
        self,
        name: str | None = None,
        description: bool = True,
        describe_sweep: bool = True,
        results_suffix: bool = True,
        title: bool = True,
    ) -> pn.Column:
        """Produce panel output summarising the title, description and sweep setting.

        Args:
            name (str | None): Name for the panel. Defaults to benchmark title or
                                 "Data Collection Parameters" if title is False.
            description (bool): Whether to include the benchmark description. Defaults to True.
            describe_sweep (bool): Whether to include the sweep description. Defaults to True.
            results_suffix (bool): Whether to add a "Results:" heading. Defaults to True.
            title (bool): Whether to include the benchmark title. Defaults to True.

        Returns:
            pn.Column: A panel with the benchmark summary
        """
        if name is None:
            if title:
                name = self.title
            else:
                name = "Data Collection Parameters"
        col = pn.Column(name=name)
        if title:
            col.append(self.to_title())
        if self.description is not None and description:
            col.append(self.to_description())
        if describe_sweep:
            col.append(self.describe_sweep())
        if results_suffix:
            col.append(pn.pane.Markdown("## Results:"))
        return col

    @staticmethod
    def partition_input_vars(vars_) -> tuple[list, list]:
        """Split variables into (optimized, non-optimized) based on the optimize flag."""
        opt = [v for v in vars_ if getattr(v, "optimize", True)]
        non_opt = [v for v in vars_ if not getattr(v, "optimize", True)]
        return opt, non_opt

    @property
    def optimized_input_vars(self) -> list:
        """Return input variables where optimize=True (suggested by Optuna)."""
        return self.partition_input_vars(self.input_vars or [])[0]

    @property
    def non_optimized_input_vars(self) -> list:
        """Return input variables where optimize=False (swept/aggregated, not suggested)."""
        return self.partition_input_vars(self.input_vars or [])[1]

    def optuna_targets(self, as_var: bool = False) -> list[Any]:
        """Get the list of result variables that are optimization targets.

        Args:
            as_var (bool): If True, return the variable objects rather than their names.
                          Defaults to False.

        Returns:
            list[Any]: List of result variable names or objects that are optimization targets
        """
        targets = []
        for rv in self.result_vars:
            if hasattr(rv, "direction") and rv.direction != OptDir.none:
                if as_var:
                    targets.append(rv)
                else:
                    targets.append(rv.name)
        return targets
