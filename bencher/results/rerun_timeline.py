"""Map a sweep dimension onto a Rerun timeline so the sweep can be scrubbed.

This is the **rerun backend's implementation of the ``panes`` chart type**. Where the
panel backend lays a sweep's samples out as a grid of images, one pane per sample,
this lays them along a rerun timeline named after the swept variable: the samples
share an entity path, so latest-at does the animation and dragging the cursor sweeps
the parameter. Both are registered under the name ``panes``, so
``BenchRunCfg(backend="rerun")`` swaps one for the other with nothing else changing.

Rerun's timeline is the only scrubber it has, so a sweep axis has to be expressed as
one -- but it does not have to pretend to be a clock. An integer *sequence* index is
labelled ``#3`` with no unit, so a polygon with three sides sits at ``#3``; see
:class:`TimelineIndex`.

Any result type can go on the timeline. A ``ResultRerun`` already *is* a recording,
so its cached ``.rrd`` chunks are re-indexed onto the sweep timeline; everything
else is logged onto the same timeline through the same archetype mapping the rerun
backend uses for the entity tree
(:func:`~bencher.results.rerun_result._log_result_var`) -- images as
``rr.EncodedImage``, numbers as ``rr.Scalars``, and so on. A swept float alongside
an image therefore reads as a time series *of* the sweep, moving in step with it.

Why not just splice the recordings
----------------------------------
``to_rerun_summary`` merges a sweep's recordings by splicing: each sample keeps
whatever timeline it recorded internally and is shifted to start after the previous
one ends. A benchmark that logs a single static frame per sample has no such
timeline, and rerun's automatic ``log_time`` cannot be written to (``set_time`` on
it is ignored, the SDK always stamps wall clock), so there is nothing to splice and
nothing to play.

Scaling past one dimension
--------------------------
Rerun timelines are independent axes, not a joint index: a latest-at query resolves
on the timeline being viewed and ignores the others, so logging a 2-D sweep as two
timelines does not give a 2-D scrubber -- parking one axis collapses the other to
whichever sample happened to be logged last. Only one dimension can be time. The
remaining dimensions are peeled onto the entity tree, one branch per coordinate,
each with its own Blueprint view: scrubbing the single timeline advances every
branch together, so an N-D sweep reads as a grid of views animating in lockstep
over the timeline dimension.
"""

from __future__ import annotations

import importlib.util
import itertools
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, assert_never

import numpy as np
import panel as pn
import xarray as xr
from param import Number, Parameter
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
from bencher.variables.inputs import with_subsampling_divisions
from bencher.variables.results import (
    PANEL_TYPES,
    ResultImage,
    ResultRerun,
    ResultString,
    ResultVideo,
)

logger = logging.getLogger(__name__)

# The timelines a sample's chunks lose on the way into the composition. Only the
# wall clock: rerun stamps ``log_time`` on every log call and it cannot be
# overwritten, so it records when the .rrd happened to be captured rather than
# anything about the sweep, and carrying it through would offer the viewer an axis
# on which the whole sweep is a blip. Rerun's other built-in timeline, ``log_tick``,
# is not in here: it is only written to a chunk when the benchmark set it, and
# bencher's own over-time recordings do exactly that (see
# :func:`~bencher.results.rerun_result._log_to_rerun`), so dropping it would throw
# away an axis somebody chose rather than an axis nobody did.
_DROPPED_TIMELINES = frozenset({"log_time"})

# Entity path parts are restricted to this alphabet so a coordinate value like
# "0.5 rad" or "a/b" cannot inject a path separator or need escaping.
_UNSAFE_ENTITY_CHARS = re.compile(r"[^0-9A-Za-z_.-]+")

# Which Blueprint view displays each result type, given the archetype
# ``_log_result_var`` writes for it (named in the comments). A ``ResultRerun`` is
# absent because its view kinds are read back from the recording's own archetypes.
_RESULT_VIEW_KINDS: dict[type, RerunViewKind] = {
    ResultImage: RerunViewKind.spatial_2d,  # rr.EncodedImage
    ResultVideo: RerunViewKind.spatial_2d,  # rr.AssetVideo
    ResultString: RerunViewKind.text_document,  # rr.TextDocument
}


