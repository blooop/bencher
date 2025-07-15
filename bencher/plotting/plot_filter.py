from __future__ import annotations
from typing import Optional
from dataclasses import dataclass
from bencher.plotting.plt_cnt_cfg import PltCntCfg
import logging
import panel as pn


class VarRange:
    """A VarRange represents the bounded and unbounded ranges of integers.  This class is used to define filters for various variable types.  For example by defining cat_var = VarRange(0,0), calling matches(0) will return true, but any other integer will not match.  You can also have unbounded ranges for example VarRange(2,None) will match to 2,3,4... up to infinity. for By default the lower and upper bounds are set to -1 so so that no matter what value is passed to matches() will return false.  Matches only takes 0 and positive integers."""

    def __init__(self, lower_bound: int = 0, upper_bound: int = -1) -> None:
        """
        Args:
            lower_bound (int, optional): The smallest acceptable value to matches(). Passing None will result in a lower bound of 0 (as matches only accepts positive integers). Defaults to 0.
            upper_bound (int, optional): The largest acceptable value to matches().  Passing None will result in no upper bound. Defaults to -1 which results in a range with no matches.
        """
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound

    def matches(self, val: int) -> bool:
        """Checks that a value is within the variable range.  lower_bound and upper_bound are inclusive (lower_bound<=val<=upper_bound )

        Args:
            val (int): A positive integer representing a number of items

        Returns:
            bool: True if the items is within the range, False otherwise.

        Raises:
            ValueError: If val < 0
        """
        if val < 0:
            raise ValueError("val must be >= 0")
        if self.lower_bound is not None:
            lower_match = val >= self.lower_bound
        else:
            lower_match = True

        if self.upper_bound is not None:
            upper_match = val <= self.upper_bound
        else:
            upper_match = True

        return lower_match and upper_match

    def matches_info(self, val: int, name: str) -> tuple[bool, str]:
        """Get matching info for a value with a descriptive name.

        Args:
            val (int): A positive integer to check against the range
            name (str): A descriptive name for the value being checked, used in the output string

        Returns:
            tuple[bool, str]: A tuple containing:
                - bool: True if the value matches the range, False otherwise
                - str: A formatted string describing the match result
        """
        match = self.matches(val)
        info = f"{name}\t{self.lower_bound}>= {val} <={self.upper_bound} is {match}"
        return match, info

    def __str__(self) -> str:
        return f"VarRange(lower_bound={self.lower_bound}, upper_bound={self.upper_bound})"


@dataclass
class PlotFilter:
    """A class for representing the types of results a plot is able to represent."""

    float_range: VarRange = VarRange()
    cat_range: VarRange = VarRange()
    vector_len: VarRange = VarRange(1, 1)
    result_vars: VarRange = VarRange(1, 1)
    panel_range: VarRange = VarRange(0, 0)
    repeats_range: VarRange = VarRange(1, None)
    input_range: VarRange = VarRange(1, None)

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
            (plot_filter.vector_len, plt_cnt_cfg.vector_len, "vec"),
            (plot_filter.result_vars, plt_cnt_cfg.result_vars, "results"),
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
        logging.info(self.matches_info)

    def to_panel(self, **kwargs) -> Optional[pn.pane.Markdown]:
        """Convert match information to a Panel Markdown pane if debug mode is enabled.

        Args:
            **kwargs: Additional keyword arguments to pass to the Panel Markdown constructor

        Returns:
            Optional[pn.pane.Markdown]: A Markdown pane containing match information if in debug mode,
                                        None otherwise
        """
        if self.plt_cnt_cfg.print_debug:
            return pn.pane.Markdown(self.matches_info, **kwargs)
        return None
