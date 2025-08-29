from typing import Protocol, Callable, List
import logging
import warnings
from bencher.bench_cfg import BenchRunCfg, BenchCfg
from bencher.variables.parametrised_sweep import ParametrizedSweep
from bencher.bencher import Bench
from bencher.bench_report import BenchReport, GithubPagesCfg

from copy import deepcopy


class Benchable(Protocol):
    def bench(self, run_cfg: BenchRunCfg, report: BenchReport) -> BenchCfg:
        raise NotImplementedError


class ParametrizedSweepProvider(Protocol):
    def get_parametrized_sweep(self) -> ParametrizedSweep:
        """Return the ParametrizedSweep instance to be benchmarked."""
        raise NotImplementedError


class ReusableParametrizedSweep:
    """A wrapper that provides a ParametrizedSweep for reuse in benchmarking.

    This class implements the ParametrizedSweepProvider protocol and simply
    returns the wrapped ParametrizedSweep instance. It can be extended to
    add caching, modification, or other reuse patterns.
    """

    def __init__(self, parametrized_sweep: ParametrizedSweep):
        """Initialize with a ParametrizedSweep to be reused.

        Args:
            parametrized_sweep (ParametrizedSweep): The sweep instance to wrap and reuse
        """
        self._parametrized_sweep = parametrized_sweep

    def get_parametrized_sweep(self) -> ParametrizedSweep:
        """Return the wrapped ParametrizedSweep instance.

        Returns:
            ParametrizedSweep: The wrapped sweep instance
        """
        return self._parametrized_sweep


