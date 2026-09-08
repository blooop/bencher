"""Map a sweep dimension onto a Rerun timeline so the sweep can be scrubbed.

``to_rerun_summary`` already merges a sweep's per-sample ``.rrd`` files into one
recording, but it merges them by *splicing*: each sample keeps whatever timeline
it recorded internally and is shifted to start after the previous one ends.  For
the common case — a benchmark that logs a single static frame per sample — that
leaves nothing meaningful to scrub.  The only timeline is rerun's automatic
``log_time``, the samples land nanoseconds apart on a wall-clock axis, and the
axis says nothing about which parameter value is on screen.

This module composes the same recordings the other way round: one swept
dimension becomes a *named* rerun timeline carrying the parameter's own values,
and every sample is logged at the same entity path.  Scrubbing that timeline
then sweeps the parameter, one sample per tick, with the parameter value written
on the axis.

Scaling past one dimension
--------------------------
Rerun timelines are independent axes, not a joint index: a latest-at query
resolves on the timeline being viewed and ignores the others, so logging a 2-D
sweep as two timelines does not give a 2-D scrubber — parking one axis collapses
the other to whichever sample happened to be logged last.  Only one dimension
can be time.  The remaining dimensions are therefore peeled onto the entity
tree, one branch per coordinate, each with its own Blueprint view: scrubbing the
single timeline advances every branch together, so an N-D sweep reads as a grid
of views animating in lockstep over the timeline dimension.
"""

from __future__ import annotations

import itertools
import logging
import re
from dataclasses import dataclass, field
from typing import Any, assert_never

import numpy as np
import panel as pn
import xarray as xr
from param import Parameter
from strenum import StrEnum

from bencher.plotting.plot_filter import PlotFilter, VarRange
from bencher.results.bench_result_base import BenchResultBase, ReduceType
from bencher.results.composable_container.composable_container_rerun import (
    RerunViewKind,
    _batch_view_kinds,
    views_for_kinds,
)
from bencher.results.rerun_summary import leaf_recording_path
from bencher.utils import callable_name
from bencher.variables.results import ResultRerun

logger = logging.getLogger(__name__)

# Rerun's two automatic timelines. They are re-derived on every log call, so a
# sample's ``log_time`` records when the .rrd happened to be captured, not
# anything about the sweep. Carrying them into the composition would leave the
# viewer defaulting to a wall-clock axis on which the whole sweep is a blip.
_AUTOMATIC_TIMELINES = frozenset({"log_time", "log_tick"})

# Entity path parts are restricted to this alphabet so a coordinate value like
# "0.5 rad" or "a/b" cannot inject a path separator or need escaping.
_UNSAFE_ENTITY_CHARS = re.compile(r"[^0-9A-Za-z_.-]+")


class TimelineIndex(StrEnum):
    """How a swept coordinate is encoded as a rerun index value.

    Rerun has no float timeline: an index is either an integer sequence or a
    nanosecond duration/timestamp. ``value`` therefore encodes a numeric
    coordinate as a duration in seconds, which is the only encoding that keeps
    the parameter's own numbers (and their uneven spacing) on the axis.
    """

    auto = "auto"  # value for numeric coordinates, sequence for everything else
    value = "value"  # duration in seconds; raises on a non-numeric coordinate
    sequence = "sequence"  # 0, 1, 2, ... the sample's position along the dimension


@dataclass(frozen=True)
class _DurationIndex:
    """Coordinates are logged as durations, one second per unit of the parameter."""

    values: tuple[int, ...]  # nanoseconds

    def arrow_type(self):
        import pyarrow as pa

        return pa.duration("ns")


@dataclass(frozen=True)
class _SequenceIndex:
    """Coordinates are logged as their integer position along the dimension."""

    values: tuple[int, ...]

    def arrow_type(self):
        import pyarrow as pa

        return pa.int64()


_IndexEncoding = _DurationIndex | _SequenceIndex


# A duration index is an i64 count of nanoseconds, so a coordinate must land inside
# this range once scaled by 1e9 -- roughly +/- 9.2e9 in parameter units.
_INT64_MIN, _INT64_MAX = -(2**63), 2**63 - 1


def _durations_or_none(coords: np.ndarray) -> tuple[int, ...] | None:
    """Coordinates as nanosecond durations, or None if that would not be faithful.

    Two ways it would not be. Coordinates spaced below a nanosecond round to the
    same index, and samples sharing an index overwrite each other under latest-at --
    the sweep would silently lose every sample but the last at each tick. Coordinates
    beyond about 9.2e9 overflow the i64 the index is stored in. Both are decided here
    rather than at the pyarrow cast so the caller can choose what to do about it.
    """
    if not np.issubdtype(coords.dtype, np.number):
        return None
    values = tuple(round(float(c) * 1e9) for c in coords)
    if any(v < _INT64_MIN or v > _INT64_MAX for v in values):
        return None
    if len(set(values)) < len(values):
        return None
    return values


