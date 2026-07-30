from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from strenum import StrEnum

from bencher.results.composable_container.composable_container_base import (
    ComposableContainerBase,
    ComposeType,
)


class RerunViewKind(StrEnum):
    """Rerun Blueprint view types supported by recording composition."""

    spatial_2d = "spatial_2d"
    spatial_3d = "spatial_3d"
    time_series = "time_series"
    bar_chart = "bar_chart"
    tensor = "tensor"
    text_document = "text_document"
    text_log = "text_log"
    map = "map"
    graph = "graph"
    state_timeline = "state_timeline"


@dataclass(frozen=True)
class RerunRecording:
    """One recording and its presentation metadata inside a composition."""

    path: str | Path
    label: str | None = None
    view_kinds: tuple[RerunViewKind, ...] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))
        if self.view_kinds is not None:
            object.__setattr__(
                self,
                "view_kinds",
                tuple(RerunViewKind(kind) for kind in self.view_kinds),
            )


_ARCHETYPE_VIEW_KINDS = {
    # Spatial 2D
    "Arrows2D": RerunViewKind.spatial_2d,
    "Boxes2D": RerunViewKind.spatial_2d,
    "DepthImage": RerunViewKind.spatial_2d,
    "Ellipses2D": RerunViewKind.spatial_2d,
    "EncodedDepthImage": RerunViewKind.spatial_2d,
    "EncodedImage": RerunViewKind.spatial_2d,
    "Image": RerunViewKind.spatial_2d,
    "LineStrips2D": RerunViewKind.spatial_2d,
    "Pinhole": RerunViewKind.spatial_2d,
    "Points2D": RerunViewKind.spatial_2d,
    "SegmentationImage": RerunViewKind.spatial_2d,
    "VideoFrameReference": RerunViewKind.spatial_2d,
    "VideoStream": RerunViewKind.spatial_2d,
    # Spatial 3D
    "Arrows3D": RerunViewKind.spatial_3d,
    "Asset3D": RerunViewKind.spatial_3d,
    "Boxes3D": RerunViewKind.spatial_3d,
    "Capsules3D": RerunViewKind.spatial_3d,
    "CoordinateFrame": RerunViewKind.spatial_3d,
    "Cylinders3D": RerunViewKind.spatial_3d,
    "Ellipsoids3D": RerunViewKind.spatial_3d,
    "GridMap": RerunViewKind.spatial_3d,
    "InstancePoses3D": RerunViewKind.spatial_3d,
    "LineStrips3D": RerunViewKind.spatial_3d,
    "Mesh3D": RerunViewKind.spatial_3d,
    "Points3D": RerunViewKind.spatial_3d,
    "Transform3D": RerunViewKind.spatial_3d,
    "TransformAxes3D": RerunViewKind.spatial_3d,
    "ViewCoordinates": RerunViewKind.spatial_3d,
    "VoxelGridMap": RerunViewKind.spatial_3d,
    # Non-spatial views
    "BarChart": RerunViewKind.bar_chart,
    "GraphEdges": RerunViewKind.graph,
    "GraphNodes": RerunViewKind.graph,
    "GeoLineStrings": RerunViewKind.map,
    "GeoPoints": RerunViewKind.map,
    "Scalars": RerunViewKind.time_series,
    "SeriesLines": RerunViewKind.time_series,
    "SeriesPoints": RerunViewKind.time_series,
    "StateChange": RerunViewKind.state_timeline,
    "StateConfiguration": RerunViewKind.state_timeline,
    "Tensor": RerunViewKind.tensor,
    "TextDocument": RerunViewKind.text_document,
    "TextLog": RerunViewKind.text_log,
}

_VIEW_NAMES = {
    RerunViewKind.spatial_2d: "2D",
    RerunViewKind.spatial_3d: "3D",
    RerunViewKind.time_series: "Time series",
    RerunViewKind.bar_chart: "Bar chart",
    RerunViewKind.tensor: "Tensor",
    RerunViewKind.text_document: "Document",
    RerunViewKind.text_log: "Log",
    RerunViewKind.map: "Map",
    RerunViewKind.graph: "Graph",
    RerunViewKind.state_timeline: "State timeline",
}

