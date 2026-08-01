from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import assert_never

import panel as pn

from bencher.plotting.plt_cnt_cfg import PltCntCfg

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Nothing:
    """No count matches at all."""


@dataclass(frozen=True)
class _Between:
    """Every count from ``low`` to ``high`` inclusive matches."""

    low: int
    high: int

    def __post_init__(self) -> None:
        if self.low < 0:
            raise ValueError(f"low must be >= 0, got {self.low}")
        if self.high < self.low:
            raise ValueError(f"high must be >= low, got low={self.low} high={self.high}")


@dataclass(frozen=True)
class _AtLeast:
    """Every count from ``low`` upwards matches; there is no upper bound."""

    low: int

    def __post_init__(self) -> None:
        if self.low < 0:
            raise ValueError(f"low must be >= 0, got {self.low}")


_Bounds = _Nothing | _Between | _AtLeast


@dataclass(frozen=True)
class VarRange:
    """A set of acceptable counts, used to declare which sweep shapes a plot handles.

    ``matches()`` only accepts counts of 0 or more (a count of variables can never be
    negative). Build a range with one of the named constructors -- there is no
    meaningful "raw" pair of bounds, and no sentinel value standing in for
    "unbounded" or "nothing":

    * :meth:`none` -- matches no count at all.
    * :meth:`exactly` -- ``exactly(2)`` matches only 2.
    * :meth:`between` -- ``between(0, 1)`` matches 0 and 1.
    * :meth:`at_most` -- ``at_most(2)`` matches 0, 1 and 2.
    * :meth:`at_least` -- ``at_least(2)`` matches 2, 3, 4, ... with no upper limit.
    * :meth:`unbounded` -- matches every count.
    """

    bounds: _Bounds

    @classmethod
    def none(cls) -> VarRange:
        """A range that no count matches."""
        return cls(_Nothing())

    @classmethod
    def exactly(cls, count: int) -> VarRange:
        """A range matching ``count`` and nothing else."""
        return cls(_Between(count, count))

    @classmethod
    def between(cls, low: int, high: int) -> VarRange:
        """A range matching every count from ``low`` to ``high`` inclusive."""
        return cls(_Between(low, high))

    @classmethod
    def at_most(cls, high: int) -> VarRange:
        """A range matching every count from 0 to ``high`` inclusive."""
        return cls(_Between(0, high))

    @classmethod
    def at_least(cls, low: int) -> VarRange:
        """A range matching ``low`` and every larger count."""
        return cls(_AtLeast(low))

    @classmethod
    def unbounded(cls) -> VarRange:
        """A range matching every count."""
        return cls(_AtLeast(0))

    def matches(self, val: int) -> bool:
        """Check whether a count falls in this range.

        Args:
            val (int): A count of items; must be 0 or more.

        Returns:
            bool: True if the count is in the range, False otherwise.

        Raises:
            ValueError: If val < 0
        """
        if val < 0:
            raise ValueError("val must be >= 0")
        match self.bounds:
            case _Nothing():
                return False
            case _Between(low=low, high=high):
                return low <= val <= high
            case _AtLeast(low=low):
                return low <= val
            case _ as unreachable:
                assert_never(unreachable)

    def matches_info(self, val: int, name: str) -> tuple[bool, str]:
        """Get matching info for a value with a descriptive name.

        Args:
            val (int): A count of items to check against the range
            name (str): A descriptive name for the value being checked, used in the output string

        Returns:
            tuple[bool, str]: A tuple containing:
                - bool: True if the value matches the range, False otherwise
                - str: A formatted string describing the match result
        """
        match = self.matches(val)
        info = f"{name}\t{self._describe(val)} is {match}"
        return match, info

    def _describe(self, val: int) -> str:
        """Render this range around ``val`` for the human-readable match report.

        The ``lo>= val <=hi`` spelling (with ``None`` for "no upper bound") is kept
        verbatim from the pre-sum-type implementation so that debug panes and
        ``explain_selection()`` reasons read exactly as before.
        """
        match self.bounds:
            case _Nothing():
                return f"no count matches {val}"
            case _Between(low=low, high=high):
                return f"{low}>= {val} <={high}"
            case _AtLeast(low=low):
                return f"{low}>= {val} <=None"
            case _ as unreachable:
                assert_never(unreachable)

    def __str__(self) -> str:
        match self.bounds:
            case _Nothing():
                return "VarRange.none()"
            case _Between(low=low, high=high):
                if low == high:
                    return f"VarRange.exactly({low})"
                if low == 0:
                    return f"VarRange.at_most({high})"
                return f"VarRange.between({low}, {high})"
            case _AtLeast(low=low):
                if low == 0:
                    return "VarRange.unbounded()"
                return f"VarRange.at_least({low})"
            case _ as unreachable:
                assert_never(unreachable)

    def __repr__(self) -> str:
        return str(self)