def encode_index(coords: np.ndarray, index: TimelineIndex, dim: str) -> _IndexEncoding:
    """Encode a dimension's coordinates as rerun index values.

    Args:
        coords: the dimension's coordinate values, in sweep order.
        index: which encoding to use; see :class:`TimelineIndex`.
        dim: the dimension name, used in the log line and error message.

    Raises:
        ValueError: if ``TimelineIndex.value`` is asked for on coordinates that
            cannot be put on a time axis without losing samples.
    """
    match TimelineIndex(index):
        case TimelineIndex.sequence:
            return _SequenceIndex(values=tuple(range(len(coords))))
        case TimelineIndex.value:
            values = _durations_or_none(coords)
            if values is None:
                raise ValueError(
                    f"the coordinates of timeline dimension {dim!r} cannot be placed on a "
                    f"rerun time axis without collapsing samples onto the same index "
                    f"(non-numeric, spaced below a nanosecond, or out of i64 range); "
                    f"pass index=TimelineIndex.sequence"
                )
            return _DurationIndex(values=values)
        case TimelineIndex.auto:
            values = _durations_or_none(coords)
            if values is None:
                logger.debug("numbering the samples of %s instead of timing them", dim)
                return _SequenceIndex(values=tuple(range(len(coords))))
            return _DurationIndex(values=values)
        case _ as unreachable:
            assert_never(unreachable)


def _entity_parts(dim: str, values: list[Any]) -> list[str]:
    """The entity-path segment naming each coordinate of a peeled dimension.

    Two coordinates that sanitize to the same segment ("a/b" and "a_b", say) would
    silently merge into one branch and overwrite each other, so the whole dimension
    falls back to positions when that happens. All-or-nothing rather than
    disambiguating the offenders: a mix of names and numbers in one axis is harder to
    read than numbers throughout.
    """
    parts = [_UNSAFE_ENTITY_CHARS.sub("_", f"{dim}_{value}").strip("_") or "_" for value in values]
    if len(set(parts)) < len(parts):
        logger.debug("coordinates of %s collide as entity paths; numbering them instead", dim)
        return [f"{dim}_{position}" for position in range(len(values))]
    return parts


@dataclass
class _Branch:
    """One entity-tree branch: the samples of the timeline dimension at fixed
    coordinates of every other dimension."""

    prefix: str
    label: str
    chunks: list = field(default_factory=list)
    view_kinds: set[RerunViewKind] = field(default_factory=set)


def _retimed_chunks(chunk, timeline: str, arrow_type, raw_value: int) -> list:
    """Return *chunk* with the automatic timelines dropped and *timeline* pinned.

    Every row of the chunk belongs to one sample, so the whole column is the
    single constant *raw_value*. Timelines the benchmark set itself are kept, so
    a sample that recorded its own ``time_s`` can still be scrubbed within the
    sweep tick it sits on.
    """
    import pyarrow as pa
    from rerun.experimental import Chunk

    batch = chunk.to_record_batch()
    keep = [
        position
        for position, arrow_field in enumerate(batch.schema)
        if arrow_field.name not in _AUTOMATIC_TIMELINES
    ]
    columns = [batch.column(position) for position in keep]
    fields = [batch.schema.field(position) for position in keep]

    time_field = pa.field(
        timeline,
        arrow_type,
        nullable=False,
        metadata={
            b"rerun:index_name": timeline.encode(),
            b"rerun:is_sorted": b"true",
            b"rerun:kind": b"index",
        },
    )
    # After the control columns (RowId), which rerun requires to come first.
    at = sum(1 for f in fields if (f.metadata or {}).get(b"rerun:kind") == b"control")
    columns.insert(at, pa.array([raw_value] * batch.num_rows).cast(arrow_type))
    fields.insert(at, time_field)

    schema = pa.schema(fields, metadata=batch.schema.metadata)
    return Chunk.from_record_batch(pa.RecordBatch.from_arrays(columns, schema=schema))


