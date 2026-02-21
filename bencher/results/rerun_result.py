from __future__ import annotations

import itertools
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import panel as pn
import xarray as xr
from param import Parameter

from bencher.results.bench_result_base import BenchResultBase, ReduceType
from bencher.variables.results import (
    ResultImage,
    ResultVideo,
    ResultString,
)


class RerunResult(BenchResultBase):
    """Result class that renders N-dimensional benchmark data into a rerun viewer.

    Categorical dimensions become entity path segments (tree branches).
    Float dimensions and over_time become rerun timelines (independently scrubable).
    Result variables become leaf entities with appropriate rerun archetypes.
    """

    def to_rerun(
        self,
        result_var: Optional[Parameter] = None,
        width: int = 950,
        height: int = 712,
    ) -> pn.pane.panel:  # pragma: no cover
        """Convert N-dimensional benchmark results to a rerun viewer.

        Saves the recording to an .rrd file and returns a Panel pane with
        the rerun web viewer embedded as an iframe. Requires the Flask file
        server to be running (call ``bch.run_flask_in_thread()`` first).

        Args:
            result_var: Optional specific result variable to display. If None, all are shown.
            width: Width of the rerun viewer widget.
            height: Height of the rerun viewer widget.

        Returns:
            A panel pane containing the rerun viewer.
        """
        import rerun as rr
        from bencher.utils import gen_rerun_data_path
        from bencher.utils_rerun import rrd_to_pane

        bench_name = self.bench_cfg.bench_name or "bencher"
        recording = rr.RecordingStream(
            f"bencher/{bench_name}", make_default=False, make_thread_default=False
        )

        dataset = self.to_dataset(reduce=ReduceType.SQUEEZE, result_var=result_var)

        # Classify dimensions
        float_dims = [v.name for v in self.plt_cnt_cfg.float_vars]
        cat_dims = [v.name for v in self.plt_cnt_cfg.cat_vars]

        # Detect over_time dimension
        time_dim = None
        if self.bench_cfg.over_time and "over_time" in dataset.dims:
            time_dim = "over_time"

        # Determine which result variables to log
        if result_var is not None:
            rv_list = [result_var]
        else:
            rv_list = list(self.bench_cfg.result_vars)

        # Filter dims to only those present in the reduced dataset
        float_dims = [d for d in float_dims if d in dataset.dims]
        cat_dims = [d for d in cat_dims if d in dataset.dims]

        _log_to_rerun(
            rr=rr,
            recording=recording,
            dataset=dataset,
            entity_path="",
            result_vars=rv_list,
            float_dims=float_dims,
            cat_dims=cat_dims,
            time_dim=time_dim,
            bench_cfg=self.bench_cfg,
        )

        # Write the recording to an .rrd file and serve via iframe.
        # This avoids the ipywidgets_bokeh dependency that
        # pn.pane.IPyWidget requires in a Panel/Bokeh server context.
        rrd_path = gen_rerun_data_path(bench_name)
        rrd_data = recording.memory_recording().drain_as_bytes()
        with open(rrd_path, "wb") as f:
            f.write(rrd_data)
        # Build a URL relative to the local Flask file server (port 8001)
        url_path = rrd_path.split("cachedir")[1]
        return rrd_to_pane(f"http://127.0.0.1:8001/{url_path}", width=width, height=height)