# The sweep shapes a timeline can be made of. Registered as the rerun ``panes``
# plugin's match rule as well as checked inside the renderer: selection resolves a
# chart type to one backend, so a rule the registry cannot see would let the rerun
# implementation win a 0-D sweep and then decline to draw it -- losing the panel
# implementation's output rather than falling back to it.
TIMELINE_PLOT_FILTER = PlotFilter(
    float_range=VarRange.unbounded(),
    cat_range=VarRange.unbounded(),
    panel_range=VarRange.unbounded(),
    repeats_range=VarRange.at_least(1),
    # A timeline needs a dimension to be made of; a 0-D sweep has none.
    input_range=VarRange.at_least(1),
)


def _view_kind_for(result_var: Parameter) -> RerunViewKind | None:
    """The view kind for a directly-logged result var, or None if it has no mapping.

    None rather than a default: ``_log_result_var`` warns and skips a result type it
    has no archetype for, and inventing a view for data that was never logged would
    put an empty panel in the report where the warning should be the only trace.
    """
    for result_type, kind in _RESULT_VIEW_KINDS.items():
        if isinstance(result_var, result_type):
            return kind
    # Numeric family (ResultFloat/ResultBool/param.Number subclasses) -> rr.Scalars.
    if isinstance(result_var, Number):
        return RerunViewKind.time_series
    return None


class TimelineIndex(StrEnum):
    """How a swept coordinate is encoded as a rerun index value.

    Rerun offers two kinds of index: an integer *sequence*, which the viewer labels
    ``#3`` with no unit, and a nanosecond duration or timestamp, which it labels
    ``+3s``. A sweep axis is neither a clock nor a stopwatch, so the sequence is the
    honest one -- ``#3`` for a polygon with three sides says what it means, where
    ``+3s`` claims a unit the parameter does not have.
    """

    #: Integer ticks. The coordinate's own value where that is a whole number, the
    #: sample's position otherwise. No unit on the axis either way.
    tick = "tick"
    #: The sample's position, 0, 1, 2, ..., whatever the coordinates are.
    position = "position"
    #: A duration, one second per unit of the parameter. Reads as time, and is the
    #: only encoding that shows a non-uniform sweep as non-uniform.
    duration = "duration"


@dataclass(frozen=True)
class _DurationIndex:
    """Coordinates are logged as durations, one second per unit of the parameter."""

    values: tuple[int, ...]  # nanoseconds

    #: The axis shows the parameter's own numbers, so nothing else has to.
    shows_values = True

    def arrow_type(self):
        import pyarrow as pa

        return pa.duration("ns")

    def set_time(self, recording, timeline: str, raw: int) -> None:
        # numpy, not timedelta: timedelta rounds to microseconds, which would merge
        # coordinates that differ in the nanosecond digits.
        recording.set_time(timeline, duration=np.timedelta64(raw, "ns"))


@dataclass(frozen=True)
class _SequenceIndex:
    """Coordinates are logged as integer ticks.

    ``shows_values`` says whether those ticks *are* the coordinates (an integer
    sweep) or merely count the samples (anything else). When they only count, the
    parameter's actual value has to be legible somewhere else, so the renderer adds a
    read-out of it against the tick.
    """

    values: tuple[int, ...]
    shows_values: bool

    def arrow_type(self):
        import pyarrow as pa

        return pa.int64()

    def set_time(self, recording, timeline: str, raw: int) -> None:
        recording.set_time(timeline, sequence=raw)


_IndexEncoding = _DurationIndex | _SequenceIndex

# Both index kinds are stored in an i64: a tick is that integer directly, a duration
# is a count of nanoseconds, so a coordinate must land inside this range once scaled
# by 1e9 -- roughly +/- 9.2e9 in parameter units.
_INT64_MIN, _INT64_MAX = -(2**63), 2**63 - 1


