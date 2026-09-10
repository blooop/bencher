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
    _index_fields,
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

#: Dataset attribute naming two per-sample variables to draw as a tracking scatter
#: beneath the timeline -- every sample as a point, the cursor's own picked out. Set
#: by the producer of the sweep (``Bench.plot_pareto_front`` stamps the study's two
#: objectives), because which pair is worth plotting against each other is a fact
#: about the sweep and not something a renderer can infer from dtypes.
READOUT_SCATTER_ATTR = "bencher_readout_scatter"

#: Dataset attribute naming the tracking scatter's plot, e.g. "Pareto front". Only
#: the producer of a sweep knows what the set of samples *is*, and that is what a
#: title says; without one the plot is drawn with its axes labelled and no title.
READOUT_SCATTER_TITLE_ATTR = "bencher_readout_scatter_title"

# Everything the plot draws is coloured for a light ground. Rerun's *web* viewer --
# the one a published report embeds -- renders light, where a pale label is invisible;
# its desktop viewer renders dark. Nothing in the data model is theme-aware, so one
# of the two has to be chosen, and it is the one reports are read in.
#
# The tracking scatter's colours. The front is context and the cursor is the subject,
# so the whole set is drawn faint and one point is drawn solid on top of it.
_SCATTER_ALL_COLOR = (120, 130, 150)
_SCATTER_CURRENT_COLOR = (235, 140, 0)
# The cursor's label is logged apart from its marker so the two can differ: rerun
# draws a label in its entity's colour, so the marker's amber would be the text's
# colour too, and amber on the pale pill cannot be read.
_SCATTER_LABEL_COLOR = (0, 0, 0)
# Logged in place of the cursor's marker at a tick whose sample has no position:
# an empty batch is what clears an entity latest-at would otherwise carry forward.
_NO_POINTS = np.zeros((0, 2))

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
    #: ``((x_min, x_max), (y_min, y_max))`` to open a 2-D view on, for a view that
    #: draws its own frame and labels: fit to the data alone would crop them.
    bounds: tuple[tuple[float, float], tuple[float, float]] | None = None


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


def _sample_chunks(path: str):
    """Yield ``(entity, chunk)`` for every data chunk in one sample's ``.rrd``.

    Recording properties are per-file metadata (start time, app id). Every sample
    carries one; forwarding them would add a ``__properties`` entity to each branch
    that displays nothing, so they are not data and are not yielded.
    """
    from rerun.experimental import RrdReader

    reader = RrdReader(path)
    for store in reader.recordings():
        for chunk in reader.stream(store=store):
            entity = str(chunk.entity_path).lstrip("/")
            if entity.startswith("__properties"):
                continue
            yield entity, chunk


def _content_key(batch) -> bytes:
    """A digest of what a chunk says, ignoring the row ids rerun stamps on it.

    Two chunks that say the same thing about the same components digest the same
    whichever file they came from: the ``RowId`` control column is minted per log
    call and the wall clock per capture, so both are left out. Arrow IPC is the
    medium because it serialises schema and data together deterministically, where
    hashing the buffers directly would see padding and offsets that differ between
    equal arrays.
    """
    import hashlib

    import pyarrow as pa

    keep = [
        position
        for position, arrow_field in enumerate(batch.schema)
        if (arrow_field.metadata or {}).get(b"rerun:kind") != b"control"
        and arrow_field.name not in _DROPPED_TIMELINES
    ]
    # Field metadata carries the component identity and is kept, but re-ordered:
    # rerun writes it from a hash map, so two files spell the same metadata in a
    # different order and the IPC bytes would differ over nothing.
    fields = [
        pa.field(
            arrow_field.name,
            arrow_field.type,
            arrow_field.nullable,
            metadata=dict(sorted((arrow_field.metadata or {}).items())),
        )
        for arrow_field in (batch.schema.field(position) for position in keep)
    ]
    subset = pa.RecordBatch.from_arrays(
        [batch.column(position) for position in keep], schema=pa.schema(fields)
    )
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, subset.schema) as writer:
        writer.write_batch(subset)
    return hashlib.blake2b(sink.getvalue().to_pybytes(), digest_size=16).digest()


