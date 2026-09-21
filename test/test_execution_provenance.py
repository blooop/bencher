"""Provenance an out-of-process launcher exports, and what it may not override."""

from __future__ import annotations

import json

import pytest

import bencher as bn
from bencher.example.benchmark_data import ExampleBenchCfg
from bencher.execution import Execution, environment_provenance


@pytest.fixture(name="launcher_env")
def exported_provenance(monkeypatch) -> None:
    """What a CI job exports around the process that actually runs the benchmark."""
    monkeypatch.setenv("BENCHER_SOURCE_REVISION", "0123456789abcdef")
    monkeypatch.setenv("BENCHER_WORKFLOW", "nightly")
    monkeypatch.setenv("BENCHER_WORKFLOW_RUN", "4471")
    monkeypatch.setenv("BENCHER_LANE", "gpu-02")
    monkeypatch.setenv("BENCHER_ATTEMPT", "2")
    monkeypatch.setenv("BENCHER_DISPLAY_LABEL", "nightly #4471")


def collect(run_cfg=None):
    bench = bn.Bench("provenance", ExampleBenchCfg())
    try:
        return bench.collect(
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=run_cfg or bn.BenchRunCfg(),
        )
    finally:
        bench.close()


@pytest.mark.usefixtures("launcher_env")
def test_the_launcher_fills_every_field_it_knows():
    execution = Execution.start()
    assert execution.source_revision == "0123456789abcdef"
    assert execution.workflow == "nightly"
    assert execution.workflow_run == "4471"
    assert execution.lane == "gpu-02"
    assert execution.attempt == 2
    assert execution.display_label == "nightly #4471"


@pytest.mark.usefixtures("launcher_env")
def test_an_argument_wins_over_the_environment():
    """A launcher that already resolved the revision in-process is the better source."""
    execution = Execution.start(source_revision="in-process", attempt=1)
    assert execution.source_revision == "in-process"
    assert execution.attempt == 1
    assert execution.workflow == "nightly"


@pytest.mark.usefixtures("launcher_env")
def test_the_identity_is_never_inherited():
    """Only provenance crosses the boundary; each execution is still its own."""
    assert Execution.start().uuid != Execution.start().uuid


@pytest.mark.parametrize("value", ["", "   "])
def test_an_exported_blank_is_not_a_revision(monkeypatch, value):
    """A job template that exports a value it does not have must not attribute
    the execution to ""."""
    monkeypatch.setenv("BENCHER_SOURCE_REVISION", value)
    assert Execution.start().source_revision is None


@pytest.mark.parametrize("value", ["first", "0", "-1", "1.5"])
def test_an_unusable_attempt_is_refused_by_name(monkeypatch, value):
    """Silently dropping it would attribute a retry to the first attempt."""
    monkeypatch.setenv("BENCHER_ATTEMPT", value)
    with pytest.raises(ValueError, match="BENCHER_ATTEMPT"):
        Execution.start()


def test_an_explicit_environment_can_be_read_without_exporting_it():
    assert environment_provenance({"BENCHER_LANE": "gpu-02"}) == {"lane": "gpu-02"}
    assert environment_provenance({}) == {}


@pytest.mark.usefixtures("launcher_env")
def test_a_collected_sweep_carries_the_exported_revision(tmp_path, monkeypatch):
    """The whole point: the run is a child process, and its report says so."""
    monkeypatch.chdir(tmp_path)
    result = collect()
    assert result.bench_cfg.execution.source_revision == "0123456789abcdef"


@pytest.mark.usefixtures("launcher_env")
def test_a_frozen_report_records_it_for_publication(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    entry = bn.render_report(
        bn.save_results([collect()], tmp_path / "results.pkl"),
        tmp_path / "reports",
        complete=True,
    )
    manifest = json.loads(entry.with_name("report.json").read_text())
    assert manifest["execution"]["source_revision"] == "0123456789abcdef"
    assert manifest["execution"]["workflow_run"] == "4471"
