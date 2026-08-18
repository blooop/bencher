from __future__ import annotations

import argparse

import param

from bencher.history import OnHistoryReset


class TimeCfg(param.Parameterized):
    """Configuration for over-time tracking and historical results.

    See ``docs/over_time.md`` for how these parameters interact with the
    regression-detection family (:class:`RegressionCfg`).
    """

    over_time: bool = param.Boolean(
        False,
        doc="If true each time the function is called it will plot a timeseries of historical and the latest result.",
    )

    clear_history: bool = param.Boolean(False, doc="Clear historical results")

    on_history_reset: str = param.Selector(
        default=OnHistoryReset.WARN,
        objects=list(OnHistoryReset),
        doc="Policy for history-affecting schema changes detected at history-load "
        "time (a result column removed or redefined, or the whole history "
        "orphaned by an input/const change). 'warn' (default): log a WARNING "
        "naming the change and continue. 'error': raise HistoryResetError so a "
        "CI run can never silently lose a baseline; use 'warn'/'ignore' for one "
        "run (or clear_history) to acknowledge a deliberate change. 'ignore': "
        "log at DEBUG only. Retained data is never deleted by any policy — "
        "removed columns stay dormant in the stored history and resume if the "
        "variable returns with the same identity.",
    )

    max_events: int | None = param.Integer(
        None,
        bounds=(1, None),
        allow_None=True,
        doc="Maximum number of over_time events to retain. "
        "Oldest events are trimmed. Set to None for unlimited.",
    )

    max_slider_points: int | None = param.Integer(
        10,
        bounds=(2, None),
        allow_None=True,
        doc="Maximum number of time points shown in the over_time slider. "
        "Evenly subsampled (first and last always included). "
        "The aggregated tab still uses all data. "
        "Defaults to 10 to cap embed cost. Set to None for no subsampling.",
    )

    show_aggregated_tab: bool = param.Boolean(
        False,
        doc="When over_time is active, show an 'All Time Points (aggregated)' tab "
        "alongside the per-time-point slider. Defaults to False for performance. "
        "Set True to enable the aggregation view.",
    )

    show_aggregate_plots: bool = param.Boolean(
        True,
        doc="When aggregate is set on plot_sweep, show the aggregated BandResult "
        "plots in the auto-plots view. Set False to skip the aggregation "
        "computation and extra render, improving performance.",
    )

    event: str | None = param.String(
        None,
        doc="A string representation of a sequence over time, i.e. datetime, pull request number, or run number",
    )

    @classmethod
    def add_cli_args(cls, parser: argparse.ArgumentParser) -> None:
        """Register this group's command-line flags on *parser*."""
        parser.add_argument(
            "--time_event",
            type=str,
            default=cls.param.event.default,
            help=cls.param.event.doc,
        )

    @classmethod
    def apply_cli_args(cls, namespace: argparse.Namespace) -> TimeCfg:
        """Build a :class:`TimeCfg` from values parsed by :meth:`add_cli_args`."""
        return cls(event=namespace.time_event)
