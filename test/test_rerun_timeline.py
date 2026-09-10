"""Tests for mapping a swept dimension onto a rerun timeline.

``to_rerun_timeline_path`` is exercised directly rather than through the pane: the
whole point of the renderer is what ends up *inside* the ``.rrd`` — which timeline
carries which values, at which entity paths — and a pane hides all of it.
"""

from pathlib import Path

import numpy as np
import panel as pn
import pytest
import rerun as rr
from PIL import Image
from rerun.experimental import RrdReader

import bencher as bn
from bencher.plugins.registry import get_registry
from bencher.results.bench_result_base import ReduceType
from bencher.results.rerun_timeline import (
    TimelineIndex,
    _coord_label,
    _DurationIndex,
    _entity_parts,
    _layout_views,
    _readout_entity,
    _SequenceIndex,
    default_timeline_dim,
    encode_index,
)

NANOS_PER_SECOND = 1_000_000_000


class StaticPoseSweep(bn.ParametrizedSweep):
    """One static frame per sample: nothing to scrub except the sweep itself."""

    theta = bn.FloatSweep(default=1.0, bounds=[1.0, 3.0], samples=3)
    scale = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    out_rerun = bn.ResultRerun(width=200, height=150)

    def benchmark(self):
        recording = rr.RecordingStream("test_rerun_timeline", make_default=False)
        recording.log("pose", rr.Points2D([[self.theta, self.scale]]))
        self.out_rerun = bn.capture_rerun_rrd(recording)
        return super().benchmark()


class ThreeDimSweep(bn.ParametrizedSweep):
    """Three swept dimensions: one can be time, the other two have to tile."""

    theta = bn.FloatSweep(default=1.0, bounds=[1.0, 3.0], samples=3)
    scale = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    offset = bn.FloatSweep(default=0.0, bounds=[0.0, 1.0], samples=2)
    out_rerun = bn.ResultRerun(width=200, height=150)

    def benchmark(self):
        recording = rr.RecordingStream("test_rerun_timeline_3d", make_default=False)
        recording.log("pose", rr.Points2D([[self.theta, self.scale + self.offset]]))
        self.out_rerun = bn.capture_rerun_rrd(recording)
        return super().benchmark()


class FiveStepSweep(StaticPoseSweep):
    """A range whose interior steps are arithmetic, not exact decimals."""

    scale = bn.FloatSweep(default=0.0, bounds=[-0.1, 0.1], samples=5)


class InnerTimelineSweep(bn.ParametrizedSweep):
    """Each sample records its own ``time_s`` timeline as well as being a sample."""

    freq = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    out_rerun = bn.ResultRerun(width=200, height=150)

    def benchmark(self):
        recording = rr.RecordingStream("test_rerun_timeline_inner", make_default=False)
        for step in range(4):
            recording.set_time("time_s", duration=step * 0.1)
            recording.log("wave", rr.Scalars(self.freq * step))
        self.out_rerun = bn.capture_rerun_rrd(recording)
        return super().benchmark()


class VaryingTreeSweep(bn.ParametrizedSweep):
    """Each sample logs an entity named after itself, as a real rig sweep does.

    The shape latest-at cannot animate on its own: a path written at one sample and
    not the next is still the most recent value there, so it stays on screen.
    """

    part = bn.StringSweep(["arm", "mast", "skid"])
    out_rerun = bn.ResultRerun(width=200, height=150)

    def benchmark(self):
        recording = rr.RecordingStream("test_rerun_timeline_tree", make_default=False)
        recording.log(f"parts/{self.part}", rr.Points3D([[1.0, 2.0, 3.0]]))
        self.out_rerun = bn.capture_rerun_rrd(recording)
        return super().benchmark()


class InnerTickSweep(bn.ParametrizedSweep):
    """Each sample records its inner timeline on ``log_tick``.

    That is what bencher's own over-time recordings do
    (:func:`~bencher.results.rerun_result._log_to_rerun`), so a cached
    ``ResultRerun`` really can arrive with a meaningful ``log_tick``.
    """

    freq = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    out_rerun = bn.ResultRerun(width=200, height=150)

    def benchmark(self):
        recording = rr.RecordingStream("test_rerun_timeline_tick", make_default=False)
        for step in range(4):
            recording.set_time("log_tick", sequence=step)
            recording.log("wave", rr.Scalars(self.freq * step))
        self.out_rerun = bn.capture_rerun_rrd(recording)
        return super().benchmark()


class SharedSceneSweep(bn.ParametrizedSweep):
    """A fixed scene with one moving part, which is what a rig sweep records.

    ``scene`` is the same in every sample and ``probe`` moves with the sweep -- the
    robot and the sensor mount being placed on it.
    """

    theta = bn.FloatSweep(default=1.0, bounds=[1.0, 3.0], samples=3)
    out_rerun = bn.ResultRerun(width=200, height=150)

    def benchmark(self):
        recording = rr.RecordingStream("test_rerun_timeline_shared", make_default=False)
        recording.log("scene/floor", rr.Points3D([[0.0, 0.0, 0.0], [1.0, 1.0, 0.0]]), static=True)
        recording.log("scene/wall", rr.Points3D([[2.0, 0.0, 0.0]]))
        recording.log("probe", rr.Points3D([[self.theta, 0.0, 1.0]]))
        self.out_rerun = bn.capture_rerun_rrd(recording)
        return super().benchmark()


class SharedSceneWithClockSweep(SharedSceneSweep):
    """The same scene, but the wall is recorded on the sample's own timeline."""

    def benchmark(self):
        recording = rr.RecordingStream("test_rerun_timeline_shared_clock", make_default=False)
        recording.log("scene/floor", rr.Points3D([[0.0, 0.0, 0.0]]), static=True)
        recording.set_time("time_s", duration=0.5)
        recording.log("scene/wall", rr.Points3D([[2.0, 0.0, 0.0]]))
        recording.log("probe", rr.Points3D([[self.theta, 0.0, 1.0]]))
        self.out_rerun = bn.capture_rerun_rrd(recording)
        return bn.ParametrizedSweep.benchmark(self)


class CategoricalSweep(bn.ParametrizedSweep):
    """A sweep whose only dimension has no numeric position on an axis."""

    shape = bn.StringSweep(["cube", "cone", "sphere"])
    out_rerun = bn.ResultRerun(width=200, height=150)

    def benchmark(self):
        recording = rr.RecordingStream("test_rerun_timeline_cat", make_default=False)
        recording.log("pose", rr.Points2D([[len(self.shape), 1.0]]))
        self.out_rerun = bn.capture_rerun_rrd(recording)
        return super().benchmark()


class ImageAndMetricSweep(bn.ParametrizedSweep):
    """The shape the polygon example has: an image and a metric, no recording.

    Nothing here is rerun-specific, which is the point — this is what the rerun
    backend has to be able to render for the backend flag to be a swap rather than a
    different report.
    """

    size = bn.IntSweep(default=2, bounds=(2, 5))
    palette = bn.StringSweep(["warm", "cool"])

    frame = bn.ResultImage()
    coverage = bn.ResultFloat(units="px")

    def benchmark(self):
        fill = (200, 80, 40) if self.palette == "warm" else (40, 80, 200)
        path = bn.gen_image_path("frame")
        Image.new("RGB", (self.size * 4, self.size * 4), fill).save(path, "PNG")
        self.frame = str(path)
        self.coverage = float(self.size**2)
        return super().benchmark()


