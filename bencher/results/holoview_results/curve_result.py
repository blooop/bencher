from __future__ import annotations
from typing import Optional
import holoviews as hv
from param import Parameter
import hvplot.xarray  # noqa pylint: disable=duplicate-code,unused-import
import xarray as xr

from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import VarRange
from bencher.variables.results import ResultVar, ResultBool
from bencher.results.holoview_results.holoview_result import HoloviewResult


class CurveResult(HoloviewResult):
    """A class for creating curve plots from benchmark results.

    Curve plots are useful for visualizing the relationship between a continuous
    input variable and a result variable. This class provides methods to generate
    line plots that can also display standard deviation bounds when benchmark runs
    include multiple repetitions.
    """

    def to_plot(
        self, result_var: Parameter = None, override: bool = True, **kwargs
    ) -> Optional[hv.Curve]:
        """Generates a curve plot from benchmark data.

        This is a convenience method that calls to_curve() with the same parameters.

        Args:
            result_var (Parameter, optional): The result variable to plot. If None, uses the default.
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            **kwargs: Additional keyword arguments passed to the plot rendering.

        Returns:
            Optional[hv.Curve]: A curve plot if data is appropriate,
                              otherwise returns filter match results.
        """
        return self.to_curve(result_var=result_var, override=override, **kwargs)

    def to_curve(
        self,
        result_var: Parameter = None,
        override: bool = True,
        target_dimension: int = 2,
        **kwargs,
    ):
        """Generates a curve plot from benchmark data.

        This method applies filters to ensure the data is appropriate for a curve plot
        and then passes the filtered data to to_curve_ds for rendering.

        Args:
            result_var (Parameter, optional): The result variable to plot. If None, uses the default.
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            target_dimension (int, optional): The target dimensionality for data filtering. Defaults to 2.
            **kwargs: Additional keyword arguments passed to the plot rendering.

        Returns:
            Optional[hv.Curve]: A curve plot if data is appropriate,
                              otherwise returns filter match results.
        """
        return self.filter(
            self.to_curve_ds,
            float_range=VarRange(1, 1),
            cat_range=VarRange(0, None),
            repeats_range=VarRange(2, None),
            reduce=ReduceType.REDUCE,
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=(ResultVar, ResultBool),
            override=override,
            **kwargs,
        )

    def to_curve_ds(
        self, dataset: xr.Dataset, result_var: Parameter, **kwargs
    ) -> Optional[hv.Curve]:
        """Creates a curve plot from the provided dataset.

        Given a filtered dataset, this method generates a curve visualization showing
        the relationship between a continuous input variable and the result variable.
        When multiple benchmark repetitions are available, standard deviation bounds
        can also be displayed using a spread plot.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter): The result variable to plot.
            **kwargs: Additional keyword arguments passed to the curve plot options.

        Returns:
            Optional[hv.Curve]: A curve plot with optional standard deviation spread.
        """
        hvds = hv.Dataset(dataset)
        title = self.title_from_ds(dataset, result_var, **kwargs)
        # print(result_var.name)
        # print( dataset)
        pt = hv.Overlay()
        # find pairs of {var_name} {var_name}_std to plot the line and their spreads.
        var = result_var.name
        std_var = f"{var}_std"
        pt *= hvds.to(hv.Curve, vdims=var, label=var).opts(title=title, **kwargs)
        # Only create a Spread if the matching _std variable exists
        if std_var in dataset.data_vars:
            pt *= hvds.to(hv.Spread, vdims=[var, std_var])

        # for var in dataset.data_vars:
        #     print(var)
        #     if not var.endswith("_std"):
        #         std_var = f"{var}_std"
        #         pt *= hvds.to(hv.Curve, vdims=var, label=var).opts(title=title, **kwargs)
        #         #Only create a Spread if the matching _std variable exists
        #         if std_var in dataset.data_vars:
        #             pt *= hvds.to(hv.Spread, vdims=[var, std_var])

        return pt.opts(legend_position="right")