def _read_branch_chunks(branch: _Branch, path: str, timeline: str, arrow_type, raw: int) -> None:
    """Read one sample's ``.rrd`` into *branch*, re-rooted and re-timed."""
    from rerun.experimental import RrdReader

    reader = RrdReader(path)
    for store in reader.recordings():
        for chunk in reader.stream(store=store):
            source = str(chunk.entity_path).lstrip("/")
            # Recording properties are per-file metadata (start time, app id). Every
            # sample carries one; forwarding them would add a __properties entity to
            # each branch that displays nothing.
            if source.startswith("__properties"):
                continue
            batch = chunk.to_record_batch()
            branch.view_kinds.update(_batch_view_kinds(batch))
            rerooted = chunk.with_entity_path(f"{branch.prefix}/{source}")
            branch.chunks.extend(_retimed_chunks(rerooted, timeline, arrow_type, raw))


def _layout_views(rrb, views: list, branch_dims: list[str]):
    """Arrange one view per branch.

    A 1-D sweep peels nothing and has a single view. One peeled dimension is a row,
    which keeps the branch order (and so the parameter order) readable left to right.
    Two or more peeled dimensions have already lost that ordering to the flattened
    product, so they go in a ``Grid``, which packs them without growing one axis
    without bound.
    """
    if len(views) == 1:
        return views[0]
    if len(branch_dims) == 1:
        return rrb.Horizontal(*views)
    return rrb.Grid(*views)


class RerunTimelineResult(BenchResultBase):
    """Renders a sweep's ``ResultRerun`` samples as one scrubbable recording."""

    def to_rerun_timeline(
        self,
        result_var: Parameter | None = None,
        result_types=(ResultRerun,),
        timeline_dim: str | None = None,
        index: TimelineIndex | str = TimelineIndex.auto,
        pane_collection: pn.pane = None,
        **kwargs,
    ) -> pn.panel | None:
        """Merge every recording into one viewer scrubbed by a swept parameter.

        Args:
            result_var (Parameter, optional): The result var to render. Defaults to None (all).
            result_types (tuple, optional): Result types to render. Defaults to (ResultRerun,).
            timeline_dim (str, optional): Which swept dimension becomes the timeline.
                Defaults to the last (fastest varying) dimension of the dataset.
            index (TimelineIndex | str, optional): How coordinates are encoded as
                index values. Defaults to ``auto``.
            pane_collection (pn.pane, optional): Collection to stack multiple result
                vars into. Defaults to ``pn.Row()``.
            **kwargs: Passed to the viewer pane (e.g. ``width``, ``height``).

        Returns:
            pn.panel | None: a panel pane holding one rerun viewer per result var.
        """
        plot_filter = PlotFilter(
            float_range=VarRange.unbounded(),
            cat_range=VarRange.unbounded(),
            panel_range=VarRange.at_least(1),
            repeats_range=VarRange.at_least(1),
            input_range=VarRange.at_least(1),
        )
        matches_res = plot_filter.matches_result(
            self.plt_cnt_cfg, callable_name(self.to_rerun_timeline), override=False
        )
        if not matches_res.overall:
            return matches_res.to_panel()

        if pane_collection is None:
            pane_collection = pn.Row()

        dataset = self.to_dataset(ReduceType.SQUEEZE, deep=False)
        for rv in self.get_results_var_list(result_var):
            if isinstance(rv, result_types):
                pane = self.to_rerun_timeline_ds(
                    dataset, rv, timeline_dim=timeline_dim, index=index, **kwargs
                )
                if pane is not None:
                    pane_collection.append(pane)
        return pane_collection

    def to_rerun_timeline_ds(
        self,
        dataset: xr.Dataset,
        result_var: Parameter,
        timeline_dim: str | None = None,
        index: TimelineIndex | str = TimelineIndex.auto,
        width: int | None = None,
        height: int | None = None,
        **_kwargs,
    ) -> pn.pane.HTML | None:
        """Render *result_var*'s recordings in *dataset* as one scrubbable viewer.

        Args:
            dataset (xr.Dataset): The dataset holding the benchmark results.
            result_var (Parameter): The result variable to render.
            timeline_dim (str, optional): See :meth:`to_rerun_timeline`.
            index (TimelineIndex | str, optional): See :meth:`to_rerun_timeline`.
            width (int, optional): Viewer width. Defaults to the result var's width.
            height (int, optional): Viewer height. Defaults to the result var's height.
            **_kwargs: Unused, accepted for parity with other renderers (plot
                callbacks are invoked with ``override=``).

        Returns:
            pn.pane.HTML | None: the viewer pane, or None if nothing was recorded.

        Raises:
            ValueError: if *timeline_dim* names a dimension the dataset does not have.
        """
        merged = self.to_rerun_timeline_path(
            dataset, result_var, timeline_dim=timeline_dim, index=index
        )
        if merged is None:
            logger.debug("no rerun recordings to place on a timeline for %s", result_var.name)
            return None

        # A container declared on the result var wins over the rerun viewer, the same
        # precedence to_rerun_grid_ds uses. The composition is itself an .rrd path, so
        # a single-argument renderer applies unchanged.
        render = self.declared_container(result_var)
        if render is not None:
            return render(merged)

        from bencher.utils_rrd import rrd_file_to_pane

        return rrd_file_to_pane(
            merged,
            width=width if width is not None else result_var.width,
            height=height if height is not None else result_var.height,
        )

    def to_rerun_timeline_path(
        self,
        dataset: xr.Dataset,
        result_var: Parameter,
        timeline_dim: str | None = None,
        index: TimelineIndex | str = TimelineIndex.auto,
    ) -> str | None:
        """Compose *result_var*'s recordings into one ``.rrd`` and return its path.

        Split out from :meth:`to_rerun_timeline_ds` so the composition can be
        inspected — by tests, or by anyone who wants the file rather than a pane —
        without a viewer in the way.

        Returns:
            str | None: path to the composed recording, or None if the sweep
            recorded nothing.
        """
        dims = list(dataset.sizes)
        if not dims:
            return None
        if timeline_dim is None:
            timeline_dim = dims[-1]
        elif timeline_dim not in dims:
            raise ValueError(
                f"timeline dimension {timeline_dim!r} is not a dimension of this sweep; "
                f"available: {dims}"
            )

        coords = np.asarray(dataset.coords[timeline_dim].values)
        encoding = encode_index(coords, index, timeline_dim)
        branch_dims = [dim for dim in dims if dim != timeline_dim]

        branches = self._build_branches(dataset, result_var, timeline_dim, branch_dims, encoding)
        if not branches:
            return None
        return _render_recording(branches, branch_dims)

    def _build_branches(
        self,
        dataset: xr.Dataset,
        result_var: Parameter,
        timeline_dim: str,
        branch_dims: list[str],
        encoding: _IndexEncoding,
    ) -> list[_Branch]:
        """One :class:`_Branch` per coordinate combination of *branch_dims*.

        A branch with no recorded sample is dropped rather than emitted empty, so a
        sweep whose recordings are all missing returns nothing at all instead of a
        blueprint full of blank views.
        """
        arrow_type = encoding.arrow_type()
        parts = {dim: _entity_parts(dim, list(dataset.coords[dim].values)) for dim in branch_dims}
        branches = []
        for combo in itertools.product(*(range(dataset.sizes[d]) for d in branch_dims)):
            selector = dict(zip(branch_dims, combo))
            branch_ds = dataset.isel(selector) if selector else dataset
            labels = [f"{dim}={branch_ds.coords[dim].values.item()}" for dim in branch_dims]
            prefix = "".join(
                f"/{parts[dim][position]}" for dim, position in zip(branch_dims, combo)
            )
            branch = _Branch(prefix=prefix, label=", ".join(labels) or timeline_dim)
            for position, raw in enumerate(encoding.values):
                sample = branch_ds.isel({timeline_dim: position})
                path = leaf_recording_path(self, sample, result_var)
                if path is None:
                    continue
                _read_branch_chunks(branch, path, timeline_dim, arrow_type, raw)
            if branch.chunks:
                branches.append(branch)
        return branches


