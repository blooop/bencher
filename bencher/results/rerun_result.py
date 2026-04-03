from __future__ import annotations

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

    Mapping strategy (three phases):

    **Phase 0 - over_time** (the only rerun timeline):
    - If ``over_time`` is present it is iterated as the ``log_tick`` timeline.
    - All other data is logged statically (no timeline scrubber unless
      ``over_time`` is used).

    **Phase A - Peel categorical dims** as entity-tree branches:
    - If cats AND floats exist: peel ALL cats as entity branches.
    - If cats ONLY (no floats): peel cats until exactly 1 remains
      (the last cat becomes the BarChart axis).

    **Phase B - Handle remaining float dims**:
    - 0 dims -> ``rr.Scalars`` (scalar value)
    - 1 dim, cat -> ``rr.BarChart``
    - 1 dim, float (no over_time) -> line graph via ``_log_line_graph``
    - 1 dim, float (inside over_time) -> ``rr.Tensor`` (1-D)
    - 2 dims -> ``rr.Tensor`` (2-D array displayed as heatmap)
    - 3 dims -> ``rr.Tensor`` (3-D array displayed as volume slices)
    - >3 dims -> peel outermost float dim as entity branch, recurse

    A rerun blueprint is built to control the viewer layout, with typed views
    (TimeSeriesView, TensorView, BarChartView) arranged in Grid/Vertical containers.
    The ``log_time`` timeline is disabled so only ``log_tick`` is shown.
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
        try:
            import rerun as rr
            import rerun.blueprint as rrb
        except ModuleNotFoundError:
            return pn.pane.Markdown(
                "**rerun** is not installed. Install it with `pip install rerun-sdk`."
            )
        from bencher.utils import gen_rerun_data_path
        from bencher.utils_rrd import rrd_to_pane

        bench_name = self.bench_cfg.bench_name or "bencher"
        recording = rr.RecordingStream(
            f"bencher/{bench_name}", make_default=False, make_thread_default=False
        )

        # Disable log_time before any logging so wall-clock timestamps are never recorded
        recording.disable_timeline("log_time")

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

        # Build dim_values mapping for blueprint construction
        dim_values = {}
        for d in cat_dims:
            dim_values[d] = [str(v) for v in dataset.coords[d].values]
        for d in float_dims:
            dim_values[d] = [str(v) for v in dataset.coords[d].values]

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

        # Build and send blueprint for controlled layout
        blueprint = _build_blueprint(
            rrb=rrb,
            result_vars=rv_list,
            float_dims=float_dims,
            cat_dims=cat_dims,
            time_dim=time_dim,
            dim_values=dim_values,
        )
        recording.send_blueprint(blueprint, make_active=True, make_default=True)

        # Write the recording to an .rrd file and serve via iframe.
        rrd_path = gen_rerun_data_path(bench_name)
        rrd_data = recording.memory_recording().drain_as_bytes()
        with open(rrd_path, "wb") as f:
            f.write(rrd_data)
        # Build a URL relative to the local Flask file server (port 8001)
        url_path = rrd_path.split("cachedir")[1]
        return rrd_to_pane(f"http://127.0.0.1:8001/{url_path}", width=width, height=height)


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
    inside_time_iteration: bool = False,
):
    """Recursively map N-dimensional data to rerun entity paths and timelines.

    Phase 0: iterate over_time as the sole rerun timeline (``log_tick``).
    Phase A: peel categorical dims as entity-tree branches.
    Phase B: map remaining float dims to native rerun archetypes
    (Scalars, BarChart, line graph, or Tensor).
    """
    # --- Phase 0: over_time -> the only rerun timeline ---
    if time_dim and time_dim in dataset.dims:
        for i, coord_val in enumerate(dataset.coords[time_dim].values):
            recording.set_time("log_tick", sequence=i)
            sliced = dataset.sel({time_dim: coord_val})
            _log_to_rerun(
                rr=rr,
                recording=recording,
                dataset=sliced,
                entity_path=entity_path,
                result_vars=result_vars,
                float_dims=float_dims,
                cat_dims=cat_dims,
                time_dim=None,  # consumed
                bench_cfg=bench_cfg,
                inside_time_iteration=True,
            )
        return

    # --- Phase A: peel categorical dims ---
    if cat_dims and float_dims:
        # Cats + floats: peel ALL cats as entity branches
        dim = cat_dims[-1]
        remaining_cat = cat_dims[:-1]
        for val in dataset.coords[dim].values:
            sliced = dataset.sel({dim: val})
            _log_to_rerun(
                rr=rr,
                recording=recording,
                dataset=sliced,
                entity_path=f"{entity_path}/{dim}/{str(val)}",
                result_vars=result_vars,
                float_dims=float_dims,
                cat_dims=remaining_cat,
                time_dim=None,
                bench_cfg=bench_cfg,
                inside_time_iteration=inside_time_iteration,
            )
        return

    if cat_dims and not float_dims and len(cat_dims) > 1:
        # Cat-only: peel until 1 cat remains (last cat -> BarChart axis)
        dim = cat_dims[-1]
        remaining_cat = cat_dims[:-1]
        for val in dataset.coords[dim].values:
            sliced = dataset.sel({dim: val})
            _log_to_rerun(
                rr=rr,
                recording=recording,
                dataset=sliced,
                entity_path=f"{entity_path}/{dim}/{str(val)}",
                result_vars=result_vars,
                float_dims=float_dims,
                cat_dims=remaining_cat,
                time_dim=None,
                bench_cfg=bench_cfg,
                inside_time_iteration=inside_time_iteration,
            )
        return

    # --- Phase B: handle remaining dims ---
    all_dims = list(float_dims)
    if cat_dims:  # at most 1 cat dim remaining (cat-only case)
        all_dims.append(cat_dims[0])

    # Peel extra float dims until <= 3
    if len(all_dims) > 3:
        dim = float_dims[-1]
        remaining_float = float_dims[:-1]
        for val in dataset.coords[dim].values:
            sliced = dataset.sel({dim: val})
            _log_to_rerun(
                rr=rr,
                recording=recording,
                dataset=sliced,
                entity_path=f"{entity_path}/{dim}/{str(val)}",
                result_vars=result_vars,
                float_dims=remaining_float,
                cat_dims=[],
                time_dim=None,
                bench_cfg=bench_cfg,
                inside_time_iteration=inside_time_iteration,
            )
        return

    # --- Base cases ---
    if len(all_dims) == 0:
        # 0D: scalar
        for rv in result_vars:
            _log_result_var(rr, recording, dataset, entity_path, rv)

    elif len(all_dims) == 1:
        dim = all_dims[0]
        if cat_dims and dim == cat_dims[0]:
            # 1D cat -> BarChart
            for rv in result_vars:
                _log_bar_chart(rr, recording, dataset, entity_path, rv, dim)
        elif inside_time_iteration:
            # 1D float inside over_time -> Tensor (timeline already occupied)
            for rv in result_vars:
                _log_tensor(rr, recording, dataset, entity_path, rv, [dim])
        else:
            # 1D float, no over_time -> line graph
            for rv in result_vars:
                _log_line_graph(rr, recording, dataset, entity_path, rv, dim)

    else:
        # 2D or 3D -> Tensor (heatmap / volume slices)
        for rv in result_vars:
            _log_tensor(rr, recording, dataset, entity_path, rv, list(float_dims))