def _get_time_value(dataset, dim, coord_val):
    """Extract a numeric time value suitable for rerun from a coordinate value."""
    val = coord_val
    if hasattr(val, "item"):
        val = val.item()
    # For datetime-like values, convert to seconds since epoch
    if isinstance(val, (np.datetime64,)):
        return float((val - np.datetime64("1970-01-01T00:00:00")) / np.timedelta64(1, "s"))
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _log_to_rerun(
    rr,
    recording,
    dataset: xr.Dataset,
    entity_path: str,
    result_vars: list,
    float_dims: list[str],
    cat_dims: list[str],
    time_dim: str | None,
    bench_cfg=None,
):
    """Recursively map N-dimensional data to rerun entity paths and timelines.

    Categorical dims -> entity path branches.
    Float dims + over_time -> rerun timelines.
    Result vars -> leaf entities.
    """
    # First: peel off categorical dims as entity path branches
    if cat_dims:
        dim = cat_dims[-1]
        remaining_cat = cat_dims[:-1]
        for val in dataset.coords[dim].values:
            sliced = dataset.sel({dim: val})
            label = str(val)
            _log_to_rerun(
                rr=rr,
                recording=recording,
                dataset=sliced,
                entity_path=f"{entity_path}/{dim}/{label}",
                result_vars=result_vars,
                float_dims=float_dims,
                cat_dims=remaining_cat,
                time_dim=time_dim,
                bench_cfg=bench_cfg,
            )
        return

    # All remaining dims are float + possibly over_time -> become timelines
    all_timeline_dims = list(float_dims)
    if time_dim and time_dim in dataset.dims:
        all_timeline_dims.append(time_dim)

    if len(all_timeline_dims) == 0:
        # 0D: log scalar values directly (no timeline)
        for rv in result_vars:
            _log_result_var(
                rr=rr,
                recording=recording,
                dataset=dataset,
                entity_path=entity_path,
                rv=rv,
            )

    elif len(all_timeline_dims) == 1:
        # 1D: single timeline -> log scalars at each step (creates line plot in rerun)
        dim = all_timeline_dims[0]
        for i, coord_val in enumerate(dataset.coords[dim].values):
            _set_time(rr, recording, dim, i, coord_val, time_dim)
            sliced = dataset.sel({dim: coord_val})
            for rv in result_vars:
                _log_result_var(
                    rr=rr,
                    recording=recording,
                    dataset=sliced,
                    entity_path=entity_path,
                    rv=rv,
                )

    else:
        # 2D+: multiple timelines — iterate over cartesian product
        # Each dim gets its own rr.set_time_sequence call
        dim_coords = [dataset.coords[d].values for d in all_timeline_dims]
        for indices in itertools.product(*[range(len(c)) for c in dim_coords]):
            sel_dict = {}
            for dim, coord_vals, idx in zip(all_timeline_dims, dim_coords, indices):
                _set_time(rr, recording, dim, idx, coord_vals[idx], time_dim)
                sel_dict[dim] = coord_vals[idx]
            sliced = dataset.sel(sel_dict)
            for rv in result_vars:
                _log_result_var(
                    rr=rr,
                    recording=recording,
                    dataset=sliced,
                    entity_path=entity_path,
                    rv=rv,
                )


def _set_time(rr, recording, dim: str, index: int, coord_val, time_dim: str | None):
    """Set the appropriate rerun timeline for a dimension."""
    if dim == time_dim:
        # For over_time, try to use real timestamp if the values are numeric/datetime
        time_sec = _get_time_value(None, dim, coord_val)
        if time_sec is not None:
            recording.set_time("over_time", timestamp=time_sec)
        else:
            recording.set_time("over_time", sequence=index)
    else:
        # Float sweep dims use sequence timelines indexed by position
        recording.set_time(dim, sequence=index)


def _log_result_var(rr, recording, dataset: xr.Dataset, entity_path: str, rv):
    """Log a single result variable to rerun at the current entity path."""
    rv_name = rv.name if hasattr(rv, "name") else str(rv)
    path = f"{entity_path}/{rv_name}" if entity_path else rv_name

    try:
        if isinstance(rv, (ResultImage,)):
            val = dataset[rv_name].values
            if hasattr(val, "item"):
                val = val.item()
            if val is not None and val and Path(str(val)).exists():
                recording.log(path, rr.EncodedImage(path=str(val)))
            return

        if isinstance(rv, (ResultVideo,)):
            val = dataset[rv_name].values
            if hasattr(val, "item"):
                val = val.item()
            if val is not None and val and Path(str(val)).exists():
                recording.log(path, rr.AssetVideo(path=str(val)))
            return

        if isinstance(rv, (ResultString,)):
            val = dataset[rv_name].values
            if hasattr(val, "item"):
                val = val.item()
            if val is not None:
                recording.log(path, rr.TextDocument(str(val)))
            return

        # Default: ResultVar, ResultBool, or any numeric result -> Scalars
        val = dataset[rv_name].values
        if hasattr(val, "item"):
            val = val.item()
        if val is not None and not (isinstance(val, float) and np.isnan(val)):
            recording.log(path, rr.Scalars(float(val)))

    except (KeyError, ValueError, TypeError) as e:
        logging.debug("Could not log result var %s: %s", rv_name, e)
