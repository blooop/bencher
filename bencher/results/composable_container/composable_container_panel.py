from __future__ import annotations

import panel as pn
from dataclasses import dataclass

from bencher.results.composable_container.composable_container_base import (
    ComposableContainerBase,
    ComposeType,
)


@dataclass(kw_only=True)
class ComposableContainerPanel(ComposableContainerBase):
    name: str | None = None
    var_name: str | None = None
    var_value: str | None = None
    width: int | None = None
    background_col: str | None = None
    horizontal: bool | None = None

    def __post_init__(self) -> None:
        # Backward compat: horizontal kwarg overrides compose_method
        if self.horizontal is not None:
            # Old behavior: horizontal=True -> pn.Column (down), horizontal=False -> pn.Row (right)
            self.compose_method = ComposeType.down if self.horizontal else ComposeType.right

        styles = {}
        if self.width is not None:
            styles["border-bottom"] = f"{self.width}px solid grey"
        if self.background_col is not None:
            styles["background"] = self.background_col

        container_args = {"name": self.name, "styles": styles}

        match self.compose_method:
            case ComposeType.right:
                self.container = pn.Row(**container_args)
                align = ("end", "center")
            case ComposeType.down:
                self.container = pn.Column(**container_args)
                align = ("center", "center")
            case ComposeType.sequence:
                self._tabs = pn.Tabs(**container_args)
                self.container = pn.Column(**container_args)
                align = ("center", "center")
            case ComposeType.overlay:
                styles["position"] = "relative"
                self.container = pn.Column(**container_args)
                align = ("center", "center")

        label = self.label_formatter(self.var_name, self.var_value)
        if label is not None:
            self.label_len = len(label)
            side = pn.pane.Markdown(label, align=align)
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
