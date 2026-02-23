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
    ResultVar,
    ResultBool,
)
from bencher.plotting.plot_filter import VarRange

# matplotlib tab10 palette as RGBA tuples (0-255)
_TAB10_COLORS = [
    (31, 119, 180, 255),
    (255, 127, 14, 255),
    (44, 160, 44, 255),
    (214, 39, 40, 255),
    (148, 103, 189, 255),
    (140, 86, 75, 255),
    (227, 119, 194, 255),
    (127, 127, 127, 255),
    (188, 189, 34, 255),
    (23, 190, 207, 255),
]


def _category_color(index: int) -> tuple[int, int, int, int]:
    """Return an RGBA color tuple for a categorical index from a 10-color palette."""
    return _TAB10_COLORS[index % len(_TAB10_COLORS)]


class RerunResult(BenchResultBase):
    """Result class that renders N-dimensional benchmark data into a rerun viewer.

    Categorical dimensions become entity path segments (tree branches).
    Float dimensions and over_time become rerun timelines (independently scrubable).
    Result variables become leaf entities with appropriate rerun archetypes.

    New blueprint-aware methods (to_auto_rerun, to_rerun_line, etc.) render data
    using proper rerun archetypes and blueprint layout instead of timelines.
    """

    def to_rerun(
        self,
        result_var: Optional[Parameter] = None,
        width: int = 950,
        height: int = 712,
    ) -> pn.pane.panel:  # pragma: no cover
        """Convert N-dimensional benchmark results to a rerun viewer (legacy timeline-based).

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
        rrd_path = gen_rerun_data_path(bench_name)
        rrd_data = recording.memory_recording().drain_as_bytes()
        with open(rrd_path, "wb") as f:
            f.write(rrd_data)
        # Build a URL relative to the local Flask file server (port 8001)
        url_path = rrd_path.split("cachedir")[1]
        return rrd_to_pane(f"http://127.0.0.1:8001/{url_path}", width=width, height=height)

    # ==================== BLUEPRINT-BASED PLOT METHODS ====================

    def to_auto_rerun(
        self,
        result_var: Optional[Parameter] = None,
        width: int = 950,
        height: int = 712,
    ) -> pn.pane.panel:  # pragma: no cover
        """Automatically generate blueprint-based rerun views for all applicable plot types.

        Iterates over rerun_plot_callbacks(), collects views, builds a blueprint,
        writes an .rrd file, and returns a Panel iframe pane.

        Args:
            result_var: Optional specific result variable to display.
            width: Width of the rerun viewer widget.
            height: Height of the rerun viewer widget.

        Returns:
            A panel pane containing the rerun viewer with blueprint layout.
        """
        import rerun as rr
        from bencher.utils import gen_rerun_data_path
        from bencher.utils_rerun import rrd_to_pane
        from bencher.results.rerun_blueprint_builder import RerunBlueprintBuilder

        bench_name = self.bench_cfg.bench_name or "bencher"
        recording = rr.RecordingStream(
            f"bencher/{bench_name}", make_default=False, make_thread_default=False
        )

        builder = RerunBlueprintBuilder()

        for plot_cb in self.rerun_plot_callbacks():
            try:
                views = plot_cb(self, recording=recording, result_var=result_var)
                if views is not None:
                    if isinstance(views, list):
                        builder.add_views(views)
                    else:
                        builder.add_view(views)
            except (KeyError, ValueError, TypeError, AttributeError) as e:
                logging.debug("Rerun plot callback %s failed: %s", plot_cb.__name__, e)

        blueprint = builder.build(include_time_panel=self.bench_cfg.over_time)
        rr.send_blueprint(blueprint, recording=recording)

        rrd_path = gen_rerun_data_path(bench_name)
        rrd_data = recording.memory_recording().drain_as_bytes()
        with open(rrd_path, "wb") as f:
            f.write(rrd_data)
        url_path = rrd_path.split("cachedir")[1]
        return rrd_to_pane(f"http://127.0.0.1:8001/{url_path}", width=width, height=height)

    def to_rerun_line(
        self,
        recording=None,
        result_var: Optional[Parameter] = None,
    ) -> list | None:  # pragma: no cover
        """Render line plots using rr.LineStrips2D in rrb.Spatial2DView.

        Filter: float_range=(1,1), cat_range=(0,None), repeats=(1,1)
        Float var values -> X coords, result values -> Y coords.
        Categorical var -> separate colored LineStrips2D per cat value.
        """
        import rerun as rr
        import rerun.blueprint as rrb

        # Check filter match
        if not self._rerun_filter_matches(
            float_range=VarRange(1, 1),
            cat_range=VarRange(0, None),
            repeats_range=VarRange(1, 1),
        ):
            return None

        dataset = self.to_dataset(reduce=ReduceType.SQUEEZE, result_var=result_var)
        rv_list = self.get_results_var_list(result_var)
        float_var = self.plt_cnt_cfg.float_vars[0]
        x_values = dataset.coords[float_var.name].values.astype(float)
        cat_vars = self.plt_cnt_cfg.cat_vars

        views = []
        for rv in rv_list:
            if not isinstance(rv, (ResultVar, ResultBool)):
                continue
            rv_name = rv.name

            if len(cat_vars) > 0:
                cat_var = cat_vars[0]
                cat_values = dataset.coords[cat_var.name].values
                for ci, cat_val in enumerate(cat_values):
                    sliced = dataset.sel({cat_var.name: cat_val})
                    y_values = sliced[rv_name].values.astype(float)
                    points = np.column_stack([x_values, y_values])
                    entity = f"{rv_name}/line/{cat_var.name}/{cat_val}"
                    color = _category_color(ci)
                    recording.log(
                        entity,
                        rr.LineStrips2D([points], colors=[color]),
                    )
            else:
                y_values = dataset[rv_name].values.astype(float)
                points = np.column_stack([x_values, y_values])
                entity = f"{rv_name}/line"
                recording.log(entity, rr.LineStrips2D([points]))

            view = rrb.Spatial2DView(
                name=f"{rv_name} line",
                origin=f"{rv_name}/line",
            )
            views.append(view)

        return views if views else None

    def to_rerun_bar(
        self,
        recording=None,
        result_var: Optional[Parameter] = None,
    ) -> list | None:  # pragma: no cover
        """Render bar charts using rr.BarChart in rrb.BarChartView.

        Filter: float_range=(0,0), cat_range=(1,None), repeats=(1,1)
        Category labels logged as companion rr.TextDocument.
        """
        import rerun as rr
        import rerun.blueprint as rrb

        if not self._rerun_filter_matches(
            float_range=VarRange(0, 0),
            cat_range=VarRange(1, None),
            repeats_range=VarRange(1, 1),
        ):
            return None

        dataset = self.to_dataset(reduce=ReduceType.SQUEEZE, result_var=result_var)
        rv_list = self.get_results_var_list(result_var)

        views = []
        for rv in rv_list:
            if not isinstance(rv, (ResultVar, ResultBool)):
                continue
            rv_name = rv.name
            values = dataset[rv_name].values.flatten().astype(float)
            entity = f"{rv_name}/bar"
            recording.log(entity, rr.BarChart(values))

            # Log category labels as text document
            cat_labels = []
            for cv in self.plt_cnt_cfg.cat_vars:
                cat_labels.extend([str(v) for v in dataset.coords[cv.name].values])
            if cat_labels:
                label_text = ", ".join(cat_labels)
                recording.log(f"{rv_name}/bar_labels", rr.TextDocument(label_text))

            view = rrb.BarChartView(
                name=f"{rv_name} bar",
                origin=f"{rv_name}/bar",
            )
            views.append(view)

        return views if views else None

    def to_rerun_curve(
        self,
        recording=None,
        result_var: Optional[Parameter] = None,
    ) -> list | None:  # pragma: no cover
        """Render curve plots (mean +/- std) using rr.LineStrips2D in rrb.Spatial2DView.

        Filter: float_range=(1,1), cat_range=(0,None), repeats=(2,None)
        Logs 3 line strips: mean, upper (mean+std), lower (mean-std).
        """
        import rerun as rr
        import rerun.blueprint as rrb

        if not self._rerun_filter_matches(
            float_range=VarRange(1, 1),
            cat_range=VarRange(0, None),
            repeats_range=VarRange(2, None),
        ):
            return None

        dataset = self.to_dataset(reduce=ReduceType.REDUCE, result_var=result_var)
        rv_list = self.get_results_var_list(result_var)
        float_var = self.plt_cnt_cfg.float_vars[0]
        x_values = dataset.coords[float_var.name].values.astype(float)

        views = []
        for rv in rv_list:
            if not isinstance(rv, (ResultVar, ResultBool)):
                continue
            rv_name = rv.name
            std_name = f"{rv_name}_std"

            if rv_name not in dataset.data_vars:
                continue
            mean_values = dataset[rv_name].values.flatten().astype(float)
            if std_name in dataset.data_vars:
                std_values = dataset[std_name].values.flatten().astype(float)
            else:
                std_values = np.zeros_like(mean_values)

            upper_values = mean_values + std_values
            lower_values = mean_values - std_values

            mean_pts = np.column_stack([x_values, mean_values])
            upper_pts = np.column_stack([x_values, upper_values])
            lower_pts = np.column_stack([x_values, lower_values])

            recording.log(
                f"{rv_name}/curve/mean",
                rr.LineStrips2D([mean_pts], colors=[(31, 119, 180, 255)]),
            )
            recording.log(
                f"{rv_name}/curve/upper",
                rr.LineStrips2D([upper_pts], colors=[(31, 119, 180, 100)]),
            )
            recording.log(
                f"{rv_name}/curve/lower",
                rr.LineStrips2D([lower_pts], colors=[(31, 119, 180, 100)]),
            )

            view = rrb.Spatial2DView(
                name=f"{rv_name} curve",
                origin=f"{rv_name}/curve",
            )
            views.append(view)

        return views if views else None

    def to_rerun_heatmap(
        self,
        recording=None,
        result_var: Optional[Parameter] = None,
    ) -> list | None:  # pragma: no cover
        """Render heatmaps using rr.Tensor in rrb.TensorView.

        Filter: input_range=(2,None)
        """
        import rerun as rr
        import rerun.blueprint as rrb

        if not self._rerun_filter_matches(input_range=VarRange(2, None)):
            return None

        dataset = self.to_dataset(reduce=ReduceType.SQUEEZE, result_var=result_var)
        rv_list = self.get_results_var_list(result_var)

        views = []
        for rv in rv_list:
            if not isinstance(rv, (ResultVar, ResultBool)):
                continue
            rv_name = rv.name
            data = dataset[rv_name].values
            if data.ndim < 2:
                continue
            # Take 2D slice (first two dims)
            while data.ndim > 2:
                data = data[0]
            entity = f"{rv_name}/heatmap"
            recording.log(entity, rr.Tensor(data.astype(float)))

            view = rrb.TensorView(
                name=f"{rv_name} heatmap",
                origin=entity,
            )
            views.append(view)

        return views if views else None

    def to_rerun_histogram(
        self,
        recording=None,
        result_var: Optional[Parameter] = None,
    ) -> list | None:  # pragma: no cover
        """Render histograms using np.histogram -> rr.BarChart in rrb.BarChartView.

        Filter: input_range=(0,0), repeats=(2,None)
        """
        import rerun as rr
        import rerun.blueprint as rrb

        if not self._rerun_filter_matches(
            input_range=VarRange(0, 0),
            repeats_range=VarRange(2, None),
        ):
            return None

        dataset = self.to_dataset(reduce=ReduceType.NONE, result_var=result_var)
        rv_list = self.get_results_var_list(result_var)

        views = []
        for rv in rv_list:
            if not isinstance(rv, (ResultVar,)):
                continue
            rv_name = rv.name
            data = dataset[rv_name].values.flatten()
            data = data[~np.isnan(data)]
            if len(data) == 0:
                continue
            counts, _ = np.histogram(data, bins="auto")
            entity = f"{rv_name}/histogram"
            recording.log(entity, rr.BarChart(counts.astype(float)))

            view = rrb.BarChartView(
                name=f"{rv_name} histogram",
                origin=entity,
            )
            views.append(view)

        return views if views else None

    def to_rerun_scatter(
        self,
        recording=None,
        result_var: Optional[Parameter] = None,
    ) -> list | None:  # pragma: no cover
        """Render scatter plots using rr.Points2D in rrb.Spatial2DView.

        Filter: float_range=(0,0), cat_range=(1,None), repeats=(2,None)
        """
        import rerun as rr
        import rerun.blueprint as rrb

        if not self._rerun_filter_matches(
            float_range=VarRange(0, 0),
            cat_range=VarRange(1, None),
            repeats_range=VarRange(2, None),
        ):
            return None

        dataset = self.to_dataset(reduce=ReduceType.NONE, result_var=result_var)
        rv_list = self.get_results_var_list(result_var)

        views = []
        for rv in rv_list:
            if not isinstance(rv, (ResultVar, ResultBool)):
                continue
            rv_name = rv.name
            data = dataset[rv_name].values.flatten()
            data = data[~np.isnan(data.astype(float))]
            if len(data) == 0:
                continue

            # X axis is the sample index, Y axis is the value
            x = np.arange(len(data), dtype=float)
            y = data.astype(float)
            positions = np.column_stack([x, y])

            entity = f"{rv_name}/scatter"
            recording.log(entity, rr.Points2D(positions))

            view = rrb.Spatial2DView(
                name=f"{rv_name} scatter",
                origin=entity,
            )
            views.append(view)

        return views if views else None

    def _rerun_filter_matches(
        self,
        float_range: VarRange | None = None,
        cat_range: VarRange | None = None,
        repeats_range: VarRange | None = None,
        input_range: VarRange | None = None,
    ) -> bool:
        """Check if the current data dimensions match the given filter criteria."""
        cfg = self.plt_cnt_cfg
        if float_range is not None and not float_range.matches(cfg.float_cnt):
            return False
        if cat_range is not None and not cat_range.matches(cfg.cat_cnt):
            return False
        if repeats_range is not None and not repeats_range.matches(cfg.repeats):
            return False
        if input_range is not None and not input_range.matches(cfg.inputs_cnt):
            return False
        return True

    @staticmethod
    def rerun_plot_callbacks() -> list:
        """Return the list of rerun plot callback methods to iterate in to_auto_rerun."""
        return [
            RerunResult.to_rerun_line,
            RerunResult.to_rerun_bar,
            RerunResult.to_rerun_curve,
            RerunResult.to_rerun_heatmap,
            RerunResult.to_rerun_histogram,
            RerunResult.to_rerun_scatter,
        ]


# ==================== LEGACY TIMELINE-BASED HELPERS ====================


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
