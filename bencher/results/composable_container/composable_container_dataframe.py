from dataclasses import dataclass
import panel as pn
import xarray as xr
from bencher.results.composable_container.composable_container_base import ComposableContainerBase
from bencher.results.composable_container.composable_container_base import ComposeType


@dataclass(kw_only=True)
class ComposableContainerDataset(ComposableContainerBase):
    name: str | None = None
    var_name: str | None = None
    var_value: str | None = None
    width: int | None = None
    background_col: str | None = None
    horizontal: bool = True

    def __post_init__(
        self,
    ) -> None:
        container_args = {
            "name": self.name,
            "styles": {},
        }

        if self.width is not None:
            container_args["styles"]["border-bottom"] = f"{self.width}px solid grey"
        if self.background_col is not None:
            container_args["styles"]["background"] = self.background_col

        if self.horizontal:
            self.container = pn.Column(**container_args)
            align = ("center", "center")
        else:
            self.container = pn.Row(**container_args)
            align = ("end", "center")

        label = self.label_formatter(self.var_name, self.var_value)
        if label is not None:
            self.label_len = len(label)
            side = pn.pane.Markdown(label, align=align)
            self.append(side)

    def render(self, **kwargs):  # pylint: disable=unused-argument
        match self.compose_method:
            case ComposeType.right:
                return xr.concat(self.container, 0)
            case ComposeType.down:
                return xr.concat(self.container, 1)
            case ComposeType.sequence:
                return xr.concat(self.container, 2)
            # case ComposeType.overlay:
            # return xr.Dataset.mean()
