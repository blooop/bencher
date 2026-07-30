"""Combine the per-sample rerun recordings of a sweep into one viewer.

``ResultRerun`` records one ``.rrd`` per benchmark sample — that is the unit
diskcache keys on, so it has to stay that way.  Rendering a sweep therefore
means one embedded web viewer *per sample*: a 3x3 sweep spawns nine independent
wasm viewers and nothing can be compared across them.

:class:`~bencher.results.composable_container.composable_container_rerun.ComposableContainerRerun`
already knows how to merge several complete recordings into one recording plus
blueprint, but it is driven from inside ``benchmark()``, where only a single
sample's recordings are visible.  This module drives the same container from the
*result* side instead: it walks the result dataset, collects the cached ``.rrd``
path of every sample, and composes them by ``ComposeType``.

Because the container both accepts ``.rrd`` paths and renders to one, nesting is
just recursion — each sweep dimension builds a container whose children are
either leaf sample paths or the rendered output of the dimension below it.

Mirrors :class:`~bencher.results.video_summary.VideoSummaryResult`, which does
the same thing for ``ResultImage``/``ResultVideo`` samples.
"""

from __future__ import annotations

import logging
import os
from copy import deepcopy

import panel as pn
import xarray as xr
from param import Parameter

from bencher.plotting.plot_filter import PlotFilter, VarRange
from bencher.results.bench_result_base import BenchResultBase, ReduceType
from bencher.results.composable_container.composable_container_base import (
    ComposeType,
    compose_method_list_for_dims,
)
from bencher.results.composable_container.composable_container_rerun import (
    ComposableContainerRerun,
)
from bencher.utils import callable_name
from bencher.variables.results import ResultRerun, result_is_missing

logger = logging.getLogger(__name__)


