from __future__ import annotations

import argparse
import logging

from typing import List, Optional, Dict, Any, Union, TypeVar

import param
import panel as pn
from datetime import datetime
from copy import deepcopy

from bencher.variables.sweep_base import hash_sha1, describe_variable
from bencher.variables.time import TimeSnapshot, TimeEvent
from bencher.variables.results import OptDir
from bencher.job import Executors
from bencher.results.laxtex_result import to_latex

T = TypeVar("T")  # Generic type variable


class BenchPlotSrvCfg(param.Parameterized):
    """Configuration for the benchmarking plot server.

    This class defines parameters for controlling how the benchmark visualization
    server operates, including network configuration.

    Attributes:
        port (int): The port to launch panel with
        allow_ws_origin (bool): Add the port to the whitelist (warning will disable remote
                               access if set to true)
        show (bool): Open the served page in a web browser
    """

    port: Optional[int] = param.Integer(None, doc="The port to launch panel with")
    allow_ws_origin: bool = param.Boolean(
        False,
        doc="Add the port to the whitelist, (warning will disable remote access if set to true)",
    )
    show: bool = param.Boolean(True, doc="Open the served page in a web browser")


class BenchRunCfg(BenchPlotSrvCfg):
    """Configuration class for benchmark execution parameters.

    This class extends BenchPlotSrvCfg to provide comprehensive control over benchmark execution,
    including caching behavior, reporting options, visualization settings, and execution strategy.
    It defines numerous parameters that control how benchmark runs are performed, cached,
    and displayed to the user.

    Attributes:
        repeats (int): The number of times to sample the inputs
        over_time (bool): If true each time the function is called it will plot a
                         timeseries of historical and the latest result
        use_optuna (bool): Show optuna plots
        summarise_constant_inputs (bool): Print the inputs that are kept constant
                                         when describing the sweep parameters
        print_bench_inputs (bool): Print the inputs to the benchmark function
                                  every time it is called
        print_bench_results (bool): Print the results of the benchmark function
                                   every time it is called
        clear_history (bool): Clear historical results
        print_pandas (bool): Print a pandas summary of the results to the console
        print_xarray (bool): Print an xarray summary of the results to the console
        serve_pandas (bool): Serve a pandas summary on the results webpage
        serve_pandas_flat (bool): Serve a flattened pandas summary on the results webpage
        serve_xarray (bool): Serve an xarray summary on the results webpage
        auto_plot (bool): Automatically deduce the best type of plot for the results
        raise_duplicate_exception (bool): Used to debug unique plot names
        cache_results (bool): Benchmark level cache for completed benchmark results
        clear_cache (bool): Clear the cache of saved input->output mappings
        cache_samples (bool): Enable per-sample caching
        only_hash_tag (bool): Use only the tag hash for cache identification
        clear_sample_cache (bool): Clear the per-sample cache
        overwrite_sample_cache (bool): Recalculate and overwrite cached sample values
        only_plot (bool): Do not calculate benchmarks if no results are found in cache
        use_holoview (bool): Use holoview for plotting
        nightly (bool): Run a more extensive set of tests for a nightly benchmark
        time_event (str): String representation of a sequence over time
        headless (bool): Run the benchmarks headlessly
        render_plotly (bool): Controls plotly rendering behavior with bokeh
        level (int): Method of defining the number of samples to sweep over
        run_tag (str): Tag for isolating cached results
        run_date (datetime): Date the benchmark run was performed
        executor (Executors): Executor for running the benchmark
        plot_size (int): Sets both width and height of the plot
        plot_width (int): Sets width of the plots
        plot_height (int): Sets height of the plot
    """

    repeats: int = param.Integer(1, doc="The number of times to sample the inputs")

    over_time: bool = param.Boolean(
        False,
        doc="If true each time the function is called it will plot a timeseries of historical and the latest result.",
    )

    use_optuna: bool = param.Boolean(False, doc="show optuna plots")

    summarise_constant_inputs: bool = param.Boolean(
        True, doc="Print the inputs that are kept constant when describing the sweep parameters"
    )

    print_bench_inputs: bool = param.Boolean(
        True, doc="Print the inputs to the benchmark function every time it is called"
    )

    print_bench_results: bool = param.Boolean(
        True, doc="Print the results of the benchmark function every time it is called"
    )

    clear_history: bool = param.Boolean(False, doc="Clear historical results")

    print_pandas: bool = param.Boolean(
        False, doc="Print a pandas summary of the results to the console."
    )

    print_xarray: bool = param.Boolean(
        False, doc="Print an xarray summary of the results to the console"
    )

    serve_pandas: bool = param.Boolean(
        False,
        doc="Serve a pandas summary on the results webpage.  If you have a large dataset consider setting this to false if the page loading is slow",
    )

    serve_pandas_flat: bool = param.Boolean(
        True,
        doc="Serve a flattened pandas summary on the results webpage.  If you have a large dataset consider setting this to false if the page loading is slow",
    )

    serve_xarray: bool = param.Boolean(
        False,
        doc="Serve an xarray summary on the results webpage. If you have a large dataset consider setting this to false if the page loading is slow",
    )

    auto_plot: bool = param.Boolean(
        True, doc=" Automatically dedeuce the best type of plot for the results."
    )

    raise_duplicate_exception: bool = param.Boolean(False, doc=" Used to debug unique plot names.")

    cache_results: bool = param.Boolean(
        False,
        doc="This is a benchmark level cache that stores the results of a fully completed benchmark. At the end of a benchmark the values are added to the cache but are not if the benchmark does not complete.  If you want to cache values during the benchmark you need to use the cache_samples option. Beware that depending on how you change code in the objective function, the cache could provide values that are not correct.",
    )

    clear_cache: bool = param.Boolean(
        False, doc=" Clear the cache of saved input->output mappings."
    )

    cache_samples: bool = param.Boolean(
        False,
        doc="If true, every time the benchmark function is called, bencher will check if that value has been calculated before and if so load the from the cache.  Note that the sample level cache is different from the benchmark level cache which only caches the aggregate of all the results at the end of the benchmark. This cache lets you stop a benchmark halfway through and continue. However, beware that depending on how you change code in the objective function, the cache could provide values that are not correct.",
    )

    only_hash_tag: bool = param.Boolean(
        False,
        doc="By default when checking if a sample has been calculated before it includes the hash of the greater benchmarking context.  This is safer because it means that data generated from one benchmark will not affect data from another benchmark.  However, if you are careful it can be more flexible to ignore which benchmark generated the data and only use the tag hash to check if that data has been calculated before. ie, you can create two benchmarks that sample a subset of the problem during exploration and give them the same tag, and then afterwards create a larger benchmark that covers the cases you already explored.  If this value is true, the combined benchmark will use any data from other benchmarks with the same tag.",
    )

    clear_sample_cache: bool = param.Boolean(
        False,
        doc="Clears the per-sample cache.  Use this if you get unexpected behavior.  The per_sample cache is tagged by the specific benchmark it was sampled from. So clearing the cache of one benchmark will not clear the cache of other benchmarks.",
    )

    overwrite_sample_cache: bool = param.Boolean(
        False,
        doc="If True, recalculate the value and overwrite the value stored in the sample cache",
    )

    only_plot: bool = param.Boolean(
        False, doc="Do not attempt to calculate benchmarks if no results are found in the cache"
    )

    use_holoview: bool = param.Boolean(False, doc="Use holoview for plotting")

    nightly: bool = param.Boolean(
        False, doc="Run a more extensive set of tests for a nightly benchmark"
    )

    time_event: Optional[str] = param.String(
        None,
        doc="A string representation of a sequence over time, i.e. datetime, pull request number, or run number",
    )

    headless: bool = param.Boolean(False, doc="Run the benchmarks headlessly")

    render_plotly: bool = param.Boolean(
        True,
        doc="Plotly and Bokeh don't play nicely together, so by default pre-render plotly figures to a non dynamic version so that bokeh plots correctly.  If you want interactive 3D graphs, set this to true but be aware that your 2D interactive graphs will probably stop working.",
    )

    level: int = param.Integer(
        default=0,
        bounds=[0, 12],
        doc="The level parameter is a method of defining the number samples to sweep over in a variable agnostic way, i.e you don't need to specify the number of samples for each variable as they are calculated dynamically from the sampling level.  See example_level.py for more information.",
    )

    run_tag: str = param.String(
        default="",
        doc="Define a tag for a run to isolate the results stored in the cache from other runs",
    )

    run_date: datetime = param.Date(
        default=datetime.now(),
        doc="The date the bench run was performed",
    )

    # parallel = param.Boolean(
    #     default=False,
    #     doc="Run the sweep in parallel.  Warning! You need to make sure your code is threadsafe before using this option",
    # )

    executor = param.Selector(
        objects=list(Executors),
        doc="The function can be run serially or in parallel with different futures executors",
    )

    plot_size: Optional[int] = param.Integer(
        default=None, doc="Sets the width and height of the plot"
    )
    plot_width: Optional[int] = param.Integer(
        default=None,
        doc="Sets with width of the plots, this will override the plot_size parameter",
    )
    plot_height: Optional[int] = param.Integer(
        default=None, doc="Sets the height of the plot, this will override the plot_size parameter"
    )

    @staticmethod
    def from_cmd_line() -> BenchRunCfg:  # pragma: no cover
        """Create a BenchRunCfg by parsing command line arguments.

        Parses command line arguments to create a configuration for benchmark runs.

        Returns:
            BenchRunCfg: Configuration object with settings from command line arguments
        """

        parser = argparse.ArgumentParser(description="benchmark")

        parser.add_argument(
            "--use-cache",
            action="store_true",
            help=BenchRunCfg.param.cache_results.doc,
        )

        parser.add_argument(
            "--only-plot",
            action="store_true",
            help=BenchRunCfg.param.only_plot.doc,
        )

        parser.add_argument(
            "--port",
            type=int,
            help=BenchRunCfg.param.port.doc,
        )

        parser.add_argument(
            "--nightly",
            action="store_true",
            help="Turn on nightly benchmarking",
        )

        parser.add_argument(
            "--time_event",
            type=str,
            default=BenchRunCfg.param.time_event.default,
            help=BenchRunCfg.param.time_event.doc,
        )

        parser.add_argument(
            "--repeats",
            type=int,
            default=BenchRunCfg.param.repeats.default,
            help=BenchRunCfg.param.repeats.doc,
        )

        return BenchRunCfg(**vars(parser.parse_args()))

    def deep(self):
        return deepcopy(self)


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
        input_vars (List): A list of ParameterizedSweep variables to perform a parameter sweep over
        result_vars (List): A list of ParameterizedSweep results to collect and plot
        const_vars (List): Variables to keep constant but are different from the default value
        result_hmaps (List): A list of holomap results
        meta_vars (List): Meta variables such as recording time and repeat id
        all_vars (List): Stores a list of both the input_vars and meta_vars
        iv_time (List[TimeSnapshot | TimeEvent]): Parameter for sampling the same inputs over time
        iv_time_event (List[TimeEvent]): Parameter for sampling inputs over time as a discrete type
        over_time (bool): Controls whether the function is sampled over time
        name (str): The name of the benchmarkCfg
        title (str): The title of the benchmark
        raise_duplicate_exception (bool): Used for debugging filename generation uniqueness
        bench_name (str): The name of the benchmark and save folder
        description (str): A longer description of the benchmark function
        post_description (str): Comments on the output of the graphs
        has_results (bool): Whether this config has results
        pass_repeat (bool): Whether to pass the 'repeat' kwarg to the benchmark function
        tag (str): Tags for grouping different benchmarks
        hash_value (str): Stored hash value of the config
        plot_callbacks (List): Callables that take a BenchResult and return panel representation
    """

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
        doc="Stores a list of both the input_vars and meta_vars that are used to define a unique hash for the input",
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

    over_time: bool = param.Boolean(
        False, doc="A parameter to control whether the function is sampled over time"
    )
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
            repeats_hash = hash_sha1(self.repeats)
        else:
            repeats_hash = 0

        hash_val = hash_sha1(
            (
                hash_sha1(str(self.bench_name)),
                hash_sha1(str(self.title)),
                hash_sha1(self.over_time),
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

        if self.const_vars and (self.summarise_constant_inputs):
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
        if self.level is not None:
            benchmark_sampling_str.append(f"    bench level: {self.level}")
        benchmark_sampling_str.append(f"    cache_results: {self.cache_results}")
        benchmark_sampling_str.append(f"    cache_samples {self.cache_samples}")
        benchmark_sampling_str.append(f"    only_hash_tag: {self.only_hash_tag}")
        benchmark_sampling_str.append(f"    executor: {self.executor}")

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


class DimsCfg:
    """A class to store data about the sampling and result dimensions.

    This class processes a BenchCfg object to extract and organize information about
    the dimensions of the benchmark, including names, ranges, sizes, and coordinates.
    It is used to set up the structure for analyzing and visualizing benchmark results.

    Attributes:
        dims_name (List[str]): Names of the benchmark dimensions
        dim_ranges (List[List[Any]]): Values for each dimension
        dims_size (List[int]): Size (number of values) for each dimension
        dim_ranges_index (List[List[int]]): Indices for each dimension value
        dim_ranges_str (List[str]): String representation of dimension ranges
        coords (Dict[str, List[Any]]): Mapping of dimension names to their values
    """

    def __init__(self, bench_cfg: BenchCfg) -> None:
        """Initialize the DimsCfg with dimension information from a benchmark configuration.

        Extracts dimension names, ranges, sizes, and coordinates from the provided benchmark
        configuration for use in organizing and analyzing benchmark results.

        Args:
            bench_cfg (BenchCfg): The benchmark configuration containing dimension information
        """
        self.dims_name: List[str] = [i.name for i in bench_cfg.all_vars]

        self.dim_ranges: List[List[Any]] = []
        self.dim_ranges = [i.values() for i in bench_cfg.all_vars]
        self.dims_size: List[int] = [len(p) for p in self.dim_ranges]
        self.dim_ranges_index: List[List[int]] = [list(range(i)) for i in self.dims_size]
        self.dim_ranges_str: List[str] = [f"{s}\n" for s in self.dim_ranges]
        self.coords: Dict[str, List[Any]] = dict(zip(self.dims_name, self.dim_ranges))

        logging.debug(f"dims_name: {self.dims_name}")
        logging.debug(f"dim_ranges {self.dim_ranges_str}")
        logging.debug(f"dim_ranges_index {self.dim_ranges_index}")
        logging.debug(f"coords: {self.coords}")
