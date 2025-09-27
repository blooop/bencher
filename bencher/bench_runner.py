from typing import Protocol, Callable, List, Union, runtime_checkable
from functools import partial
import logging
import warnings
from datetime import datetime
from bencher.bench_cfg import BenchRunCfg, BenchCfg
from bencher.variables.parametrised_sweep import ParametrizedSweep
from bencher.bencher import Bench
from bencher.bench_report import BenchReport, GithubPagesCfg
from copy import deepcopy
import inspect


@runtime_checkable
class BenchableV1(Protocol):
    """Legacy two-argument bench callable: bench(run_cfg, report)."""

    def __call__(
        self, run_cfg: BenchRunCfg, report: BenchReport
    ) -> BenchCfg:  # pragma: no cover - typing only
        ...


@runtime_checkable
class BenchableV2(Protocol):
    """New one-argument bench callable: bench(run_cfg)."""

    def __call__(self, run_cfg: BenchRunCfg) -> BenchCfg:  # pragma: no cover - typing only
        ...


# Accept both versions during transition
Benchable = Union[BenchableV1, BenchableV2]


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
        self.bench_fns: List[Benchable] = []

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
        self._legacy_warning_emitted: set = set()

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
                shared_report = None
                if grouped and self.bench_fns:
                    shared_name = (
                        f"{run_cfg.run_tag}_{self.name}"
                        if run_cfg.run_tag
                        else f"{self.name}_grouped"
                    )
                    shared_report = BenchReport(shared_name)

                for bench_fn in self.bench_fns:
                    adapter, func_name = self._normalize_bench(bench_fn)
                    run_lvl = deepcopy(run_cfg)
                    run_lvl.level = lvl
                    run_lvl.repeats = r
                    logging.info(
                        "Running %s at level: %s with repeats:%s",
                        func_name,
                        lvl,
                        r,
                    )

                    result, report = adapter(run_lvl)
                    self._finalise_names(result, report, func_name, run_lvl)
                    self.results.append(result)

                    if shared_report is not None:
                        self._merge_reports(shared_report, report)
                    elif report is not None:
                        self.show_publish(report, show, publish, save, debug)

                if shared_report is not None:
                    self.show_publish(shared_report, show, publish, save, debug)
        return self.results

    def _normalize_bench(
        self, bench_fn: Benchable
    ) -> tuple[Callable[[BenchRunCfg], tuple[BenchCfg, BenchReport]], str]:
        arity = self._determine_arity(bench_fn)
        func_name = self._resolve_name(bench_fn)

        if arity >= 2 and bench_fn not in self._legacy_warning_emitted:
            warnings.warn(
                (
                    "Benchable callables that accept (run_cfg, report) are deprecated and will "
                    "be removed in a future release. Update to a single-argument signature: "
                    "bench(run_cfg)."
                ),
                DeprecationWarning,
                stacklevel=3,
            )
            self._legacy_warning_emitted.add(bench_fn)

        if arity >= 2:

            def legacy_adapter(run_cfg: BenchRunCfg, fn=bench_fn, name=func_name):
                report = BenchReport(name)
                bound = partial(fn, report=report)
                result = bound(run_cfg)
                ensured_report = self._ensure_report(result, name, fallback=report)
                return result, ensured_report

            return legacy_adapter, func_name

        def modern_adapter(run_cfg: BenchRunCfg, fn=bench_fn, name=func_name):
            result = fn(run_cfg)
            report = self._ensure_report(result, name)
            return result, report

        return modern_adapter, func_name

    @staticmethod
    def _determine_arity(fn: Benchable) -> int:
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            return 2

        pos_params = [
            p
            for p in sig.parameters.values()
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]
        return len(pos_params)

    @staticmethod
    def _resolve_name(fn: Benchable) -> str:
        func_name = getattr(fn, "__name__", None)
        if func_name is None and hasattr(fn, "func"):
            func_name = getattr(fn.func, "__name__", None)
        return func_name or "bench"

    @staticmethod
    def _ensure_report(
        result: BenchCfg,
        default_name: str,
        *,
        fallback: BenchReport | None = None,
    ) -> BenchReport:
        report = getattr(result, "report", None)
        if isinstance(report, BenchReport):
            if not report.bench_name:
                report.bench_name = default_name
            return report

        report = fallback or BenchReport(default_name)
        try:
            setattr(result, "report", report)
        except AttributeError:
            pass
        if not report.bench_name:
            report.bench_name = default_name
        return report

    @staticmethod
    def _merge_reports(dest: BenchReport | None, src: BenchReport | None) -> None:
        if dest is None or src is None or dest is src:
            return

        for pane in list(src.pane):
            dest.append_tab(pane, name=getattr(pane, "name", None))

    @staticmethod
    def _tag_suffix(run_cfg: BenchRunCfg) -> str:
        if run_cfg.run_tag:
            return f"_{run_cfg.run_tag}"
        current_date = datetime.now().strftime("%Y-%m-%d")
        return f"_{current_date}"

    @staticmethod
    def _compose_bench_name(base: str | None, func_name: str, suffix: str) -> str:
        name = base or func_name
        if func_name and not name.endswith(func_name):
            name = f"{name}_{func_name}"
        if suffix and not name.endswith(suffix):
            name = f"{name}{suffix}"
        return name

    def _finalise_names(
        self,
        result: BenchCfg,
        report: BenchReport | None,
        func_name: str,
        run_cfg: BenchRunCfg,
    ) -> None:
        suffix = self._tag_suffix(run_cfg)

        base = None
        if hasattr(result, "bench_cfg") and hasattr(result.bench_cfg, "bench_name"):
            base = result.bench_cfg.bench_name
        elif report is not None and report.bench_name:
            base = report.bench_name

        bench_name = self._compose_bench_name(base, func_name, suffix)

        if hasattr(result, "bench_cfg") and hasattr(result.bench_cfg, "bench_name"):
            result.bench_cfg.bench_name = bench_name

        if report is not None:
            report.bench_name = bench_name

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
