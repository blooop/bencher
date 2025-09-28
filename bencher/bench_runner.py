from typing import Protocol, Callable, List
import logging
import warnings
from datetime import datetime
from bencher.bench_cfg import BenchRunCfg, BenchCfg
from bencher.variables.parametrised_sweep import ParametrizedSweep
from bencher.bencher import Bench
from bencher.bench_report import BenchReport, GithubPagesCfg
from copy import deepcopy


class Benchable(Protocol):
    def bench(self, run_cfg: BenchRunCfg, report: BenchReport) -> BenchCfg:
        raise NotImplementedError


class BenchRunner:
    """A class to manage running multiple benchmarks in groups, or running the same benchmark but at multiple resolutions.

    BenchRunner provides a framework for organizing, configuring, and executing multiple
    benchmark runs with different parameters. It supports progressive refinement of benchmark
    resolution, caching of results, and publication of results to various formats.
    """

    def __init__(
        self,
        name: str | Benchable = None,
        bench_class: ParametrizedSweep = None,
        run_cfg: BenchRunCfg | None = None,
        publisher: Callable = None,
        run_tag: str = None,
    ) -> None:
        """Initialize a BenchRunner instance.

        Args:
            name (str, optional): The name of the benchmark runner, used for reports and caching.
                If None, auto-generates a unique name. Defaults to None.
            bench_class (ParametrizedSweep, optional): An initial benchmark class to add. Defaults to None.
            run_cfg (BenchRunCfg, optional): Configuration for benchmark execution. Defaults to None.
            publisher (Callable, optional): Function to publish results. Defaults to None.
            run_tag (str, optional): Tag for the run, used in naming and caching. If provided,
                overrides the run_tag in run_cfg. Defaults to None.
        """
        self.bench_fns = []

        # Handle name parameter - can be None, string, or Benchable
        if name is None:
            self.name = self._generate_name()
        elif isinstance(name, str):
            self.name = name
        elif isinstance(name, Callable):
            self.name = name.__name__
            self.add_run(name)
        else:
            # Fallback - treat as name
            self.name = str(name)

        self.run_cfg = BenchRunner.setup_run_cfg(run_cfg)
        # Override run_tag if provided as parameter
        if run_tag is not None:
            self.run_cfg.run_tag = run_tag
        self.publisher = publisher
        if bench_class is not None:
            self.add_bench(bench_class)
        self.results = []
        self.servers = []

    def _generate_name(self) -> str:
        """Generate a unique name for the BenchRunner instance.

        Returns:
            str: A unique name based on timestamp, object id, and random value
        """
        import time
        import hashlib
        import random

        # Create a unique name based on timestamp, object id, and random value
        timestamp = int(time.time() * 1000)  # millisecond precision
        obj_id = id(self)
        random_val = random.randint(0, 999999)

        # Create a hash from these values
        unique_string = f"{timestamp}_{obj_id}_{random_val}"
        hash_obj = hashlib.md5(unique_string.encode())
        hash_hex = hash_obj.hexdigest()[:8]  # Use first 8 characters

        return f"bench_runner_{hash_hex}"

    @staticmethod
    def setup_run_cfg(
        run_cfg: BenchRunCfg | None = None, level: int = 2, cache_results: bool = True
    ) -> BenchRunCfg:
        """Configure benchmark run settings with reasonable defaults.

        Creates a copy of the provided configuration with the specified level and
        caching behavior settings applied.

        Args:
            run_cfg (BenchRunCfg, optional): Base configuration to modify. Defaults to None.
            level (int, optional): Benchmark sampling resolution level. Defaults to 2.
            cache_results (bool, optional): Whether to enable result caching. Defaults to True.

        Returns:
            BenchRunCfg: A new configuration object with the specified settings
        """
        run_cfg_out = BenchRunCfg() if run_cfg is None else deepcopy(run_cfg)
        run_cfg_out.cache_samples = cache_results
        run_cfg_out.only_hash_tag = cache_results
        run_cfg_out.level = level
        return run_cfg_out

    @staticmethod
    def from_parametrized_sweep(
        class_instance: ParametrizedSweep,
        run_cfg: BenchRunCfg | None = None,
        report: BenchReport | None = None,
    ) -> Bench:
        """Create a Bench instance from a ParametrizedSweep class.

        Args:
            class_instance (ParametrizedSweep): The parametrized sweep class instance to benchmark
            run_cfg (BenchRunCfg, optional): Configuration for benchmark execution. Defaults to None.
            report (BenchReport, optional): Report to store benchmark results. Defaults to None.

        Returns:
            Bench: A configured Bench instance ready to run the benchmark
        """
        if run_cfg is None:
            run_cfg = BenchRunCfg()
        if report is None:
            report = BenchReport()
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

    def add_run(self, bench_fn: Benchable) -> None:
        """Add a benchmark function to be executed by this runner.

        Args:
            bench_fn (Benchable): A callable that implements the Benchable protocol
        """
        self.bench_fns.append(bench_fn)

    def add_bench(self, class_instance: ParametrizedSweep) -> None:
        """Add a parametrized sweep class instance as a benchmark.

        Creates and adds a function that will create a Bench instance from the
        provided parametrized sweep class when executed.

        Args:
            class_instance (ParametrizedSweep): The parametrized sweep to benchmark
        """

        def cb(run_cfg: BenchRunCfg, report: BenchReport) -> BenchCfg:
            bench = BenchRunner.from_parametrized_sweep(
                class_instance, run_cfg=run_cfg, report=report
            )
            result = bench.plot_sweep(f"bench_{class_instance.name}")
            # Attach the report to the result for access later
            result.report = report
            return result

        self.add_run(cb)

    def run(
        self,
        # New unified parameters (level and repeats are starting values)
        level: int = 2,
        repeats: int = 1,
        max_level: int = None,
        max_repeats: int = None,
        # Legacy parameters for backward compatibility (deprecated)
        min_level: int = None,
        start_repeats: int = None,
        # Other parameters
        run_cfg: BenchRunCfg = None,
        publish: bool = False,
        debug: bool = False,
        show: bool = False,
        save: bool = False,
        grouped: bool = False,
        cache_results: bool = True,
    ) -> List[BenchCfg]:
        """Unified interface for running benchmarks.

        This function provides a single entry point for benchmark runs:
        - Single runs: Use level and repeats parameters only
        - Progressive runs: Set max_level and/or max_repeats for automatic progression

        Args:
            # Primary parameters (starting values)
            level (int): Starting benchmark level. Defaults to 2.
            repeats (int): Starting number of repeats. Defaults to 1.
            max_level (int, optional): Maximum level for progression. If None, uses single level.
            max_repeats (int, optional): Maximum repeats for progression. If None, uses single repeat count.

            # Legacy parameters (deprecated - use level/max_level instead)
            min_level (int, optional): DEPRECATED - use 'level' parameter instead.
            start_repeats (int, optional): DEPRECATED - use 'repeats' parameter instead.

            run_cfg (BenchRunCfg, optional): benchmark run configuration. Defaults to None.
            publish (bool, optional): Publish the results to git, requires a publish url to be set up. Defaults to False.
            debug (bool, optional): Enable debug output during publishing. Defaults to False.
            show (bool, optional): show the results in the local web browser. Defaults to False.
            save (bool, optional): save the results to disk in index.html. Defaults to False.
            grouped (bool, optional): Produce a single html page with all the benchmarks included. Defaults to False.
            cache_results (bool, optional): Use the sample cache to reused previous results. Defaults to True.

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

        # Set up level and repeat ranges
        min_level = level
        final_max_level = max_level if max_level is not None else level
        min_repeats = repeats
        final_max_repeats = max_repeats if max_repeats is not None else repeats

        for r in range(min_repeats, final_max_repeats + 1):
            for lvl in range(min_level, final_max_level + 1):
                if grouped:
                    report_level = BenchReport(f"{run_cfg.run_tag}_{self.name}")

                for bch_fn in self.bench_fns:
                    run_lvl = deepcopy(run_cfg)
                    run_lvl.level = lvl
                    run_lvl.repeats = r
                    logging.info(f"Running {bch_fn} at level: {lvl} with repeats:{r}")
                    if grouped:
                        res = bch_fn(run_lvl, report_level)
                    else:
                        individual_report = BenchReport()
                        res = bch_fn(run_lvl, individual_report)
                        if run_cfg.run_tag:
                            tag_suffix = f"_{run_cfg.run_tag}"
                        else:
                            current_date = datetime.now().strftime("%Y-%m-%d")
                            tag_suffix = f"_{current_date}"
                        # Update the report name for saving
                        if hasattr(res, "bench_cfg") and hasattr(res.bench_cfg, "bench_name"):
                            # For BenchResult objects
                            original_name = res.bench_cfg.bench_name
                            new_name = f"{original_name}_{bch_fn.__name__}{tag_suffix}"
                            res.bench_cfg.bench_name = new_name
                            individual_report.bench_name = new_name
                        elif hasattr(res, "report"):
                            # For objects with report attribute
                            original_name = res.report.bench_name
                            new_name = f"{original_name}_{bch_fn.__name__}{tag_suffix}"
                            res.report.bench_name = new_name
                            individual_report.bench_name = new_name
                        else:
                            # Fallback - use function name
                            new_name = f"{bch_fn.__name__}{tag_suffix}"
                            individual_report.bench_name = new_name
                        self.show_publish(individual_report, show, publish, save, debug)
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

    def __del__(self) -> None:
        """Destructor that ensures proper cleanup of resources.

        Automatically calls shutdown() to stop any running servers when the
        BenchRunner instance is garbage collected.
        """
        self.shutdown()
