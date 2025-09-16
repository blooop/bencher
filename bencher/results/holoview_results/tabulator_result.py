from __future__ import annotations
import panel as pn

from bencher.results.holoview_results.holoview_result import HoloviewResult

from param import Parameter
import hvplot.xarray  # noqa pylint: disable=duplicate-code,unused-import
import xarray as xr
import pandas as pd


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

        # Assume input is an xarray.Dataset. Keep Dataset throughout.
        ds: xr.Dataset = dataset if isinstance(dataset, xr.Dataset) else xr.Dataset(dataset)

        # Step 1: If a result variable is specified, select it and keep as Dataset
        if result_var is not None and result_var.name in ds.data_vars:
            ds = ds[[result_var.name]]

        # Step 2: Build a flat pandas DataFrame
        if len(ds.dims) == 0:
            df = pd.DataFrame({name: [da.values.item()] for name, da in ds.data_vars.items()})
        else:
            # N-D: to DataFrame and reset the index so coordinates become columns
            df = ds.to_dataframe().reset_index()

        return pn.widgets.Tabulator(df, **kwargs)