class RecordingAndMetricSweep(StaticPoseSweep):
    """A scene and a number, which is the shape every real benchmark has."""

    coverage = bn.ResultFloat(units="fraction")

    def benchmark(self):
        self.coverage = float(self.theta)
        return super().benchmark()


class FrontSweep(bn.ParametrizedSweep):
    """A two-objective design space with a scene per design, judged under two lights.

    ``theta`` trades ``near`` against ``far`` everywhere, so every trial is on the
    front; ``light`` is a condition to aggregate over, not a design choice.
    """

    theta = bn.FloatSweep(default=1.0, bounds=[1.0, 3.0], samples=3)
    light = bn.StringSweep(["day", "night"])
    near = bn.ResultFloat(units="m", direction=bn.OptDir.minimize)
    far = bn.ResultFloat(units="m", direction=bn.OptDir.minimize)
    out_rerun = bn.ResultRerun(width=200, height=150)

    def benchmark(self):
        self.near = float(self.theta)
        self.far = 3.0 - float(self.theta)
        recording = rr.RecordingStream("test_rerun_timeline_front", make_default=False)
        recording.log("pose", rr.Points2D([[self.theta, float(self.light == "day")]]))
        self.out_rerun = bn.capture_rerun_rrd(recording)
        return super().benchmark()


class FractionalSweep(bn.ParametrizedSweep):
    """A sweep whose coordinates are not whole numbers, so ticks cannot be them."""

    freq = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=3)
    metric = bn.ResultFloat()

    def benchmark(self):
        self.metric = self.freq**2
        return super().benchmark()


class UnmappedResultSweep(bn.ParametrizedSweep):
    """A result type the rerun mapping has no archetype for, beside one it does."""

    size = bn.IntSweep(default=2, bounds=(2, 4))

    frame = bn.ResultImage()
    where = bn.ResultPath()

    def benchmark(self):
        path = bn.gen_image_path("unmapped")
        Image.new("RGB", (8, 8), (10, 10, 10)).save(path, "PNG")
        self.frame = str(path)
        self.where = str(path)
        return super().benchmark()


def name_only(path: str) -> pn.pane.Markdown:
    """A declared container naming the composition instead of embedding a viewer.

    Module level, not a closure: the declared container is pickled into the cache
    along with the result var.
    """
    return pn.pane.Markdown(f"timeline: {Path(path).name}")


class DeclaredContainerSweep(StaticPoseSweep):
    """A ResultRerun declaring how it renders, in place of the rerun viewer."""

    out_rerun = bn.ResultRerun(width=200, height=150, container=name_only)


def full_path(path: str) -> pn.pane.Markdown:
    """A declared container handing the composed .rrd path back to the test.

    Module level for the same reason as :func:`name_only`: the container is pickled
    into the cache with the result var.
    """
    return pn.pane.Markdown(f"composed: {path}")


class PathContainerSweep(RecordingAndMetricSweep):
    """A ResultRerun whose container reports where the composition was written."""

    out_rerun = bn.ResultRerun(width=200, height=150, container=full_path)


class WideBranchSweep(PathContainerSweep):
    """Five values on the branch axis, three on the timeline.

    Thinning to two divisions has to visibly shorten the first and leave the
    second alone, which two-valued ``scale`` cannot show either way.
    """

    scale = bn.FloatSweep(default=1.0, bounds=[1.0, 5.0], samples=5)


def _composed(res, **kwargs) -> str:
    """The .rrd ``to_rerun_timeline`` composed, going through the public renderer."""
    pane = res.to_rerun_timeline(**kwargs)
    assert isinstance(pane, pn.pane.Markdown), type(pane)
    return pane.object.removeprefix("composed: ")


def _sweep(input_vars, cls=StaticPoseSweep, result_vars=("out_rerun",), **cfg):
    bench = cls().to_bench(bn.BenchRunCfg(**cfg) if cfg else None)
    return bench.plot_sweep(input_vars=input_vars, result_vars=list(result_vars))


def _timeline_path(res, **kwargs):
    """Compose *res*'s result vars onto a timeline and return the .rrd path."""
    dataset = res.to_dataset(ReduceType.SQUEEZE, deep=False)
    return res.to_rerun_timeline_path(dataset, res.bench_cfg.result_vars, **kwargs)


def _indices(path: str) -> dict[str, dict[str, list]]:
    """``{entity_path: {timeline_name: [index values]}}`` for a composed recording."""
    reader = RrdReader(str(path))
    out: dict[str, dict[str, list]] = {}
    for chunk in reader.stream(store=reader.recordings()[0]):
        entity = str(chunk.entity_path)
        if entity.endswith("__properties"):
            continue
        batch = chunk.to_record_batch()
        timelines = out.setdefault(entity, {})
        for field in batch.schema:
            if (field.metadata or {}).get(b"rerun:kind") != b"index":
                continue
            column = batch.column(batch.schema.get_field_index(field.name))
            timelines.setdefault(field.name, []).extend(column.to_pylist())
    return out


def _texts(path: str, entity: str) -> list[str]:
    """The TextDocument texts logged at *entity*, in index order."""
    reader = RrdReader(str(path))
    rows: list[tuple[int, str]] = []
    for chunk in reader.stream(store=reader.recordings()[0]):
        if str(chunk.entity_path) != entity:
            continue
        batch = chunk.to_record_batch()
        index = next(
            batch.column(i).to_pylist()
            for i, field in enumerate(batch.schema)
            if (field.metadata or {}).get(b"rerun:kind") == b"index"
        )
        text = next(
            batch.column(i).to_pylist()
            for i, field in enumerate(batch.schema)
            if field.name.startswith("TextDocument") and field.name.endswith("text")
        )
        rows.extend(zip(index, ("".join(t) if t else "" for t in text)))
    return [text for _, text in sorted(rows)]


def _media_types(path: str, entity: str) -> list[str]:
    """The TextDocument media types logged at *entity*, in index order."""
    reader = RrdReader(str(path))
    found: list[str] = []
    for chunk in reader.stream(store=reader.recordings()[0]):
        if str(chunk.entity_path) != entity:
            continue
        batch = chunk.to_record_batch()
        for i, field in enumerate(batch.schema):
            if field.name.startswith("TextDocument") and field.name.endswith("media_type"):
                found.extend("".join(v) if v else "" for v in batch.column(i).to_pylist())
    return found


def _xy(point) -> list:
    """A logged 2-D position as ``[x, y]``, however arrow handed it back."""
    return list(point.values()) if isinstance(point, dict) else list(point)


def _static(path: str, entity: str) -> list[bool]:
    """Whether each chunk logged at *entity* went to the static store."""
    reader = RrdReader(str(path))
    return [
        chunk.is_static
        for chunk in reader.stream(store=reader.recordings()[0])
        if str(chunk.entity_path) == entity
    ]


