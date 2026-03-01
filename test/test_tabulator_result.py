import pandas as pd
import xarray as xr
import numpy as np

from bencher.results.holoview_results.tabulator_result import TabulatorResult


class _DummyBenchCfg:
    # Minimal stub to satisfy BenchResultBase.__init__
    result_hmaps = []


class _Var:
    def __init__(self, name: str):
        self.name = name


def _mk_tr() -> TabulatorResult:
    return TabulatorResult(_DummyBenchCfg())


def test_to_tabulator_ds_0d_dataset():
    ds = xr.Dataset({"v": xr.DataArray(42)})
    tr = _mk_tr()
    tab = tr.to_tabulator_ds(ds, _Var("v"))
    assert hasattr(tab, "value")
    assert isinstance(tab.value, pd.DataFrame)
    assert list(tab.value.columns) == ["v"] or "v" in tab.value.columns
    assert len(tab.value) == 1


def test_to_tabulator_ds_1d_dataset():
    arr = xr.DataArray(np.arange(3), dims=["x"], coords={"x": [0, 1, 2]})
    ds = xr.Dataset({"v": arr})
    tr = _mk_tr()
    tab = tr.to_tabulator_ds(ds, _Var("v"))
    assert isinstance(tab.value, pd.DataFrame)
    # Expect flattened index columns present
    for col in ["x", "v"]:
        assert col in tab.value.columns
    assert len(tab.value) == 3


def test_to_tabulator_ds_2d_dataset():
    arr = xr.DataArray(
        np.arange(6).reshape(2, 3), dims=["x", "y"], coords={"x": [0, 1], "y": [0, 1, 2]}
    )
    ds = xr.Dataset({"v": arr})
    tr = _mk_tr()
    tab = tr.to_tabulator_ds(ds, _Var("v"))
    assert isinstance(tab.value, pd.DataFrame)
    for col in ["x", "y", "v"]:
        assert col in tab.value.columns
    assert len(tab.value) == 6
