import pytest
import numpy as np
import xarray as xr
import panel as pn

from bencher.results.composable_container.composable_container_base import (
    ComposeType,
    ComposableContainerBase,
)
from bencher.results.composable_container.composable_container_panel import (
    ComposableContainerPanel,
)
from bencher.results.composable_container.composable_container_dataframe import (
    ComposableContainerDataset,
)
from bencher.results.composable_container.composable_container_video import (
    ComposableContainerVideo,
)


def test_imports():
    """All container classes are importable from the package."""
    from bencher.results.composable_container import (
        ComposeType,
        ComposableContainerBase,
        ComposableContainerVideo,
        ComposableContainerPanel,
        ComposableContainerDataset,
        RenderCfg,
    )

    assert ComposeType is not None
    assert ComposableContainerBase is not None
    assert ComposableContainerVideo is not None
    assert ComposableContainerPanel is not None
    assert ComposableContainerDataset is not None
    assert RenderCfg is not None


def test_imports_from_bencher():
    """Container classes are importable from top-level bencher package."""
    import bencher as bch

    assert bch.ComposableContainerPanel is not None
    assert bch.ComposableContainerDataset is not None


class TestSharedInterface:
    """All backends share the ComposableContainerBase interface."""

    @pytest.mark.parametrize(
        "cls", [ComposableContainerBase, ComposableContainerPanel, ComposableContainerDataset]
    )
    def test_has_append(self, cls):
        assert hasattr(cls, "append")

    @pytest.mark.parametrize(
        "cls", [ComposableContainerBase, ComposableContainerPanel, ComposableContainerDataset]
    )
    def test_has_render(self, cls):
        assert hasattr(cls, "render")

    @pytest.mark.parametrize(
        "cls", [ComposableContainerBase, ComposableContainerPanel, ComposableContainerDataset]
    )
    def test_has_compose_method(self, cls):
        assert hasattr(cls, "compose_method")

    @pytest.mark.parametrize(
        "cls", [ComposableContainerBase, ComposableContainerPanel, ComposableContainerDataset]
    )
    def test_has_label_formatter(self, cls):
        assert hasattr(cls, "label_formatter")


@pytest.mark.parametrize("compose_type", list(ComposeType))
class TestPanelAllComposeTypes:
    def test_panel_render(self, compose_type):
        c = ComposableContainerPanel(compose_method=compose_type)
        c.append(pn.pane.Markdown("A"))
        c.append(pn.pane.Markdown("B"))
        result = c.render()
        assert result is not None


@pytest.mark.parametrize("compose_type", list(ComposeType))
class TestDatasetAllComposeTypes:
    def test_dataset_render(self, compose_type):
        da = xr.DataArray(np.ones((2, 3)), dims=["y", "x"])
        c = ComposableContainerDataset(compose_method=compose_type)
        c.append(da)
        c.append(da)
        result = c.render()
        assert result is not None


@pytest.mark.parametrize("compose_type", list(ComposeType))
class TestVideoAllComposeTypes:
    def test_video_render(self, compose_type):
        from bencher.results.composable_container.composable_container_video import RenderCfg

        img = np.ones((2, 1, 3))
        c = ComposableContainerVideo()
        c.append(img)
        c.append(img)
        result = c.render(RenderCfg(compose_method=compose_type, duration=0.1))
        assert result is not None
