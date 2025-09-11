from __future__ import annotations
import panel as pn

from bencher.results.holoview_results.holoview_result import HoloviewResult

from typing import Optional
import holoviews as hv
from param import Parameter
import hvplot.xarray  # noqa pylint: disable=duplicate-code,unused-import
import xarray as xr

from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import VarRange
from bencher.variables.results import ResultVar, ResultBool
from bencher.results.holoview_results.holoview_result import HoloviewResult


class TabulatorResult(HoloviewResult):
    def to_plot(self, **kwargs) -> pn.widgets.Tabulator:  # pylint:disable=unused-argument
        """Create an interactive table visualization of the data.

        Passes the data to the panel Tabulator type to display an interactive table.
        See https://panel.holoviz.org/reference/widgets/Tabulator.html for extra options.

        Args:
            **kwargs: Additional parameters to pass to the Tabulator constructor.

        Returns:
            pn.widgets.Tabulator: An interactive table widget.
        """
        return self.to_tabulator(**kwargs)

    def to_tabulator(self, result_var: Parameter = None, **kwargs) -> pn.widgets.Tabulator:
        """Generates a Tabulator widget from benchmark data.

        This is a convenience method that calls to_tabulator_ds() with the same parameters.

        Args:
            result_var (Parameter, optional): The result variable to include in the table. If None, uses the default.
            **kwargs: Additional keyword arguments passed to the Tabulator constructor.

        Returns:
            pn.widgets.Tabulator: An interactive table widget.
        """
        return self.filter(
            self.to_tabulator_ds,
            result_var=result_var,
            **kwargs,
        )

    def to_tabulator_ds(
        self, dataset: xr.Dataset, result_var: Parameter, **kwargs
    ) -> pn.widgets.Tabulator:
        """Creates a Tabulator widget from the provided dataset.

        Given a filtered dataset, this method generates an interactive table visualization.

        Args:
            dataset (xr.Dataset): The filtered dataset to visualize.
            result_var (Parameter): The result variable to include in the table.
            **kwargs: Additional keyword arguments passed to the Tabulator constructor.

        Returns:
            pn.widgets.Tabulator: An interactive table widget.
        """
        import xarray as xr
        import pandas as pd
        import numpy as np

        # Ensure we are working with an xarray.Dataset
        ds: xr.Dataset
        if isinstance(dataset, xr.DataArray):
            name = dataset.name or (result_var.name if result_var is not None else "value")
            ds = dataset.to_dataset(name=name)
        else:
            ds = dataset

        # If a specific result variable is requested, reduce to that single variable
        if result_var is not None and isinstance(ds, xr.Dataset):
            # Use double brackets to keep it a Dataset (not a DataArray)
            if result_var.name in ds.data_vars:
                ds = ds[[result_var.name]]
            else:
                # Fall back gracefully if missing; keep current dataset
                pass

        # Convert to a flattened pandas DataFrame (indices -> columns)
        # Handle 0-D Dataset explicitly since xarray cannot create an index for it.
        if len(ds.dims) == 0:
            if result_var is not None and result_var.name in ds.data_vars:
                df = pd.DataFrame({result_var.name: [ds[result_var.name].values.item()]})
            else:
                # Collect all data variables into a single-row DataFrame
                data = {
                    name: [da.values.item()]
                    for name, da in ds.data_vars.items()
                } or {"value": [ds.values.item()] if hasattr(ds, "values") else [None]}
                df = pd.DataFrame(data)
        else:
            df = ds.to_dataframe().reset_index()

        # Guard against accidental numpy array outputs (shouldn't occur with to_dataframe)
        if isinstance(df, np.ndarray):
            df = pd.DataFrame({result_var.name if result_var is not None else "value": df.ravel()})

        return pn.widgets.Tabulator(df, **kwargs)