class RerunSummaryResult(BenchResultBase):
    """Renders all ``ResultRerun`` samples of a sweep as one merged recording."""

    def to_rerun_summary(
        self,
        result_var: Parameter | None = None,
        result_types=(ResultRerun,),
        **kwargs,
    ) -> pn.panel | None:
        """Merge every recording into one viewer, played back as a time sequence.

        Every swept dimension is composed in time rather than in space, so the
        samples play one after another on a single timeline instead of tiling
        into nested grids.

        Args:
            result_var (Parameter, optional): The result var to render. Defaults to None (all).
            result_types (tuple, optional): Result types to render. Defaults to (ResultRerun,).
            **kwargs: Passed through to :meth:`to_rerun_grid`.

        Returns:
            pn.panel | None: a panel pane holding a single rerun viewer.
        """
        return self.to_rerun_grid(
            result_var=result_var,
            result_types=result_types,
            time_sequence_dimension=-1,
            **kwargs,
        )

    def to_rerun_grid(
        self,
        result_var: Parameter | None = None,
        result_types=(ResultRerun,),
        pane_collection: pn.pane = None,
        time_sequence_dimension: int = 0,
        compose_method_list: list | None = None,
        reverse: bool = False,
        **kwargs,
    ) -> pn.panel | None:
        """Merge every recording of the sweep into one embedded rerun viewer.

        Args:
            result_var (Parameter, optional): The result var to render. Defaults to None (all).
            result_types (tuple, optional): Result types to render. Defaults to (ResultRerun,).
            pane_collection (pn.pane, optional): Collection to stack multiple result
                vars into. Defaults to ``pn.Row()``.
            time_sequence_dimension (int, optional): Compose dimensions up to this index
                onto a timeline instead of in space. ``-1`` sequences every dimension.
                Defaults to 0.
            compose_method_list (list, optional): Explicit per-dimension composition
                methods, overriding the defaults. See ``bn.ComposeType``.
            reverse (bool, optional): Reverse the dimension order. Defaults to False.
            **kwargs: Passed to the viewer pane (e.g. ``width``, ``height``).

        Returns:
            pn.panel | None: a panel pane holding one rerun viewer per result var.
        """
        plot_filter = PlotFilter(
            float_range=VarRange(0, None),
            cat_range=VarRange(0, None),
            panel_range=VarRange(1, None),
            input_range=VarRange(1, None),
        )
        matches_res = plot_filter.matches_result(
            self.plt_cnt_cfg, callable_name(self.to_rerun_grid), override=False
        )
        if not matches_res.overall:
            return matches_res.to_panel()

        if pane_collection is None:
            pane_collection = pn.Row()

        dataset = self.to_dataset(ReduceType.SQUEEZE, deep=False)
        for rv in self.get_results_var_list(result_var):
            if isinstance(rv, result_types):
                pane = self.to_rerun_grid_ds(
                    dataset,
                    rv,
                    time_sequence_dimension=time_sequence_dimension,
                    compose_method_list=compose_method_list,
                    reverse=reverse,
                    **kwargs,
                )
                if pane is not None:
                    pane_collection.append(pane)
        return pane_collection

    def to_rerun_grid_ds(
        self,
        dataset: xr.Dataset,
        result_var: Parameter,
        time_sequence_dimension: int = 0,
        compose_method_list: list | None = None,
        reverse: bool = False,
        target_dimension: int = 0,
        width: int | None = None,
        height: int | None = None,
        **kwargs,
    ) -> pn.pane.HTML | None:
        """Merge *result_var*'s recordings in *dataset* into one viewer pane.

        Args:
            dataset (xr.Dataset): The dataset holding the benchmark results.
            result_var (Parameter): The result variable to render.
            time_sequence_dimension (int, optional): See :meth:`to_rerun_grid`. Defaults to 0.
            compose_method_list (list, optional): Explicit composition methods.
            reverse (bool, optional): Reverse the dimension order. Defaults to False.
            target_dimension (int, optional): Recursion floor. Defaults to 0.
            width (int, optional): Viewer width. Defaults to the result var's width.
            height (int, optional): Viewer height. Defaults to the result var's height.
            **kwargs: Unused, accepted for parity with other renderers.

        Returns:
            pn.pane.HTML | None: the viewer pane, or None if nothing was recorded.
        """
        from bencher.utils_rrd import rrd_file_to_pane

        merged = self._compose_ds(
            dataset,
            result_var=result_var,
            target_dimension=target_dimension,
            time_sequence_dimension=time_sequence_dimension,
            compose_method_list=compose_method_list,
            reverse=reverse,
        )
        if merged is None:
            logger.debug("no rerun recordings to compose for %s", result_var.name)
            return None

        return rrd_file_to_pane(
            merged,
            width=width if width is not None else result_var.width,
            height=height if height is not None else result_var.height,
        )

    def _compose_ds(
        self,
        dataset: xr.Dataset,
        result_var: Parameter,
        target_dimension: int = 0,
        compose_method: ComposeType = ComposeType.right,
        compose_method_list: list | None = None,
        time_sequence_dimension: int = 0,
        reverse: bool = False,
    ) -> str | None:
        """Recursively compose *dataset* into a single ``.rrd`` path.

        Peels one dimension per level (outermost last, matching
        ``VideoSummaryResult._to_video_panes_ds``).  Each level renders its own
        ``.rrd``, which the level above appends as a child recording, so the
        merge engine in ``ComposableContainerRerun`` is reused unchanged.

        Returns:
            str | None: path to the composed recording, or None if this branch
            of the sweep recorded nothing.
        """
        num_dims = len(dataset.sizes)
        dims = list(dataset.sizes)
        if reverse:
            dims = list(reversed(dims))

        if compose_method_list is None:
            compose_method_list = compose_method_list_for_dims(
                num_dims,
                first_compose_method=compose_method,
                time_sequence_dimension=time_sequence_dimension,
            )

        remaining = deepcopy(compose_method_list)
        if len(remaining) > 1:
            compose_method = remaining.pop()

        if num_dims <= target_dimension or num_dims == 0:
            return self._leaf_path(dataset, result_var)

        selected_dim = dims[-1]
        outer = ComposableContainerRerun(compose_method=compose_method, name=selected_dim)
        for i in range(dataset.sizes[selected_dim]):
            sliced = dataset.isel({selected_dim: i})
            child = self._compose_ds(
                sliced,
                result_var=result_var,
                target_dimension=target_dimension,
                compose_method_list=remaining,
                time_sequence_dimension=time_sequence_dimension,
            )
            if child is None:
                continue
            # Label each child with the slice it represents so the generated
            # blueprint names its view after the swept value.
            label_val = sliced.coords[selected_dim].values.item()
            outer.append(child, label=f"{selected_dim}={label_val}")

        if not outer.container:
            return None
        return outer.render()

    def _leaf_path(self, dataset: xr.Dataset, result_var: Parameter) -> str | None:
        """Return the ``.rrd`` path for a fully-sliced *dataset*, or None if unrecorded."""
        value = self.zero_dim_da_to_val(dataset[result_var.name])
        if result_is_missing(result_var, value):
            return None
        path = str(value)
        if not path or not os.path.isfile(path):
            logger.debug("rerun recording %s missing on disk", path)
            return None
        return path
