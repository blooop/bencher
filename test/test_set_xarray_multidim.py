import pytest
import numpy as np
import xarray as xr
from bencher.bencher import set_xarray_multidim

class TestSetXarrayMultidim:
    def test_1d_array(self):
        data = xr.DataArray([1, 2, 3], dims=['x'])
        result = set_xarray_multidim(data.copy(), (1,), 99)
        expected = xr.DataArray([1, 99, 3], dims=['x'])
        assert result.equals(expected)

    def test_2d_array(self):
        data = xr.DataArray([[1, 2], [3, 4]], dims=['x', 'y'])
        result = set_xarray_multidim(data.copy(), (0, 1), 99)
        expected = xr.DataArray([[1, 99], [3, 4]], dims=['x', 'y'])
        assert result.equals(expected)

    def test_3d_array(self):
        data = xr.DataArray(np.arange(8).reshape(2,2,2), dims=['x', 'y', 'z'])
        result = set_xarray_multidim(data.copy(), (1, 0, 1), 42)
        expected = data.copy()
        expected[1, 0, 1] = 42
        assert result.equals(expected)

    def test_4d_array(self):
        data = xr.DataArray(np.zeros((2,2,2,2)), dims=['a','b','c','d'])
        result = set_xarray_multidim(data.copy(), (1,1,1,1), 7)
        expected = data.copy()
        expected[1,1,1,1] = 7
        assert result.equals(expected)

    def test_5d_array(self):
        data = xr.DataArray(np.zeros((2,2,2,2,2)), dims=['a','b','c','d','e'])
        result = set_xarray_multidim(data.copy(), (1,1,1,1,1), 5)
        expected = data.copy()
        expected[1,1,1,1,1] = 5
        assert result.equals(expected)

    def test_6d_array(self):
        data = xr.DataArray(np.zeros((2,2,2,2,2,2)), dims=['a','b','c','d','e','f'])
        result = set_xarray_multidim(data.copy(), (1,1,1,1,1,1), 6)
        expected = data.copy()
        expected[1,1,1,1,1,1] = 6
        assert result.equals(expected)

    def test_7d_array(self):
        data = xr.DataArray(np.zeros((2,2,2,2,2,2,2)), dims=['a','b','c','d','e','f','g'])
        result = set_xarray_multidim(data.copy(), (1,1,1,1,1,1,1), 7)
        expected = data.copy()
        expected[1,1,1,1,1,1,1] = 7
        assert result.equals(expected)

    def test_8d_array(self):
        data = xr.DataArray(np.zeros((2,2,2,2,2,2,2,2)), dims=['a','b','c','d','e','f','g','h'])
        result = set_xarray_multidim(data.copy(), (1,1,1,1,1,1,1,1), 8)
        expected = data.copy()
        expected[1,1,1,1,1,1,1,1] = 8
        assert result.equals(expected)

    def test_9d_array(self):
        data = xr.DataArray(np.zeros((2,2,2,2,2,2,2,2,2)), dims=['a','b','c','d','e','f','g','h','i'])
        result = set_xarray_multidim(data.copy(), (1,1,1,1,1,1,1,1,1), 9)
        expected = data.copy()
        expected[1,1,1,1,1,1,1,1,1] = 9
        assert result.equals(expected)
