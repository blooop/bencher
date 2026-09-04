from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

import numpy as np
import panel as pn
import xarray as xr
from param import Number, Parameter

from bencher.results.bench_result_base import BenchResultBase, ReduceType
from bencher.results.rerun_summary import RerunSummaryResult
from bencher.variables.results import (
    ResultImage,
    ResultRerun,
    ResultString,
    ResultVideo,
    result_is_missing,
)

logger = logging.getLogger(__name__)


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

    A ``ResultRerun`` skips all three phases: its samples are already recordings, so
    :class:`~bencher.results.rerun_summary.RerunSummaryResult` merges them into a
    viewer of their own instead. See :meth:`to_rerun`.
    """

    def to_rerun(
        self,
        result_var: Parameter | str | None = None,
        width: int = 950,
        height: int = 712,
    ) -> pn.panel:  # pragma: no cover
        """Convert N-dimensional benchmark results to a rerun viewer.

        Result variables are rendered in two ways, because ``ResultRerun`` samples
        are *already* rerun recordings and there is nothing to map onto a scalar
        archetype:

        - Everything else is mapped onto the entity tree by :func:`_log_to_rerun`
          and written to one ``.rrd``, embedded as a single viewer.
        - Each ``ResultRerun`` has its per-sample ``.rrd`` files merged into one
          recording by :meth:`RerunSummaryResult.to_rerun_grid_ds`, embedded as its
          own viewer sized by that result var's ``width``/``height``.

        Requires the Flask file server to be running (call
        ``bch.run_flask_in_thread()`` first).

        Args:
            result_var: Optional specific result variable, by object or by name, to
                display. If None, all are shown.
            width: Width of the viewer holding the mapped (non-``ResultRerun``) data.
            height: Height of the viewer holding the mapped (non-``ResultRerun``) data.

        Returns:
            A panel pane containing the rerun viewer, or a Column of them when a
            ``ResultRerun`` is swept alongside other result variables.
        """
        # Checked once here rather than in each helper below, both of which need the SDK.
        if importlib.util.find_spec("rerun") is None:
            return pn.pane.Markdown(
                "**rerun** is not installed. Install it with `pip install rerun-sdk`."
            )

        rv_list = self._to_rerun_result_vars(result_var)
        # A ResultRerun holds one .rrd path per sample. Sending that path through the
        # scalar renderers dropped every recording from the report with a
        # "could not convert string to float" warning (#1134), so the two families are
        # split here and rendered by the machinery that fits each.
        recorded = [rv for rv in rv_list if isinstance(rv, ResultRerun)]
        mapped = [rv for rv in rv_list if not isinstance(rv, ResultRerun)]

        panes = []
        # Nothing to map means an empty recording, so it is skipped — unless there are
        # no result vars at all, where the empty viewer is still the honest answer.
        if mapped or not recorded:
            panes.append(
                self._to_rerun_mapped(mapped, result_var=result_var, width=width, height=height)
            )
        panes.extend(self._to_rerun_recordings(recorded))
        if not panes:
            # Every result var was a recording and none of them merged, so the mapped
            # viewer was skipped and there is nothing left to embed. Say which vars
            # came up empty; an empty Column renders as a hole in the report.
            names = ", ".join(f"`{rv.name}`" for rv in recorded)
            return pn.pane.Markdown(f"No rerun recordings to show for {names}.")
        if len(panes) == 1:
            return panes[0]
        return pn.Column(*panes)

    def _to_rerun_result_vars(
        self, result_var: Parameter | str | None
    ) -> list[Parameter]:  # pragma: no cover
        """The result vars to render, resolving one named by string to its Parameter.

        ``to_dataset`` accepts a result var either way and the ``hasattr(rv, "name")``
        fallbacks in this module exist for the string form, so a name does reach here
        unresolved. The partition in :meth:`to_rerun` classifies by type, and a string
        is not a ``ResultRerun`` however it is spelled, so an unresolved name sent the
        recording back through the scalar renderers -- #1134 again, by another door.

        Raises:
            ValueError: the name matches no result var of this sweep. Handing it back
                unresolved would put a ``str`` in a list of ``Parameter`` and leave the
                same misclassification one layer down.
        """
        declared = list(self.bench_cfg.result_vars)
        if result_var is None:
            return declared
        name = result_var if isinstance(result_var, str) else result_var.name
        resolved = [rv for rv in declared if rv.name == name]
        if not resolved:
            raise ValueError(
                f"{name!r} is not a result var of this sweep; declared: "
                f"{[rv.name for rv in declared]}"
            )
        return resolved

    def _to_rerun_recordings(self, result_vars: list) -> list[pn.panel]:  # pragma: no cover
        """One merged viewer per ``ResultRerun``, or none if it recorded nothing.

        ``to_rerun_grid_ds`` is called unbound because ``RerunResult`` does not inherit
        ``RerunSummaryResult``: both are mixed into ``BenchResult``, which is what
        supplies the ``_compose_ds`` the call reaches for through ``self``.
        """
        if not result_vars:
            return []
        dataset = self.to_dataset(ReduceType.SQUEEZE, deep=False)
        panes = []
        for rv in result_vars:
            pane = RerunSummaryResult.to_rerun_grid_ds(self, dataset, rv)
            if pane is None:
                # Both meanings of the None above, because it does not distinguish
                # them: never sampled, or sampled and the .rrd no longer on disk.
                logger.warning(
                    "No rerun recordings to merge for result var %r: nothing was "
                    "recorded, or the .rrd files have left the cache",
                    rv.name,
                )
                continue
            panes.append(pane)
        return panes

    def _to_rerun_mapped(
        self,
        result_vars: list,
        result_var: Parameter | None,
        width: int,
        height: int,
    ) -> pn.panel:  # pragma: no cover
        """Map *result_vars* onto the rerun entity tree and embed them as one viewer.

        ``result_var`` narrows the dataset exactly as :meth:`to_rerun`'s argument of
        the same name does; ``result_vars`` is what actually gets logged, which is a
        different list whenever a ``ResultRerun`` was filtered out of it.
        """
        import rerun as rr
        import rerun.blueprint as rrb

        from bencher.utils import gen_rerun_data_path
        from bencher.utils_rrd import rrd_file_to_pane

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
            result_vars=result_vars,
            float_dims=float_dims,
            cat_dims=cat_dims,
            time_dim=time_dim,
        )

        # Build and send blueprint for controlled layout
        blueprint = _build_blueprint(
            rrb=rrb,
            result_vars=result_vars,
            float_dims=float_dims,
            cat_dims=cat_dims,
            time_dim=time_dim,
            dim_values=dim_values,
        )
        recording.send_blueprint(blueprint, make_active=True, make_default=True)

        # Write the recording to an .rrd file and serve via the Panel static route.
        rrd_path = gen_rerun_data_path(bench_name)
        rrd_data = recording.memory_recording().drain_as_bytes()
        with open(rrd_path, "wb") as f:
            f.write(rrd_data)
        return rrd_file_to_pane(rrd_path, width=width, height=height)

    def to_rerun_plots(self, **kwargs) -> pn.panel:  # pragma: no cover
        """Plot callback for the rerun backend — drop-in replacement for ``to_auto_plots``.

        Renders the sweep summary, the rerun viewer, and the post-description,
        mirroring the structure of ``BenchResult.to_auto_plots`` so that switching
        ``backend="rerun"`` on ``BenchRunCfg`` produces a familiar report layout.
        """
        plot_cols = pn.Column()
        plot_cols.append(self.bench_cfg.to_sweep_summary(name="Plots View"))
        plot_cols.append(self.to_rerun(**kwargs))
        plot_cols.append(self.bench_cfg.to_post_description())
        return plot_cols


def _rv_name_and_path(entity_path: str, rv) -> tuple[str, str]:
    """Return (rv_name, entity_path/rv_name) for a result variable."""
    rv_name = rv.name if hasattr(rv, "name") else str(rv)
    path = f"{entity_path}/{rv_name}" if entity_path else rv_name
    return rv_name, path


def _extract_scalar(dataset: xr.Dataset, rv_name: str, sel: dict | None = None):
    """Extract a scalar value from *dataset[rv_name]*, optionally slicing first."""
    da = dataset[rv_name]
    if sel:
        da = da.sel(sel)
    val = da.values
    if hasattr(val, "item"):
        val = val.item()
    return val


def _log_to_rerun(
    rr,
    recording,
    dataset: xr.Dataset,
    entity_path: str,
    result_vars: list,
    float_dims: list[str],
    cat_dims: list[str],
    time_dim: str | None,
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
                entity_path=f"{entity_path}/{dim}/{val!s}",
                result_vars=result_vars,
                float_dims=float_dims,
                cat_dims=remaining_cat,
                time_dim=None,
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
                entity_path=f"{entity_path}/{dim}/{val!s}",
                result_vars=result_vars,
                float_dims=float_dims,
                cat_dims=remaining_cat,
                time_dim=None,
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
                entity_path=f"{entity_path}/{dim}/{val!s}",
                result_vars=result_vars,
                float_dims=remaining_float,
                cat_dims=[],
                time_dim=None,
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
    rv_name, path = _rv_name_and_path(entity_path, rv)
    try:
        for i, coord_val in enumerate(dataset.coords[float_dim].values):
            val = _extract_scalar(dataset, rv_name, {float_dim: coord_val})
            if result_is_missing(rv, val):
                # Never-sampled point: skip the tick so the plot shows a genuine
                # gap instead of a fabricated value (plan 23 C12).
                continue
            recording.set_time("log_tick", sequence=i)
            recording.log(path, rr.Scalars(float(val)))
    except (KeyError, ValueError, TypeError) as e:
        logger.warning("Could not log line graph for %s at %r: %s", rv_name, path, e)


def _log_bar_chart(rr, recording, dataset: xr.Dataset, entity_path: str, rv, cat_dim: str):
    """Log a result variable as a BarChart over a categorical dimension."""
    rv_name, path = _rv_name_and_path(entity_path, rv)
    try:
        values = []
        for coord_val in dataset.coords[cat_dim].values:
            val = _extract_scalar(dataset, rv_name, {cat_dim: coord_val})
            # A never-sampled category stays NaN (rendered as a gap) rather than
            # being fabricated as a real zero-height bar (plan 23 C12).
            values.append(float("nan") if result_is_missing(rv, val) else float(val))
        recording.log(path, rr.BarChart(values))
    except (KeyError, ValueError, TypeError) as e:
        logger.warning("Could not log bar chart for %s at %r: %s", rv_name, path, e)


def _log_tensor(rr, recording, dataset: xr.Dataset, entity_path: str, rv, dims: list[str]):
    """Log a result variable as an N-D Tensor (heatmap for 2D, volume for 3D)."""
    rv_name, path = _rv_name_and_path(entity_path, rv)
    try:
        data_array = dataset[rv_name]
        # Transpose to requested dim order, then blank every missing cell BEFORE
        # coercing to float. `result_is_missing` is the only oracle that knows a
        # type's sentinel, and the sentinel is not always NaN: the -1 family
        # (ResultReference, pre-plan-22 ResultDataSet cells) is *finite*, so an
        # np.isfinite filter alone would plot -1 as real data and drag
        # value_range's floor down to it (plan 23 C12).
        raw = data_array.transpose(*dims).values
        arr = np.array(
            [float("nan") if result_is_missing(rv, v) else v for v in raw.ravel()],
            dtype=np.float32,
        ).reshape(raw.shape)
        # Surviving NaNs stay NaN so the viewer shows genuine gaps instead of
        # fabricated zeros.
        finite = arr[np.isfinite(arr)]
        if finite.size == 0:
            logger.warning(
                "Tensor for %s at %r contains no recorded values; skipping", rv_name, path
            )
            return
        # Pass value_range so the viewer maps the colormap to the actual data range
        vmin, vmax = float(finite.min()), float(finite.max())
        if vmin == vmax:
            vmax = vmin + 1.0
        recording.log(path, rr.Tensor(arr, dim_names=dims, value_range=[vmin, vmax]))
    except (KeyError, ValueError, TypeError) as e:
        logger.warning("Could not log tensor for %s at %r: %s", rv_name, path, e)


def _log_result_var(rr, recording, dataset: xr.Dataset, entity_path: str, rv):
    """Log a single result variable to rerun at the current entity path."""
    rv_name, path = _rv_name_and_path(entity_path, rv)

    try:
        val = _extract_scalar(dataset, rv_name)
        if result_is_missing(rv, val):
            # Never-sampled point: nothing to log — a genuine gap (plan 23 C12).
            return

        if isinstance(rv, ResultImage):
            if val and Path(str(val)).exists():
                recording.log(path, rr.EncodedImage(path=str(val)))
            return

        if isinstance(rv, ResultVideo):
            if val and Path(str(val)).exists():
                recording.log(path, rr.AssetVideo(path=str(val)))
            return

        if isinstance(rv, ResultString):
            recording.log(path, rr.TextDocument(str(val)))
            return

        # Numeric family (ResultFloat/ResultBool/param.Number subclasses) -> Scalars.
        if isinstance(rv, Number):
            recording.log(path, rr.Scalars(float(val)))
            return

        # No blind float() fallthrough: a type without a rerun mapping (e.g.
        # ResultPath) surfaces visibly instead of being coerced (plan 23 C12).
        logger.warning(
            "No rerun mapping for result var %s of type %s at %r; skipping",
            rv_name,
            type(rv).__name__,
            path,
        )

    except (KeyError, ValueError, TypeError) as e:
        logger.warning("Could not log result var %s at %r: %s", rv_name, path, e)


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


def _peel_dim_as_grid(rrb, entity_path, dim, dim_values, build_child):
    """Build a Grid by peeling *dim* and calling *build_child* for each value."""
    children = []
    for val in dim_values.get(dim, []):
        children.append(build_child(f"{entity_path}/{dim}/{val}"))
    if not children:
        return rrb.Vertical()
    return rrb.Grid(*children, grid_columns=len(children), name=dim)


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

    def _recurse(ep, *, fd=float_dims, cd=cat_dims, td=None, it=inside_time_iteration):
        return _build_blueprint_contents(rrb, ep, result_vars, fd, cd, td, dim_values, it)

    # --- Phase 0: over_time -> just mark inside_time_iteration ---
    if time_dim:
        return _recurse(entity_path, it=True)

    # --- Phase A: peel categorical dims ---
    if cat_dims and float_dims:
        dim = cat_dims[-1]
        rc = cat_dims[:-1]
        return _peel_dim_as_grid(
            rrb,
            entity_path,
            dim,
            dim_values,
            lambda ep: _recurse(ep, cd=rc),
        )

    if cat_dims and not float_dims and len(cat_dims) > 1:
        dim = cat_dims[-1]
        rc = cat_dims[:-1]
        return _peel_dim_as_grid(
            rrb,
            entity_path,
            dim,
            dim_values,
            lambda ep: _recurse(ep, cd=rc),
        )

    # --- Phase B: handle remaining dims ---
    all_dims = list(float_dims)
    if cat_dims:
        all_dims.append(cat_dims[0])

    # Peel extra float dims until <= 3
    if len(all_dims) > 3:
        dim = float_dims[-1]
        rf = float_dims[:-1]
        return _peel_dim_as_grid(
            rrb,
            entity_path,
            dim,
            dim_values,
            lambda ep: _recurse(ep, fd=rf, cd=[]),
        )

    # --- Leaf: build views for result variables ---
    views = [
        _make_leaf_view(rrb, entity_path, rv, all_dims, cat_dims, inside_time_iteration)
        for rv in result_vars
    ]
    if len(views) == 1:
        return views[0]
    return rrb.Vertical(*views)


def _make_leaf_view(rrb, entity_path, rv, all_dims, cat_dims, inside_time_iteration):
    """Build a single typed rerun view for a result variable."""
    rv_name = rv.name if hasattr(rv, "name") else str(rv)
    _, path = _rv_name_and_path(entity_path, rv_name)
    if len(all_dims) == 0:
        return rrb.TimeSeriesView(origin=path, name=rv_name)
    if len(all_dims) == 1:
        dim = all_dims[0]
        if cat_dims and dim == cat_dims[0]:
            return rrb.BarChartView(origin=path, name=rv_name)
        if inside_time_iteration:
            return rrb.TensorView(origin=path, name=rv_name)
        return rrb.TimeSeriesView(origin=path, name=rv_name)
    return rrb.TensorView(origin=path, name=rv_name)
