from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bencher.results.composable_container.composable_container_base import (
    ComposableContainerBase,
    ComposeType,
)


@dataclass(kw_only=True)
class ComposableContainerRerun(ComposableContainerBase):
    """Rerun-based composable container that maps ComposeType to rerun blueprint containers."""

    name: str | None = None
    var_name: str | None = None
    var_value: str | None = None
    recording: Any = None

    def render(self) -> Any:
        """Render the container as a rerun blueprint layout container.

        Maps ComposeType to rerun blueprint equivalents:
        - right -> rrb.Horizontal
        - down -> rrb.Vertical
        - sequence -> rrb.Tabs
        - overlay -> rrb.Grid
        """
        import rerun.blueprint as rrb

        views = []
        for item in self.container:
            if isinstance(item, ComposableContainerRerun):
                views.append(item.render())
            else:
                views.append(item)

        label = self.label_formatter(self.var_name, self.var_value)
        if label is not None:
            if self.recording is not None:
                import rerun as rr

                label_path = f"_labels/{label}"
                self.recording.log(label_path, rr.TextDocument(label))
                views.insert(0, rrb.TextDocumentView(origin=label_path))

        if len(views) == 0:
            return rrb.Vertical()
        if len(views) == 1:
            return views[0]

        composers = {
            ComposeType.right: rrb.Horizontal,
            ComposeType.down: rrb.Vertical,
            ComposeType.sequence: rrb.Tabs,
            ComposeType.overlay: rrb.Grid,
        }
        composer = composers.get(self.compose_method, rrb.Vertical)
        return composer(*views)