def _render_recording(branches: list[_Branch], branch_dims: list[str]) -> str:
    """Write *branches* to one ``.rrd`` with a Blueprint view per branch."""
    import rerun as rr
    import rerun.blueprint as rrb

    from bencher.utils import gen_rerun_data_path

    # Underscore, not the "bencher/timeline" slash style ComposableContainerRerun uses:
    # rerun 0.37 migrates a slashed application id to a generated entry name and logs a
    # warning on every render saying so.
    recording = rr.RecordingStream(
        "bencher_timeline", make_default=False, make_thread_default=False
    )
    for branch in branches:
        recording.send_chunks(branch.chunks)

    # A 1-D sweep peels no dimension onto the entity tree, so every sample shares the
    # root and one view shows the whole animation.
    views = [
        views_for_kinds(rrb, branch.view_kinds, origin=branch.prefix or "/", label=branch.label)
        for branch in branches
    ]
    blueprint = rrb.Blueprint(
        _layout_views(rrb, views, branch_dims),
        rrb.TimePanel(state="expanded"),
        auto_layout=False,
        auto_views=False,
        collapse_panels=True,
    )
    recording.send_blueprint(blueprint, make_active=True, make_default=True)

    output = gen_rerun_data_path("timeline")
    with open(output, "wb") as handle:
        handle.write(recording.memory_recording().drain_as_bytes())
    return str(output)
