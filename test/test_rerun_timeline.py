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
    _DurationIndex,
    _entity_parts,
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


class TestRerunTimelineND:
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

        panes = {(name, backend) for name, backend, _ in _builtin_specs() if name == "panes"}
        assert panes == {("panes", "panel"), ("panes", "rerun")}

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