def _components(path: str, entity: str) -> set[str]:
    """The component column names logged at *entity* in a composed recording."""
    reader = RrdReader(str(path))
    out: set[str] = set()
    for chunk in reader.stream(store=reader.recordings()[0]):
        if str(chunk.entity_path) != entity:
            continue
        for field in chunk.to_record_batch().schema:
            if (field.metadata or {}).get(b"rerun:kind") == b"data":
                out.add(field.name)
    return out


class TestEncodeIndex:
    def test_whole_numbers_become_ticks_carrying_the_values(self):
        """``#3`` for a polygon with three sides: the value, and no unit claimed."""
        encoded = encode_index(np.array([3, 4, 7]), TimelineIndex.tick, "sides")
        assert isinstance(encoded, _SequenceIndex)
        assert encoded.values == (3, 4, 7)
        assert encoded.shows_values

    def test_integral_floats_count_as_whole_numbers(self):
        """A FloatSweep over 1..3 in three samples is 1.0, 2.0, 3.0 -- ticks."""
        encoded = encode_index(np.array([1.0, 2.0, 3.0]), TimelineIndex.tick, "theta")
        assert encoded.values == (1, 2, 3)
        assert encoded.shows_values

    def test_fractional_values_fall_back_to_counting_samples(self):
        """1.5 is not a tick, so the ticks count instead -- and say they are counting,
        which is what makes the renderer add a read-out of the real value."""
        encoded = encode_index(np.array([1.0, 1.5, 2.0]), TimelineIndex.tick, "theta")
        assert encoded.values == (0, 1, 2)
        assert not encoded.shows_values

    def test_categorical_falls_back_to_counting_samples(self):
        encoded = encode_index(np.array(["a", "b"]), TimelineIndex.tick, "shape")
        assert isinstance(encoded, _SequenceIndex)
        assert encoded.values == (0, 1)
        assert not encoded.shows_values

    def test_repeated_ticks_would_lose_samples_so_positions_are_used(self):
        """Two samples on one index overwrite each other under latest-at."""
        encoded = encode_index(np.array([2.0, 2.0, 5.0]), TimelineIndex.tick, "sides")
        assert encoded.values == (0, 1, 2)
        assert not encoded.shows_values

    def test_position_counts_samples_even_for_whole_numbers(self):
        encoded = encode_index(np.array([3, 4, 7]), TimelineIndex.position, "sides")
        assert encoded.values == (0, 1, 2)
        assert not encoded.shows_values

    def test_duration_puts_the_values_on_a_time_axis(self):
        encoded = encode_index(np.array([1.0, 1.5, 4.0]), TimelineIndex.duration, "theta")
        assert isinstance(encoded, _DurationIndex)
        assert encoded.values == (NANOS_PER_SECOND, 1_500_000_000, 4 * NANOS_PER_SECOND)
        assert encoded.shows_values

    def test_duration_is_the_encoding_that_keeps_uneven_spacing(self):
        """Ticks are evenly spaced by construction; only the duration axis shows a
        non-uniform sweep as non-uniform."""
        encoded = encode_index(np.array([0.0, 1.0, 10.0]), TimelineIndex.duration, "theta")
        gaps = np.diff(encoded.values)
        assert gaps[1] == 9 * gaps[0]

    def test_duration_refuses_a_categorical_dimension(self):
        """Silently renumbering would put a lie on the axis, so it raises instead."""
        with pytest.raises(ValueError, match="cannot be placed on a rerun time axis"):
            encode_index(np.array(["a", "b"]), TimelineIndex.duration, "shape")

    def test_duration_refuses_sub_nanosecond_spacing(self):
        """Rounding these to the same index would drop every sample but the last."""
        with pytest.raises(ValueError, match="collapsing samples"):
            encode_index(np.array([0.0, 1e-12, 2e-12]), TimelineIndex.duration, "theta")

    def test_duration_refuses_values_too_large_for_an_i64_of_nanoseconds(self):
        with pytest.raises(ValueError, match="i64 range"):
            encode_index(np.array([1e12, 2e12]), TimelineIndex.duration, "hertz")


class TestDefaultTimelineDim:
    def test_prefers_a_numeric_dimension_over_a_categorical_one(self):
        """A categorical axis is a facet, not a continuum, however long it is."""
        res = _sweep(["size", "palette"], cls=ImageAndMetricSweep, result_vars=("frame",))
        dataset = res.to_dataset(ReduceType.SQUEEZE, deep=False)
        assert default_timeline_dim(dataset, list(dataset.sizes)) == "size"

    def test_prefers_the_longest_numeric_dimension(self):
        res = _sweep(["theta", "scale"])
        dataset = res.to_dataset(ReduceType.SQUEEZE, deep=False)
        # theta has 3 samples and scale 2, and theta is not the last dimension.
        assert default_timeline_dim(dataset, list(dataset.sizes)) == "theta"

    def test_all_categorical_still_picks_one(self):
        res = _sweep(["shape"], cls=CategoricalSweep)
        dataset = res.to_dataset(ReduceType.SQUEEZE, deep=False)
        assert default_timeline_dim(dataset, list(dataset.sizes)) == "shape"


class TestRerunTimeline1D:
    def test_every_sample_shares_one_entity_path(self):
        """Latest-at only animates if the samples overwrite each other."""
        path = _timeline_path(_sweep(["theta"]))
        assert path is not None
        assert set(_indices(path)) == {"/out_rerun/pose"}

    def test_the_timeline_is_named_after_the_swept_variable(self):
        path = _timeline_path(_sweep(["theta"]))
        assert set(_indices(path)["/out_rerun/pose"]) == {"theta"}

    def test_the_timeline_carries_the_parameter_values(self):
        """theta sweeps 1..3 in 3 samples, so the axis reads #1, #2, #3."""
        path = _timeline_path(_sweep(["theta"]))
        assert sorted(_indices(path)["/out_rerun/pose"]["theta"]) == [1, 2, 3]

    def test_log_time_is_dropped(self):
        """Wall-clock capture time says nothing about the sweep and would otherwise
        be the timeline the viewer opens on."""
        path = _timeline_path(_sweep(["theta"]))
        assert "log_time" not in _indices(path)["/out_rerun/pose"]

    def test_position_index_numbers_the_samples(self):
        path = _timeline_path(_sweep(["theta"]), index=TimelineIndex.position)
        assert sorted(_indices(path)["/out_rerun/pose"]["theta"]) == [0, 1, 2]

    def test_duration_index_is_still_available(self):
        path = _timeline_path(_sweep(["theta"]), index=TimelineIndex.duration)
        seconds = [v.total_seconds() for v in _indices(path)["/out_rerun/pose"]["theta"]]
        assert sorted(seconds) == [1.0, 2.0, 3.0]

    def test_categorical_sweep_gets_counted_ticks(self):
        path = _timeline_path(_sweep(["shape"], cls=CategoricalSweep))
        assert sorted(_indices(path)["/out_rerun/pose"]["shape"]) == [0, 1, 2]