def _shared_entities(samples: list[tuple[int, str]], n_ticks: int) -> set[str]:
    """The entities that every one of a branch's samples records identically.

    Such an entity is the same picture at every tick, so it can be logged once, as
    static data, and the viewer shows it at every tick anyway; logging it per tick
    stores one copy per sample of something that never changes. A benchmark that
    draws a robot with a quarter-million triangles and then sweeps a sensor mount
    across it is the case this exists for: the mount moves, the robot does not, and
    without this the robot is most of the file, repeated once per tick.

    Static is the only safe form for a shared copy. The branch views are pinned to
    the cursor's own tick (see :meth:`RerunTimelineResult.to_rerun_timeline_path`), so
    an entity logged at one tick is invisible at the others whatever latest-at would
    say; static data shows under every time range. And static overrides temporal
    for the same component, which is why the decision is per *entity* and needs
    every chunk of it to match: a component that is static from one chunk and
    per-tick from another would have the static copy win at every tick.

    An entity is shared only when the branch has a sample at every tick -- a tick
    with no recording must show nothing, and a static copy would show there too --
    and only when none of its chunks carries a timeline of the benchmark's own: a
    sample that recorded its own ``time_s`` has an inner axis to keep, which static
    data has none of.
    """
    if len(samples) != n_ticks:
        return set()
    # keys[entity] is the sorted digests of the entity's chunks, or None where a
    # chunk of it has an inner timeline and so the entity is out of the running.
    per_tick: list[dict[str, list[bytes] | None]] = []
    for _, path in samples:
        keys: dict[str, list[bytes] | None] = {}
        for entity, chunk in _sample_chunks(path):
            if entity in keys and keys[entity] is None:
                continue
            batch = chunk.to_record_batch()
            if any(f.name not in _DROPPED_TIMELINES for f in _index_fields(batch)):
                keys[entity] = None
                continue
            found = keys.setdefault(entity, [])
            assert found is not None
            found.append(_content_key(batch))
        per_tick.append({entity: None if k is None else sorted(k) for entity, k in keys.items()})
    first = per_tick[0]
    return {
        entity
        for entity, keys in first.items()
        if keys is not None and all(other.get(entity) == keys for other in per_tick[1:])
    }


def _send_recordings(
    recording,
    view: _View,
    samples: list[tuple[int, str]],
    n_ticks: int,
    timeline: str,
    arrow_type,
) -> None:
    """Re-root a branch's sample ``.rrd`` files under *view* on the sweep timeline.

    *samples* pairs each tick's raw index value with the recording captured there,
    for the ticks that have one; *n_ticks* is how many the branch has in all. What
    is the same in every sample is sent once and static, everything else once per
    tick at that tick -- see :func:`_shared_entities`.
    """
    shared = _shared_entities(samples, n_ticks)
    if shared:
        logger.debug(
            "%s: %d entities are identical at all %d ticks and are logged once",
            view.origin,
            len(shared),
            n_ticks,
        )
    first_raw = samples[0][0]
    for raw, path in samples:
        for entity, chunk in _sample_chunks(path):
            batch = chunk.to_record_batch()
            view.view_kinds.update(_batch_view_kinds(batch))
            view.logged = True
            rerooted = chunk.with_entity_path(f"{view.origin}/{entity}")
            if entity not in shared:
                recording.send_chunks(_rewrite_chunk(rerooted, timeline, arrow_type, raw))
            elif raw == first_raw:
                # The wall clock is the only index it can carry, so stripping that
                # leaves it static.
                recording.send_chunks(_rewrite_chunk(rerooted, timeline))


# How much of the viewer the read-out strip takes. It is a legend for the cursor,
# not a panel to study, so it gets the sliver that makes it legible and no more.
_READOUT_ROW_SHARES = (6, 1)
# Unless it holds a plot: axes, tick labels and a point to find among them need
# height a legend does not, and a plot in a sliver is a plot nobody can read.
_PLOT_ROW_SHARES = (5, 2)


def _layout_views(
    rrb,
    branches: list[list],
    branch_sizes: dict[str, int],
    readout=None,
    readout_shares: tuple[int, int] = _READOUT_ROW_SHARES,
):
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
    return rrb.Vertical(layout, readout, row_shares=list(readout_shares))