def _log_line_graph(rr, recording, dataset: xr.Dataset, entity_path: str, rv, float_dim: str):
    """Log a 1D float sweep as a line graph by iterating the float dim as log_tick."""
    rv_name = rv.name if hasattr(rv, "name") else str(rv)
    path = f"{entity_path}/{rv_name}" if entity_path else rv_name
    try:
        for i, coord_val in enumerate(dataset.coords[float_dim].values):
            recording.set_time("log_tick", sequence=i)
            sliced = dataset.sel({float_dim: coord_val})
            val = sliced[rv_name].values
            if hasattr(val, "item"):
                val = val.item()
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                recording.log(path, rr.Scalars(float(val)))
    except (KeyError, ValueError, TypeError) as e:
        logging.debug("Could not log line graph for %s: %s", rv_name, e)


def _log_bar_chart(rr, recording, dataset: xr.Dataset, entity_path: str, rv, cat_dim: str):
    """Log a result variable as a BarChart over a categorical dimension."""
    rv_name = rv.name if hasattr(rv, "name") else str(rv)
    path = f"{entity_path}/{rv_name}" if entity_path else rv_name
    try:
        values = []
        for coord_val in dataset.coords[cat_dim].values:
            sliced = dataset.sel({cat_dim: coord_val})
            val = sliced[rv_name].values
            if hasattr(val, "item"):
                val = val.item()
            values.append(float(val) if val is not None else 0.0)
        recording.log(path, rr.BarChart(values))
    except (KeyError, ValueError, TypeError) as e:
        logging.debug("Could not log bar chart for %s: %s", rv_name, e)


def _log_tensor(rr, recording, dataset: xr.Dataset, entity_path: str, rv, dims: list[str]):
    """Log a result variable as an N-D Tensor (heatmap for 2D, volume for 3D)."""
    rv_name = rv.name if hasattr(rv, "name") else str(rv)
    path = f"{entity_path}/{rv_name}" if entity_path else rv_name
    try:
        data_array = dataset[rv_name]
        # Transpose to requested dim order and extract numpy array
        arr = data_array.transpose(*dims).values.astype(np.float32)
        # Replace NaN with 0 so the tensor renders cleanly
        arr = np.nan_to_num(arr, nan=0.0)
        recording.log(path, rr.Tensor(arr, dim_names=dims))
    except (KeyError, ValueError, TypeError) as e:
        logging.debug("Could not log tensor for %s: %s", rv_name, e)