class BenchRunner:
    """A class to manage running multiple benchmarks in groups, or running the same benchmark but at multiple resolutions.

    BenchRunner provides a framework for organizing, configuring, and executing multiple
    benchmark runs with different parameters. It supports progressive refinement of benchmark
    resolution, caching of results, and publication of results to various formats.
    """

    def __init__(
        self,
        name: str | Benchable | ParametrizedSweep | ParametrizedSweepProvider = None,
        bench_class: ParametrizedSweep = None,
        run_cfg: BenchRunCfg = BenchRunCfg(),
        publisher: Callable = None,
    ) -> None:
        """Initialize a BenchRunner instance.

        Args:
            name (str | Benchable | ParametrizedSweep | ParametrizedSweepProvider, optional): The name of the benchmark runner,
                a Benchable object to add, a ParametrizedSweep class to add, or a ParametrizedSweepProvider.
                If None, auto-generates a name. Used for reports and caching. Defaults to None.
            bench_class (ParametrizedSweep, optional): An initial benchmark class to add. Defaults to None.
            run_cfg (BenchRunCfg, optional): Configuration for benchmark execution. Defaults to BenchRunCfg().
            publisher (Callable, optional): Function to publish results. Defaults to None.
        """
        self.bench_fns = []

        # Handle name parameter - can be None, string, Benchable, ParametrizedSweep, or ParametrizedSweepProvider
        if name is None:
            self.name = self._generate_name()
        elif isinstance(name, str):
            self.name = name
        elif isinstance(name, ParametrizedSweep):
            # It's a ParametrizedSweep, so shift parameters
            self.name = self._generate_name()
            bench_class = name
        elif hasattr(name, "get_parametrized_sweep"):
            # It's a ParametrizedSweepProvider
            self.name = self._generate_name()
            bench_class = name.get_parametrized_sweep()
        elif hasattr(name, "bench"):
            # It's a Benchable object
            self.name = self._generate_name()
            self.add_run(name)
        else:
            # Fallback - treat as name
            self.name = str(name)
        self.run_cfg = BenchRunner.setup_run_cfg(run_cfg)
        self.publisher = publisher
        if bench_class is not None:
            self.add_bench(bench_class)
        self.results = []
        self.servers = []

    def _generate_name(self) -> str:
        """Generate an auto name for the benchmark runner."""
        import time
        import hashlib
        import random

        # Create a unique name based on timestamp, object id, and random value
        timestamp = int(time.time() * 1000000)  # microseconds for more precision
        obj_id = id(self)
        random_val = random.randint(0, 999999)
        combined = f"bench_runner_{timestamp}_{obj_id}_{random_val}"

        # Create a short hash for a cleaner name
        hash_obj = hashlib.md5(combined.encode())
        short_hash = hash_obj.hexdigest()[:8]

        return f"bench_runner_{short_hash}"

    @staticmethod
    def setup_run_cfg(
        run_cfg: BenchRunCfg = BenchRunCfg(), level: int = 2, cache_results: bool = True
    ) -> BenchRunCfg:
        """Configure benchmark run settings with reasonable defaults.

        Creates a copy of the provided configuration with the specified level and
        caching behavior settings applied.

        Args:
            run_cfg (BenchRunCfg, optional): Base configuration to modify. Defaults to BenchRunCfg().
            level (int, optional): Benchmark sampling resolution level. Defaults to 2.
            cache_results (bool, optional): Whether to enable result caching. Defaults to True.

        Returns:
            BenchRunCfg: A new configuration object with the specified settings
        """
        run_cfg_out = deepcopy(run_cfg)
        run_cfg_out.cache_samples = cache_results
        run_cfg_out.only_hash_tag = cache_results
        run_cfg_out.level = level
        return run_cfg_out

    @staticmethod
    def from_parametrized_sweep(
        class_instance: ParametrizedSweep,
        run_cfg: BenchRunCfg = BenchRunCfg(),
        report: BenchReport = BenchReport(),
    ) -> Bench:
        """Create a Bench instance from a ParametrizedSweep class.

        Args:
            class_instance (ParametrizedSweep): The parametrized sweep class instance to benchmark
            run_cfg (BenchRunCfg, optional): Configuration for benchmark execution. Defaults to BenchRunCfg().
            report (BenchReport, optional): Report to store benchmark results. Defaults to BenchReport().

        Returns:
            Bench: A configured Bench instance ready to run the benchmark
        """
        return Bench(
            f"bench_{class_instance.name}",
            class_instance,
            run_cfg=run_cfg,
            report=report,
        )

    def add(self, bench_fn: Benchable) -> "BenchRunner":
        """Add a benchmark function to be executed by this runner.

        Args:
            bench_fn (Benchable): A callable that implements the Benchable protocol

        Returns:
            BenchRunner: Self for method chaining
        """
        self.add_run(bench_fn)
        return self

    def add_run(self, bench_fn: Benchable) -> "BenchRunner":
        """Add a benchmark function to be executed by this runner.

        Args:
            bench_fn (Benchable): A callable that implements the Benchable protocol

        Returns:
            BenchRunner: Self for method chaining
        """
        self.bench_fns.append(bench_fn)
        return self

    def add_bench(self, class_instance: ParametrizedSweep) -> "BenchRunner":
        """Add a parametrized sweep class instance as a benchmark.

        Creates and adds a function that will create a Bench instance from the
        provided parametrized sweep class when executed.

        Args:
            class_instance (ParametrizedSweep): The parametrized sweep to benchmark

        Returns:
            BenchRunner: Self for method chaining
        """

        def cb(run_cfg: BenchRunCfg, report: BenchReport) -> BenchCfg:
            bench = BenchRunner.from_parametrized_sweep(
                class_instance, run_cfg=run_cfg, report=report
            )
            return bench.plot_sweep(f"bench_{class_instance.name}")

        self.add_run(cb)
        return self

    def run(
        self,
        # New unified parameters (level and repeats are starting values)
        level: int = 2,
        repeats: int = 1,
        max_level: int = None,
        max_repeats: int = None,
        # Modern simple sampling strategy
        sampling=None,
        # Simple sampling strategy (autocomplete-friendly!)
        # Legacy parameters for backward compatibility (deprecated)
        min_level: int = None,
        start_repeats: int = None,
        # Other parameters
        input_vars: List = None,
        result_vars: List = None,
        const_vars: List = None,
        title: str = None,
        description: str = None,
        # Execution parameters
        run_cfg: BenchRunCfg = None,
        publish: bool = False,
        debug: bool = False,
        show: bool = False,
        save: bool = False,
        grouped: bool = True,
        cache_results: bool = True,
    ) -> List[BenchCfg]:
        """Unified interface for running benchmarks with flexible sampling strategies.

        This function provides a single entry point for all types of benchmark runs:
        - Single runs: Use level and repeats parameters only
        - Progressive sampling: Set max_level and/or max_repeats for automatic progression
        - Expressive strategies: Use sampling parameter with composable strategies
        - Simple strategies: Use simple_sampling parameter with autocomplete-friendly enums

        Args:
            # Primary parameters (starting values)
            level (int): Starting sampling level. Defaults to 2.
            repeats (int): Starting number of repeats. Defaults to 1.
            max_level (int, optional): Maximum level for progression. If None, uses single level.
            max_repeats (int, optional): Maximum repeats for progression. If None, uses single repeat count.

            # Legacy parameters (deprecated - use level/max_level instead)
            min_level (int, optional): DEPRECATED - use 'level' parameter instead.
            start_repeats (int, optional): DEPRECATED - use 'repeats' parameter instead.

            input_vars (List, optional): Input variables for the benchmark sweep.
            result_vars (List, optional): Result variables to collect.
            const_vars (List, optional): Variables to keep constant.
            title (str, optional): Title for the benchmark.
            description (str, optional): Description for the benchmark.

            # Execution parameters
            run_cfg (BenchRunCfg, optional): Benchmark run configuration.
            publish (bool, optional): Publish results. Defaults to False.
            debug (bool, optional): Enable debug output. Defaults to False.
            show (bool, optional): Show results in browser. Defaults to False.
            save (bool, optional): Save results to disk. Defaults to False.
            grouped (bool, optional): Group results in single page. Defaults to True.
            cache_results (bool, optional): Use sample cache. Defaults to True.

        Returns:
            List[BenchCfg]: A list of benchmark configuration objects with results
        """
        # Handle deprecation warnings for legacy parameters
        if min_level is not None:
            warnings.warn(
                "min_level parameter is deprecated. Use 'level' parameter instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            if level == 2:  # Only override if level is still default
                level = min_level

        if start_repeats is not None:
            warnings.warn(
                "start_repeats parameter is deprecated. Use 'repeats' parameter instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            if repeats == 1:  # Only override if repeats is still default
                repeats = start_repeats

        if run_cfg is None:
            run_cfg = deepcopy(self.run_cfg)
        run_cfg = BenchRunner.setup_run_cfg(run_cfg, cache_results=cache_results)

        # Execute benchmark with each configuration
        for config_idx, sample_cfg in enumerate(sampling_configs):
            if grouped:
                report_level = BenchReport(f"{sample_cfg.run_tag}_{self.name}")

            # Check if config specifies which benchmark to run (for simple_sampling strategies that include benchmark ordering)
            if hasattr(sample_cfg, "_benchmark_idx"):
                # Config specifies which benchmark to run
                bch_fn = self.bench_fns[sample_cfg._benchmark_idx]  # pylint: disable=protected-access
                bench_functions = [bch_fn]
            else:
                # Run all benchmark functions (legacy behavior)
                bench_functions = self.bench_fns

            for bch_fn in bench_functions:
                logging.info(
                    f"Running {bch_fn} at level: {sample_cfg.level} with repeats: {sample_cfg.repeats} (config {config_idx + 1}/{len(sampling_configs)})"
                )

                if grouped:
                    if hasattr(bch_fn, "__code__") and len(bch_fn.__code__.co_varnames) > 2:
                        # Enhanced benchmark function that can accept additional parameters
                        res = self._run_enhanced_benchmark(
                            bch_fn,
                            sample_cfg,
                            report_level,
                            input_vars,
                            result_vars,
                            const_vars,
                            title,
                            description,
                        )
                    else:
                        # Legacy benchmark function
                        res = bch_fn(sample_cfg, report_level)
                else:
                    if hasattr(bch_fn, "__code__") and len(bch_fn.__code__.co_varnames) > 2:
                        report = BenchReport()
                        res = self._run_enhanced_benchmark(
                            bch_fn,
                            sample_cfg,
                            report,
                            input_vars,
                            result_vars,
                            const_vars,
                            title,
                            description,
                        )
                        res.report.bench_name = (
                            f"{res.report.bench_name}_{bch_fn.__name__}_{sample_cfg.run_tag}"
                        )
                    else:
                        res = bch_fn(sample_cfg, BenchReport())
                        res.report.bench_name = (
                            f"{res.report.bench_name}_{bch_fn.__name__}_{sample_cfg.run_tag}"
                        )
                    self.show_publish(res.report, show, publish, save, debug)

                self.results.append(res)

            if grouped:
                self.show_publish(report_level, show, publish, save, debug)

        return self.results

    def show_publish(
        self, report: BenchReport, show: bool, publish: bool, save: bool, debug: bool
    ) -> None:
        """Handle publishing, saving, and displaying of a benchmark report.

        Args:
            report (BenchReport): The benchmark report to process
            show (bool): Whether to display the report in a browser
            publish (bool): Whether to publish the report
            save (bool): Whether to save the report to disk
            debug (bool): Whether to enable debug mode for publishing
        """
        if save:
            report.save(
                directory="reports", filename=f"{report.bench_name}.html", in_html_folder=False
            )
        if publish and self.publisher is not None:
            if isinstance(self.publisher, GithubPagesCfg):
                p = self.publisher
                report.publish_gh_pages(p.github_user, p.repo_name, p.folder_name, p.branch_name)
            else:
                report.publish(remote_callback=self.publisher, debug=debug)
        if show:
            self.servers.append(report.show(self.run_cfg))

    def show(
        self,
        report: BenchReport = None,
        show: bool = True,
        publish: bool = False,
        save: bool = False,
        debug: bool = False,
    ) -> None:
        """Display or publish a specific benchmark report.

        This is a convenience method to show, publish, or save a specific report.
        If no report is provided, it will use the most recent result.

        Args:
            report (BenchReport, optional): The report to process. Defaults to None (most recent).
            show (bool, optional): Whether to display in browser. Defaults to True.
            publish (bool, optional): Whether to publish the report. Defaults to False.
            save (bool, optional): Whether to save to disk. Defaults to False.
            debug (bool, optional): Enable debug mode for publishing. Defaults to False.

        Raises:
            RuntimeError: If no report is specified and no results are available
        """
        if report is None:
            if len(self.results) > 0:
                report = self.results[-1].report
            else:
                raise RuntimeError("no reports to show")
        self.show_publish(report=report, show=show, publish=publish, save=save, debug=debug)

    def shutdown(self) -> None:
        """Stop all running panel servers launched by this benchmark runner.

        This method ensures that any web servers started to display benchmark results
        are properly shut down.
        """
        while self.servers:
            self.servers.pop().stop()

    def _run_enhanced_benchmark(
        self,
        bch_fn: Callable,
        run_cfg: BenchRunCfg,
        report: BenchReport,
        input_vars: List = None,
        result_vars: List = None,
        const_vars: List = None,
        title: str = None,
        description: str = None,
    ) -> BenchCfg:
        """Run benchmark function with enhanced parameters."""
        try:
            # Try to call with enhanced signature
            return bch_fn(run_cfg, report, input_vars, result_vars, const_vars, title, description)
        except TypeError:
            # Fall back to legacy signature
            return bch_fn(run_cfg, report)

    def __del__(self) -> None:
        """Destructor that ensures proper cleanup of resources.

        Automatically calls shutdown() to stop any running servers when the
        BenchRunner instance is garbage collected.
        """
        self.shutdown()

    @staticmethod
    def create_enhanced_benchmark(
        benchmark_fn: Callable,
        input_vars: List = None,
        result_vars: List = None,
        const_vars: List = None,
        title: str = None,
        description: str = None,
    ) -> Callable:
        """Create an enhanced benchmark function with predefined parameters.

        Args:
            benchmark_fn: Base benchmark function
            input_vars: Default input variables
            result_vars: Default result variables
            const_vars: Default constant variables
            title: Default title
            description: Default description

        Returns:
            Enhanced benchmark function that accepts additional parameters
        """

        def enhanced_benchmark(
            run_cfg: BenchRunCfg,
            report: BenchReport,
            override_input_vars: List = None,
            override_result_vars: List = None,
            override_const_vars: List = None,
            override_title: str = None,
            override_description: str = None,
        ) -> BenchCfg:
            # Use overrides if provided, otherwise use defaults
            final_input_vars = (
                override_input_vars if override_input_vars is not None else input_vars
            )
            final_result_vars = (
                override_result_vars if override_result_vars is not None else result_vars
            )
            final_const_vars = (
                override_const_vars if override_const_vars is not None else const_vars
            )
            final_title = override_title if override_title is not None else title
            final_description = (
                override_description if override_description is not None else description
            )

            # Create Bench instance and run sweep
            if hasattr(benchmark_fn, "worker_class_instance"):
                # Direct Bench instance
                bench = benchmark_fn
            else:
                # Create Bench from function
                bench_name = final_title or benchmark_fn.__name__
                bench = Bench(bench_name, benchmark_fn, run_cfg=run_cfg, report=report)

            return bench.plot_sweep(
                input_vars=final_input_vars,
                result_vars=final_result_vars,
                const_vars=final_const_vars,
                title=final_title,
                description=final_description,
                run_cfg=run_cfg,
            )

        return enhanced_benchmark
