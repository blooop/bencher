from __future__ import annotations

from typing import Any, List


class RerunBlueprintBuilder:
    """Helper class for collecting rerun blueprint views and building a final blueprint."""

    def __init__(self) -> None:
        self._views: List[Any] = []

    def add_view(self, view: Any) -> None:
        if view is not None:
            self._views.append(view)

    def add_views(self, views: List[Any]) -> None:
        for v in views:
            self.add_view(v)

    def build(self, include_time_panel: bool = True) -> Any:
        import rerun.blueprint as rrb

        contents = list(self._views) if self._views else []
        args = [rrb.Vertical(*contents)]
        if include_time_panel:
            args.append(rrb.TimePanel(expanded=True))
        return rrb.Blueprint(*args)

    def __len__(self) -> int:
        return len(self._views)
