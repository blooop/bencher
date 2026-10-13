"""backend="rerun" must render ``ResultRerun`` recordings, not drop them (#1134).

Before this, ``to_rerun`` dispatched every result var through the scalar
renderers, so a ``ResultRerun``'s ``.rrd`` *path string* reached the bar-chart
renderer and died on ``float(path)``: the report showed the scalar charts and
none of the recordings, with one WARNING per sample as the only signal.
"""

# _to_rerun_recordings is the half of to_rerun under test; the public method wraps
# it in a Column with the mapped viewer.

import re
from pathlib import Path

import panel as pn
import pytest
import rerun as rr
import rerun.blueprint as rrb
from rerun.chunk import RrdReader

import bencher as bn
from bencher.plugins.registry import get_registry
from bencher.results.bench_result_base import ReduceType
from bencher.results.rerun_result import RerunResult, _build_blueprint

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


def _blank(res, name: str) -> None:
    """Blank every cell of *name*, as if the sweep had never recorded it.

    ``to_dataset`` caches per instance and ``deep=False`` hands back that cached
    object, so this is what the renderer under test goes on to read.
    """
    res.to_dataset(ReduceType.SQUEEZE, deep=False)[name][:] = "NAN"


def _leaf_entity_paths(path: str) -> set[str]:
    reader = RrdReader(str(path))
    return {
        str(chunk.entity_path)
        for chunk in reader.stream(store=reader.recordings()[0])
        if str(chunk.entity_path).endswith("/points")
    }


class TestRerunBackendRecordings:
    def test_backend_is_a_plot_selection_preference_not_a_separate_report(self):
        """``backend`` reaches plot selection, where a chart type implemented by both
        backends resolves to the rerun one. It used to swap the whole callback list
        for a rerun-only report, which only worked on sweeps that had no callbacks of
        their own."""
        res = _sweep()
        assert res.bench_cfg.backend == "rerun"
        chosen = {(p.name, p.backend) for p in get_registry().select(res.to_bench_data())}
        assert ("panes", "panel") in chosen
        chosen_rerun = {
            (p.name, p.backend) for p in get_registry().select(res.to_bench_data(), backend="rerun")
        }
        assert ("panes", "rerun") in chosen_rerun

    def test_the_all_rerun_report_is_still_reachable_by_callback(self):
        res = _sweep()
        bench = BackendSweep().to_bench(bn.BenchRunCfg(repeats=1, backend="rerun"))
        res = bench.plot_sweep(
            input_vars=["shape"],
            result_vars=["volume", "recording"],
            plot_callbacks=[RerunResult.to_rerun_plots],
        )
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

    def test_recording_named_by_string_is_still_merged(self, caplog):
        """``to_dataset`` takes a result var by name, so ``to_rerun`` has to resolve one.

        An unresolved name is a string, which no ``isinstance(rv, ResultRerun)`` can
        classify, so the recording went back through the bar-chart renderer.
        """
        res = _sweep()
        with caplog.at_level("WARNING", logger=LOGGER):
            pane = res.to_rerun(result_var="recording")
        assert isinstance(pane, pn.pane.Markdown), type(pane)
        assert _composed_path(pane).endswith(".rrd")
        assert "could not convert string to float" not in caplog.text, caplog.text

    def test_scalar_named_by_string_still_maps(self):
        """Resolving names must not divert a scalar away from the mapped viewer."""
        res = _sweep()
        pane = res.to_rerun(result_var="volume")
        assert isinstance(pane, pn.pane.HTML), type(pane)

    def test_unknown_result_var_name_is_refused_by_name(self):
        """An unresolvable name has to stop here; it cannot be classified by type."""
        res = _sweep()
        with pytest.raises(ValueError, match="nope") as excinfo:
            res.to_rerun(result_var="nope")
        assert "recording" in str(excinfo.value), excinfo.value

    def test_recording_only_sweep_skips_the_empty_mapped_viewer(self):
        """With nothing to map there is no empty recording to embed, so one pane."""
        res = _sweep(RecordingOnlySweep, result_vars=("recording",))
        pane = res.to_rerun()
        assert isinstance(pane, pn.pane.Markdown), type(pane)
        assert _composed_path(pane).endswith(".rrd")


