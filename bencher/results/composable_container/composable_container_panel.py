from __future__ import annotations

import panel as pn
from dataclasses import dataclass

from bencher.results.composable_container.composable_container_base import (
    ComposableContainerBase,
    ComposeType,
)


_LABEL_STYLES = {
    "white-space": "nowrap",
    "min-width": "max-content",
    "padding": "0 4px",
    "font-size": "0.95em",
    "font-weight": "500",
    "color": "rgba(0, 0, 0, 0.88)",
    "text-align": "center",
}
_CELL_DIVIDER = "1px solid rgba(0, 0, 0, 0.18)"
_CELL_GAP = "6px"


def make_label_pane(text: str) -> pn.pane.Markdown:
    """Build a Markdown pane styled as a grid dimension label.

    Used both by ComposableContainerPanel (leading label on each slice) and
    by the grid-rendering pipeline in bench_result_base to repeat labels
    across wide rows/columns.
    """
    return pn.pane.Markdown(
        text,
        align=("center", "center"),
        margin=(0, 2),
        styles=_LABEL_STYLES,
    )


@dataclass(kw_only=True)
class ComposableContainerPanel(ComposableContainerBase):
    name: str | None = None
    var_name: str | None = None
    var_value: str | None = None
    nesting_depth: int | None = None
    background_col: str | None = None
    horizontal: bool | None = None

    def __post_init__(self) -> None:
        # Backward compat: horizontal kwarg overrides compose_method
        if self.horizontal is not None:
            # Old behavior: horizontal=True -> pn.Column (down), horizontal=False -> pn.Row (right)
            self.compose_method = ComposeType.down if self.horizontal else ComposeType.right

        styles = {}
        if self.nesting_depth is not None:
            # Grid lines on each slice wrapper: right + bottom edges combine
            # across siblings to form a visible grid. Depth is communicated by
            # the background tint, not by border thickness, so the line weight
            # is constant across recursion levels.
            styles["border-bottom"] = _CELL_DIVIDER
            styles["border-right"] = _CELL_DIVIDER
        if self.background_col is not None:
            styles["background"] = self.background_col

        container_args = {"name": self.name, "styles": {**styles, "gap": _CELL_GAP}}

        match self.compose_method:
            case ComposeType.right:
                self.container = pn.Row(**container_args)
            case ComposeType.down:
                self.container = pn.Column(**container_args)
            case ComposeType.sequence:
                self._tabs = pn.Tabs(**container_args)
                self.container = pn.Column(**container_args)
            case ComposeType.overlay:
                overlay_args = {
                    **container_args,
                    "styles": {**container_args["styles"], "position": "relative"},
                }
                self.container = pn.Column(**overlay_args)

        label = self.label_formatter(self.var_name, self.var_value)
        if label is not None:
            side = make_label_pane(label)
            if self.compose_method == ComposeType.sequence:
                # For Tabs, label sits outside the tab bar in a wrapper Column
                self.container.append(side)
            else:
                self.append(side)

    def append(self, obj):
        if self.compose_method == ComposeType.sequence:
            self._tabs.append(obj)
        else:
            self.container.append(obj)

    def render(self):
        if self.compose_method == ComposeType.sequence:
            self.container.append(self._tabs)
            return self.container
        return self.container