def _readout_view(rrb, view: _View):
    """One read-out's Blueprint view, opened on its own bounds where it has them."""
    if view.bounds is None:
        return views_for_kinds(rrb, view.view_kinds, origin=view.origin, label=view.label)
    (x_min, x_max), (y_min, y_max) = view.bounds
    return rrb.Spatial2DView(
        origin=view.origin,
        name=view.label,
        visual_bounds=rrb.VisualBounds2D(x_range=(x_min, x_max), y_range=(y_min, y_max)),
    )


def _readout_layout(rrb, readouts: list[_View]):
    """The read-out strip: nothing, one view, or the scatter beside the value.

    Side by side rather than stacked, because the strip is a sliver by design and
    halving its height again would leave neither legible.
    """
    if not readouts:
        return None
    built = [_readout_view(rrb, view) for view in readouts]
    return built[0] if len(built) == 1 else rrb.Horizontal(*built)


def _readout_shares(readouts: list[_View]) -> tuple[int, int]:
    """How much height the strip gets: a plot's share if any read-out is one."""
    if any(RerunViewKind.spatial_2d in view.view_kinds for view in readouts):
        return _PLOT_ROW_SHARES
    return _READOUT_ROW_SHARES


def _readout_entity(dim: str) -> str:
    """Entity path of the swept parameter's value read-out.

    Under ``sweep/`` rather than beside the result variables so it cannot collide
    with one that happens to share the dimension's name.
    """
    return f"/sweep/{dim}"


@dataclass(frozen=True)
class _ReadoutScatter:
    """A request to plot two of a sweep's per-sample values against each other.

    The pair and its title travel together. A title says what the *set* is, so it
    names the pair somebody asked to see and not whichever pair the renderer ended
    up drawing: reading it off the dataset regardless titled a plot of a front's
    *inputs* "Pareto front".
    """

    x: str
    y: str
    title: str | None = None

    @classmethod
    def resolve(
        cls, dataset: xr.Dataset, requested: tuple[str, str] | None
    ) -> _ReadoutScatter | None:
        """*requested* if a caller named a pair, else the dataset's own request.

        Raises:
            ValueError: if a pair was asked for that is not exactly two variables.
                An empty one included -- that used to be falsy all the way down and
                so silently suppressed the dataset's request instead.
        """
        title = None
        if requested is None:
            requested = dataset.attrs.get(READOUT_SCATTER_ATTR)
            if requested is None:
                return None
            title = dataset.attrs.get(READOUT_SCATTER_TITLE_ATTR)
        pair = list(requested)
        if len(pair) != 2:
            raise ValueError(
                "a tracking scatter needs exactly two variables to plot against each "
                f"other, got {pair}"
            )
        return cls(pair[0], pair[1], title)


def _front_entity(dim: str) -> str:
    """Entity path of the tracking scatter.

    A sibling of the read-out rather than a child: a view at the read-out's origin
    would otherwise swallow the scatter and draw both in one panel.
    """
    return f"/front/{dim}"


# The plot frame's colours: the axes and their labels read against the light ground,
# the grid is there to be looked past.
_FRAME_COLOR = (20, 20, 25)
_GRID_COLOR = (170, 175, 185)
_TITLE_COLOR = (0, 0, 0)


def _nice_ticks(low: float, high: float, target: int = 4) -> list[float]:
    """About *target* round-number tick values covering ``[low, high]``.

    The step is 1, 2 or 5 times a power of ten -- the spacing every plotting library
    settles on -- chosen so the range holds roughly *target* of them. Ticks outside
    the range are dropped, so a padded axis is labelled only where it has data-side
    meaning.
    """
    span = high - low
    if span <= 0:
        return [low]
    raw = span / max(target - 1, 1)
    magnitude = 10 ** np.floor(np.log10(raw))
    fraction = raw / magnitude
    step = magnitude * (
        1 if fraction < 1.5 else 2 if fraction < 3.5 else 5 if fraction < 7.5 else 10
    )
    first = np.ceil(low / step) * step
    ticks = np.arange(first, high + step / 2, step)
    # Round off the arithmetic so a tick is 0.3, not 0.30000000000000004.
    decimals = max(0, -int(np.floor(np.log10(step))))
    return [float(round(t, decimals)) for t in ticks]


def _monotonic(values: np.ndarray) -> bool:
    """Whether *values* never turn back, so a line through them in order is a curve."""
    steps = np.diff(np.asarray(values, dtype=float))
    return bool(np.all(steps >= 0) or np.all(steps <= 0))


