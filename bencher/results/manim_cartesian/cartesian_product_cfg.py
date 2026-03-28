"""Data model for Cartesian product animation configuration.

No manim dependency — pure Python dataclasses that bridge BenchCfg
to the animation scene.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SweepVar:
    """A single dimension of the Cartesian product.

    Attributes:
        name: Human-readable variable name (e.g. "theta", "repeat").
        values: The sampled values for this dimension.
    """

    name: str
    values: list[Any] = field(default_factory=list)


@dataclass
class CartesianProductCfg:
    """Configuration describing an N-dimensional Cartesian product sweep.

    ``all_vars`` includes every dimension — input variables *and* meta
    variables (repeat, over_time).  They are all first-class dimensions
    of the product.

    Attributes:
        all_vars: Every dimension of the Cartesian product.
        result_names: Names of the result variables being collected.
    """

    all_vars: list[SweepVar] = field(default_factory=list)
    result_names: list[str] = field(default_factory=list)

    @property
    def ndim(self) -> int:
        """Number of dimensions."""
        return len(self.all_vars)

    @property
    def shape(self) -> tuple[int, ...]:
        """Shape of the result tensor."""
        return tuple(len(v.values) for v in self.all_vars)

    @property
    def total_cells(self) -> int:
        """Total number of cells in the Cartesian product."""
        result = 1
        for s in self.shape:
            result *= s
        return result


MAX_DISPLAY_PER_DIM = 5
"""Maximum values per dimension shown in the animation grid.

Dimensions with more values are truncated to first 2, a gap marker, and
last 2 — mirroring the ``format_values_list`` approach in the LaTeX
summary.
"""


def truncate_values(values: list[Any], max_display: int = MAX_DISPLAY_PER_DIM) -> list[Any]:
    """Return a truncated value list with an ellipsis marker when needed.

    The marker ``"..."`` is inserted at index 2 when the list is too long,
    keeping the first 2 and last 2 values (same rule as the LaTeX summary).
    """
    if len(values) <= max_display:
        return list(values)
    return [values[0], values[1], "...", values[-2], values[-1]]


def from_bench_cfg(bench_cfg) -> CartesianProductCfg:
    """Build a :class:`CartesianProductCfg` from a ``BenchCfg`` instance.

    Uses ``bench_cfg.all_vars`` (input_vars + meta_vars) so that repeat
    and over_time are included as full dimensions — they are just more
    dimensions of the Cartesian product.

    This mirrors the extraction pattern in ``DimsCfg.__init__``
    (``bench_cfg.py``).
    """
    all_vars = [
        SweepVar(name=iv.name, values=truncate_values(list(iv.values())))
        for iv in bench_cfg.all_vars
    ]
    result_names = [rv.name for rv in bench_cfg.result_vars]
    return CartesianProductCfg(all_vars=all_vars, result_names=result_names)