class TestResultTypesOtherThanRecordings:
    """A sweep with no ``ResultRerun`` at all still goes on the timeline.

    This is what makes ``backend="rerun"`` a swap: the polygon example records
    images and floats, not recordings.
    """

    def test_an_image_sweep_lands_on_the_timeline(self):
        res = _sweep(["size"], cls=ImageAndMetricSweep, result_vars=("frame",))
        entities = _indices(_timeline_path(res))
        assert set(entities) == {"/frame"}
        assert sorted(entities["/frame"]["size"]) == [2, 3, 4, 5]

    def test_each_result_var_gets_its_own_origin_on_one_timeline(self):
        """An image and a metric are two views scrubbed together, not one view asked
        to draw both."""
        res = _sweep(["size"], cls=ImageAndMetricSweep, result_vars=("frame", "coverage"))
        entities = _indices(_timeline_path(res))
        assert set(entities) == {"/frame", "/coverage"}
        for timelines in entities.values():
            assert set(timelines) == {"size"}

    def test_a_fractional_sweep_gets_a_read_out_of_the_parameter_value(self):
        """The ticks only count the samples there, so nothing else on screen would
        say which value the cursor is parked on."""
        res = _sweep(["freq"], cls=FractionalSweep, result_vars=("metric",))
        entities = _indices(_timeline_path(res))
        assert _readout_entity("freq") in entities
        assert sorted(entities[_readout_entity("freq")]["freq"]) == [0, 1, 2]

    def test_a_categorical_sweep_gets_a_text_read_out_of_the_category(self):
        """Without it a string sweep is ``#0``, ``#1``, ``#2`` and nothing in the
        viewer says whether the cursor is parked on ``cube`` or ``sphere``."""
        path = _timeline_path(_sweep(["shape"], cls=CategoricalSweep))
        readout = _readout_entity("shape")
        assert sorted(_indices(path)[readout]["shape"]) == [0, 1, 2]
        # Text, not a scalar: a category has no position on an axis to plot.
        assert any(name.startswith("TextDocument") for name in _components(path, readout))

    def test_a_tick_sweep_gets_no_read_out(self):
        """``#3`` already is the value, so a plot of it against itself is clutter."""
        res = _sweep(["size"], cls=ImageAndMetricSweep, result_vars=("frame",))
        assert _readout_entity("size") not in _indices(_timeline_path(res))

    def test_a_result_type_with_no_rerun_mapping_is_reported_once(self, caplog):
        """ResultPath has no archetype. The sweep must not fail, the mapped result var
        must still render, and the log must not carry one line per sample."""
        res = _sweep(["size"], cls=UnmappedResultSweep, result_vars=("frame", "where"))
        with caplog.at_level("WARNING", logger="bencher.results.rerun_timeline"):
            path = _timeline_path(res)
        assert caplog.text.count("No rerun timeline mapping") == 1, caplog.text
        assert set(_indices(path)) == {"/frame"}


class TestRidingCoordinates:
    """A sweep over a set of designs is not a grid: what makes rank 3 rank 3 rides on
    the dimension as coordinates, and the read-out is where a reader finds it."""

    def test_coordinates_riding_on_the_timeline_dimension_are_read_out(self):
        res = _sweep(["size"], cls=ImageAndMetricSweep, result_vars=("frame",))
        dataset = res.to_dataset(ReduceType.SQUEEZE).assign_coords(
            design=("size", ["a", "b", "c", "d"]), gain=("size", [0.5, 1.0, 1.5, 2.0])
        )
        dataset.coords["gain"].attrs["units"] = "dB"
        path = res.to_rerun_timeline_path(dataset, res.bench_cfg.result_vars)
        readout = _readout_entity("size")
        # Whole-number ticks show the size already; the read-out is there for what
        # they do not show, and it says the tick's own value too so it reads alone.
        assert sorted(_indices(path)[readout]["size"]) == [2, 3, 4, 5]
        # A bullet per field: a design carries its whole parameter set here, which run
        # together is a paragraph to scan rather than a list to read.
        assert _texts(path, readout) == [
            "- **size** = 2\n- **design** = a\n- **gain** = 0.5 dB",
            "- **size** = 3\n- **design** = b\n- **gain** = 1.0 dB",
            "- **size** = 4\n- **design** = c\n- **gain** = 1.5 dB",
            "- **size** = 5\n- **design** = d\n- **gain** = 2.0 dB",
        ]
        assert _media_types(path, readout) == ["text/markdown"] * 4

    def test_a_coordinate_on_a_branch_dimension_is_not_a_read_out(self):
        """Only what rides on the timeline dimension moves with the cursor."""
        res = _sweep(["size", "palette"], cls=ImageAndMetricSweep, result_vars=("frame",))
        dataset = res.to_dataset(ReduceType.SQUEEZE).assign_coords(hue=("palette", [30.0, 210.0]))
        path = res.to_rerun_timeline_path(dataset, res.bench_cfg.result_vars, timeline_dim="size")
        assert _readout_entity("size") not in _indices(path)

    def test_a_pareto_front_is_scrubbed_by_rank_with_its_design_read_out(self):
        """End to end from a study: the rank is the timeline, the aggregated condition
        tiles, and the cursor names the design and its scores."""
        bench = FrontSweep().to_bench(bn.BenchRunCfg(repeats=1))
        result = bench.optimize(n_trials=4, aggregate=["light"], warm_start=False, plot=False)
        res = bench.plot_pareto_front(result, result_vars=["out_rerun"], auto_plot=False)
        path = _timeline_path(res)
        entities = _indices(path)
        # Two objectives, so the front also plots itself; see TestTrackingScatter.
        plot = {entity for entity in entities if entity.startswith("/front/pareto_rank/")}
        assert set(entities) - plot == {
            "/light_day/out_rerun/pose",
            "/light_night/out_rerun/pose",
            _readout_entity("pareto_rank"),
        }
        assert {"/front/pareto_rank/all", "/front/pareto_rank/current"} <= plot
        ranks = list(range(len(result.pareto_trials())))
        for entity, timelines in entities.items():
            # The plot is static apart from the cursor's own marker and reading, so
            # it has no index of its own to check.
            if entity in plot and not entity.startswith("/front/pareto_rank/current"):
                assert timelines == {}
                continue
            assert sorted(timelines["pareto_rank"]) == ranks
        texts = _texts(path, _readout_entity("pareto_rank"))
        for rank, (text, trial) in enumerate(zip(texts, result.pareto_trials())):
            lines = text.splitlines()
            assert lines[0] == f"- **pareto_rank** = {rank}"
            assert lines[1] == f"- **theta** = {_coord_label(trial.params['theta'])}"
            assert f"- **near_mean** = {_coord_label(trial.values[0])} m" in lines
            assert f"- **far_mean** = {_coord_label(trial.values[1])} m" in lines