class _PlotFrame:
    """The unit box a 2-D read-out plot is drawn in, and the mapping onto it.

    A rerun 2-D view keeps its aspect ratio and puts +y downward, so two objectives
    of unlike scale drawn at their own values would come out as a sliver with the
    better end at the top. The data is instead mapped onto a fixed landscape box,
    larger values upward, and the axes are drawn on that box with the true values as
    tick labels. The box is padded past the data by a little so no point sits on
    the frame.

    The values it is built from must be finite: the range is what the tick arithmetic
    reads, and a NaN reaching that raises rather than degrading. Callers filter.
    """

    width = 160.0
    height = 100.0
    pad = 0.12

    def __init__(self, x: np.ndarray, y: np.ndarray) -> None:
        self.x_range = self._padded(x)
        self.y_range = self._padded(y)

    @classmethod
    def _padded(cls, values: np.ndarray) -> tuple[float, float]:
        low, high = float(np.min(values)), float(np.max(values))
        if high == low:
            # A flat axis still needs a range to be drawn on.
            margin = abs(low) * 0.5 or 0.5
            return low - margin, high + margin
        margin = (high - low) * cls.pad
        return low - margin, high + margin

    def project_x(self, x) -> np.ndarray:
        low, high = self.x_range
        return (np.asarray(x, dtype=float) - low) / (high - low) * self.width

    def project_y(self, y) -> np.ndarray:
        low, high = self.y_range
        return self.height - (np.asarray(y, dtype=float) - low) / (high - low) * self.height

    def project(self, x, y) -> np.ndarray:
        return np.column_stack((self.project_x(x), self.project_y(y)))

    def bounds(self, titled: bool) -> tuple[tuple[float, float], tuple[float, float]]:
        """What the view opens on: the box plus room for the labels around it.

        Above the box sit the y axis name and, when there is one, the title; below it
        the tick row and the x axis name; to the left the y tick labels.
        """
        return (
            (-0.3 * self.width, 1.3 * self.width),
            ((-0.6 if titled else -0.34) * self.height, 1.52 * self.height),
        )


def _log_plot_frame(
    rr, staging, origin: str, frame: _PlotFrame, x_name: str, y_name: str, title: str | None
) -> None:
    """Draw the title, axes, gridlines, tick labels and axis names for *frame*, static.

    Labels are points of no size carrying text: rerun has no free-standing text in a
    spatial view, and a point's label is the one thing it draws at a position. Rerun
    hangs a label centred *below* its point, so each is placed above what it labels.
    The pieces stack the way a plot's do -- title, y axis name, box, tick row, x axis
    name -- which is the height :meth:`_PlotFrame.bounds` opens the view on.
    """
    w, h = frame.width, frame.height
    x_ticks = _nice_ticks(*frame.x_range)
    y_ticks = _nice_ticks(*frame.y_range)
    px = frame.project_x(x_ticks)
    py = frame.project_y(y_ticks)
    staging.log(
        f"{origin}/frame",
        rr.LineStrips2D(
            [[[0.0, h], [w, h]], [[0.0, 0.0], [0.0, h]]],
            colors=_FRAME_COLOR,
            radii=rr.Radius.ui_points(1.5),
        ),
        static=True,
    )
    grid = [[[float(v), 0.0], [float(v), h]] for v in px] + [
        [[0.0, float(v)], [w, float(v)]] for v in py
    ]
    staging.log(
        f"{origin}/grid",
        rr.LineStrips2D(grid, colors=_GRID_COLOR, radii=rr.Radius.ui_points(0.5)),
        static=True,
    )
    no_size = rr.Radius.ui_points(0.0)
    staging.log(
        f"{origin}/x_ticks",
        rr.Points2D(
            [[float(v), h + 0.05 * h] for v in px],
            radii=no_size,
            colors=_FRAME_COLOR,
            labels=[_coord_label(t) for t in x_ticks],
            show_labels=True,
        ),
        static=True,
    )
    staging.log(
        f"{origin}/y_ticks",
        rr.Points2D(
            [[-0.15 * w, float(v)] for v in py],
            radii=no_size,
            colors=_FRAME_COLOR,
            labels=[_coord_label(t) for t in y_ticks],
            show_labels=True,
        ),
        static=True,
    )
    # Each axis name sits with its own axis: the y name over the top of the y axis,
    # the x name under the tick row it belongs to. Alongside the y axis instead, a
    # long name would run across the plot, rotation being something rerun cannot do.
    staging.log(
        f"{origin}/axis_names",
        rr.Points2D(
            [[0.5 * w, h + 0.24 * h], [0.0, -0.26 * h]],
            radii=no_size,
            colors=_FRAME_COLOR,
            labels=[x_name, y_name],
            show_labels=True,
        ),
        static=True,
    )
    if title is not None:
        staging.log(
            f"{origin}/title",
            rr.Points2D(
                [[0.5 * w, -0.5 * h]],
                radii=no_size,
                colors=_TITLE_COLOR,
                labels=[title],
                show_labels=True,
            ),
            static=True,
        )


