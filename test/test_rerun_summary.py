"""Tests for merging a sweep's per-sample rerun recordings into one viewer."""

# _compose_ds is exercised directly: it returns the composed .rrd path, which the
# public renderers wrap in a pane, so it is the only way to assert on the merge.
# pylint: disable=protected-access

from pathlib import Path

import panel as pn
import rerun as rr
from rerun.experimental import RrdReader

import bencher as bn
from bencher.results import rerun_summary
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


class Rerun3DSweep(bn.ParametrizedSweep):
    """Three swept dimensions, the smallest sweep where partial reversal shows."""

    freq = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    amp = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    mode = bn.StringSweep(["fast", "slow"])
    out_rerun = bn.ResultRerun(width=200, height=150)

    def benchmark(self):
        recording = rr.RecordingStream("test_rerun_summary", make_default=False)
        for step in range(4):
            recording.set_time("time_s", duration=step * 0.1)
            recording.log("wave", rr.Scalars(self.amp * self.freq * step))
        self.out_rerun = bn.capture_rerun_rrd(recording)
        return super().benchmark()


def name_only(path: str) -> pn.pane.Markdown:
    """A declared container that names the composition instead of embedding a viewer.

    Module level, not a closure: the declared container is pickled into the cache
    along with the result var.
    """
    return pn.pane.Markdown(f"composed: {Path(path).name}")


class DeclaredContainerSweep(RerunSweep):
    """A ResultRerun declaring how it renders, in place of the rerun viewer."""

    out_rerun = bn.ResultRerun(width=200, height=150, container=name_only)


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


def _record_levels(monkeypatch) -> list[tuple[str, ComposeType]]:
    """Capture ``(dimension, compose_method)`` per composition level, outermost first.

    ``_compose_ds`` builds one container per level before recursing, and names it
    after the dimension it peels, so intercepting construction is what reveals the
    peel order and the method each level ended up with.
    """
    levels: list[tuple[str, ComposeType]] = []
    real = rerun_summary.ComposableContainerRerun

    def spy(**kwargs):
        levels.append((kwargs["name"], kwargs["compose_method"]))
        return real(**kwargs)

    monkeypatch.setattr(rerun_summary, "ComposableContainerRerun", spy)
    return levels


def _dedupe(pairs):
    """First occurrence of each level, dropping the repeats from sibling slices."""
    seen, ordered = set(), []
    for name, method in pairs:
        if name in seen:
            continue
        seen.add(name)
        ordered.append((name, method))
    return ordered


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

    def test_declared_container_wins_over_the_rerun_viewer(self):
        """Same precedence as ds_to_container and the over_time path (PR #1015).

        The declared container receives the *composed* recording, so unlike
        test_rerun_declared_container the leaves must be real .rrd files.
        """
        bench = DeclaredContainerSweep().to_bench()
        res = bench.plot_sweep(input_vars=["freq"], result_vars=["out_rerun"])
        pane = res.to_rerun_grid()
        assert pane is not None and len(pane) == 1
        rendered = pane[0]
        assert isinstance(rendered, pn.pane.Markdown), type(rendered)
        assert rendered.object.startswith("composed: ")
        assert rendered.object.endswith(".rrd")

    def test_short_compose_method_list_is_honoured(self, monkeypatch):
        """A list shorter than the sweep must still apply its last entry.

        The list is consumed from the end, so a single-entry list belongs to the
        outermost dimension rather than being dropped for the default method.
        """
        levels = _record_levels(monkeypatch)
        res = _sweep(["freq", "amp"])
        res.to_rerun_grid(compose_method_list=[ComposeType.overlay])
        assert _dedupe(levels)[0] == ("amp", ComposeType.overlay)

    def test_registered_as_named_only_plots(self):
        from bencher.plugins.builtins import _named_only_specs

        names = {name for name, _, _ in _named_only_specs()}
        assert {"rerun_summary", "rerun_grid"} <= names


class TestReverse:
    """``reverse`` has to flip every level, not just the outermost one."""

    @staticmethod
    def _order(monkeypatch, reverse: bool) -> list[str]:
        levels = _record_levels(monkeypatch)
        bench = Rerun3DSweep().to_bench()
        res = bench.plot_sweep(input_vars=["freq", "amp", "mode"], result_vars=["out_rerun"])
        res.to_rerun_grid(reverse=reverse)
        return [name for name, _ in _dedupe(levels)]

    def test_forward_peels_outermost_last(self, monkeypatch):
        assert self._order(monkeypatch, reverse=False) == ["mode", "amp", "freq"]

    def test_reverse_peels_every_level(self, monkeypatch):
        """Reversing only the top level would give freq, mode, amp."""
        assert self._order(monkeypatch, reverse=True) == ["freq", "amp", "mode"]


class TestOverride:
    def test_override_is_not_swallowed(self):
        """Every plot callback is invoked with ``override=``, so it must reach the filter.

        A sweep with no input vars fails the shape filter, which is what makes the
        difference between honouring and dropping the keyword observable.
        """
        bench = RerunSweep().to_bench()
        res = bench.plot_sweep(input_vars=[], result_vars=["out_rerun"])
        assert isinstance(res.to_rerun_grid(), pn.pane.Markdown)  # filter message
        assert len(res.to_rerun_grid(override=True)) == 1
