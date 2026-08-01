from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, assert_never

import panel as pn

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
    # This backend stores a live Panel layout rather than the base's plain list, so
    # children can be appended straight into the rendered tree.  Declared here for the
    # same reason ComposableContainerRerun narrows the field to its own element type.
    container: pn.layout.ListLike | list[Any] = field(default_factory=list)
    # Set only by the ComposeType.sequence arm below, None on every other method.  It is
    # declared here (rather than assigned on one arm of the match) so that append() and
    # render() read one field instead of each re-deriving "am I a tab strip?" from
    # compose_method, and so a compose method that forgets to set it cannot produce an
    # UnboundLocalError three frames from the cause (plan 23 C6, phase P8).
    _tabs: pn.Tabs | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
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
            case _ as unreachable:
                assert_never(unreachable)

        label = self.label_formatter(self.var_name, self.var_value)
        if label is not None:
            self.label_len = len(label)
            side = pn.pane.Markdown(label, align=align)
            if self._tabs is not None:
                # For Tabs, label sits outside the tab bar in a wrapper Column
                self.container.append(side)
            else:
                self.append(side)

    def append(self, obj):
        if self._tabs is not None:
            self._tabs.append(obj)
        else:
            self.container.append(obj)

    def render(self):
        if self._tabs is not None:
            self.container.append(self._tabs)
        return self.container