def _per_sample_values(dataset: xr.Dataset, name: str, dim: str) -> np.ndarray | None:
    """*name*'s one value per sample of *dim*, whether it is a coordinate or a variable.

    A sweep over a set of designs carries what it was ranked on either way: as a
    coordinate riding on the dimension when the producer put it there, or as a
    result variable when the sweep has no other dimension for it to span.
    """
    if name not in dataset.variables:
        return None
    array = dataset[name]
    if array.dims != (dim,):
        return None
    return np.asarray(array.values)


def _riding_coords(dataset: xr.Dataset, dim: str) -> list[str]:
    """Coordinates that ride on *dim*: one value per sample and no axis of their own.

    A sweep over a set of designs rather than a grid carries each design's inputs this
    way -- ``Bench.plot_pareto_front`` puts the searched parameters on the rank -- and
    they are what a reader parked on a tick wants to know.
    """
    # str(): xarray types a coordinate key as Hashable, but every name here reaches an
    # entity path and a read-out line, both of which want the string.
    return [
        str(name) for name, coord in dataset.coords.items() if name != dim and coord.dims == (dim,)
    ]


def _readout_text(dataset: xr.Dataset, dim: str, position: int) -> str:
    """Markdown naming the sample at *position*: its own value, then what rides on it.

    One bullet per field rather than one line of them. A design carries its whole
    parameter set here -- five offsets, a placement and two scores for a lidar mount --
    and run together with separators that is a paragraph to scan rather than a list to
    read, wrapped at whatever width the strip happens to have.
    """
    sample = dataset.isel({dim: position})
    lines = []
    for name in (dim, *_riding_coords(dataset, dim)):
        coord = sample.coords[name]
        # "ul" is bencher's unitless marker, not a unit to print -- the same reading
        # ``describe_variable`` gives it.
        units = coord.attrs.get("units", "")
        suffix = f" {units}" if units and units != "ul" else ""
        lines.append(f"- **{name}** = {_coord_label(coord.values.item())}{suffix}")
    return "\n".join(lines)


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
        readout_scatter: tuple[str, str] | None = None,
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
            readout_scatter (tuple[str, str], optional): Two per-sample variables to
                plot against each other beneath the timeline, every sample a point
                and the cursor's own picked out — how a sweep over a *set* says
                where in that set the slider is parked. Defaults to the dataset's
                ``bencher_readout_scatter`` attribute, which the producer of the
                sweep sets (see :data:`READOUT_SCATTER_ATTR`); the title carried
                beside that attribute names *that* pair, so a pair asked for here
                is drawn with its axes labelled and no title.
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
            readout_scatter=readout_scatter,
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
        readout_scatter: tuple[str, str] | None = None,
    ) -> str | None:
        """Compose *result_vars* into one ``.rrd`` on a timeline and return its path.

        Split out from :meth:`to_rerun_timeline` so the composition can be inspected
        -- by tests, or by anyone who wants the file rather than a pane -- without a
        viewer in the way.

        Returns:
            str | None: path to the composed recording, or None if the sweep recorded
            nothing that could go on a timeline.

        Raises:
            ValueError: if *timeline_dim* names a dimension the dataset does not have,
                or a *readout_scatter* was asked for that is not exactly two
                variables.
        """
        # Parsed here rather than where it is drawn: an arity error found halfway
        # through logging has already staged a recording nobody unlinks.
        scatter = _ReadoutScatter.resolve(dataset, readout_scatter)
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
        branches, readouts = self._log_sweep(
            recording,
            dataset,
            result_vars,
            timeline_dim,
            branch_dims,
            encoding,
            scatter,
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
                # No cursor range on the read-outs: each is a picture of the whole
                # sweep with the cursor's own sample marked on it, and one visible
                # point is not that.
                readout=_readout_layout(rrb, readouts),
                readout_shares=_readout_shares(readouts),
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

        A dimension that carries other coordinates -- one value per sample, riding on
        it rather than spanning an axis of their own -- gets a text read-out whatever
        its index shows, listing them beside its own value. That is how a sweep over a
        set of designs says which design the cursor is on: the rank is a whole number
        and the axis shows it, but ``#3`` says nothing about the mount at rank 3.

        Returns:
            _View | None: the read-out's view, or None when the axis already shows
            everything there is to show.
        """
        import rerun as rr

        riding = _riding_coords(dataset, timeline_dim)
        if encoding.shows_values and not riding:
            return None
        coords = np.asarray(dataset.coords[timeline_dim].values)
        numeric = bool(np.issubdtype(coords.dtype, np.number)) and not riding
        origin = _readout_entity(timeline_dim)
        for position, (raw, value) in enumerate(zip(encoding.values, coords)):
            encoding.set_time(staging, timeline_dim, raw)
            if numeric:
                staging.log(origin, rr.Scalars(float(value)))
            else:
                staging.log(
                    origin,
                    rr.TextDocument(
                        _readout_text(dataset, timeline_dim, position),
                        media_type=rr.MediaType.MARKDOWN,
                    ),
                )
        staging.reset_time()
        return _View(
            origin=origin,
            label=timeline_dim,
            view_kinds={RerunViewKind.time_series if numeric else RerunViewKind.text_document},
            logged=True,
        )

    def _log_front_scatter(
        self,
        staging,
        dataset: xr.Dataset,
        timeline_dim: str,
        encoding: _IndexEncoding,
        scatter: _ReadoutScatter,
    ) -> _View | None:
        """Plot every sample against two of its own numbers, and mark the cursor's.

        A sweep over a set of designs is usually a set somebody has to choose *from* --
        a Pareto front, a candidate list -- and the shape of that set in the space it
        was ranked in is what the choice is made against. The whole set is logged
        statically, so it is on screen at every tick, and the current sample is logged
        per tick on top of it: latest-at then moves the highlight with the cursor,
        which is what says where on the front the slider is parked.

        Rerun has no plot view with two free axes -- its time series takes the
        timeline as x -- so the plot is drawn: the values are mapped onto a fixed box
        (see :class:`_PlotFrame`) and the axes, grid and tick labels are logged as
        geometry around it, with the cursor's point labelled by its actual values.

        Returns:
            _View | None: the scatter's view, or None when the dataset does not carry
            both named values one-per-sample, or no sample carries both.
        """
        import rerun as rr

        x_name, y_name = scatter.x, scatter.y
        title = scatter.title
        x = _per_sample_values(dataset, x_name, timeline_dim)
        y = _per_sample_values(dataset, y_name, timeline_dim)
        if x is None or y is None:
            logger.warning(
                "no tracking scatter: %s and %s are not both one value per %s",
                x_name,
                y_name,
                timeline_dim,
            )
            return None
        x = x.astype(float)
        y = y.astype(float)
        # A sample the worker could not score carries NaN, and a NaN has no position
        # on the frame: it is left off the set, off the range the axes are drawn from,
        # and off the curve.
        placed = np.isfinite(x) & np.isfinite(y)
        if not placed.any():
            logger.warning("no tracking scatter: no sample carries both %s and %s", x_name, y_name)
            return None
        origin = _front_entity(timeline_dim)
        frame = _PlotFrame(x[placed], y[placed])
        _log_plot_frame(rr, staging, f"{origin}/axes", frame, x_name, y_name, title)
        points = frame.project(x, y)
        # Draw order, so the cursor's marker is never buried under the set it is
        # picked out of -- one point of each sits at exactly the same place.
        staging.log(
            f"{origin}/all",
            rr.Points2D(
                points[placed],
                colors=_SCATTER_ALL_COLOR,
                radii=rr.Radius.ui_points(3.0),
                draw_order=1.0,
            ),
            static=True,
        )
        if _monotonic(x[placed]):
            # The samples are in order along x, so joining them draws the set as the
            # curve it is -- a front -- rather than leaving the eye to connect dots.
            staging.log(
                f"{origin}/all/curve",
                rr.LineStrips2D(
                    [points[placed]],
                    colors=_SCATTER_ALL_COLOR,
                    radii=rr.Radius.ui_points(1.0),
                    draw_order=0.0,
                ),
                static=True,
            )
        for position, raw in enumerate(encoding.values):
            encoding.set_time(staging, timeline_dim, raw)
            # An unscored sample clears the marker rather than leaving it unlogged:
            # latest-at would otherwise hold the previous tick's point and read as
            # this design's score.
            marker = points[position : position + 1] if placed[position] else _NO_POINTS
            # The values themselves go in the label: the axes are the plot's own unit
            # box, so what the viewer reports on hover is a position on the frame
            # and not the number the sweep recorded.
            reading = (
                f"{_coord_label(dataset.coords[timeline_dim].values[position])}: "
                f"{_coord_label(x[position])}, {_coord_label(y[position])}"
            )
            labels = [reading] if placed[position] else []
            staging.log(
                f"{origin}/current",
                rr.Points2D(
                    marker,
                    colors=_SCATTER_CURRENT_COLOR,
                    radii=rr.Radius.ui_points(7.0),
                    draw_order=2.0,
                ),
            )
            # The reading rides on an entity of its own so it is not painted in the
            # marker's colour; see _SCATTER_LABEL_COLOR.
            staging.log(
                f"{origin}/current/reading",
                rr.Points2D(
                    marker,
                    colors=_SCATTER_LABEL_COLOR,
                    radii=rr.Radius.ui_points(0.0),
                    labels=labels,
                    show_labels=True,
                    draw_order=3.0,
                ),
            )
        staging.reset_time()
        return _View(
            origin=origin,
            label=title or f"{y_name} against {x_name}",
            view_kinds={RerunViewKind.spatial_2d},
            logged=True,
            bounds=frame.bounds(titled=title is not None),
        )

    def _log_sweep(
        self,
        recording,
        dataset: xr.Dataset,
        result_vars: list[Parameter],
        timeline_dim: str,
        branch_dims: list[str],
        encoding: _IndexEncoding,
        scatter: _ReadoutScatter | None = None,
    ) -> tuple[list[list[_View]], list[_View]]:
        """Log every sample onto the sweep timeline; return its views and the read-outs.

        A view that received nothing is dropped. Empty branches retain their slots
        in the Cartesian product so missing recordings cannot shift later cells to
        another row or column. The caller omits an entirely empty composition.

        Returns:
            The branch views, grouped by branch, and the read-outs — separate because
            those are laid out along the bottom rather than as a branch.
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
                if isinstance(result_var, ResultRerun):
                    # The whole branch at once, not tick by tick: what the samples
                    # have in common is decided across them.
                    samples = [
                        (raw, path)
                        for position, raw in enumerate(encoding.values)
                        if (
                            path := leaf_recording_path(
                                self, branch_ds.isel({timeline_dim: position}), result_var
                            )
                        )
                        is not None
                    ]
                    if samples:
                        _send_recordings(
                            recording, view, samples, len(encoding.values), timeline_dim, arrow_type
                        )
                    if view.logged:
                        branch_views.append(view)
                    continue
                for position, raw in enumerate(encoding.values):
                    sample = branch_ds.isel({timeline_dim: position})
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

        readouts = [
            view
            for view in (
                self._log_front_scatter(staging, dataset, timeline_dim, encoding, scatter)
                if scatter is not None
                else None,
                self._log_value_readout(staging, dataset, timeline_dim, encoding),
            )
            if view is not None
        ]
        staged_any = staged_any or bool(readouts)

        if staged_any:
            from bencher.utils import gen_rerun_data_path

            staged_path = gen_rerun_data_path("timeline_stage")
            with open(staged_path, "wb") as handle:
                handle.write(staging.memory_recording().drain_as_bytes())
            _forward_stage(recording, staged_path, timeline_dim)
            # Purely an intermediate: the composition is what callers are handed.
            Path(staged_path).unlink(missing_ok=True)
        return branches, readouts