@dataclass
class PlotFilter:
    """The sweep shapes a plot is able to represent.

    Every field defaults to :meth:`VarRange.unbounded`, so a default-constructed
    ``PlotFilter()`` matches every shape. Narrow only the dimensions a plot actually
    constrains; an omitted field never silently hides the plot.
    """

    float_range: VarRange = field(default_factory=VarRange.unbounded)
    cat_range: VarRange = field(default_factory=VarRange.unbounded)
    panel_range: VarRange = field(default_factory=VarRange.unbounded)
    repeats_range: VarRange = field(default_factory=VarRange.unbounded)
    input_range: VarRange = field(default_factory=VarRange.unbounded)

    def matches_result(
        self, plt_cnt_cfg: PltCntCfg, plot_name: str, override: bool
    ) -> PlotMatchesResult:
        """Checks if the result data signature matches the type of data the plot is able to display.

        Args:
            plt_cnt_cfg (PltCntCfg): Configuration containing counts of different plot elements
            plot_name (str): Name of the plot being checked
            override (bool): Whether to override filter matching rules

        Returns:
            PlotMatchesResult: Object containing match results and information
        """
        return PlotMatchesResult(self, plt_cnt_cfg, plot_name, override)


class PlotMatchesResult:
    """Stores information about which properties match the requirements of a particular plotter"""

    def __init__(
        self,
        plot_filter: PlotFilter,
        plt_cnt_cfg: PltCntCfg,
        plot_name: str,
        override: bool,
    ) -> None:
        """Initialize a PlotMatchesResult with filter matching information.

        Args:
            plot_filter (PlotFilter): The filter defining acceptable ranges for plot properties
            plt_cnt_cfg (PltCntCfg): Configuration containing counts of different plot elements
            plot_name (str): Name of the plot being checked
            override (bool): Whether to override filter matching rules
        """
        match_info: list[str] = []
        matches: list[bool] = []

        match_candidates: list[tuple[VarRange, int, str]] = [
            (plot_filter.float_range, plt_cnt_cfg.float_cnt, "float"),
            (plot_filter.cat_range, plt_cnt_cfg.cat_cnt, "cat"),
            (plot_filter.panel_range, plt_cnt_cfg.panel_cnt, "panels"),
            (plot_filter.repeats_range, plt_cnt_cfg.repeats, "repeats"),
            (plot_filter.input_range, plt_cnt_cfg.inputs_cnt, "inputs"),
        ]

        for m, cnt, name in match_candidates:
            match, info = m.matches_info(cnt, name)
            matches.append(match)
            if not match:
                match_info.append(f"\t{info}")
        if override:
            match_info.append(f"override: {override}")
            self.overall = True
        else:
            self.overall = all(matches)

        match_info.insert(0, f"plot {plot_name} matches: {self.overall}")
        self.matches_info: str = "\n".join(match_info).strip()
        self.plt_cnt_cfg: PltCntCfg = plt_cnt_cfg

        # if self.plt_cnt_cfg.print_debug:
        logger.info(self.matches_info)

    def to_panel(self, **kwargs) -> pn.pane.Markdown | None:
        """Convert match information to a Panel Markdown pane if debug mode is enabled.

        Args:
            **kwargs: Additional keyword arguments to pass to the Panel Markdown constructor

        Returns:
            pn.pane.Markdown | None: A Markdown pane containing match information if in debug mode,
                                        None otherwise
        """
        if self.plt_cnt_cfg.print_debug:
            return pn.pane.Markdown(self.matches_info, **kwargs)
        return None
