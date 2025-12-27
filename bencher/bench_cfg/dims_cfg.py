"""Dimension info extraction from BenchCfg."""

from __future__ import annotations

import logging
from typing import List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from bencher.bench_cfg.bench_cfg_class import BenchCfg


class DimsCfg:
    """Extracts dimension names, ranges, sizes, and coordinates from a BenchCfg."""

    def __init__(self, bench_cfg: BenchCfg) -> None:
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