class TestTrackingScatter:
    """Where on the front the slider is parked, drawn in the space it was ranked in."""

    def _points(self, path: str, entity: str) -> list[list[list[float]]]:
        """The Points2D positions logged at *entity*, one list of points per row."""
        reader = RrdReader(str(path))
        rows: list[list[list[float]]] = []
        for chunk in reader.stream(store=reader.recordings()[0]):
            if str(chunk.entity_path) != entity:
                continue
            batch = chunk.to_record_batch()
            for i, field in enumerate(batch.schema):
                if field.name.startswith("Points2D") and "positions" in field.name:
                    for row in batch.column(i).to_pylist():
                        rows.append([[float(v) for v in _xy(point)] for point in row])
        return rows

    def _scatter_dataset(self, res):
        return res.to_dataset(ReduceType.SQUEEZE).assign_coords(
            cost=("size", [4.0, 3.0, 2.0, 1.0]), risk=("size", [1.0, 2.0, 3.0, 4.0])
        )

    def test_the_whole_set_is_static_and_the_cursors_point_moves(self):
        res = _sweep(["size"], cls=ImageAndMetricSweep, result_vars=("frame",))
        path = res.to_rerun_timeline_path(
            self._scatter_dataset(res),
            res.bench_cfg.result_vars,
            readout_scatter=("cost", "risk"),
        )
        entities = _indices(path)
        origin = "/front/size"
        # The set carries no sweep index and reads back static, which is what puts it
        # on screen at every tick. (Only the composed result is pinned here: the
        # log_time strip leaves an unindexed chunk reading static too, so this does
        # not separately witness the `static=True` on the log call.)
        assert _static(path, f"{origin}/all") == [True]
        assert entities[f"{origin}/all"] == {}
        # The highlight is one point per tick, which is what makes it follow the cursor.
        # The four ticks arrive as one indexed chunk, not four static ones.
        assert _static(path, f"{origin}/current") == [False]
        assert sorted(entities[f"{origin}/current"]["size"]) == [2, 3, 4, 5]

    def test_the_highlight_is_the_sample_the_cursor_is_on(self):
        res = _sweep(["size"], cls=ImageAndMetricSweep, result_vars=("frame",))
        path = res.to_rerun_timeline_path(
            self._scatter_dataset(res),
            res.bench_cfg.result_vars,
            readout_scatter=("cost", "risk"),
        )
        rows = self._points(path, "/front/size/all")
        assert len(rows) == 1
        every = rows[0]
        # Drawn on the plot's own box, not at the raw values: cost falls 4..1 so x
        # falls left, risk rises 1..4 so y rises -- which in rerun's downward 2-D y is a
        # falling coordinate -- and the four samples span the box less its padding.
        xs = [point[0] for point in every]
        ys = [point[1] for point in every]
        assert xs == sorted(xs, reverse=True) and ys == sorted(ys, reverse=True)
        assert 0 < xs[-1] < xs[0] < 160 and 0 < ys[-1] < ys[0] < 100
        # One point per tick, each the sample sitting at that tick.
        assert self._points(path, "/front/size/current") == [[point] for point in every]

    def test_the_scatter_and_the_value_read_out_share_the_strip(self):
        import rerun.blueprint as rrb

        from bencher.results.composable_container.composable_container_rerun import (
            RerunViewKind,
        )
        from bencher.results.rerun_timeline import _readout_layout, _View

        views = [
            _View(origin="/front/x", label="a vs b", view_kinds={RerunViewKind.spatial_2d}),
            _View(origin="/sweep/x", label="x", view_kinds={RerunViewKind.text_document}),
        ]
        layout = _readout_layout(rrb, views)
        assert isinstance(layout, rrb.Horizontal)
        assert len(layout.contents) == 2
        assert _readout_layout(rrb, []) is None
        assert not isinstance(_readout_layout(rrb, views[:1]), rrb.Horizontal)

    def test_a_sweep_that_does_not_carry_both_values_gets_no_scatter(self, caplog):
        """Named against a dataset that has no such per-sample pair, it says so and
        renders the rest rather than failing the whole composition."""
        res = _sweep(["size"], cls=ImageAndMetricSweep, result_vars=("frame",))
        with caplog.at_level("WARNING", logger="bencher.results.rerun_timeline"):
            path = res.to_rerun_timeline_path(
                res.to_dataset(ReduceType.SQUEEZE),
                res.bench_cfg.result_vars,
                readout_scatter=("cost", "risk"),
            )
        assert "no tracking scatter" in caplog.text
        assert "/front/size/all" not in _indices(path)
        assert "/frame" in _indices(path)

    def test_a_pair_is_what_a_plane_takes(self):
        res = _sweep(["size"], cls=ImageAndMetricSweep, result_vars=("frame",))
        with pytest.raises(ValueError, match="exactly two"):
            res.to_rerun_timeline_path(
                self._scatter_dataset(res),
                res.bench_cfg.result_vars,
                readout_scatter=("cost",),
            )

    def test_the_dataset_can_carry_the_request_itself(self):
        """The producer of a sweep knows which pair is worth plotting; the renderer
        cannot infer it, so the sweep says so on the dataset."""
        from bencher.results.rerun_timeline import READOUT_SCATTER_ATTR

        res = _sweep(["size"], cls=ImageAndMetricSweep, result_vars=("frame",))
        dataset = self._scatter_dataset(res)
        dataset.attrs[READOUT_SCATTER_ATTR] = ["cost", "risk"]
        path = res.to_rerun_timeline_path(dataset, res.bench_cfg.result_vars)
        assert "/front/size/all" in _indices(path)

    def test_a_two_objective_front_plots_itself(self):
        """End to end: the study's own objectives become the scatter's axes."""
        bench = FrontSweep().to_bench(bn.BenchRunCfg(repeats=1))
        result = bench.optimize(n_trials=4, aggregate=["light"], warm_start=False, plot=False)
        res = bench.plot_pareto_front(result, result_vars=["out_rerun"], auto_plot=False)
        from bencher.results.rerun_timeline import READOUT_SCATTER_ATTR

        assert res.ds.attrs[READOUT_SCATTER_ATTR] == ["near_mean", "far_mean"]
        entities = _indices(_timeline_path(res))
        assert "/front/pareto_rank/all" in entities
        ranks = list(range(len(result.pareto_trials())))
        assert sorted(entities["/front/pareto_rank/current"]["pareto_rank"]) == ranks


