from pathlib import Path

import pytest
import rerun as rr
from rerun.blueprint.components import ContainerKind
from rerun.experimental import RrdReader

import bencher as bn
from bencher.result_collector import _materialize_result_value
from bencher.results.composable_container.composable_container_base import ComposeType
from bencher.results.composable_container.composable_container_rerun import (
    _RERUN_COMPOSE_SPECS,
    ComposableContainerRerun,
    RerunRecording,
    RerunViewKind,
    _batch_time_bounds,
    _SharedViewLayout,
    _StackedViewLayout,
)
from bencher.variables.results import ResultRerun


def _write_recording(tmp_path: Path, name: str, *archetypes) -> Path:
    recording = rr.RecordingStream(name, make_default=False)
    for entity_path, archetype in archetypes:
        recording.log(entity_path, archetype)
    path = tmp_path / f"{name}.rrd"
    path.write_bytes(recording.memory_recording().drain_as_bytes())
    return path


def _write_temporal_recording(tmp_path: Path, name: str, *, steps: int = 4) -> Path:
    """Write a recording that spans ``steps`` ticks of a ``frame`` sequence timeline."""
    recording = rr.RecordingStream(name, make_default=False)
    for step in range(steps):
        recording.set_time("frame", sequence=step)
        recording.log("points", rr.Points2D([[step, step]]))
    path = tmp_path / f"{name}.rrd"
    path.write_bytes(recording.memory_recording().drain_as_bytes())
    return path


def _recording_time_bounds(path: str | Path, timeline: str) -> dict[str, tuple[int, int]]:
    """Return ``{entity_path: (first, last)}`` on ``timeline`` for a composed recording."""
    reader = RrdReader(path)
    bounds = {}
    for chunk in reader.stream(store=reader.recordings()[0]):
        chunk_bounds = _batch_time_bounds(chunk.to_record_batch()).get(timeline)
        if chunk_bounds is None:
            continue
        entity_path = str(chunk.entity_path)
        existing = bounds.get(entity_path, chunk_bounds)
        bounds[entity_path] = (
            min(existing[0], chunk_bounds[0]),
            max(existing[1], chunk_bounds[1]),
        )
    return bounds


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


def _container_kinds(path: str | Path) -> set[str]:
    """Return the Blueprint container kinds by name (``Horizontal``, ``Vertical``, …)."""
    return {
        ContainerKind(value).name
        for values in _blueprint_column_values(path, "ContainerBlueprint:container_kind")
        for value in values
    }


@pytest.mark.parametrize(
    ("compose_method", "expected_container_kind"),
    [
        (ComposeType.right, "Horizontal"),
        (ComposeType.down, "Vertical"),
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
    assert expected_container_kind in _container_kinds(output)


def test_sequence_splices_recordings_end_to_end(tmp_path):
    first = _write_temporal_recording(tmp_path, "first", steps=4)
    second = _write_temporal_recording(tmp_path, "second", steps=3)
    output = tmp_path / "sequence.rrd"

    container = ComposableContainerRerun(
        compose_method=ComposeType.sequence,
        output_path=output,
        name="Sequence composition",
    )
    container.append(first, label="First")
    container.append(second, label="Second")
    container.render()

    bounds = _recording_time_bounds(output, "frame")
    # The first recording keeps its own times; the second starts after it ends.
    assert bounds["/item_0/points"] == (0, 3)
    assert bounds["/item_1/points"] == (4, 6)
    # Every item but the last is cleared so it does not linger under the next one.
    assert bounds["/item_0"] == (4, 4)
    assert "/item_1" not in bounds
    # One shared view, so playing the timeline runs the items back to back.
    assert _blueprint_column_values(output, "ViewBlueprint:space_origin") == [["/"]]


def test_sequence_preserves_original_times_under_overlay(tmp_path):
    """``overlay`` is the same layout as ``sequence`` but leaves the times alone."""
    first = _write_temporal_recording(tmp_path, "first", steps=4)
    second = _write_temporal_recording(tmp_path, "second", steps=3)
    output = tmp_path / "overlay-times.rrd"

    container = ComposableContainerRerun(
        compose_method=ComposeType.overlay,
        output_path=output,
    )
    container.append(first)
    container.append(second)
    container.render()

    bounds = _recording_time_bounds(output, "frame")
    assert bounds["/item_0/points"] == (0, 3)
    assert bounds["/item_1/points"] == (0, 2)


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


def test_output_path_must_be_an_rrd(tmp_path):
    source = _write_recording(tmp_path, "source", ("points", rr.Points2D([[0, 0]])))
    container = ComposableContainerRerun(output_path=tmp_path / "output.mp4")
    container.append(source)

    with pytest.raises(ValueError, match="must end in .rrd"):
        container.render()


def test_append_rejects_duplicate_metadata(tmp_path):
    item = RerunRecording(tmp_path / "source.rrd", label="Source")
    container = ComposableContainerRerun()

    with pytest.raises(ValueError, match="not both"):
        container.append(item, label="Other")


def test_result_rerun_materializes_composable_container(tmp_path):
    source = _write_recording(tmp_path, "source", ("points", rr.Points2D([[0, 0]])))
    output = tmp_path / "materialized.rrd"
    container = ComposableContainerRerun(output_path=output)
    container.append(source)

    result = _materialize_result_value(ResultRerun(), container)

    assert result == str(output)
    assert output.is_file()


def test_every_compose_type_has_a_rerun_spec():
    """One table, checked (plan 23 P8).

    This replaced a pair of tables -- a ``_shares_one_view`` predicate and a
    ``_LAYOUT_CLASS_NAMES`` dict -- that had to stay exactly complementary with
    nothing asserting that they did.
    """
    assert set(_RERUN_COMPOSE_SPECS) == set(ComposeType)
    for member in ComposeType:
        assert isinstance(_RERUN_COMPOSE_SPECS[member], (_SharedViewLayout, _StackedViewLayout))


def test_rerun_specs_match_the_two_tables_they_replaced():
    """Parity oracle: the pre-P8 ``_shares_one_view`` / ``_LAYOUT_CLASS_NAMES`` pair."""
    legacy_shares_one_view = {ComposeType.overlay, ComposeType.sequence}
    legacy_layout_class_names = {ComposeType.right: "Horizontal", ComposeType.down: "Vertical"}

    for member in ComposeType:
        spec = _RERUN_COMPOSE_SPECS[member]
        if member in legacy_shares_one_view:
            assert isinstance(spec, _SharedViewLayout)
            # Only sequence spliced its items along the timeline.
            assert spec.splice_in_time is (member == ComposeType.sequence)
        else:
            assert isinstance(spec, _StackedViewLayout)
            assert spec.layout_class_name == legacy_layout_class_names[member]


def test_unknown_compose_method_is_rejected_by_name():
    """An out-of-vocabulary compose method names itself instead of raising KeyError."""
    container = ComposableContainerRerun(compose_method="not_a_compose_type")
    with pytest.raises(ValueError, match="not_a_compose_type"):
        _ = container._spec  # pylint: disable=protected-access


def test_public_api_exports_rerun_composition_types():
    assert bn.ComposableContainerRerun is ComposableContainerRerun
    assert bn.RerunRecording is RerunRecording
    assert bn.RerunViewKind is RerunViewKind
