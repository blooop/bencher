from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import partial
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


def _infer_chunk_view_kinds(chunk) -> set[RerunViewKind]:
    kinds = set()
    for arrow_field in chunk.to_record_batch().schema:
        metadata = arrow_field.metadata or {}
        archetype = metadata.get(b"rerun:archetype")
        if archetype is None:
            continue
        archetype_name = archetype.decode().rsplit(".", maxsplit=1)[-1]
        kind = _ARCHETYPE_VIEW_KINDS.get(archetype_name)
        if kind is not None:
            kinds.add(kind)
    return kinds


def _ordered_view_kinds(kinds: Iterable[RerunViewKind]) -> list[RerunViewKind]:
    selected = set(kinds)
    return [kind for kind in RerunViewKind if kind in selected]


def _namespace_chunk(chunk, *, prefix: str, kinds: set[RerunViewKind]):
    kinds.update(_infer_chunk_view_kinds(chunk))
    source_path = str(chunk.entity_path).lstrip("/")
    return chunk.with_entity_path(f"{prefix}/{source_path}")


def _blueprint_view(rrb, kind: RerunViewKind, *, origin: str, name: str):
    view_classes = {
        RerunViewKind.spatial_2d: rrb.Spatial2DView,
        RerunViewKind.spatial_3d: rrb.Spatial3DView,
        RerunViewKind.time_series: rrb.TimeSeriesView,
        RerunViewKind.bar_chart: rrb.BarChartView,
        RerunViewKind.tensor: rrb.TensorView,
        RerunViewKind.text_document: rrb.TextDocumentView,
        RerunViewKind.text_log: rrb.TextLogView,
        RerunViewKind.map: rrb.MapView,
        RerunViewKind.graph: rrb.GraphView,
        RerunViewKind.state_timeline: rrb.StateTimelineView,
    }
    return view_classes[kind](origin=origin, name=name)


def _blueprint_views(rrb, kinds: Iterable[RerunViewKind], *, origin: str, label: str):
    ordered = _ordered_view_kinds(kinds)
    if not ordered:
        ordered = [RerunViewKind.spatial_2d]
    views = [
        _blueprint_view(
            rrb,
            kind,
            origin=origin,
            name=label if len(ordered) == 1 else f"{label} — {_VIEW_NAMES[kind]}",
        )
        for kind in ordered
    ]
    if len(views) == 1:
        return views[0]
    return rrb.Vertical(*views, name=label)


@dataclass(kw_only=True)
class ComposableContainerRerun(ComposableContainerBase):
    """Combine complete Rerun recordings into one recording and Blueprint.

    Input entity paths are namespaced under ``/item_N`` before being forwarded
    into a new recording. The generated Blueprint maps Bencher composition onto
    Rerun as follows:

    - ``right`` -> ``rrb.Horizontal``
    - ``down`` -> ``rrb.Vertical``
    - ``sequence`` -> ``rrb.Tabs``
    - ``overlay`` -> shared views rooted at ``/``

    View types are inferred from Rerun archetype metadata. Pass ``view_kinds`` to
    :meth:`append` when a recording needs an explicit override.
    """

    container: list[RerunRecording] = field(default_factory=list)
    output_path: str | Path | None = None
    name: str | None = None
    application_id: str = "bencher/composed"

    def append(
        self,
        obj: str | Path | RerunRecording,
        *,
        label: str | None = None,
        view_kinds: Iterable[RerunViewKind | str] | None = None,
    ) -> None:
        """Append an RRD path or a recording value with optional view metadata."""
        if isinstance(obj, RerunRecording):
            if label is not None or view_kinds is not None:
                raise ValueError(
                    "label and view_kinds must be set on RerunRecording or append(), not both"
                )
            item = obj
        else:
            kinds = (
                tuple(RerunViewKind(kind) for kind in view_kinds)
                if view_kinds is not None
                else None
            )
            item = RerunRecording(path=obj, label=label, view_kinds=kinds)
        self.container.append(item)

    def _output_file(self) -> Path:
        if self.output_path is not None:
            output = Path(self.output_path)
            if output.suffix.lower() != ".rrd":
                raise ValueError("Rerun composition output_path must end in .rrd")
            output.parent.mkdir(parents=True, exist_ok=True)
            return output

        from bencher.utils import gen_rerun_data_path

        return Path(gen_rerun_data_path("composed"))

    def _build_blueprint(self, rrb, item_kinds: list[set[RerunViewKind]]):
        if self.compose_method == ComposeType.overlay:
            all_kinds = set().union(*item_kinds)
            return _blueprint_views(
                rrb,
                all_kinds,
                origin="/",
                label=self.name or "Overlay",
            )

        layouts = []
        for index, (item, kinds) in enumerate(zip(self.container, item_kinds)):
            layouts.append(
                _blueprint_views(
                    rrb,
                    kinds,
                    origin=f"/item_{index}",
                    label=item.label or f"Item {index + 1}",
                )
            )

        if len(layouts) == 1:
            return layouts[0]
        match self.compose_method:
            case ComposeType.right:
                return rrb.Horizontal(*layouts, name=self.name)
            case ComposeType.down:
                return rrb.Vertical(*layouts, name=self.name)
            case ComposeType.sequence:
                return rrb.Tabs(*layouts, name=self.name)
            case _:
                raise RuntimeError(f"Unsupported Rerun compose type: {self.compose_method}")

    def render(self, **_kwargs: Any) -> str:
        """Materialize the composition as one path-backed ``.rrd`` artifact."""
        if not self.container:
            raise ValueError("Cannot render an empty ComposableContainerRerun")

        missing = [Path(item.path) for item in self.container if not Path(item.path).is_file()]
        if missing:
            raise FileNotFoundError(f"Rerun recording does not exist: {missing[0]}")

        import rerun as rr
        import rerun.blueprint as rrb
        from rerun.experimental import RrdReader

        recording = rr.RecordingStream(
            self.application_id,
            make_default=False,
            make_thread_default=False,
        )
        item_kinds: list[set[RerunViewKind]] = []

        for index, item in enumerate(self.container):
            inferred_kinds: set[RerunViewKind] = set()
            reader = RrdReader(item.path)
            stores = reader.recordings()
            if not stores:
                raise ValueError(f"RRD contains no recording stores: {item.path}")

            namespace_chunk = partial(
                _namespace_chunk,
                prefix=f"/item_{index}",
                kinds=inferred_kinds,
            )
            for store in stores:
                recording.send_chunks(reader.stream(store=store).map(namespace_chunk))
            item_kinds.append(set(item.view_kinds or inferred_kinds))

        blueprint = rrb.Blueprint(
            self._build_blueprint(rrb, item_kinds),
            auto_layout=False,
            auto_views=False,
            collapse_panels=True,
        )
        recording.send_blueprint(blueprint, make_active=True, make_default=True)

        output = self._output_file()
        output.write_bytes(recording.memory_recording().drain_as_bytes())
        return str(output)
