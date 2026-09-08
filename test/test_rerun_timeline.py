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
from rerun.experimental import RrdReader

import bencher as bn
from bencher.results.bench_result_base import ReduceType
from bencher.results.rerun_timeline import (
    TimelineIndex,
    _DurationIndex,
    _entity_parts,
    _SequenceIndex,
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


class CategoricalSweep(bn.ParametrizedSweep):
    """A sweep whose only dimension has no numeric position on an axis."""

    shape = bn.StringSweep(["cube", "cone", "sphere"])
    out_rerun = bn.ResultRerun(width=200, height=150)

    def benchmark(self):
        recording = rr.RecordingStream("test_rerun_timeline_cat", make_default=False)
        recording.log("pose", rr.Points2D([[len(self.shape), 1.0]]))
        self.out_rerun = bn.capture_rerun_rrd(recording)
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


def _sweep(input_vars, cls=StaticPoseSweep):
    bench = cls().to_bench()
    return bench.plot_sweep(input_vars=input_vars, result_vars=["out_rerun"])


def _timeline_path(res, **kwargs):
    """Compose *res*'s only ResultRerun onto a timeline and return the .rrd path."""
    dataset = res.to_dataset(ReduceType.SQUEEZE, deep=False)
    return res.to_rerun_timeline_path(dataset, res.bench_cfg.result_vars[0], **kwargs)


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


class TestEncodeIndex:
    def test_numeric_becomes_a_duration_carrying_the_values(self):
        encoded = encode_index(np.array([1.0, 1.5, 4.0]), TimelineIndex.auto, "theta")
        assert isinstance(encoded, _DurationIndex)
        assert encoded.values == (NANOS_PER_SECOND, 1_500_000_000, 4 * NANOS_PER_SECOND)

    def test_uneven_spacing_survives(self):
        """A duration index is what keeps a non-uniform sweep non-uniform on the axis."""
        encoded = encode_index(np.array([0.0, 1.0, 10.0]), TimelineIndex.auto, "theta")
        gaps = np.diff(encoded.values)
        assert gaps[1] == 9 * gaps[0]

    def test_categorical_falls_back_to_a_sequence(self):
        encoded = encode_index(np.array(["a", "b"]), TimelineIndex.auto, "shape")
        assert isinstance(encoded, _SequenceIndex)
        assert encoded.values == (0, 1)

    def test_sequence_numbers_positions_even_for_numbers(self):
        encoded = encode_index(np.array([1.0, 1.5, 4.0]), TimelineIndex.sequence, "theta")
        assert encoded.values == (0, 1, 2)

    def test_value_refuses_a_categorical_dimension(self):
        """Silently renumbering would put a lie on the axis, so it raises instead."""
        with pytest.raises(ValueError, match="cannot be placed on a rerun time axis"):
            encode_index(np.array(["a", "b"]), TimelineIndex.value, "shape")

    def test_sub_nanosecond_spacing_falls_back_to_a_sequence(self):
        """Rounding these to the same index would drop every sample but the last."""
        coords = np.array([0.0, 1e-12, 2e-12])
        encoded = encode_index(coords, TimelineIndex.auto, "theta")
        assert isinstance(encoded, _SequenceIndex)
        assert encoded.values == (0, 1, 2)
        with pytest.raises(ValueError, match="collapsing samples"):
            encode_index(coords, TimelineIndex.value, "theta")

    def test_values_too_large_for_an_i64_of_nanoseconds_fall_back(self):
        encoded = encode_index(np.array([1e12, 2e12]), TimelineIndex.auto, "hertz")
        assert isinstance(encoded, _SequenceIndex)


class TestRerunTimeline1D:
    def test_every_sample_shares_one_entity_path(self):
        """Latest-at only animates if the samples overwrite each other."""
        path = _timeline_path(_sweep(["theta"]))
        assert path is not None
        entities = set(_indices(path))
        assert entities == {"/pose"}

    def test_the_timeline_is_named_after_the_swept_variable(self):
        path = _timeline_path(_sweep(["theta"]))
        assert set(_indices(path)["/pose"]) == {"theta"}

    def test_the_timeline_carries_the_parameter_values(self):
        """theta sweeps 1..3 in 3 samples, so the axis reads 1s, 2s, 3s."""
        path = _timeline_path(_sweep(["theta"]))
        seconds = [v.total_seconds() for v in _indices(path)["/pose"]["theta"]]
        assert sorted(seconds) == [1.0, 2.0, 3.0]

    def test_log_time_is_dropped(self):
        """Wall-clock capture time says nothing about the sweep and would otherwise
        be the timeline the viewer opens on."""
        path = _timeline_path(_sweep(["theta"]))
        assert "log_time" not in _indices(path)["/pose"]

    def test_sequence_index_numbers_the_samples(self):
        path = _timeline_path(_sweep(["theta"]), index=TimelineIndex.sequence)
        assert sorted(_indices(path)["/pose"]["theta"]) == [0, 1, 2]

    def test_categorical_sweep_gets_a_sequence_timeline(self):
        path = _timeline_path(_sweep(["shape"], cls=CategoricalSweep))
        assert sorted(_indices(path)["/pose"]["shape"]) == [0, 1, 2]


class TestInnerTimeline:
    def test_a_sample_keeps_its_own_timeline_alongside_the_sweep_one(self):
        """The two are independent axes: ``freq`` steps between samples, ``time_s``
        within one. Keeping both means either can be scrubbed."""
        path = _timeline_path(_sweep(["freq"], cls=InnerTimelineSweep))
        timelines = _indices(path)["/wave"]
        assert set(timelines) == {"freq", "time_s"}
        assert sorted({t.total_seconds() for t in timelines["freq"]}) == [1.0, 2.0]
        assert sorted({round(t.total_seconds(), 3) for t in timelines["time_s"]}) == [
            0.0,
            0.1,
            0.2,
            0.3,
        ]


class TestRerunTimelineND:
    def test_the_remaining_dimension_becomes_entity_branches(self):
        """One dimension can be time; the rest have to be somewhere in the tree."""
        path = _timeline_path(_sweep(["theta", "scale"]), timeline_dim="theta")
        entities = _indices(path)
        assert set(entities) == {"/scale_1.0/pose", "/scale_2.0/pose"}
        for timelines in entities.values():
            assert set(timelines) == {"theta"}

    def test_branches_share_the_one_cursor(self):
        """Every branch is indexed at the same three ticks, so they animate together."""
        path = _timeline_path(_sweep(["theta", "scale"]), timeline_dim="theta")
        ticks = {
            frozenset(t.total_seconds() for t in tl["theta"]) for tl in _indices(path).values()
        }
        assert ticks == {frozenset({1.0, 2.0, 3.0})}

    def test_no_sample_is_dropped(self):
        entities = _indices(_timeline_path(_sweep(["theta", "scale"]), timeline_dim="theta"))
        assert sum(len(tl["theta"]) for tl in entities.values()) == 6

    def test_the_default_timeline_is_the_last_dimension(self):
        """Matches to_rerun_summary and to_video_summary, where the innermost
        dimension is the one that plays."""
        path = _timeline_path(_sweep(["theta", "scale"]))
        assert set(_indices(path)) == {"/theta_1.0/pose", "/theta_2.0/pose", "/theta_3.0/pose"}

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


class TestRerunTimelinePanes:
    def test_one_pane_for_a_2d_sweep(self):
        res = _sweep(["theta", "scale"])
        pane = res.to_rerun_timeline()
        assert pane is not None
        assert len(pane) == 1

    def test_declared_container_wins_over_the_rerun_viewer(self):
        """Same precedence as to_rerun_grid_ds and the over_time path."""
        bench = DeclaredContainerSweep().to_bench()
        res = bench.plot_sweep(input_vars=["theta"], result_vars=["out_rerun"])
        pane = res.to_rerun_timeline()
        assert pane is not None and len(pane) == 1
        assert isinstance(pane[0], pn.pane.Markdown), type(pane[0])
        assert pane[0].object.startswith("timeline: ")

    def test_registered_as_a_named_only_plot(self):
        from bencher.plugins.builtins import _named_only_specs

        assert "rerun_timeline" in {name for name, _, _ in _named_only_specs()}
