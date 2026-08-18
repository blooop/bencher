from __future__ import annotations

import logging
from typing import Any

from bencher.bench_cfg.bench_cfg_class import BenchCfg

logger = logging.getLogger(__name__)


class DimsCfg:
    """A class to store data about the sampling and result dimensions.

    This class processes a BenchCfg object to extract and organize information about
    the dimensions of the benchmark, including names, ranges, sizes, and coordinates.
    It is used to set up the structure for analyzing and visualizing benchmark results.

    Attributes:
        dims_name (list[str]): Names of the benchmark dimensions
        dim_ranges (list[list[Any]]): Values for each dimension
        dims_size (list[int]): Size (number of values) for each dimension
        dim_ranges_index (list[list[int]]): Indices for each dimension value
        dim_ranges_str (list[str]): String representation of dimension ranges
        coords (dict[str, list[Any]]): Mapping of dimension names to their values
    """

    def __init__(self, bench_cfg: BenchCfg) -> None:
        """Initialize the DimsCfg with dimension information from a benchmark configuration.

        Extracts dimension names, ranges, sizes, and coordinates from the provided benchmark
        configuration for use in organizing and analyzing benchmark results.

        Args:
            bench_cfg (BenchCfg): The benchmark configuration containing dimension information
        """
        self.dims_name: list[str] = [i.name for i in bench_cfg.all_vars]

        self.dim_ranges: list[list[Any]] = [i.values() for i in bench_cfg.all_vars]
        self.dims_size: list[int] = [len(p) for p in self.dim_ranges]
        self.dim_ranges_index: list[list[int]] = [list(range(i)) for i in self.dims_size]
        self.dim_ranges_str: list[str] = [f"{s}\n" for s in self.dim_ranges]
        self.coords: dict[str, list[Any]] = dict(zip(self.dims_name, self.dim_ranges))

        logger.debug(f"dims_name: {self.dims_name}")
        logger.debug(f"dim_ranges {self.dim_ranges_str}")
        logger.debug(f"dim_ranges_index {self.dim_ranges_index}")
        logger.debug(f"coords: {self.coords}")