# ``rerun.blueprint`` is imported lazily, so the view classes are referenced by
# attribute name rather than by value.
_VIEW_CLASS_NAMES = {
    RerunViewKind.spatial_2d: "Spatial2DView",
    RerunViewKind.spatial_3d: "Spatial3DView",
    RerunViewKind.time_series: "TimeSeriesView",
    RerunViewKind.bar_chart: "BarChartView",
    RerunViewKind.tensor: "TensorView",
    RerunViewKind.text_document: "TextDocumentView",
    RerunViewKind.text_log: "TextLogView",
    RerunViewKind.map: "MapView",
    RerunViewKind.graph: "GraphView",
    RerunViewKind.state_timeline: "StateTimelineView",
}

_LAYOUT_CLASS_NAMES = {
    ComposeType.right: "Horizontal",
    ComposeType.down: "Vertical",
}

# Gap inserted between spliced recordings so consecutive items never share an index.
_SPLICE_GAP_NS = 1


def _index_fields(batch) -> list:
    """Return the timeline (index) fields of a chunk record batch."""
    return [
        arrow_field
        for arrow_field in batch.schema
        if (arrow_field.metadata or {}).get(b"rerun:kind") == b"index"
    ]


def _batch_view_kinds(batch) -> set[RerunViewKind]:
    """Infer which Blueprint view types can display the archetypes in a chunk."""
    kinds = set()
    for arrow_field in batch.schema:
        archetype = (arrow_field.metadata or {}).get(b"rerun:archetype")
        if archetype is None:
            continue
        archetype_name = archetype.decode().rsplit(".", maxsplit=1)[-1]
        kind = _ARCHETYPE_VIEW_KINDS.get(archetype_name)
        if kind is not None:
            kinds.add(kind)
    return kinds


def _index_values(batch, name: str):
    """Return one timeline column as a numpy int64 array of raw index units."""
    import pyarrow as pa

    column = batch.column(batch.schema.get_field_index(name))
    return column.cast(pa.int64()).to_numpy(zero_copy_only=False)


def _batch_time_bounds(batch) -> dict[str, tuple[int, int]]:
    """Return ``{timeline_name: (first, last)}`` in raw index units for one chunk."""
    bounds = {}
    for arrow_field in _index_fields(batch):
        values = _index_values(batch, arrow_field.name)
        bounds[arrow_field.name] = (int(values.min()), int(values.max()))
    return bounds


def _shifted_chunks(chunk, offsets: dict[str, int]) -> list:
    """Return ``chunk`` with each timeline column advanced by ``offsets[timeline]``."""
    import pyarrow as pa
    from rerun.experimental import Chunk

    batch = chunk.to_record_batch()
    columns = list(batch.columns)
    shifted_any = False
    for arrow_field in _index_fields(batch):
        offset = offsets.get(arrow_field.name, 0)
        if offset == 0:
            continue
        position = batch.schema.get_field_index(arrow_field.name)
        shifted = _index_values(batch, arrow_field.name) + offset
        columns[position] = pa.array(shifted).cast(batch.column(position).type)
        shifted_any = True
    if not shifted_any:
        return [chunk]
    return Chunk.from_record_batch(pa.RecordBatch.from_arrays(columns, schema=batch.schema))


@dataclass
class _ComposedItem:
    """One source recording, re-rooted under ``prefix``, with its layout metadata."""

    prefix: str
    label: str
    chunks: list = field(default_factory=list)
    view_kinds: set[RerunViewKind] = field(default_factory=set)
    time_bounds: dict[str, tuple[int, int]] = field(default_factory=dict)
    time_types: dict[str, Any] = field(default_factory=dict)

    def add(self, chunk) -> None:
        """Record a chunk and fold its archetypes and time range into the metadata."""
        self.chunks.append(chunk)
        batch = chunk.to_record_batch()
        self.view_kinds.update(_batch_view_kinds(batch))
        for arrow_field in _index_fields(batch):
            self.time_types[arrow_field.name] = arrow_field.type
        for name, (first, last) in _batch_time_bounds(batch).items():
            existing = self.time_bounds.get(name, (first, last))
            self.time_bounds[name] = (min(existing[0], first), max(existing[1], last))