class TestNothingRecorded:
    def test_recording_only_sweep_with_nothing_recorded_says_so(self, caplog):
        """The report must not get a hole where the only result var recorded nothing.

        The mapped viewer is skipped when there is nothing to map, so with the
        recordings gone too there is no pane left to return.
        """
        res = _sweep(RecordingOnlySweep, result_vars=("recording",))
        _blank(res, "recording")
        with caplog.at_level("WARNING", logger=LOGGER):
            pane = res.to_rerun()
        assert isinstance(pane, pn.pane.Markdown), type(pane)
        assert "recording" in pane.object, pane.object
        assert len(pn.Column(pane)) == 1
        assert "No rerun recordings to merge" in caplog.text

    def test_unrecorded_result_var_warns_instead_of_showing_nothing(self, caplog):
        """A ResultRerun that recorded nothing says so, rather than silently vanishing."""
        res = _sweep()
        rv = next(rv for rv in res.bench_cfg.result_vars if rv.name == "recording")
        _blank(res, "recording")
        with caplog.at_level("WARNING", logger=LOGGER):
            panes = res._to_rerun_recordings([rv])
        assert panes == []
        assert "No rerun recordings to merge" in caplog.text
        assert "recording" in caplog.text


class RepeatedLineSweep(bn.ParametrizedSweep):
    """A 1-float line whose repeats spread by a known amount at each point."""

    x = bn.FloatSweep(default=0.0, bounds=[0.0, 2.0], samples=3)

    out = bn.ResultFloat()
    timed = bn.ResultFloat(units="s")
    label = bn.ResultString()

    calls = 0

    def benchmark(self):
        # Successive calls alternate x - 1 and x + 1. With three points and two
        # repeats, each point gets one of each whichever order the sweep runs in,
        # so its mean is x and its std (xarray's, ddof=0) is 1. That needs an odd
        # sample count: with an even one, every point's calls share one parity.
        assert self.param.x.samples % 2 == 1, "samples must stay odd"
        RepeatedLineSweep.calls += 1
        self.out = self.x + (1.0 if RepeatedLineSweep.calls % 2 else -1.0)
        self.timed = self.out
        self.label = f"x={self.x}"
        return super().benchmark()


class FlatSecondDimSweep(RepeatedLineSweep):
    """A line over ``x`` with a second float dim of one sample."""

    y = bn.FloatSweep(default=0.0, bounds=[0.0, 1.0], samples=1)


class UserStdSweep(RepeatedLineSweep):
    """A user result var whose name happens to end in ``_std``."""

    out_std = bn.ResultFloat()

    def benchmark(self):
        self.out_std = 5.0
        return super().benchmark()


def _record(monkeypatch, sweep, input_vars, result_vars, repeats=2) -> str:
    """Run *sweep* on the rerun backend and return the path of the .rrd it wrote."""
    captured = {}

    def capture(path, **_kwargs):
        captured["path"] = path
        return pn.pane.Markdown("viewer")

    monkeypatch.setattr("bencher.utils_rrd.rrd_file_to_pane", capture)
    RepeatedLineSweep.calls = 0
    run_cfg = bn.BenchRunCfg(
        repeats=repeats, backend="rerun", cache_results=False, cache_samples=False
    )
    res = (
        sweep()
        .to_bench(run_cfg)
        .plot_sweep(input_vars=input_vars, result_vars=result_vars, plot_callbacks=False)
    )
    res.to_rerun()
    return str(captured["path"])


def _entity_batches(path: str, entity: str) -> list:
    reader = RrdReader(path)
    return [
        chunk.to_record_batch()
        for chunk in reader.stream(store=reader.recordings()[0])
        if str(chunk.entity_path) == entity
    ]


