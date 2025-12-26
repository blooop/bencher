"""Configuration for the benchmarking plot server."""

from __future__ import annotations

from typing import Optional

import param


class BenchPlotSrvCfg(param.Parameterized):
    """Plot server settings: port, websocket origin, and browser launch."""

    port: Optional[int] = param.Integer(None, doc="The port to launch panel with")
    allow_ws_origin: bool = param.Boolean(
        False,
        doc="Add the port to the whitelist, (warning will disable remote access if set to true)",
    )
    show: bool = param.Boolean(True, doc="Open the served page in a web browser")
