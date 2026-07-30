"""Tests for merging a sweep's per-sample rerun recordings into one viewer."""

import rerun as rr
from rerun.experimental import RrdReader

import bencher as bn
from bencher.results.bench_result_base import ReduceType
from bencher.results.composable_container.composable_container_base import (
    ComposeType,
    compose_method_list_for_dims,
)


class RerunSweep(bn.ParametrizedSweep):
    """Records one short scalar timeline per sample."""

    freq = bn.FloatSweep(default=1.0, bounds=[1.0, 3.0], samples=3)
    amp = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    out_rerun = bn.ResultRerun(width=200, height=150)

    def benchmark(self):
        recording = rr.RecordingStream("test_rerun_summary", make_default=False)
        for step in range(4):
            recording.set_time("time_s", duration=step * 0.1)
            recording.log("wave", rr.Scalars(self.amp * self.freq * step))
        self.out_rerun = bn.capture_rerun_rrd(recording)
        return super().benchmark()


def _leaf_entity_paths(path: str) -> set[str]:
    """Return the data entity paths of a composed recording."""
    reader = RrdReader(str(path))
    return {
        str(chunk.entity_path)
        for chunk in reader.stream(store=reader.recordings()[0])
        if str(chunk.entity_path).endswith("/wave")
    }


def _sweep(input_vars):
    bench = RerunSweep().to_bench()
    return bench.plot_sweep(input_vars=input_vars, result_vars=["out_rerun"])


class TestComposeMethodListForDims:
    def test_alternates_and_appends_sequence(self):
        methods = compose_method_list_for_dims(2, first_compose_method=ComposeType.down)
        assert methods[-1] == ComposeType.sequence
        # down -> right alternation, plus the trailing sequence.
        assert methods[1] == ComposeType.right

    def test_negative_sequences_everything(self):
        methods = compose_method_list_for_dims(3, time_sequence_dimension=-1)
        assert methods == [ComposeType.sequence] * 4

    def test_forces_sequence_up_to_dimension(self):
        methods = compose_method_list_for_dims(3, time_sequence_dimension=1)
        assert methods[0] == ComposeType.sequence
        assert methods[1] == ComposeType.sequence

    def test_matches_video_summary_helper(self):
        """The extracted helper must agree with VideoSummaryResult's method."""
        res = _sweep(["freq"])
        dataset = res.to_dataset(ReduceType.SQUEEZE, deep=False)
        assert res.dataset_to_compose_list(dataset) == compose_method_list_for_dims(
            len(dataset.sizes)
        )


class TestRerunSummary:
    def test_one_pane_for_a_2d_sweep(self):
        """A 3x2 sweep collapses to a single viewer pane, not six."""
        res = _sweep(["freq", "amp"])
        assert dict(res.to_dataset().sizes) == {"freq": 3, "amp": 2}
        pane = res.to_rerun_grid()
        assert pane is not None
        assert len(pane) == 1

    def test_every_sample_reaches_the_merged_recording(self):
        """Nesting must not drop samples: 3x2 leaves land in one recording."""
        res = _sweep(["freq", "amp"])
        rv = res.bench_cfg.result_vars[0]
        merged = res._compose_ds(res.to_dataset(ReduceType.SQUEEZE, deep=False), result_var=rv)
        assert merged is not None
        paths = _leaf_entity_paths(merged)
        assert len(paths) == 6, paths
        # Two levels of nesting, one per swept dimension.
        assert all(p.count("/item_") == 2 for p in paths), paths

    def test_1d_sweep_composes(self):
        res = _sweep(["freq"])
        rv = res.bench_cfg.result_vars[0]
        merged = res._compose_ds(res.to_dataset(ReduceType.SQUEEZE, deep=False), result_var=rv)
        assert merged is not None
        assert len(_leaf_entity_paths(merged)) == 3

    def test_summary_sequences_every_dimension(self):
        """to_rerun_summary is to_rerun_grid with everything on a timeline."""
        res = _sweep(["freq", "amp"])
        pane = res.to_rerun_summary()
        assert pane is not None
        assert len(pane) == 1

    def test_explicit_compose_method_list(self):
        res = _sweep(["freq", "amp"])
        pane = res.to_rerun_grid(
            compose_method_list=[ComposeType.right, ComposeType.down, ComposeType.sequence]
        )
        assert pane is not None
        assert len(pane) == 1

    def test_registered_as_named_only_plots(self):
        from bencher.plugins.builtins import _named_only_specs

        names = {name for name, _, _ in _named_only_specs()}
        assert {"rerun_summary", "rerun_grid"} <= names
