"""Configuration for benchmark time and history settings."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import param


class TimeCfg(param.Parameterized):
    """Time and history: time series tracking, run tagging, and historical results."""

    over_time: bool = param.Boolean(
        False,
        doc="If true each time the function is called it will plot a timeseries of "
        "historical and the latest result.",
    )

    clear_history: bool = param.Boolean(False, doc="Clear historical results")

    time_event: Optional[str] = param.String(
        None,
        doc="A string representation of a sequence over time, i.e. datetime, pull request "
        "number, or run number",
    )

    run_tag: str = param.String(
        default="",
        doc="Define a tag for a run to isolate the results stored in the cache from other runs",
    )

    run_date: datetime = param.Date(
        default=datetime.now(),
        doc="The date the bench run was performed",
    )
