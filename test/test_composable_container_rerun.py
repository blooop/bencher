from pathlib import Path

import pytest
import rerun as rr
from rerun.experimental import RrdReader

import bencher as bn
from bencher.result_collector import _materialize_result_value
from bencher.results.composable_container.composable_container_base import ComposeType
from bencher.results.composable_container.composable_container_rerun import (
    ComposableContainerRerun,
    RerunRecording,
    RerunViewKind,
)
from bencher.variables.results import ResultRerun


def _write_recording(tmp_path: Path, name: str, *archetypes) -> Path:
    recording = rr.RecordingStream(name, make_default=False)
    for entity_path, archetype in archetypes:
        recording.log(entity_path, archetype)
    path = tmp_path / f"{name}.rrd"
    path.write_bytes(recording.memory_recording().drain_as_bytes())
    return path


def _recording_entity_paths(path: str | Path) -> set[str]:
    reader = RrdReader(path)
    assert len(reader.recordings()) == 1
    return {str(chunk.entity_path) for chunk in reader.stream(store=reader.recordings()[0])}


def _blueprint_column_values(path: str | Path, column_name: str) -> list:
    reader = RrdReader(path)
    assert len(reader.blueprints()) == 1
    values = []
    for chunk in reader.stream(store=reader.blueprints()[0]):
        batch = chunk.to_record_batch()
        if column_name in batch.schema.names:
            values.extend(batch.column(batch.schema.get_field_index(column_name)).to_pylist())
    return values


@pytest.mark.parametrize(
    ("compose_method", "expected_container_kind"),
    [
        (ComposeType.right, 2),
        (ComposeType.down, 3),
        (ComposeType.sequence, 1),
    ],
)
def test_composes_recordings_with_blueprint_layout(
    tmp_path, compose_method, expected_container_kind
):
    left = _write_recording(tmp_path, "left", ("points", rr.Points2D([[0, 0]])))
    right = _write_recording(tmp_path, "right", ("points", rr.Points2D([[1, 1]])))
    output = tmp_path / f"{compose_method}.rrd"

    container = ComposableContainerRerun(
        compose_method=compose_method,
        output_path=output,
        name=f"{compose_method} composition",
    )
    container.append(left, label="Left")
    container.append(right, label="Right")

    assert container.render() == str(output)
    assert output.is_file()
    assert {"/item_0/points", "/item_1/points"} <= _recording_entity_paths(output)
    origins = _blueprint_column_values(output, "ViewBlueprint:space_origin")
    assert {value[0] for value in origins} == {"/item_0", "/item_1"}
    container_kinds = _blueprint_column_values(output, "ContainerBlueprint:container_kind")
    assert [expected_container_kind] in container_kinds


def test_overlay_uses_one_shared_view(tmp_path):
    first = _write_recording(tmp_path, "first", ("points", rr.Points2D([[0, 0]])))
    second = _write_recording(tmp_path, "second", ("boxes", rr.Boxes2D(half_sizes=[[1, 1]])))
    output = tmp_path / "overlay.rrd"

    container = ComposableContainerRerun(
        compose_method=ComposeType.overlay,
        output_path=output,
    )
    container.append(first)
    container.append(second)
    container.render()

    assert {"/item_0/points", "/item_1/boxes"} <= _recording_entity_paths(output)
    assert _blueprint_column_values(output, "ViewBlueprint:space_origin") == [["/"]]
    assert _blueprint_column_values(output, "ViewBlueprint:class_identifier") == [["2D"]]


def test_infers_multiple_view_kinds(tmp_path):
    source = _write_recording(
        tmp_path,
        "mixed",
        ("scene/points", rr.Points3D([[0, 0, 0]])),
        ("metrics/loss", rr.Scalars(0.5)),
    )
    output = tmp_path / "mixed-output.rrd"

    container = ComposableContainerRerun(output_path=output)
    container.append(source, label="Mixed")
    container.render()

    identifiers = _blueprint_column_values(output, "ViewBlueprint:class_identifier")
    assert {value[0] for value in identifiers} == {"3D", "TimeSeries"}


def test_view_kind_can_be_overridden(tmp_path):
    source = _write_recording(tmp_path, "source", ("points", rr.Points2D([[0, 0]])))
    output = tmp_path / "override.rrd"

    container = ComposableContainerRerun(output_path=output)
    container.append(source, view_kinds=[RerunViewKind.spatial_3d])
    container.render()

    assert _blueprint_column_values(output, "ViewBlueprint:class_identifier") == [["3D"]]


def test_accepts_recording_value_object(tmp_path):
    source = _write_recording(tmp_path, "source", ("points", rr.Points2D([[0, 0]])))
    output = tmp_path / "value-object.rrd"
    item = RerunRecording(source, label="Source", view_kinds=(RerunViewKind.spatial_2d,))

    container = ComposableContainerRerun(output_path=output)
    container.append(item)

    assert Path(container.render()).is_file()


def test_empty_container_is_rejected(tmp_path):
    container = ComposableContainerRerun(output_path=tmp_path / "empty.rrd")

    with pytest.raises(ValueError, match="empty"):
        container.render()


def test_missing_recording_is_rejected(tmp_path):
    container = ComposableContainerRerun(output_path=tmp_path / "output.rrd")
    container.append(tmp_path / "missing.rrd")

    with pytest.raises(FileNotFoundError, match="missing.rrd"):
        container.render()


def test_result_rerun_materializes_composable_container(tmp_path):
    source = _write_recording(tmp_path, "source", ("points", rr.Points2D([[0, 0]])))
    output = tmp_path / "materialized.rrd"
    container = ComposableContainerRerun(output_path=output)
    container.append(source)

    result = _materialize_result_value(ResultRerun(), container)

    assert result == str(output)
    assert output.is_file()


def test_public_api_exports_rerun_composition_types():
    assert bn.ComposableContainerRerun is ComposableContainerRerun
    assert bn.RerunRecording is RerunRecording
    assert bn.RerunViewKind is RerunViewKind