def _log_result_var(rr, recording, dataset: xr.Dataset, entity_path: str, rv):
    """Log a single result variable to rerun at the current entity path."""
    rv_name = rv.name if hasattr(rv, "name") else str(rv)
    path = f"{entity_path}/{rv_name}" if entity_path else rv_name

    try:
        if isinstance(rv, ResultImage):
            val = dataset[rv_name].values
            if hasattr(val, "item"):
                val = val.item()
            if val is not None and val and Path(str(val)).exists():
                recording.log(path, rr.EncodedImage(path=str(val)))
            return

        if isinstance(rv, ResultVideo):
            val = dataset[rv_name].values
            if hasattr(val, "item"):
                val = val.item()
            if val is not None and val and Path(str(val)).exists():
                recording.log(path, rr.AssetVideo(path=str(val)))
            return

        if isinstance(rv, ResultString):
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


def _build_blueprint(rrb, result_vars, float_dims, cat_dims, time_dim, dim_values):
    """Build a rerun Blueprint with typed views matching the data layout."""
    root = _build_blueprint_contents(
        rrb=rrb,
        entity_path="",
        result_vars=result_vars,
        float_dims=float_dims,
        cat_dims=cat_dims,
        time_dim=time_dim,
        dim_values=dim_values,
        inside_time_iteration=False,
    )
    return rrb.Blueprint(root, collapse_panels=True)


def _build_blueprint_contents(
    rrb,
    entity_path: str,
    result_vars: list,
    float_dims: list[str],
    cat_dims: list[str],
    time_dim: str | None,
    dim_values: dict[str, list[str]],
    inside_time_iteration: bool = False,
):
    """Recursively build blueprint containers/views mirroring _log_to_rerun structure."""
    # --- Phase 0: over_time -> just mark inside_time_iteration ---
    if time_dim:
        return _build_blueprint_contents(
            rrb=rrb,
            entity_path=entity_path,
            result_vars=result_vars,
            float_dims=float_dims,
            cat_dims=cat_dims,
            time_dim=None,
            dim_values=dim_values,
            inside_time_iteration=True,
        )

    # --- Phase A: peel categorical dims ---
    if cat_dims and float_dims:
        dim = cat_dims[-1]
        remaining_cat = cat_dims[:-1]
        children = []
        for val in dim_values.get(dim, []):
            child = _build_blueprint_contents(
                rrb=rrb,
                entity_path=f"{entity_path}/{dim}/{val}",
                result_vars=result_vars,
                float_dims=float_dims,
                cat_dims=remaining_cat,
                time_dim=None,
                dim_values=dim_values,
                inside_time_iteration=inside_time_iteration,
            )
            children.append(child)
        n_cols = len(children)
        return rrb.Grid(*children, grid_columns=n_cols, name=dim)

    if cat_dims and not float_dims and len(cat_dims) > 1:
        dim = cat_dims[-1]
        remaining_cat = cat_dims[:-1]
        children = []
        for val in dim_values.get(dim, []):
            child = _build_blueprint_contents(
                rrb=rrb,
                entity_path=f"{entity_path}/{dim}/{val}",
                result_vars=result_vars,
                float_dims=float_dims,
                cat_dims=remaining_cat,
                time_dim=None,
                dim_values=dim_values,
                inside_time_iteration=inside_time_iteration,
            )
            children.append(child)
        n_cols = len(children)
        return rrb.Grid(*children, grid_columns=n_cols, name=dim)

    # --- Phase B: handle remaining dims ---
    all_dims = list(float_dims)
    if cat_dims:
        all_dims.append(cat_dims[0])

    # Peel extra float dims until <= 3
    if len(all_dims) > 3:
        dim = float_dims[-1]
        remaining_float = float_dims[:-1]
        children = []
        for val in dim_values.get(dim, []):
            child = _build_blueprint_contents(
                rrb=rrb,
                entity_path=f"{entity_path}/{dim}/{val}",
                result_vars=result_vars,
                float_dims=remaining_float,
                cat_dims=[],
                time_dim=None,
                dim_values=dim_values,
                inside_time_iteration=inside_time_iteration,
            )
            children.append(child)
        n_cols = len(children)
        return rrb.Grid(*children, grid_columns=n_cols, name=dim)

    # --- Leaf: build views for result variables ---
    def _make_view(rv_name: str):
        path = f"{entity_path}/{rv_name}" if entity_path else rv_name
        if len(all_dims) == 0:
            # 0D scalar -> TimeSeriesView
            return rrb.TimeSeriesView(origin=path, name=rv_name)
        if len(all_dims) == 1:
            dim = all_dims[0]
            if cat_dims and dim == cat_dims[0]:
                return rrb.BarChartView(origin=path, name=rv_name)
            if inside_time_iteration:
                return rrb.TensorView(origin=path, name=rv_name)
            # 1D float line graph
            return rrb.TimeSeriesView(origin=path, name=rv_name)
        # 2D / 3D -> TensorView
        return rrb.TensorView(origin=path, name=rv_name)

    views = []
    for rv in result_vars:
        rv_name = rv.name if hasattr(rv, "name") else str(rv)
        views.append(_make_view(rv_name))

    if len(views) == 1:
        return views[0]
    return rrb.Vertical(*views)
