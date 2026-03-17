from __future__ import annotations

import holoviews as hv
import numpy as np
from param import Parameter
import xarray as xr

from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import VarRange
from bencher.variables.results import ResultVar, ResultBool
from bencher.results.holoview_results.holoview_result import HoloviewResult


class BandResult(HoloviewResult):
    """Percentile band plot showing distribution spread over a continuous axis.

    Displays nested shaded bands (e.g. 10th-90th and 25th-75th percentiles)
    with a median line and individual scatter points, giving a richer view of
    the distribution than mean +/- std.  Particularly useful with
    ``agg_over_dims`` to show how a high-dimensional sweep's distribution
    evolves over time.
    """

    def to_plot(
        self, result_var: Parameter | None = None, override: bool = True, **kwargs
    ) -> hv.Overlay | None:
        return self.to_band(result_var=result_var, override=override, **kwargs)

    def to_band(
        self,
        result_var: Parameter | None = None,
        override: bool = True,
        **kwargs,
    ):
        # Extract agg_over_dims so filter() doesn't pre-aggregate the dataset.
        # BandResult computes its own percentiles from the raw data.
        band_agg_dims = kwargs.pop("agg_over_dims", None)
        kwargs.pop("agg_fn", None)
        return self.filter(
            self.to_band_ds,
            float_range=VarRange(0, None),
            cat_range=VarRange(0, None),
            repeats_range=VarRange(1, None),
            input_range=VarRange(0, None),
            reduce=ReduceType.NONE,
            target_dimension=None,
            result_var=result_var,
            result_types=(ResultVar, ResultBool),
            override=override,
            agg_over_dims=None,
            band_agg_dims=band_agg_dims,
            **kwargs,
        )

    def to_band_ds(self, dataset: xr.Dataset, result_var: Parameter, **kwargs) -> hv.Overlay | None:
        """Create a percentile band plot from the provided dataset.

        Flattens all dimensions except the continuous axis (typically over_time)
        into a sample pool and computes percentiles across those samples.
        """
        var = result_var.name

        # band_agg_dims is passed through from to_band to avoid filter pre-aggregation
        agg_over_dims = kwargs.pop("band_agg_dims", None)

        title = self.title_from_ds(dataset, result_var, **kwargs)

        use_holomap = self._use_holomap_for_time(dataset)

        if use_holomap:
            return self._band_over_time(dataset, var, title, agg_over_dims, **kwargs)

        # Without over_time: find a continuous x-axis from remaining dims
        return self._band_static(dataset, var, title, agg_over_dims, **kwargs)

    def _band_over_time(
        self,
        dataset: xr.Dataset,
        var: str,
        title: str,
        agg_over_dims: list[str] | None,
        **kwargs,
    ) -> hv.Overlay | None:
        """Build percentile bands with time on x-axis."""
        da = dataset[var]

        # Determine which dims to flatten (everything except over_time)
        sample_dims = [d for d in da.dims if d != "over_time"]
        if agg_over_dims:
            sample_dims = [d for d in sample_dims if d in agg_over_dims or d == "repeat"]
        if not sample_dims:
            return None

        # Stack sample dims, compute percentiles at each time point
        stacked = da.stack(sample=sample_dims).transpose("over_time", "sample")
        values = stacked.values  # shape: (n_time, n_samples)

        time_coords = da.coords["over_time"].values
        p10 = np.nanpercentile(values, 10, axis=1)
        p25 = np.nanpercentile(values, 25, axis=1)
        p50 = np.nanpercentile(values, 50, axis=1)
        p75 = np.nanpercentile(values, 75, axis=1)
        p90 = np.nanpercentile(values, 90, axis=1)

        # Build scatter data: repeat each time coord for every sample
        n_time, n_samples = values.shape
        scatter_x = np.repeat(time_coords, n_samples)
        scatter_y = values.ravel()

        return self._build_band_overlay(
            time_coords, p10, p25, p50, p75, p90, scatter_x, scatter_y, var, title, **kwargs
        )

    def _band_static(
        self,
        dataset: xr.Dataset,
        var: str,
        title: str,
        agg_over_dims: list[str] | None,
        **kwargs,
    ) -> hv.Overlay | None:
        """Build percentile bands over a non-time continuous axis."""
        da = dataset[var]
        all_dims = list(da.dims)

        # Figure out which dim is the x-axis (not aggregated, not repeat)
        agg_set = set(agg_over_dims) if agg_over_dims else set()
        candidate_x = [d for d in all_dims if d not in agg_set and d != "repeat"]

        if not candidate_x:
            # All dims aggregated and no time — can't make a meaningful band plot
            return None

        x_dim = candidate_x[0]
        sample_dims = [d for d in all_dims if d != x_dim]
        if not sample_dims:
            return None

        stacked = da.stack(sample=sample_dims).transpose(x_dim, "sample")
        values = stacked.values  # shape: (n_x, n_samples)

        x_coords = da.coords[x_dim].values
        p10 = np.nanpercentile(values, 10, axis=1)
        p25 = np.nanpercentile(values, 25, axis=1)
        p50 = np.nanpercentile(values, 50, axis=1)
        p75 = np.nanpercentile(values, 75, axis=1)
        p90 = np.nanpercentile(values, 90, axis=1)

        # Build scatter data: repeat each x coord for every sample
        n_x, n_samples = values.shape
        scatter_x = np.repeat(x_coords, n_samples)
        scatter_y = values.ravel()

        return self._build_band_overlay(
            x_coords, p10, p25, p50, p75, p90, scatter_x, scatter_y, var, title, **kwargs
        )

    @staticmethod
    def _build_band_overlay(
        x_coords,
        p10,
        p25,
        p50,
        p75,
        p90,
        scatter_x,
        scatter_y,
        var: str,
        title: str,
        **kwargs,
    ) -> hv.Overlay:
        """Construct the overlay of Area bands + median Curve + scatter points."""
        # Outer band: 10th-90th percentile
        band_outer = hv.Area(
            (x_coords, p10, p90),
            kdims=["x"],
            vdims=["p10", "p90"],
            label="10th\u201390th pctl",
        ).opts(alpha=0.2, color="steelblue", line_alpha=0)

        # Inner band: 25th-75th percentile
        band_inner = hv.Area(
            (x_coords, p25, p75),
            kdims=["x"],
            vdims=["p25", "p75"],
            label="25th\u201375th pctl",
        ).opts(alpha=0.4, color="steelblue", line_alpha=0)

        # Median line
        median_line = hv.Curve(
            (x_coords, p50),
            kdims=["x"],
            vdims=[var],
            label="median",
        ).opts(color="steelblue", line_width=2)

        # Scatter overlay: individual data points (drop NaNs)
        mask = ~np.isnan(scatter_y)
        scatter = hv.Scatter(
            (scatter_x[mask], scatter_y[mask]),
            kdims=["x"],
            vdims=[var],
            label="samples",
        ).opts(color="grey", alpha=0.3, size=3)

        overlay = band_outer * band_inner * median_line * scatter
        overlay = overlay.opts(title=title, xrotation=30, legend_position="right")
        return overlay
