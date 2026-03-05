import pytest
import numpy as np
import xarray as xr

from bencher.results.composable_container.composable_container_base import ComposeType
from bencher.results.composable_container.composable_container_dataframe import (
    ComposableContainerDataset,
)


def _make_da(val=1.0):
    return xr.DataArray(np.full((2, 3), val), dims=["y", "x"])


class TestComposableContainerDataset:
    def test_right_concat_col_dim(self):
        c = ComposableContainerDataset(compose_method=ComposeType.right)
        c.append(_make_da())
        c.append(_make_da())
        result = c.render()
        assert "col" in result.dims
        assert result.sizes["col"] == 2

    def test_down_concat_row_dim(self):
        c = ComposableContainerDataset(compose_method=ComposeType.down)
        c.append(_make_da())
        c.append(_make_da())
        result = c.render()
        assert "row" in result.dims
        assert result.sizes["row"] == 2

    def test_sequence_concat_sequence_dim(self):
        c = ComposableContainerDataset(compose_method=ComposeType.sequence)
        c.append(_make_da())
        c.append(_make_da())
        result = c.render()
        assert "sequence" in result.dims
        assert result.sizes["sequence"] == 2

    def test_overlay_computes_mean(self):
        c = ComposableContainerDataset(compose_method=ComposeType.overlay)
        c.append(_make_da(2.0))
        c.append(_make_da(4.0))
        result = c.render()
        assert "overlay" not in result.dims
        np.testing.assert_allclose(result.values, 3.0)

    def test_empty_raises(self):
        c = ComposableContainerDataset(compose_method=ComposeType.right)
        with pytest.raises(ValueError):
            c.render()

    def test_single_item_passthrough(self):
        da = _make_da(5.0)
        c = ComposableContainerDataset(compose_method=ComposeType.right)
        c.append(da)
        result = c.render()
        xr.testing.assert_identical(result, da)

    @pytest.mark.parametrize("compose_type", list(ComposeType))
    def test_all_compose_types_parametrized(self, compose_type):
        c = ComposableContainerDataset(compose_method=compose_type)
        c.append(_make_da())
        c.append(_make_da())
        result = c.render()
        assert result is not None
