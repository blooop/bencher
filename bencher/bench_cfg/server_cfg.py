from __future__ import annotations

from enum import auto

import param
from strenum import LowercaseStrEnum


class ShowMode(LowercaseStrEnum):
    """Display mode for benchmark reports."""

    LIVE = auto()
    HTML = auto()
    PUBLISHED = auto()
    NONE = auto()


_SHOW_ALIASES: dict[bool | None | str, ShowMode] = {
    True: ShowMode.LIVE,
    False: ShowMode.NONE,
    None: ShowMode.NONE,
    "static": ShowMode.HTML,
}


def normalize_show(value: bool | str | ShowMode | None) -> ShowMode:
    """Normalize a ``show`` argument to a :class:`ShowMode`.

    Accepts ``True``/``False``/``None``, any :class:`ShowMode` member, or
    the corresponding string value.  Raises :class:`ValueError` for
    anything else.
    """
    try:
        v = _SHOW_ALIASES.get(value, value)
    except TypeError:
        v = value
    try:
        return ShowMode(v)
    except ValueError:
        raise ValueError(
            f"show must be one of {[m.value for m in ShowMode]} or bool, got {value!r}"
        ) from None


class ServerCfg(param.Parameterized):
    """Configuration for the benchmarking plot server.

    This class defines parameters for controlling how the benchmark visualization
    server operates, including network configuration.

    Attributes:
        port (int): The port to launch panel with
        allow_ws_origin (bool): Add the port to the whitelist (warning will disable remote
                               access if set to true)
        show (bool | str | ShowMode): Where to view the report.
            ``True``/``ShowMode.LIVE`` (default) starts a Panel server and blocks.
            ``ShowMode.HTML`` saves an embedded HTML file and opens it in the browser,
            returning immediately.  ``ShowMode.PUBLISHED`` opens the published URL after
            ``publish=True`` (requires publish).  ``False``/``ShowMode.NONE`` displays
            nothing.
    """

    port: int | None = param.Integer(None, doc="The port to launch panel with")
    allow_ws_origin: bool = param.Boolean(
        False,
        doc="Add the port to the whitelist, (warning will disable remote access if set to true)",
    )
    show = param.ObjectSelector(
        True,
        objects=[True, False, None, "live", "static", "published", "none"],
        doc=(
            "Where to view the report. True/ShowMode.LIVE (default) starts a Panel server "
            "and blocks. ShowMode.HTML saves an embedded HTML file and opens it in the "
            "browser, returning immediately. ShowMode.PUBLISHED opens the published URL "
            "after publish=True (requires publish=True). False/ShowMode.NONE displays nothing."
        ),
    )