class TestRepeatsDrawABand:
    def test_line_graph_with_repeats_logs_measurements_with_variance(self, monkeypatch):
        """``repeats > 1`` used to log nothing: a squeezed dataset keeps ``repeat``,
        and one-value-per-cell reads failed with "can only convert an array of size
        1". The mean must now reach the recording with its variance for the band."""
        captured = {}

        def capture(path, **_kwargs):
            captured["path"] = path
            return pn.pane.Markdown("viewer")

        monkeypatch.setattr("bencher.utils_rrd.rrd_file_to_pane", capture)
        RepeatedLineSweep.calls = 0
        run_cfg = bn.BenchRunCfg(
            repeats=2, backend="rerun", cache_results=False, cache_samples=False
        )
        res = (
            RepeatedLineSweep()
            .to_bench(run_cfg)
            .plot_sweep(input_vars=["x"], result_vars=["out", "label"], plot_callbacks=False)
        )
        res.to_rerun(result_var="out")

        reader = RrdReader(str(captured["path"]))
        values, variances = [], []
        for chunk in reader.stream(store=reader.recordings()[0]):
            if str(chunk.entity_path) != "/out":
                continue
            batch = chunk.to_record_batch()
            values += [v[0] for v in batch.column("Measurements:values").to_pylist()]
            variances += [v[0] for v in batch.column("Measurements:variances").to_pylist()]
            assert "Measurements:units" not in batch.schema.names
        assert values == pytest.approx([0.0, 1.0, 2.0])
        assert variances == pytest.approx([1.0, 1.0, 1.0])

    def test_units_reach_the_recording(self, monkeypatch):
        """The unitless default ``ul`` logs no units; any other unit reaches the legend."""
        path = _record(monkeypatch, RepeatedLineSweep, ["x"], ["out", "timed"])
        out_columns = {c for b in _entity_batches(path, "/out") for c in b.schema.names}
        assert "Measurements:values" in out_columns
        assert "Measurements:units" not in out_columns
        units = [
            u
            for b in _entity_batches(path, "/timed")
            for u in b.column("Measurements:units").to_pylist()
        ]
        assert units == [["s"]] * 3

    def test_one_sample_dim_keeps_the_line_graph(self, monkeypatch):
        """A float dim of one sample is squeezed out with ``repeats=1``, so the sweep
        is a line graph. ``repeats=2`` kept it in the reduced vars, and ``/out`` came
        back as one 3x1 tensor instead of three points with a band."""
        path = _record(monkeypatch, FlatSecondDimSweep, ["x", "y"], ["out"])
        batches = _entity_batches(path, "/out")
        values = [v[0] for b in batches for v in b.column("Measurements:values").to_pylist()]
        assert values == pytest.approx([0.0, 1.0, 2.0])
        assert all("log_tick" in b.schema.names for b in batches)

    def test_a_user_var_named_std_draws_no_band(self, monkeypatch):
        """With ``repeats=1`` nothing is reduced, so ``/out`` has no spread. A user
        var named ``out_std`` used to be read as one and drew a fabricated band."""
        path = _record(monkeypatch, UserStdSweep, ["x"], ["out", "out_std"], repeats=1)
        columns = {c for b in _entity_batches(path, "/out") for c in b.schema.names}
        assert "Scalars:scalars" in columns
        assert not any(c.startswith("Measurements:") for c in columns)


class TestBlueprintTimeline:
    """The blueprint pins ``log_tick`` only when the recording logs on it."""

    @staticmethod
    def _pinned_timeline(float_dims, cat_dims, time_dim=None):
        dims = [*float_dims, *cat_dims]
        blueprint = _build_blueprint(
            rrb=rrb,
            result_vars=[RepeatedLineSweep.param.out],
            float_dims=float_dims,
            cat_dims=cat_dims,
            time_dim=time_dim,
            dim_values={d: ["0", "1"] for d in dims},
        )
        return getattr(getattr(blueprint, "time_panel", None), "timeline", None)

    @pytest.mark.parametrize(
        ("float_dims", "time_dim"), [(["x"], None), ([], "over_time"), (["x", "y"], "over_time")]
    )
    def test_pinned_when_logged_on_log_tick(self, float_dims, time_dim):
        assert self._pinned_timeline(float_dims, [], time_dim) == "log_tick"

    @pytest.mark.parametrize(
        ("float_dims", "cat_dims"), [([], []), ([], ["c"]), (["x", "y"], []), (["x", "y"], ["c"])]
    )
    def test_not_pinned_when_nothing_is_on_log_tick(self, float_dims, cat_dims):
        """A recording with no ``log_tick`` rows pinned to it showed an empty view."""
        assert self._pinned_timeline(float_dims, cat_dims) is None


if __name__ == "__main__":
    pytest.main([__file__])