def _usable(values: tuple[int, ...]) -> bool:
    """Whether an i64 index column can carry *values* without losing a sample.

    Two ways it cannot. Values outside the i64 range do not fit. Repeated values put
    two samples on one index, and samples sharing an index overwrite each other under
    latest-at -- the sweep would silently lose every sample but the last at each tick.
    Both are decided here rather than at the pyarrow cast so the caller can choose
    what to do about it.
    """
    if any(v < _INT64_MIN or v > _INT64_MAX for v in values):
        return False
    return len(set(values)) == len(values)


def _ticks_or_none(coords: np.ndarray) -> tuple[int, ...] | None:
    """Coordinates as integer ticks, or None if they are not whole numbers."""
    if not np.issubdtype(coords.dtype, np.number):
        return None
    floats = [float(c) for c in coords]
    if not all(f.is_integer() for f in floats):
        return None
    values = tuple(int(f) for f in floats)
    return values if _usable(values) else None


def _durations_or_none(coords: np.ndarray) -> tuple[int, ...] | None:
    """Coordinates as nanosecond durations, or None if that would lose a sample.

    Coordinates spaced below a nanosecond round to the same index, which ``_usable``
    catches as a repeat.
    """
    if not np.issubdtype(coords.dtype, np.number):
        return None
    values = tuple(round(float(c) * 1e9) for c in coords)
    return values if _usable(values) else None


def encode_index(coords: np.ndarray, index: TimelineIndex, dim: str) -> _IndexEncoding:
    """Encode a dimension's coordinates as rerun index values.

    Args:
        coords: the dimension's coordinate values, in sweep order.
        index: which encoding to use; see :class:`TimelineIndex`.
        dim: the dimension name, used in the log line and error message.

    Raises:
        ValueError: if ``TimelineIndex.duration`` is asked for on coordinates that
            cannot be put on a time axis without losing samples.
    """
    positions = _SequenceIndex(values=tuple(range(len(coords))), shows_values=False)
    match TimelineIndex(index):
        case TimelineIndex.position:
            return positions
        case TimelineIndex.duration:
            values = _durations_or_none(coords)
            if values is None:
                raise ValueError(
                    f"the coordinates of timeline dimension {dim!r} cannot be placed on a "
                    f"rerun time axis without collapsing samples onto the same index "
                    f"(non-numeric, spaced below a nanosecond, or out of i64 range); "
                    f"pass index=TimelineIndex.tick"
                )
            return _DurationIndex(values=values)
        case TimelineIndex.tick:
            values = _ticks_or_none(coords)
            if values is None:
                logger.debug("counting the samples of %s: its values are not whole ticks", dim)
                return positions
            return _SequenceIndex(values=values, shows_values=True)
        case _ as unreachable:
            assert_never(unreachable)


def default_timeline_dim(dataset: xr.Dataset, dims: list[str]) -> str:
    """Which dimension to animate when the caller does not say.

    A time axis reads as a continuum, so a numeric dimension is preferred over a
    categorical one however the sweep was declared, and the longest such dimension is
    preferred over a shorter one -- it makes the animation and leaves the small axes
    to tile as branches. Ties go to the last dimension, the fastest-varying one, which
    is what ``to_rerun_summary`` and ``to_video_summary`` sequence.

    Taking the last dimension unconditionally instead made a 3-value colour axis the
    timeline of a sweep whose other axis had five, which is the wrong way round: three
    scrub ticks and five side-by-side views of one polygon each.
    """
    numeric = [
        dim
        for dim in dims
        if np.issubdtype(np.asarray(dataset.coords[dim].values).dtype, np.number)
    ]
    candidates = numeric or dims
    return max(candidates, key=lambda dim: (dataset.sizes[dim], candidates.index(dim)))