def _read_item(path: str | Path, *, prefix: str, label: str) -> _ComposedItem:
    """Decode one ``.rrd`` file, re-rooting every entity path under ``prefix``."""
    from rerun.experimental import RrdReader

    reader = RrdReader(path)
    stores = reader.recordings()
    if not stores:
        raise ValueError(f"RRD contains no recording stores: {path}")

    item = _ComposedItem(prefix=prefix, label=label)
    for store in stores:
        for chunk in reader.stream(store=store):
            source_path = str(chunk.entity_path).lstrip("/")
            item.add(chunk.with_entity_path(f"{prefix}/{source_path}"))
    return item


def _splice_offsets(items: list[_ComposedItem]) -> list[dict[str, int]]:
    """Offset each item's timelines so it starts after the previous item ends.

    Timelines are spliced independently by name: an item that does not use a
    timeline neither consumes nor advances it.  The first user of a timeline
    keeps its original values.
    """
    offsets: list[dict[str, int]] = []
    timeline_ends: dict[str, int] = {}
    for item in items:
        item_offsets = {}
        for name, (first, last) in item.time_bounds.items():
            previous_end = timeline_ends.get(name)
            offset = 0 if previous_end is None else previous_end - first + _SPLICE_GAP_NS
            item_offsets[name] = offset
            timeline_ends[name] = last + offset
        offsets.append(item_offsets)
    return offsets


def _set_recording_time(recording, timeline: str, time_type, value: int) -> None:
    """Set ``timeline`` to a raw index ``value``, matching the column's time type.

    ``value`` is in nanoseconds for duration and timestamp timelines, so numpy
    types are used to keep nanosecond precision (``timedelta`` would round to
    microseconds).
    """
    import numpy as np
    import pyarrow as pa

    if pa.types.is_timestamp(time_type):
        recording.set_time(timeline, timestamp=np.datetime64(value, "ns"))
    elif pa.types.is_duration(time_type):
        recording.set_time(timeline, duration=np.timedelta64(value, "ns"))
    else:
        recording.set_time(timeline, sequence=value)