class TestSharedContent:
    """What every sample records identically is stored once, not once per tick."""

    def _chunks(self, path: str, entity: str) -> list[tuple[bool, list]]:
        """``(is_static, sweep index values)`` per chunk logged at *entity*."""
        reader = RrdReader(str(path))
        out = []
        for chunk in reader.stream(store=reader.recordings()[0]):
            if str(chunk.entity_path) != entity:
                continue
            batch = chunk.to_record_batch()
            ticks = [
                batch.column(i).to_pylist()
                for i, f in enumerate(batch.schema)
                if (f.metadata or {}).get(b"rerun:kind") == b"index" and f.name == "theta"
            ]
            out.append((chunk.is_static, ticks[0] if ticks else []))
        return out

    def test_the_unchanging_scene_is_logged_once_and_static(self):
        res = _sweep(["theta"], cls=SharedSceneSweep)
        path = _timeline_path(res)
        # Static in the sample or not: the wall was logged with the wall clock only,
        # and identical at every tick is identical at every tick.
        for part in ("floor", "wall"):
            assert self._chunks(path, f"/out_rerun/scene/{part}") == [(True, [])]
        # The moving part is still one chunk per tick, at its tick.
        probe = self._chunks(path, "/out_rerun/probe")
        assert [static for static, _ in probe] == [False, False, False]
        assert sorted(tick for _, ticks in probe for tick in ticks) == [1, 2, 3]

    def test_a_tick_with_no_recording_keeps_every_tick_separate(self):
        """A static copy would show at the empty tick too, where there is nothing."""
        res = _sweep(["theta"], cls=SharedSceneSweep)
        dataset = res.to_dataset(ReduceType.SQUEEZE).copy(deep=True)
        dataset["out_rerun"].values[1] = ""
        path = res.to_rerun_timeline_path(dataset, res.bench_cfg.result_vars)
        floor = self._chunks(path, "/out_rerun/scene/floor")
        assert [static for static, _ in floor] == [False, False]
        assert sorted(tick for _, ticks in floor for tick in ticks) == [1, 3]

    def test_an_entity_on_the_samples_own_timeline_is_not_shared(self):
        """Static data has no inner axis, and the sample's own clock is one."""
        res = _sweep(["theta"], cls=SharedSceneWithClockSweep)
        path = _timeline_path(res)
        assert self._chunks(path, "/out_rerun/scene/floor") == [(True, [])]
        wall = self._chunks(path, "/out_rerun/scene/wall")
        assert [static for static, _ in wall] == [False, False, False]
        assert "time_s" in _indices(path)["/out_rerun/scene/wall"]

    def test_sharing_is_decided_per_branch(self):
        """Two branches are two scenes; what one holds still the other may not."""
        res = _sweep(["theta"], cls=SharedSceneSweep)
        data = (
            res.to_dataset(ReduceType.SQUEEZE)["out_rerun"]
            .expand_dims(scene=["a", "b"])
            .transpose("theta", "scene")
            .copy(deep=True)
        )
        data.loc[{"scene": "b", "theta": 2.0}] = ""
        path = res.to_rerun_timeline_path(
            data.to_dataset(), res.bench_cfg.result_vars, timeline_dim="theta"
        )
        assert self._chunks(path, "/scene_a/out_rerun/scene/floor") == [(True, [])]
        assert [s for s, _ in self._chunks(path, "/scene_b/out_rerun/scene/floor")] == [
            False,
            False,
        ]


class TestInnerTimeline:
    def test_a_sample_keeps_its_own_timeline_alongside_the_sweep_one(self):
        """The two are independent axes: ``freq`` steps between samples, ``time_s``
        within one. Keeping both means either can be scrubbed."""
        path = _timeline_path(_sweep(["freq"], cls=InnerTimelineSweep))
        timelines = _indices(path)["/out_rerun/wave"]
        assert set(timelines) == {"freq", "time_s"}
        assert sorted(set(timelines["freq"])) == [1, 2]
        assert sorted({round(t.total_seconds(), 3) for t in timelines["time_s"]}) == [
            0.0,
            0.1,
            0.2,
            0.3,
        ]

    def test_a_sample_keeps_an_inner_log_tick_timeline(self):
        """``log_tick`` looks automatic but ``set_time`` overwrites it, and bencher's
        over-time recordings use it as their timeline. Only ``log_time`` is dropped."""
        path = _timeline_path(_sweep(["freq"], cls=InnerTickSweep))
        timelines = _indices(path)["/out_rerun/wave"]
        assert set(timelines) == {"freq", "log_tick"}
        assert sorted(set(timelines["log_tick"])) == [0, 1, 2, 3]


class TestRerunTimelineND:
    def test_a_branch_coordinate_is_named_the_way_a_reader_would_write_it(self):
        """A sweep's interior is arithmetic: a five-step range over -0.1..0.1 steps
        through 0.05000000000000002, and seventeen digits in a view title is noise
        the reader has to parse past. It still has to look like a float."""
        assert _coord_label(0.05000000000000002) == "0.05"
        assert _coord_label(1.0) == "1.0"
        assert _coord_label("head_sides") == "head_sides"
        path = _timeline_path(_sweep(["theta", "scale"], cls=FiveStepSweep), timeline_dim="theta")
        assert set(_indices(path)) == {
            f"/scale_{label}/out_rerun/pose" for label in ("-0.1", "-0.05", "0.0", "0.05", "0.1")
        }, sorted(_indices(path))

    def test_the_remaining_dimension_becomes_entity_branches(self):
        """One dimension can be time; the rest have to be somewhere in the tree."""
        path = _timeline_path(_sweep(["theta", "scale"]), timeline_dim="theta")
        entities = _indices(path)
        assert set(entities) == {
            "/scale_1.0/out_rerun/pose",
            "/scale_2.0/out_rerun/pose",
        }
        for timelines in entities.values():
            assert set(timelines) == {"theta"}

    def test_branches_share_the_one_cursor(self):
        """Every branch is indexed at the same three ticks, so they animate together."""
        path = _timeline_path(_sweep(["theta", "scale"]), timeline_dim="theta")
        ticks = {frozenset(tl["theta"]) for tl in _indices(path).values()}
        assert ticks == {frozenset({1, 2, 3})}

    def test_no_sample_is_dropped(self):
        entities = _indices(_timeline_path(_sweep(["theta", "scale"]), timeline_dim="theta"))
        assert sum(len(tl["theta"]) for tl in entities.values()) == 6

    def test_three_dimensions_tile_the_product_of_the_peeled_two(self):
        """The timeline stays one tick per sample; only the view count grows."""
        res = _sweep(["theta", "scale", "offset"], cls=ThreeDimSweep)
        entities = _indices(_timeline_path(res, timeline_dim="theta"))
        assert len(entities) == 4, entities
        for timelines in entities.values():
            assert len(timelines["theta"]) == 3

    def test_colliding_coordinate_names_fall_back_to_positions(self):
        """Two coordinates sanitizing to one segment would silently overwrite."""
        assert _entity_parts("shape", ["a/b", "a_b"]) == ["shape_0", "shape_1"]
        assert _entity_parts("shape", ["cube", "cone"]) == ["shape_cube", "shape_cone"]

    def test_an_unknown_timeline_dimension_is_rejected(self):
        with pytest.raises(ValueError, match="not a dimension"):
            _timeline_path(_sweep(["theta"]), timeline_dim="nope")


