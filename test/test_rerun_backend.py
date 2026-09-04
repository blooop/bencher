"""backend="rerun" must render ``ResultRerun`` recordings, not drop them (#1134).

Before this, ``to_rerun`` dispatched every result var through the scalar
renderers, so a ``ResultRerun``'s ``.rrd`` *path string* reached the bar-chart
renderer and died on ``float(path)``: the report showed the scalar charts and
none of the recordings, with one WARNING per sample as the only signal.
"""

# _to_rerun_recordings is the half of to_rerun under test; the public method wraps
# it in a Column with the mapped viewer.
# pylint: disable=protected-access

import re
from pathlib import Path

import panel as pn
import pytest
import rerun as rr
from rerun.experimental import RrdReader

import bencher as bn
from bencher.results.bench_result_base import ReduceType
from bencher.results.rerun_result import RerunResult

LOGGER = "bencher.results.rerun_result"


def name_only(path: str) -> pn.pane.Markdown:
    """Declared container naming the composition instead of embedding a viewer.

    Module level, not a closure: the declared container is pickled into the
    result cache along with the result var.
    """
    return pn.pane.Markdown(f"composed: {path}")


class BackendSweep(bn.ParametrizedSweep):
    """A scalar metric and a recording, the combination that used to drop."""

    shape = bn.StringSweep(["cube", "sphere", "cone"])

    volume = bn.ResultFloat(units="m3")
    recording = bn.ResultRerun(width=200, height=150, container=name_only)

    def benchmark(self):
        self.volume = {"cube": 1.0, "sphere": 4.19, "cone": 1.05}[self.shape]
        recording = rr.RecordingStream("test_rerun_backend", make_default=False)
        recording.log("points", rr.Points3D([[1.0, 2.0, 3.0]]), static=True)
        self.recording = bn.capture_rerun_rrd(recording)
        return super().benchmark()


class RecordingOnlySweep(BackendSweep):
    """No scalar result var, so nothing is left to map onto the entity tree."""

    volume = None


def _sweep(cls=BackendSweep, result_vars=("volume", "recording")):
    run_cfg = bn.BenchRunCfg(repeats=1, backend="rerun")
    bench = cls().to_bench(run_cfg)
    return bench.plot_sweep(input_vars=["shape"], result_vars=list(result_vars))


def _composed_path(pane: pn.pane.Markdown) -> str:
    return pane.object.removeprefix("composed: ")


def _leaf_entity_paths(path: str) -> set[str]:
    reader = RrdReader(str(path))
    return {
        str(chunk.entity_path)
        for chunk in reader.stream(store=reader.recordings()[0])
        if str(chunk.entity_path).endswith("/points")
    }


class TestRerunBackendRecordings:
    def test_backend_selects_the_rerun_report_callback(self):
        res = _sweep()
        assert res.bench_cfg.plot_callbacks == [RerunResult.to_rerun_plots]

    def test_recording_gets_its_own_pane_beside_the_scalar_viewer(self):
        """A ResultRerun swept with a scalar yields two panes, not one."""
        res = _sweep()
        panes = res.to_rerun()
        assert isinstance(panes, pn.Column), type(panes)
        assert len(panes) == 2
        assert _composed_path(panes[1]).endswith(".rrd")

    def test_every_sample_reaches_the_merged_recording(self):
        """The recordings are composed, not dropped: all three samples land in one .rrd."""
        res = _sweep()
        merged = _composed_path(res.to_rerun()[1])
        assert Path(merged).is_file()
        assert len(_leaf_entity_paths(merged)) == 3, _leaf_entity_paths(merged)

    def test_no_float_coercion_of_the_rrd_path(self, caplog):
        """The bug's signature: one 'could not convert string to float' per sample."""
        res = _sweep()
        with caplog.at_level("WARNING", logger=LOGGER):
            res.to_rerun()
        assert not re.search("could not convert string to float", caplog.text), caplog.text
        assert "recording" not in caplog.text, caplog.text

    def test_recording_reaches_the_report_layout(self):
        """to_rerun_plots is what the backend actually renders, so it carries it too."""
        res = _sweep()
        report = res.to_rerun_plots()
        assert _composed_path(report[1][1]).endswith(".rrd")

    def test_recording_only_sweep_skips_the_empty_mapped_viewer(self):
        """With nothing to map there is no empty recording to embed, so one pane."""
        res = _sweep(RecordingOnlySweep, result_vars=("recording",))
        pane = res.to_rerun()
        assert isinstance(pane, pn.pane.Markdown), type(pane)
        assert _composed_path(pane).endswith(".rrd")


class TestNothingRecorded:
    def test_unrecorded_result_var_warns_instead_of_showing_nothing(self, caplog):
        """A ResultRerun that recorded nothing says so, rather than silently vanishing."""
        res = _sweep()
        rv = next(rv for rv in res.bench_cfg.result_vars if rv.name == "recording")
        # to_dataset caches per instance and deep=False hands back that cached
        # object, so blanking it here is what _to_rerun_recordings will read.
        res.to_dataset(ReduceType.SQUEEZE, deep=False)["recording"][:] = "NAN"
        with caplog.at_level("WARNING", logger=LOGGER):
            panes = res._to_rerun_recordings([rv])
        assert panes == []
        assert "No rerun recordings to merge" in caplog.text
        assert "recording" in caplog.text


if __name__ == "__main__":
    pytest.main([__file__])