@dataclass(kw_only=True)
class ComposableContainerRerun(ComposableContainerBase):
    """Combine complete Rerun recordings into one recording and Blueprint.

    Input entity paths are namespaced under ``/item_N`` before being forwarded
    into a new recording. The generated Blueprint maps Bencher composition onto
    Rerun as follows:

    - ``right`` -> ``rrb.Horizontal``
    - ``down`` -> ``rrb.Vertical``
    - ``overlay`` -> shared views rooted at ``/``, all items playing together
    - ``sequence`` -> shared views rooted at ``/``, items spliced end to end in
      time so scrubbing the timeline plays them one after the other

    View types are inferred from Rerun archetype metadata. Pass ``view_kinds`` to
    :meth:`append` when a recording needs an explicit override.
    """

    container: list[RerunRecording] = field(default_factory=list)
    output_path: str | Path | None = None
    name: str | None = None
    application_id: str = "bencher/composed"

    @staticmethod
    def _to_recording(
        obj: str | Path | RerunRecording,
        *,
        label: str | None,
        view_kinds: Iterable[RerunViewKind | str] | None,
    ) -> RerunRecording:
        if isinstance(obj, RerunRecording):
            if label is not None or view_kinds is not None:
                raise ValueError(
                    "label and view_kinds must be set on RerunRecording or append(), not both"
                )
            return obj
        kinds = (
            tuple(RerunViewKind(kind) for kind in view_kinds) if view_kinds is not None else None
        )
        return RerunRecording(path=obj, label=label, view_kinds=kinds)

    def append(
        self,
        obj: str | Path | RerunRecording,
        *,
        label: str | None = None,
        view_kinds: Iterable[RerunViewKind | str] | None = None,
    ) -> None:
        """Append an RRD path or a recording value with optional view metadata."""
        self.container.append(self._to_recording(obj, label=label, view_kinds=view_kinds))

    @property
    def _shares_one_view(self) -> bool:
        """Whether every item is displayed in the same view rooted at ``/``."""
        return self.compose_method in (ComposeType.overlay, ComposeType.sequence)

    def _output_file(self) -> Path:
        if self.output_path is not None:
            output = Path(self.output_path)
            if output.suffix.lower() != ".rrd":
                raise ValueError("Rerun composition output_path must end in .rrd")
            output.parent.mkdir(parents=True, exist_ok=True)
            return output

        from bencher.utils import gen_rerun_data_path

        return Path(gen_rerun_data_path("composed"))

    def _views(self, rrb, kinds: Iterable[RerunViewKind], *, origin: str, label: str):
        """Build the view (or vertical stack of views) that displays one origin."""
        selected = set(kinds)
        ordered = [kind for kind in RerunViewKind if kind in selected] or [RerunViewKind.spatial_2d]
        views = [
            getattr(rrb, _VIEW_CLASS_NAMES[kind])(
                origin=origin,
                name=label if len(ordered) == 1 else f"{label} — {_VIEW_NAMES[kind]}",
            )
            for kind in ordered
        ]
        if len(views) == 1:
            return views[0]
        return rrb.Vertical(*views, name=label)

    def _layout(self, rrb, items: list[_ComposedItem]):
        """Map the compose method onto a Blueprint layout of per-item views."""
        if self._shares_one_view:
            return self._views(
                rrb,
                set().union(*(item.view_kinds for item in items)),
                origin="/",
                label=self.name or self.compose_method.title(),
            )

        views = [
            self._views(rrb, item.view_kinds, origin=item.prefix, label=item.label)
            for item in items
        ]
        if len(views) == 1:
            return views[0]
        layout_class = _LAYOUT_CLASS_NAMES.get(self.compose_method)
        if layout_class is None:
            raise RuntimeError(f"Unsupported Rerun compose type: {self.compose_method}")
        return getattr(rrb, layout_class)(*views, name=self.name)

    def _read_items(self) -> list[_ComposedItem]:
        items = []
        for index, entry in enumerate(self.container):
            item = _read_item(
                entry.path,
                prefix=f"/item_{index}",
                label=entry.label or f"Item {index + 1}",
            )
            if entry.view_kinds:
                item.view_kinds = set(entry.view_kinds)
            items.append(item)
        return items

    def _send_spliced(self, recording, items: list[_ComposedItem]) -> None:
        """Send items end to end in time, clearing each one as the next begins."""
        import rerun as rr

        offsets = _splice_offsets(items)
        for index, (item, item_offsets) in enumerate(zip(items, offsets)):
            for chunk in item.chunks:
                recording.send_chunks(_shifted_chunks(chunk, item_offsets))
            if index == len(items) - 1 or not item.time_bounds:
                continue
            # Rerun queries are latest-at, so without an explicit clear the final
            # frame of this item would linger underneath the following item.
            for timeline, (_, last) in item.time_bounds.items():
                _set_recording_time(
                    recording,
                    timeline,
                    item.time_types[timeline],
                    last + item_offsets.get(timeline, 0) + _SPLICE_GAP_NS,
                )
            recording.log(item.prefix, rr.Clear(recursive=True))
            recording.reset_time()

    def render(self, **_kwargs: Any) -> str:
        """Materialize the composition as one path-backed ``.rrd`` artifact."""
        if not self.container:
            raise ValueError("Cannot render an empty ComposableContainerRerun")

        missing = [Path(item.path) for item in self.container if not Path(item.path).is_file()]
        if missing:
            raise FileNotFoundError(f"Rerun recording does not exist: {missing[0]}")

        output = self._output_file()

        import rerun as rr
        import rerun.blueprint as rrb

        items = self._read_items()
        recording = rr.RecordingStream(
            self.application_id,
            make_default=False,
            make_thread_default=False,
        )

        if self.compose_method == ComposeType.sequence:
            self._send_spliced(recording, items)
        else:
            for item in items:
                recording.send_chunks(item.chunks)

        blueprint = rrb.Blueprint(
            self._layout(rrb, items),
            auto_layout=False,
            auto_views=False,
            collapse_panels=True,
        )
        recording.send_blueprint(blueprint, make_active=True, make_default=True)

        output.write_bytes(recording.memory_recording().drain_as_bytes())
        return str(output)
