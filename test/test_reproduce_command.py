"""The command a launcher exports to say how its execution is run again."""

from __future__ import annotations

import json

import pytest

import bencher as bn
from bencher.example.benchmark_data import ExampleBenchCfg
from bencher.execution import REPRODUCE_COMMAND_LIMIT, Execution, environment_provenance

COMMAND = "nightly-bench --suite sin --lane gpu-02"


def collect():
    bench = bn.Bench("reproduction", ExampleBenchCfg())
    try:
        return bench.collect(
            input_vars=[ExampleBenchCfg.param.theta],
            result_vars=[ExampleBenchCfg.param.out_sin],
            run_cfg=bn.BenchRunCfg(),
        )
    finally:
        bench.close()


def freeze(tmp_path):
    """Freeze one collected sweep and return its entry page."""
    return bn.render_report(
        bn.save_results([collect()], tmp_path / "results.pkl"),
        tmp_path / "reports",
        complete=True,
    )


def test_an_execution_records_no_command_unless_one_is_given():
    """Bencher cannot know how it was started, so it never invents an answer."""
    assert Execution.start().reproduce_command is None


def test_the_launcher_exports_the_command_it_composed(monkeypatch):
    monkeypatch.setenv("BENCHER_REPRODUCE_COMMAND", COMMAND)
    assert Execution.start().reproduce_command == COMMAND


def test_an_argument_wins_over_the_environment(monkeypatch):
    monkeypatch.setenv("BENCHER_REPRODUCE_COMMAND", COMMAND)
    assert Execution.start(reproduce_command="in-process").reproduce_command == "in-process"


@pytest.mark.parametrize("value", ["", "   "])
def test_an_exported_blank_is_not_a_command(monkeypatch, value):
    """A job template that exports a command it does not have says nothing."""
    monkeypatch.setenv("BENCHER_REPRODUCE_COMMAND", value)
    assert Execution.start().reproduce_command is None


def test_a_supplied_field_is_never_read_from_the_environment():
    env = {"BENCHER_REPRODUCE_COMMAND": COMMAND}
    assert environment_provenance(env) == {"reproduce_command": COMMAND}
    assert environment_provenance(env, supplied=["reproduce_command"]) == {}


def test_an_oversized_export_is_refused_by_name(monkeypatch):
    """Every character is carried by report.json and rendered into the page."""
    monkeypatch.setenv("BENCHER_REPRODUCE_COMMAND", "x" * (REPRODUCE_COMMAND_LIMIT + 1))
    with pytest.raises(ValueError, match="BENCHER_REPRODUCE_COMMAND"):
        Execution.start()


def test_an_oversized_argument_is_refused_too():
    with pytest.raises(ValueError, match="reproduce_command"):
        Execution.start(reproduce_command="x" * (REPRODUCE_COMMAND_LIMIT + 1))
    longest = "x" * REPRODUCE_COMMAND_LIMIT
    assert Execution.start(reproduce_command=longest).reproduce_command == longest


def test_a_command_that_is_not_a_string_is_refused():
    with pytest.raises(TypeError, match="reproduce_command"):
        Execution.start(reproduce_command=["nightly-bench"])


def test_the_frozen_report_records_the_command(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BENCHER_REPRODUCE_COMMAND", COMMAND)
    entry = freeze(tmp_path)
    manifest = json.loads(entry.with_name("report.json").read_text())
    assert manifest["execution"]["reproduce_command"] == COMMAND


def test_the_published_entry_page_shows_the_command(tmp_path, monkeypatch):
    """A recorded value nobody can read is a value nobody reads."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BENCHER_REPRODUCE_COMMAND", COMMAND)
    monkeypatch.setenv("BENCHER_LANE", "gpu-02")
    page = freeze(tmp_path).read_text(encoding="utf-8")
    assert COMMAND in page
    assert "gpu-02" in page


def test_markup_in_the_command_cannot_reach_the_page(tmp_path, monkeypatch):
    """It is free text from the environment, and the page is published."""
    monkeypatch.chdir(tmp_path)
    payload = '<script>alert("reproduction")</script>'
    monkeypatch.setenv("BENCHER_REPRODUCE_COMMAND", payload)
    page = freeze(tmp_path).read_text(encoding="utf-8")
    assert payload not in page
    assert "&lt;script&gt;alert(&quot;reproduction&quot;)&lt;/script&gt;" in page


def test_a_frozen_report_round_trips_through_verification(tmp_path, monkeypatch):
    """An added field must survive the reader that rebuilds the whole execution."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BENCHER_REPRODUCE_COMMAND", COMMAND)
    entry = freeze(tmp_path)
    manifest = bn.verify_report(entry.parent)
    assert Execution(**manifest["execution"]).reproduce_command == COMMAND


def test_a_report_without_the_key_still_rebuilds_its_execution(tmp_path, monkeypatch):
    """A report frozen before this field existed carries no key for it."""
    monkeypatch.chdir(tmp_path)
    entry = freeze(tmp_path)
    manifest = json.loads(entry.with_name("report.json").read_text())
    assert manifest["execution"]["reproduce_command"] is None
    del manifest["execution"]["reproduce_command"]
    assert Execution(**manifest["execution"]).reproduce_command is None