def _coord_label(value: Any) -> str:
    """A coordinate as a reader would write it.

    A sweep's endpoints are exact but its interior is arithmetic, so a five-step
    range over -0.1..0.1 has a step that ``str`` renders as 0.05000000000000002.
    Rounding to six significant figures -- past any sweep resolution -- and taking
    the shortest repr of *that* keeps a float looking like one (1.0, not 1) while
    dropping the noise. Ties it creates are caught by :func:`_entity_parts`.
    """
    if isinstance(value, (float, np.floating)):
        return repr(float(f"{float(value):.6g}"))
    return str(value)


def _entity_parts(dim: str, values: list[Any]) -> list[str]:
    """The entity-path segment naming each coordinate of a peeled dimension.

    Two coordinates that sanitize to the same segment ("a/b" and "a_b", say) would
    silently merge into one branch and overwrite each other, so the whole dimension
    falls back to positions when that happens. All-or-nothing rather than
    disambiguating the offenders: a mix of names and numbers in one axis is harder to
    read than numbers throughout.
    """
    parts = [
        _UNSAFE_ENTITY_CHARS.sub("_", f"{dim}_{_coord_label(value)}").strip("_") or "_"
        for value in values
    ]
    if len(set(parts)) < len(parts):
        logger.debug("coordinates of %s collide as entity paths; numbering them instead", dim)
        return [f"{dim}_{position}" for position in range(len(values))]
    return parts


@dataclass
class _View:
    """One entity origin, which becomes one Blueprint view.

    There is one per (branch, result variable): a result var gets its own origin so
    an image and a scalar swept together are two views side by side rather than one
    view asked to draw both.
    """

    origin: str
    label: str
    view_kinds: set[RerunViewKind] = field(default_factory=set)
    logged: bool = False


def _rewrite_chunk(chunk, timeline: str, arrow_type=None, raw_value: int | None = None) -> list:
    """Return *chunk* with ``log_time`` dropped, optionally re-indexed.

    Dropping ``log_time`` is unconditional: it says when the data happened to be
    captured, and leaving it in the composition offers the viewer a wall-clock axis
    on which the whole sweep is a blip. Rerun stamps it on every ``log()`` call and
    ``set_time`` cannot overwrite it, so the only way to be rid of it is to rewrite
    the chunk after the fact.

    *raw_value* adds the sweep index, for chunks that came from a sample's own ``.rrd``
    and so have no idea where in the sweep they sit. Every row of such a chunk belongs
    to one sample, so the whole column is that one constant. Timelines the benchmark
    set itself are kept either way, so a sample that recorded its own ``time_s`` can
    still be scrubbed within the sweep tick it sits on.
    """
    import pyarrow as pa
    from rerun.experimental import Chunk

    batch = chunk.to_record_batch()
    keep = [
        position
        for position, arrow_field in enumerate(batch.schema)
        if arrow_field.name not in _DROPPED_TIMELINES
    ]
    columns = [batch.column(position) for position in keep]
    fields = [batch.schema.field(position) for position in keep]

    if raw_value is not None:
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
    elif len(keep) == batch.num_columns:
        return [chunk]

    schema = pa.schema(fields, metadata=batch.schema.metadata)
    return Chunk.from_record_batch(pa.RecordBatch.from_arrays(columns, schema=schema))


def _forward_stage(recording, staged_path: str, timeline: str) -> None:
    """Move a staging recording's chunks into *recording*, stripping ``log_time``.

    Everything that is not a ``ResultRerun`` is logged with ``recording.log()``, which
    means rerun stamps ``log_time`` on it. Staging those logs in a recording of their
    own and forwarding them through one rewrite pass costs a single extra file for the
    whole composition, rather than a rewrite per sample.
    """
    from rerun.experimental import RrdReader

    reader = RrdReader(staged_path)
    for store in reader.recordings():
        for chunk in reader.stream(store=store):
            if str(chunk.entity_path).lstrip("/").startswith("__properties"):
                continue
            recording.send_chunks(_rewrite_chunk(chunk, timeline))


