"""Behavioral tests for ComposableContainerDataset composition from pandas DataFrames.

Complements test_composable_container_dataset.py (which covers dims/sizes per
ComposeType on raw DataArrays) by asserting that the *data* survives composition:
values, variable names, coordinates, and append order all stay intact.
"""

import numpy as np
import pandas as pd
import xarray as xr

from bencher.results.composable_container.composable_container_base import ComposeType
from bencher.results.composable_container.composable_container_dataframe import (
    ComposableContainerDataset,
)


def _make_df(values) -> pd.DataFrame:
    return pd.DataFrame({"metric": values}, index=pd.Index([0, 1, 2], name="step"))


def _make_ds(values) -> xr.Dataset:
    return _make_df(values).to_xarray()


class TestComposableContainerDataframe:
    def test_append_preserves_order_and_identity(self):
        ds_a, ds_b = _make_ds([1.0, 2.0, 3.0]), _make_ds([4.0, 5.0, 6.0])
        c = ComposableContainerDataset(compose_method=ComposeType.right)
        c.append(ds_a)
        c.append(ds_b)
        assert c.container == [ds_a, ds_b]
        assert c.container[0] is ds_a and c.container[1] is ds_b

    def test_single_pandas_dataframe_passthrough(self):
        df = _make_df([1.0, 2.0, 3.0])
        c = ComposableContainerDataset(compose_method=ComposeType.down)
        c.append(df)
        result = c.render()
        assert result is df  # untouched: no xarray conversion or concat for one item
        pd.testing.assert_frame_equal(result, _make_df([1.0, 2.0, 3.0]))

    def test_right_concat_keeps_values_in_append_order(self):
        c = ComposableContainerDataset(compose_method=ComposeType.right)
        c.append(_make_ds([1.0, 2.0, 3.0]))
        c.append(_make_ds([4.0, 5.0, 6.0]))
        result = c.render()
        assert isinstance(result, xr.Dataset)
        assert list(result.data_vars) == ["metric"]
        np.testing.assert_allclose(result["metric"].isel(col=0).values, [1.0, 2.0, 3.0])
        np.testing.assert_allclose(result["metric"].isel(col=1).values, [4.0, 5.0, 6.0])

    def test_down_concat_preserves_coords_and_values(self):
        c = ComposableContainerDataset(compose_method=ComposeType.down)
        c.append(_make_ds([1.0, 2.0, 3.0]))
        c.append(_make_ds([4.0, 5.0, 6.0]))
        result = c.render()
        assert result.sizes == {"row": 2, "step": 3}
        np.testing.assert_array_equal(result.coords["step"].values, [0, 1, 2])
        np.testing.assert_allclose(result["metric"].isel(row=1).values, [4.0, 5.0, 6.0])

    def test_sequence_concat_preserves_values(self):
        c = ComposableContainerDataset(compose_method=ComposeType.sequence)
        c.append(_make_ds([1.0, 2.0, 3.0]))
        c.append(_make_ds([4.0, 5.0, 6.0]))
        result = c.render()
        np.testing.assert_allclose(
            result["metric"].transpose("sequence", "step").values,
            [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
        )

    def test_overlay_means_elementwise(self):
        c = ComposableContainerDataset(compose_method=ComposeType.overlay)
        c.append(_make_ds([1.0, 2.0, 3.0]))
        c.append(_make_ds([3.0, 4.0, 5.0]))
        result = c.render()
        assert "overlay" not in result.dims
        np.testing.assert_allclose(result["metric"].values, [2.0, 3.0, 4.0])

    def test_overlay_skips_nan_values(self):
        """NaN is the missing-value default; overlay mean must skip it per element."""
        c = ComposableContainerDataset(compose_method=ComposeType.overlay)
        c.append(_make_ds([1.0, float("nan"), 3.0]))
        c.append(_make_ds([3.0, 4.0, float("nan")]))
        result = c.render()
        np.testing.assert_allclose(result["metric"].values, [2.0, 4.0, 3.0])

    def test_var_name_and_value_fields_stored(self):
        c = ComposableContainerDataset(
            compose_method=ComposeType.right, var_name="size", var_value="10"
        )
        assert c.var_name == "size"
        assert c.var_value == "10"
        assert c.label_formatter(c.var_name, c.var_value) == "size=10"
