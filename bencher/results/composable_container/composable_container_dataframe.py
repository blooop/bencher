from __future__ import annotations

from dataclasses import dataclass

import xarray as xr

from bencher.results.composable_container.composable_container_base import (
    ComposableContainerBase,
    ComposeType,
)


@dataclass(kw_only=True)
class ComposableContainerDataset(ComposableContainerBase):
    var_name: str | None = None
    var_value: str | None = None

    def render(self, **kwargs):  # pylint: disable=unused-argument
        if len(self.container) == 0:
            raise ValueError("Cannot render an empty ComposableContainerDataset")
        if len(self.container) == 1:
            return self.container[0]

        match self.compose_method:
            case ComposeType.right:
                return xr.concat(self.container, dim="col")
            case ComposeType.down:
                return xr.concat(self.container, dim="row")
            case ComposeType.sequence:
                return xr.concat(self.container, dim="sequence")
            case ComposeType.overlay:
                return xr.concat(self.container, dim="overlay").mean(dim="overlay")