class TestRerunTimelinePane:
    def test_one_viewer_for_the_whole_sweep(self):
        res = _sweep(["theta", "scale"])
        assert isinstance(res.to_rerun_timeline(), pn.pane.HTML)

    def test_a_zero_dimensional_sweep_has_no_axis_to_animate(self):
        res = _sweep([])
        # The shape filter's mismatch panel, not a viewer and not a crash.
        assert not isinstance(res.to_rerun_timeline(), pn.pane.HTML)

    def test_a_scalar_is_left_to_the_chart_types_that_plot_it(self):
        """`panes` on the panel backend tiles PANEL_TYPES and no scalars, so neither
        does this one. A view per metric per branch shrank the scene the sweep is
        about, to replot numbers the line and heatmap charts already carry."""
        bench = PathContainerSweep().to_bench()
        res = bench.plot_sweep(input_vars=["theta"], result_vars=["out_rerun", "coverage"])
        assert {rv.name for rv in res.bench_cfg.result_vars} == {"out_rerun", "coverage"}
        assert set(_indices(_composed(res))) == {"/out_rerun/pose"}

    def test_naming_a_scalar_still_puts_it_on_the_timeline(self):
        """The default is about what to pick automatically, not about what is allowed:
        an explicit ask is honoured whatever the type."""
        res = _sweep(["freq"], cls=FractionalSweep, result_vars=("metric",))
        metric = res.bench_cfg.result_vars[0]
        assert "/metric" in _indices(
            res.to_rerun_timeline_path(res.to_dataset(ReduceType.SQUEEZE, deep=False), [metric])
        )

    def test_declared_container_wins_over_the_rerun_viewer(self):
        """Same precedence as to_rerun_grid_ds and the over_time path."""
        bench = DeclaredContainerSweep().to_bench()
        res = bench.plot_sweep(input_vars=["theta"], result_vars=["out_rerun"])
        pane = res.to_rerun_timeline()
        assert isinstance(pane, pn.pane.Markdown), type(pane)
        assert pane.object.startswith("timeline: ")


class TestBackendSwap:
    """The renderer is the rerun backend's ``panes``, which is what makes
    ``BenchRunCfg(backend=...)`` a swap rather than a different report."""

    def test_both_backends_implement_the_same_chart_type(self):
        from bencher.plugins.builtins import _builtin_specs

        panes = {(name, backend) for name, backend, _, _ in _builtin_specs() if name == "panes"}
        assert panes == {("panes", "panel"), ("panes", "rerun")}

    def test_a_zero_dimensional_sweep_keeps_the_panel_tiling(self):
        """The rerun implementation declines a 0-D sweep, so it must not *win* one.

        Selection resolves a chart type to one backend. With a permissive registry
        rule the rerun implementation took ``panes`` on a single-sample sweep and
        then returned its shape-mismatch panel, so the report lost the recording
        the panel tiling would have shown -- a preference silently deleting output.
        """
        res = _sweep([], result_vars=("out_rerun",), backend="rerun")
        chosen = {
            (p.name, p.backend) for p in get_registry().select(res.to_bench_data(), backend="rerun")
        }
        assert ("panes", "panel") in chosen
        assert ("panes", "rerun") not in chosen

    def test_the_preference_still_wins_once_there_is_an_axis(self):
        """The guard is about shape, not about the rerun backend being second choice."""
        res = _sweep(["theta"], result_vars=("out_rerun",), backend="rerun")
        chosen = {
            (p.name, p.backend) for p in get_registry().select(res.to_bench_data(), backend="rerun")
        }
        assert ("panes", "rerun") in chosen
        assert ("panes", "panel") not in chosen

    def test_panel_is_chosen_by_default_and_rerun_when_preferred(self):
        res = _sweep(["size"], cls=ImageAndMetricSweep, result_vars=("frame",))
        data = res.to_bench_data()
        by_default = {(p.name, p.backend) for p in get_registry().select(data)}
        preferred = {(p.name, p.backend) for p in get_registry().select(data, backend="rerun")}
        assert ("panes", "panel") in by_default and ("panes", "rerun") not in by_default
        assert ("panes", "rerun") in preferred and ("panes", "panel") not in preferred

    def test_the_configured_backend_reaches_plot_selection(self):
        """``to_auto_plots`` is where the preference is applied; without it the flag
        only took effect on sweeps that had no plot callbacks of their own."""
        res = _sweep(["size"], cls=ImageAndMetricSweep, result_vars=("frame",), backend="rerun")
        assert res.bench_cfg.backend == "rerun"
        assert res.to_auto_plots() is not None


class TestSubsampling:
    """``subsampling_divisions`` has to mean the same thing on both backends.

    The panel implementation thins the samples it tiles; without the same argument
    the rerun one turned a flag that shrinks a report into one that does nothing,
    and a 2-D sweep swapping backends went from a readable grid to a viewer whose
    views were too narrow to read.

    What this one tiles is *branches*, so that is what it thins. A tick is a slider
    position rather than a panel: thinning the timeline costs resolution and buys
    no room, and the flag exists to buy room.
    """

    def _res(self, input_vars, cls=PathContainerSweep):
        bench = cls().to_bench()
        return bench.plot_sweep(input_vars=input_vars, result_vars=["out_rerun"])

    @staticmethod
    def _branches(path: str) -> set[str]:
        return {entity.lstrip("/").split("/")[0] for entity in _indices(path)}

    @staticmethod
    def _ticks(path: str, dim: str) -> list[int]:
        indices = _indices(path)
        pose = next(entity for entity in indices if entity.endswith("/pose"))
        return sorted(set(indices[pose][dim]))

    def test_every_sample_is_a_tick_when_nothing_is_thinned(self):
        assert self._ticks(_composed(self._res(["theta"])), "theta") == [1, 2, 3]

    def test_thinning_leaves_the_timeline_at_full_resolution(self):
        """theta keeps all three ticks: it is the slider, not one of the panels."""
        res = self._res(["theta", "scale"], cls=WideBranchSweep)
        path = _composed(res, timeline_dim="theta", subsampling_divisions=2)
        assert self._ticks(path, "theta") == [1, 2, 3]

    def test_thinning_drops_branch_views(self):
        """The branches are the panels, and they are what runs out of width."""
        res = self._res(["theta", "scale"], cls=WideBranchSweep)
        full = self._branches(_composed(res, timeline_dim="theta"))
        thinned = self._branches(_composed(res, timeline_dim="theta", subsampling_divisions=2))
        assert len(full) == 5, full
        assert len(thinned) == 2, thinned
        assert thinned < full

    def test_a_one_dimensional_sweep_is_untouched_by_thinning(self):
        """With no branch to thin there is nothing the flag can do but harm."""
        res = self._res(["theta"])
        assert _indices(_composed(res, subsampling_divisions=2)) == _indices(_composed(res))