def _send_recording(recording, view: _View, path: str, timeline: str, arrow_type, raw: int) -> None:
    """Re-root one sample's ``.rrd`` under *view*, re-timed onto the sweep timeline."""
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
            view.view_kinds.update(_batch_view_kinds(batch))
            view.logged = True
            rerooted = chunk.with_entity_path(f"{view.origin}/{source}")
            recording.send_chunks(_rewrite_chunk(rerooted, timeline, arrow_type, raw))


# How much of the viewer the read-out strip takes. It is a legend for the cursor,
# not a panel to study, so it gets the sliver that makes it legible and no more.
_READOUT_ROW_SHARES = (6, 1)


def _layout_views(rrb, branches: list[list], branch_sizes: dict[str, int], readout=None):
    """Arrange the views, grouped by branch, over the read-out strip.

    Each branch's result variables are stacked vertically so a sample's image and its
    metrics stay together; the branches are then laid out beside each other. One
    peeled dimension is a row, which keeps the branch order (and so the parameter
    order) readable left to right. With two dimensions, the first defines columns and
    the second rows. Higher dimensions combine into rows, with the first dimension
    still defining columns. The column count comes from the
    sampled coordinates, so resizing cannot rearrange the axes.

    Flattening branch and variable into one row instead put a 3-colour sweep of an
    image and a metric into six columns, none of them wide enough to read.

    *readout* is the swept parameter's value against the index. It spans the bottom
    rather than standing as a branch of its own: it reads against the time cursor, so
    it belongs on the axis the cursor moves along, and as a column it both stole a
    branch's width and sat nowhere near the scrubber it annotates.
    """
    groups = [
        (views[0] if len(views) == 1 else rrb.Vertical(*views))
        if views
        else rrb.TextDocumentView(name="No recording", contents=[])
        for views in branches
    ]
    if len(groups) == 1:
        layout = groups[0]
    elif len(branch_sizes) <= 1:
        layout = rrb.Horizontal(*groups)
    else:
        columns = branch_sizes[next(iter(branch_sizes))]
        rows = len(groups) // columns
        ordered = [groups[col * rows + row] for row in range(rows) for col in range(columns)]
        layout = rrb.Grid(*ordered, grid_columns=columns)
    if readout is None:
        return layout
    return rrb.Vertical(layout, readout, row_shares=list(_READOUT_ROW_SHARES))


def _readout_entity(dim: str) -> str:
    """Entity path of the swept parameter's value read-out.

    Under ``sweep/`` rather than beside the result variables so it cannot collide
    with one that happens to share the dimension's name.
    """
    return f"/sweep/{dim}"


def _declared_size(result_vars: list[Parameter], attribute: str, fallback: int) -> int:
    """The largest *attribute* declared by any result var, or *fallback*.

    Only a ``ResultRerun`` carries viewer sizing, so a sweep of images has none to
    read and falls back to the size the other rerun renderers default to.
    """
    sizes = [
        getattr(rv, attribute)
        for rv in result_vars
        if isinstance(getattr(rv, attribute, None), int)
    ]
    return max(sizes) if sizes else fallback


