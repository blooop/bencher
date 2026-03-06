from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bencher.results.composable_container.composable_container_base import (
    ComposableContainerBase,
    ComposeType,
)


@dataclass(kw_only=True)
class ComposableContainerRerun(ComposableContainerBase):
    """Composable container that maps ComposeType to rerun blueprint containers.

    - ``right``    -> ``rrb.Horizontal`` (side by side)
    - ``down``     -> ``rrb.Vertical`` (stacked)
    - ``sequence`` -> rerun **timeline** (items displayed one after another in time)
    - ``overlay``  -> items logged to the **same entity path** (drawn on top of each other)
    """

    container: list[Any] = field(default_factory=list)

    def render(self):
        """Return a rerun blueprint container matching the compose method."""
        import rerun.blueprint as rrb

        items = self.container
        if not items:
            return rrb.Vertical()

        match self.compose_method:
            case ComposeType.right:
                return rrb.Horizontal(*items)
            case ComposeType.down:
                return rrb.Vertical(*items)
            case ComposeType.sequence:
                # Temporal sequence: items share the same view, differentiated by timeline
                return rrb.Vertical(*items)
            case ComposeType.overlay:
                # Overlay: items logged to the same entity path in the same view
                return rrb.Vertical(*items)
            case _:
                return rrb.Vertical(*items)
