from typing import Protocol, Callable, List
import logging
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
        name: str | Benchable,
        bench_class: ParametrizedSweep = None,
        run_cfg: BenchRunCfg = BenchRunCfg(),
        publisher: Callable = None,
    ) -> None:
        """Initialize a BenchRunner instance.

        Args:
            name (str): The name of the benchmark runner, used for reports and caching
            bench_class (ParametrizedSweep, optional): An initial benchmark class to add. Defaults to None.
            run_cfg (BenchRunCfg, optional): Configuration for benchmark execution. Defaults to BenchRunCfg().
            publisher (Callable, optional): Function to publish results. Defaults to None.
        """
        self.bench_fns = []
        if isinstance(name, Callable):
            self.name = name.__name__
            self.add_run(name)
        else:
            self.name = name
        self.run_cfg = BenchRunner.setup_run_cfg(run_cfg)
        self.publisher = publisher
        if bench_class is not None:
            self.add_bench(bench_class)
        self.results = []
        self.servers = []

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
            return bench.plot_sweep(f"bench_{class_instance.name}")

        self.add_run(cb)

    def run(
        self,
        min_level: int = 2,
        max_level: int = 6,
        level: int = None,
        repeats: int = 1,
        run_cfg: BenchRunCfg = None,
        publish: bool = False,
        debug: bool = False,
        show: bool = False,
        save: bool = False,
        grouped: bool = True,
        cache_results: bool = True,
    ) -> List[BenchCfg]:
        """This function controls how a benchmark or a set of benchmarks are run. If you are only running a single benchmark it can be simpler to just run it directly, but if you are running several benchmarks together and want them to be sampled at different levels of fidelity or published together in a single report this function enables that workflow.  If you have an expensive function, it can be useful to view low fidelity results as they are computed but also continue to compute higher fidelity results while reusing previously computed values. The parameters min_level and max_level let you specify how to progressivly increase the sampling resolution of the benchmark sweep. By default cache_results=True so that previous values are reused.

        Args:
            min_level (int, optional): The minimum level to start sampling at. Defaults to 2.
            max_level (int, optional): The maximum level to sample up to. Defaults to 6.
            level (int, optional): If this is set, then min_level and max_level are not used and only a single level is sampled. Defaults to None.
            repeats (int, optional): The number of times to run the entire benchmarking procedure. Defaults to 1.
            run_cfg (BenchRunCfg, optional): benchmark run configuration. Defaults to None.
            publish (bool, optional): Publish the results to git, requires a publish url to be set up. Defaults to False.
            debug (bool, optional): Enable debug output during publishing. Defaults to False.
            show (bool, optional): show the results in the local web browser. Defaults to False.
            save (bool, optional): save the results to disk in index.html. Defaults to False.
            grouped (bool, optional): Produce a single html page with all the benchmarks included. Defaults to True.
            cache_results (bool, optional): Use the sample cache to reused previous results. Defaults to True.

        Returns:
            List[BenchCfg]: A list of benchmark configuration objects with results
        """
        if run_cfg is None:
            run_cfg = deepcopy(self.run_cfg)
        run_cfg = BenchRunner.setup_run_cfg(run_cfg, cache_results=cache_results)

        if level is not None:
            min_level = level
            max_level = level
        for r in range(1, repeats + 1):
            for lvl in range(min_level, max_level + 1):
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
                        res = bch_fn(run_lvl, BenchReport())
                        res.report.bench_name = f"{run_cfg.run_tag}_{res.report.bench_name}"
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
            report.save_index()
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