class RerunTimelineResult(BenchResultBase):
    """Renders a sweep as one rerun recording scrubbed by a swept parameter."""

    def to_rerun_timeline(
        self,
        result_var: Parameter | None = None,
        timeline_dim: str | None = None,
        index: TimelineIndex | str = TimelineIndex.tick,
        subsampling_divisions: int | None = None,
        width: int | None = None,
        height: int | None = None,
        **_kwargs,
    ) -> pn.panel | None:
        """Render the sweep as one rerun viewer scrubbed by a swept parameter.

        This is the ``panes`` chart type under ``backend="rerun"``, so it is selected
        automatically there and never under ``backend="panel"``.

        Args:
            result_var (Parameter, optional): Render only this result var, whatever its
                type. Defaults to None: every result var the panel ``panes`` would
                tile (``PANEL_TYPES``), in one recording, scrubbed together.
            timeline_dim (str, optional): Which swept dimension becomes the timeline.
                Defaults to the longest numeric dimension; see
                :func:`default_timeline_dim`.
            index (TimelineIndex | str, optional): How coordinates are encoded as
                index values. Defaults to ``TimelineIndex.tick``.
            subsampling_divisions (int, optional): Thin the *branch* dimensions to
                this resolution, leaving the timeline at full sample resolution.
                The panel ``panes`` implementation thins what it tiles, and what
                this one tiles is branches -- a tick is a slider position, not a
                panel, so thinning it costs resolution and buys no room.
                Defaults to None (every sample).
            width (int, optional): Viewer width. Defaults to the widest ``width``
                declared by a rendered result var, else 950.
            height (int, optional): Viewer height, chosen the same way, else 712.
            **_kwargs: Unused, accepted because plot callbacks are invoked with
                ``override=`` and the panel plot-size keywords.

        Returns:
            pn.panel | None: a pane holding one rerun viewer, or a message pane when
                there is nothing to put on a timeline.
        """
        matches_res = TIMELINE_PLOT_FILTER.matches_result(
            self.plt_cnt_cfg, callable_name(self.to_rerun_timeline), override=False
        )
        if not matches_res.overall:
            return matches_res.to_panel()

        if importlib.util.find_spec("rerun") is None:
            return pn.pane.Markdown(
                "**rerun** is not installed. Install it with `pip install rerun-sdk`."
            )

        result_vars = self.get_results_var_list(result_var)
        if result_var is None:
            # The same result types the panel implementation of `panes` tiles. A
            # scalar is not this chart type's job on either backend -- `line` and
            # `heatmap` already plot it -- and giving each one its own view in each
            # branch shrank the scene the sweep is actually about. Naming a result
            # var explicitly still puts anything on the timeline.
            result_vars = [rv for rv in result_vars if isinstance(rv, PANEL_TYPES)]
        if not result_vars:
            return None

        dataset = self.to_dataset(ReduceType.SQUEEZE, deep=False)
        merged = self.to_rerun_timeline_path(
            dataset,
            result_vars,
            timeline_dim=timeline_dim,
            index=index,
            subsampling_divisions=subsampling_divisions,
        )
        if merged is None:
            logger.debug("no samples to place on a rerun timeline")
            return None

        # A container declared on the result var wins over the rerun viewer, the same
        # precedence to_rerun_grid_ds and the over_time path use. The composition is
        # one .rrd path, so it only applies to a single result var -- with several in
        # one recording there is no one var whose container should win.
        if len(result_vars) == 1:
            render = self.declared_container(result_vars[0])
            if render is not None:
                return render(merged)

        from bencher.utils_rrd import rrd_file_to_pane

        return rrd_file_to_pane(
            merged,
            width=width if width is not None else _declared_size(result_vars, "width", 950),
            height=height if height is not None else _declared_size(result_vars, "height", 712),
        )

    def to_rerun_timeline_path(
        self,
        dataset: xr.Dataset,
        result_vars: list[Parameter],
        timeline_dim: str | None = None,
        index: TimelineIndex | str = TimelineIndex.tick,
        subsampling_divisions: int | None = None,
    ) -> str | None:
        """Compose *result_vars* into one ``.rrd`` on a timeline and return its path.

        Split out from :meth:`to_rerun_timeline` so the composition can be inspected
        -- by tests, or by anyone who wants the file rather than a pane -- without a
        viewer in the way.

        Returns:
            str | None: path to the composed recording, or None if the sweep recorded
            nothing that could go on a timeline.

        Raises:
            ValueError: if *timeline_dim* names a dimension the dataset does not have.
        """
        dims = list(dataset.sizes)
        if not dims:
            return None
        if timeline_dim is None:
            timeline_dim = default_timeline_dim(dataset, dims)
        elif timeline_dim not in dims:
            raise ValueError(
                f"timeline dimension {timeline_dim!r} is not a dimension of this sweep; "
                f"available: {dims}"
            )

        branch_dims = [dim for dim in dims if dim != timeline_dim]
        if subsampling_divisions is not None and branch_dims:
            # Only the branches. Each one is a panel on screen and they are what
            # runs out of width; the timeline is a slider, where a dropped sample
            # is resolution lost for nothing gained.
            dataset = dataset.sel(
                {
                    dim: with_subsampling_divisions(
                        dataset.coords[dim].to_numpy(), subsampling_divisions
                    )
                    for dim in branch_dims
                }
            )
        coords = np.asarray(dataset.coords[timeline_dim].values)
        encoding = encode_index(coords, index, timeline_dim)

        import rerun as rr
        import rerun.blueprint as rrb

        from bencher.utils import gen_rerun_data_path

        # Underscore, not the "bencher/timeline" slash style ComposableContainerRerun
        # uses: rerun 0.37 migrates a slashed application id to a generated entry name
        # and logs a warning on every render saying so.
        recording = rr.RecordingStream(
            "bencher_timeline", make_default=False, make_thread_default=False
        )
        branches, readout = self._log_sweep(
            recording, dataset, result_vars, timeline_dim, branch_dims, encoding
        )
        if not any(branches):
            return None

        # Each sample owns exactly one tick, so a view must show that tick and no
        # other. Latest-at would otherwise carry an entity forward from whichever
        # sample logged it last: the samples that share an entity path overwrite and
        # look animated, and the ones that do not -- a sweep over configurations,
        # where each names its own parts -- pile up instead of replacing.
        here = rrb.TimeRangeBoundary.cursor_relative(seq=0)
        cursor_only = [rrb.VisibleTimeRange(timeline_dim, start=here, end=here)]
        blueprint = rrb.Blueprint(
            _layout_views(
                rrb,
                [
                    [
                        views_for_kinds(
                            rrb,
                            view.view_kinds,
                            origin=view.origin,
                            label=view.label,
                            time_ranges=cursor_only,
                        )
                        for view in branch
                    ]
                    for branch in branches
                ],
                {dim: dataset.sizes[dim] for dim in branch_dims},
                # No cursor range on the read-out: it is a curve over the whole
                # sweep with a cursor line on it, and one visible point is not that.
                readout=None
                if readout is None
                else views_for_kinds(
                    rrb, readout.view_kinds, origin=readout.origin, label=readout.label
                ),
            ),
            # Pinned, not left to the viewer: a sample that recorded its own inner
            # timeline puts a second axis in the composition, and the sweep is the one
            # the report is about, so it is the one the viewer should open on.
            rrb.TimePanel(state="expanded", timeline=timeline_dim),
            auto_layout=False,
            auto_views=False,
            collapse_panels=True,
        )
        recording.send_blueprint(blueprint, make_active=True, make_default=True)

        output = gen_rerun_data_path("timeline")
        with open(output, "wb") as handle:
            handle.write(recording.memory_recording().drain_as_bytes())
        return str(output)

    def _log_value_readout(
        self,
        staging,
        dataset: xr.Dataset,
        timeline_dim: str,
        encoding: _IndexEncoding,
    ) -> _View | None:
        """Show the swept parameter's value against the index, when the index hides it.

        A tick index that carries the coordinates already says ``#3`` for a polygon
        with three sides, and a duration axis reads the numbers off directly; neither
        needs this. But a sweep whose values are not whole numbers falls back to
        counting samples, and then nothing on screen says which value the cursor is
        parked on -- so the value goes in a read-out of its own, moving with the same
        cursor.

        Numbers are plotted as a time series, which shows where in the range the
        cursor sits as well as the value. Categories have no position to plot, so they
        are written out as text instead; without it a string sweep is a row of ``#0``,
        ``#1``, ``#2`` with no trace of ``cube`` or ``sphere`` anywhere in the viewer.

        Returns:
            _View | None: the read-out's view, or None when the axis already shows
            the values.
        """
        import rerun as rr

        if encoding.shows_values:
            return None
        coords = np.asarray(dataset.coords[timeline_dim].values)
        numeric = bool(np.issubdtype(coords.dtype, np.number))
        origin = _readout_entity(timeline_dim)
        for raw, value in zip(encoding.values, coords):
            encoding.set_time(staging, timeline_dim, raw)
            if numeric:
                staging.log(origin, rr.Scalars(float(value)))
            else:
                staging.log(origin, rr.TextDocument(f"{timeline_dim} = {value}"))
        staging.reset_time()
        return _View(
            origin=origin,
            label=timeline_dim,
            view_kinds={RerunViewKind.time_series if numeric else RerunViewKind.text_document},
            logged=True,
        )

    def _log_sweep(
        self,
        recording,
        dataset: xr.Dataset,
        result_vars: list[Parameter],
        timeline_dim: str,
        branch_dims: list[str],
        encoding: _IndexEncoding,
    ) -> tuple[list[list[_View]], _View | None]:
        """Log every sample onto the sweep timeline; return its views and the read-out.

        A view that received nothing is dropped. Empty branches retain their slots
        in the Cartesian product so missing recordings cannot shift later cells to
        another row or column. The caller omits an entirely empty composition.

        Returns:
            The branch views, grouped by branch, and the value read-out — separate
            because the read-out is laid out along the bottom rather than as a branch.
        """
        import rerun as rr

        from bencher.results.rerun_result import _log_result_var

        # Directly-logged result vars go through a staging recording so their
        # SDK-stamped log_time can be stripped in one pass; see _forward_stage.
        staging = rr.RecordingStream(
            "bencher_timeline_stage", make_default=False, make_thread_default=False
        )
        staged_any = False
        arrow_type = encoding.arrow_type()
        parts = {dim: _entity_parts(dim, list(dataset.coords[dim].values)) for dim in branch_dims}
        branches: list[list[_View]] = []
        for combo in itertools.product(*(range(dataset.sizes[dim]) for dim in branch_dims)):
            branch_ds = dataset.isel(dict(zip(branch_dims, combo))) if branch_dims else dataset
            prefix = "".join(
                f"/{parts[dim][position]}" for dim, position in zip(branch_dims, combo)
            )
            branch_label = ", ".join(
                f"{dim}={_coord_label(branch_ds.coords[dim].values.item())}" for dim in branch_dims
            )
            branch_views: list[_View] = []
            for result_var in result_vars:
                label = result_var.name
                if branch_label:
                    label = f"{label} ({branch_label})"
                view = _View(origin=f"{prefix}/{result_var.name}", label=label)
                for position, raw in enumerate(encoding.values):
                    sample = branch_ds.isel({timeline_dim: position})
                    if isinstance(result_var, ResultRerun):
                        path = leaf_recording_path(self, sample, result_var)
                        if path is not None:
                            _send_recording(recording, view, path, timeline_dim, arrow_type, raw)
                        continue
                    kind = _view_kind_for(result_var)
                    if kind is None:
                        # _log_result_var would warn once per sample; say it once.
                        logger.warning(
                            "No rerun timeline mapping for result var %s of type %s; skipping",
                            result_var.name,
                            type(result_var).__name__,
                        )
                        break
                    encoding.set_time(staging, timeline_dim, raw)
                    _log_result_var(rr, staging, sample, prefix, result_var)
                    staged_any = True
                    view.view_kinds.add(kind)
                    view.logged = True
                staging.reset_time()
                if view.logged:
                    branch_views.append(view)
            branches.append(branch_views)

        readout = self._log_value_readout(staging, dataset, timeline_dim, encoding)
        if readout is not None:
            staged_any = True

        if staged_any:
            from bencher.utils import gen_rerun_data_path

            staged_path = gen_rerun_data_path("timeline_stage")
            with open(staged_path, "wb") as handle:
                handle.write(staging.memory_recording().drain_as_bytes())
            _forward_stage(recording, staged_path, timeline_dim)
            # Purely an intermediate: the composition is what callers are handed.
            Path(staged_path).unlink(missing_ok=True)
        return branches, readout
