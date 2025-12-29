"""Complete configuration for a benchmark protocol."""

from __future__ import annotations

from typing import List, Optional, Any, Union

import param
import panel as pn

from bencher.bench_cfg.run_cfg import BenchRunCfg
from bencher.variables.sweep_base import hash_sha1, describe_variable
from bencher.variables.time import TimeSnapshot, TimeEvent
from bencher.variables.results import OptDir
from bencher.results.laxtex_result import to_latex


class BenchCfg(BenchRunCfg):
    """Full benchmark config: input/result variables, metadata, and sweep parameters."""

    input_vars = param.List(
        default=None,
        doc="A list of ParameterizedSweep variables to perform a parameter sweep over",
    )
    result_vars = param.List(
        default=None,
        doc="A list of ParameterizedSweep results collect and plot.",
    )

    const_vars = param.List(
        default=None,
        doc="Variables to keep constant but are different from the default value",
    )

    result_hmaps = param.List(default=None, doc="a list of holomap results")

    meta_vars = param.List(
        default=None,
        doc="Meta variables such as recording time and repeat id",
    )
    all_vars = param.List(
        default=None,
        doc="Stores a list of both the input_vars and meta_vars that are used to define a unique "
        "hash for the input",
    )
    iv_time = param.List(
        default=[],
        item_type=Union[TimeSnapshot, TimeEvent],
        doc="A parameter to represent the sampling the same inputs over time as a scalar type",
    )

    iv_time_event = param.List(
        default=[],
        item_type=TimeEvent,
        doc="A parameter to represent the sampling the same inputs over time as a discrete type",
    )

    # Note: over_time is inherited from BenchRunCfg via TimeCfg delegation
    name: Optional[str] = param.String(None, doc="The name of the benchmarkCfg")
    title: Optional[str] = param.String(None, doc="The title of the benchmark")
    raise_duplicate_exception: bool = param.Boolean(
        False, doc="Use this while debugging if filename generation is unique"
    )
    bench_name: Optional[str] = param.String(
        None, doc="The name of the benchmark and the name of the save folder"
    )
    description: Optional[str] = param.String(
        None,
        doc="A place to store a longer description of the function of the benchmark",
    )
    post_description: Optional[str] = param.String(
        None, doc="A place to comment on the output of the graphs"
    )

    has_results: bool = param.Boolean(
        False,
        doc="If this config has results, true, otherwise used to store titles and other bench "
        "metadata",
    )

    pass_repeat: bool = param.Boolean(
        False,
        doc="By default do not pass the kwarg 'repeat' to the benchmark function. Set to true "
        "if you want the benchmark function to be passed the repeat number",
    )

    tag: str = param.String(
        "",
        doc="Use tags to group different benchmarks together. By default benchmarks are "
        "considered distinct from each other and are identified by the hash of their name and "
        "inputs, constants and results and tag, but you can optionally change the hash value "
        "to only depend on the tag. This way you can have multiple unrelated benchmarks share "
        "values with each other based only on the tag value.",
    )

    hash_value: str = param.String(
        "",
        doc="store the hash value of the config to avoid having to hash multiple times",
    )

    plot_callbacks = param.List(
        None,
        doc="A callable that takes a BenchResult and returns panel representation of the results",
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

    def hash_persistent(self, include_repeats: bool) -> str:
        """Generate a persistent hash for the benchmark configuration.

        Overrides the default hash function because the default hash function does not
        return the same value for the same inputs. This method references only stable
        variables that are consistent across instances of BenchCfg with the same
        configuration.

        Args:
            include_repeats (bool): Whether to include repeats as part of the hash
                                   (True by default except when using the sample cache)

        Returns:
            str: A persistent hash value for the benchmark configuration
        """

        if include_repeats:
            # needed so that the historical xarray arrays are the same size
            repeats_hash = hash_sha1(self.execution.repeats)
        else:
            repeats_hash = 0

        hash_val = hash_sha1(
            (
                hash_sha1(str(self.bench_name)),
                hash_sha1(str(self.title)),
                hash_sha1(self.time.over_time),
                repeats_hash,
                hash_sha1(self.tag),
            )
        )
        all_vars = self.input_vars + self.result_vars
        for v in all_vars:
            hash_val = hash_sha1((hash_val, v.hash_persistent()))

        for v in self.const_vars:
            hash_val = hash_sha1((v[0].hash_persistent(), hash_sha1(v[1])))

        return hash_val

    def inputs_as_str(self) -> List[str]:
        """Get a list of input variable names.

        Returns:
            List[str]: List of the names of input variables
        """
        return [i.name for i in self.input_vars]

    def to_latex(self) -> Optional[pn.pane.LaTeX]:
        """Convert benchmark configuration to LaTeX representation.

        Returns:
            Optional[pn.pane.LaTeX]: LaTeX representation of the benchmark configuration
        """
        return to_latex(self)

    def describe_sweep(
        self, width: int = 800, accordion: bool = True
    ) -> Union[pn.pane.Markdown, pn.Column]:
        """Produce a markdown summary of the sweep settings.

        Args:
            width (int): Width of the markdown panel in pixels. Defaults to 800.
            accordion (bool): Whether to wrap the description in an accordion. Defaults to True.

        Returns:
            Union[pn.pane.Markdown, pn.Column]: Panel containing the sweep description
        """

        latex = self.to_latex()
        desc = pn.pane.Markdown(self.describe_benchmark(), width=width)
        if accordion:
            desc = pn.Accordion(("Expand Full Data Collection Parameters", desc))

        sentence = self.sweep_sentence()
        if latex is not None:
            return pn.Column(sentence, latex, desc)
        return pn.Column(sentence, desc)

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
            f"Sweeping {inputs} to generate a {result_sizes} result dataframe containing "
            f"{results}. "
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
        benchmark_sampling_str.append(f"    run date: {self.time.run_date}")
        if self.time.run_tag:
            benchmark_sampling_str.append(f"    run tag: {self.time.run_tag}")
        if self.execution.level is not None:
            benchmark_sampling_str.append(f"    bench level: {self.execution.level}")
        benchmark_sampling_str.append(f"    cache_results: {self.cache.cache_results}")
        benchmark_sampling_str.append(f"    cache_samples: {self.cache.cache_samples}")
        benchmark_sampling_str.append(f"    only_hash_tag: {self.cache.only_hash_tag}")
        benchmark_sampling_str.append(f"    executor: {self.execution.executor}")

        for mv in self.meta_vars:
            benchmark_sampling_str.extend(describe_variable(mv, True))

        benchmark_sampling_str.append("```")

        benchmark_sampling_str = "\n".join(benchmark_sampling_str)
        return benchmark_sampling_str

    def to_title(self, panel_name: Optional[str] = None) -> pn.pane.Markdown:
        """Create a markdown panel with the benchmark title.

        Args:
            panel_name (Optional[str]): The name for the panel. Defaults to the benchmark title.

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
        return pn.pane.Markdown(f"{self.description}", width=width)

    def to_post_description(self, width: int = 800) -> pn.pane.Markdown:
        """Create a markdown panel with the benchmark post-description.

        Args:
            width (int): Width of the markdown panel in pixels. Defaults to 800.

        Returns:
            pn.pane.Markdown: A panel with the benchmark post-description
        """
        return pn.pane.Markdown(f"{self.post_description}", width=width)

    def to_sweep_summary(
        self,
        name: Optional[str] = None,
        description: bool = True,
        describe_sweep: bool = True,
        results_suffix: bool = True,
        title: bool = True,
    ) -> pn.Column:
        """Produce panel output summarising the title, description and sweep setting.

        Args:
            name (Optional[str]): Name for the panel. Defaults to benchmark title or
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

    def optuna_targets(self, as_var: bool = False) -> List[Any]:
        """Get the list of result variables that are optimization targets.

        Args:
            as_var (bool): If True, return the variable objects rather than their names.
                          Defaults to False.

        Returns:
            List[Any]: List of result variable names or objects that are optimization targets
        """
        targets = []
        for rv in self.result_vars:
            if hasattr(rv, "direction") and rv.direction != OptDir.none:
                if as_var:
                    targets.append(rv)
                else:
                    targets.append(rv.name)
        return targets
