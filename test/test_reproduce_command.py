"""The command a launcher exports to say how its execution is run again."""

from __future__ import annotations

import pytest

from bencher.execution import REPRODUCE_COMMAND_LIMIT, Execution, environment_provenance

COMMAND = "nightly-bench --suite sin --lane gpu-02"


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