class TestLayout:
    """Where the pieces sit, which is the difference between a viewer you can read
    and one where the scene is a thumbnail."""

    @pytest.mark.parametrize("rows, columns", [(3, 2), (2, 3)])
    def test_two_axes_have_fixed_rows_and_columns(self, rows, columns):
        import rerun.blueprint as rrb

        cells = [[f"row{row}_col{col}"] for col in range(columns) for row in range(rows)]
        layout = _layout_views(rrb, cells, {"pose": columns, "scenario": rows})
        assert isinstance(layout, rrb.Grid)
        assert layout.grid_columns == columns
        assert list(layout.contents) == [
            f"row{row}_col{col}" for row in range(rows) for col in range(columns)
        ]

    def test_missing_cell_keeps_its_place(self):
        import rerun.blueprint as rrb

        layout = _layout_views(rrb, [["a"], [], ["c"], ["d"]], {"pose": 2, "scene": 2})
        assert layout.grid_columns == 2
        assert len(layout.contents) == 4
        assert isinstance(layout.contents[2], rrb.TextDocumentView)
        assert list(layout.contents)[:2] == ["a", "c"]
        assert layout.contents[3] == "d"

    @pytest.mark.parametrize("missing", [False, True])
    @pytest.mark.parametrize("subsampling", [None, 2])
    def test_composed_recording_preserves_pose_scenario_coordinates(
        self, monkeypatch, missing, subsampling
    ):
        from bencher.results import rerun_timeline as rt

        res = _sweep(["theta"])
        data = (
            res.to_dataset(ReduceType.SQUEEZE)["out_rerun"]
            .expand_dims(
                pose=["Home", "TransportCompact", "DpdPregrasp"],
                scenario=["freespace", "table"],
            )
            .transpose("theta", "pose", "scenario")
            .copy(deep=True)
        )
        if missing:
            data.loc[{"pose": "Home", "scenario": "table"}] = ""
        layouts = []

        def capture(rrb, branches, branch_dims, readout=None, **kwargs):
            layout = _layout_views(rrb, branches, branch_dims, readout, **kwargs)
            layouts.append(layout)
            return layout

        monkeypatch.setattr(rt, "_layout_views", capture)
        path = res.to_rerun_timeline_path(
            data.to_dataset(),
            res.bench_cfg.result_vars,
            timeline_dim="theta",
            subsampling_divisions=subsampling,
        )
        assert path is not None
        grid = layouts[0]
        poses = list(data.coords["pose"].values)
        if subsampling is not None:
            poses = [poses[0], poses[-1]]
        assert len(grid.contents) == len(poses) * 2
        assert grid.grid_columns == len(poses)
        for row, scenario in enumerate(data.coords["scenario"].values):
            for col, pose in enumerate(poses):
                view = grid.contents[row * len(poses) + col]
                if missing and row == 1 and col == 0:
                    assert "No recording" in str(view.name)
                else:
                    assert str(view.origin) == f"/pose_{pose}/scenario_{scenario}/out_rerun"

    def test_no_recordings_still_returns_no_composition(self):
        res = _sweep(["theta", "scale"])
        dataset = res.to_dataset(ReduceType.SQUEEZE).copy(deep=True)
        dataset["out_rerun"].values[:] = ""
        assert res.to_rerun_timeline_path(dataset, res.bench_cfg.result_vars) is None

    def test_the_read_out_spans_the_bottom_under_the_branches(self):
        """It annotates the cursor, so it belongs on the cursor's axis. As a branch
        of its own it both stole a column's width and sat nowhere near the scrubber."""
        import rerun.blueprint as rrb

        layout = _layout_views(rrb, [["a"], ["b"]], {"pose": 2}, readout="value")
        assert isinstance(layout, rrb.Vertical)
        assert layout.contents[-1] == "value"
        assert isinstance(layout.contents[0], rrb.Horizontal)
        assert list(layout.contents[0].contents) == ["a", "b"]

    def test_without_a_read_out_the_branches_are_the_whole_viewer(self):
        import rerun.blueprint as rrb

        layout = _layout_views(rrb, [["a"], ["b"]], {"pose": 2})
        assert isinstance(layout, rrb.Horizontal)

    def test_an_origin_with_two_archetypes_becomes_tabs_not_a_stack(self):
        """A 3-D scene logged with a markdown note beside it is the common case, and
        stacking them spent half the scene's height on text read once."""
        import rerun.blueprint as rrb

        from bencher.results.composable_container.composable_container_rerun import (
            RerunViewKind,
            views_for_kinds,
        )

        view = views_for_kinds(
            rrb,
            {RerunViewKind.spatial_3d, RerunViewKind.text_document},
            origin="/out_rerun",
            label="out_rerun",
        )
        assert isinstance(view, rrb.Tabs), type(view)
        assert len(view.contents) == 2

    def test_a_single_archetype_stays_a_bare_view(self):
        import rerun.blueprint as rrb

        from bencher.results.composable_container.composable_container_rerun import (
            RerunViewKind,
            views_for_kinds,
        )

        view = views_for_kinds(
            rrb, {RerunViewKind.spatial_3d}, origin="/out_rerun", label="out_rerun"
        )
        assert isinstance(view, rrb.Spatial3DView), type(view)


def _blueprint_archetypes(path: str) -> set[str]:
    """Archetype names the composed recording's blueprint store carries."""
    reader = RrdReader(str(path))
    found = set()
    for chunk in reader.stream(store=reader.blueprints()[0]):
        for field in chunk.to_record_batch().schema:
            archetype = (field.metadata or {}).get(b"rerun:archetype")
            if archetype:
                found.add(archetype.decode().rsplit(".", 1)[-1])
    return found


class TestOneSamplePerTick:
    """A tick shows its own sample and no other.

    Latest-at resolves to the most recent value at or before the cursor, which only
    animates a sweep whose samples all write the same entity paths. A sweep over
    configurations does not: each sample names its own parts, nothing clears the
    ones the next sample lacks, and scrubbing to the end showed every part any
    sample had ever logged, piled on top of each other.
    """

    def _res(self):
        bench = VaryingTreeSweep().to_bench()
        return bench.plot_sweep(input_vars=["part"], result_vars=["out_rerun"])

    def test_the_samples_really_do_write_different_paths(self):
        """Guards the test below it: with one shared path there is nothing to fix."""
        parts = {e for e in _indices(_timeline_path(self._res())) if "/parts/" in e}
        assert parts == {
            "/out_rerun/parts/arm",
            "/out_rerun/parts/mast",
            "/out_rerun/parts/skid",
        }, parts

    def test_every_view_is_pinned_to_the_cursors_tick(self):
        assert "VisibleTimeRanges" in _blueprint_archetypes(_timeline_path(self._res()))

    def test_a_shared_path_sweep_is_pinned_the_same_way(self):
        """Not a special case for varying trees — a tick is one sample either way."""
        assert "VisibleTimeRanges" in _blueprint_archetypes(_timeline_path(_sweep(["theta"])))


class TestViewTimeRanges:
    def test_a_view_class_that_takes_a_range_gets_it(self):
        import rerun.blueprint as rrb

        from bencher.results.composable_container.composable_container_rerun import (
            RerunViewKind,
            views_for_kinds,
        )

        here = rrb.TimeRangeBoundary.cursor_relative(seq=0)
        ranges = [rrb.VisibleTimeRange("theta", start=here, end=here)]
        view = views_for_kinds(
            rrb, {RerunViewKind.spatial_3d}, origin="/x", label="x", time_ranges=ranges
        )
        assert isinstance(view, rrb.Spatial3DView)
        assert "VisibleTimeRanges" in view.properties

    def test_a_view_class_that_does_not_is_still_built(self):
        """TextDocumentView has no time_ranges. Refusing to build it would drop the
        annotation from the report over a field it does not need -- it shows one
        value regardless."""
        import rerun.blueprint as rrb

        from bencher.results.composable_container.composable_container_rerun import (
            RerunViewKind,
            views_for_kinds,
        )

        here = rrb.TimeRangeBoundary.cursor_relative(seq=0)
        ranges = [rrb.VisibleTimeRange("theta", start=here, end=here)]
        view = views_for_kinds(
            rrb, {RerunViewKind.text_document}, origin="/x", label="x", time_ranges=ranges
        )
        assert isinstance(view, rrb.TextDocumentView)
        assert "VisibleTimeRanges" not in view.properties
