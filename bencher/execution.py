"""Collection-time identity, independent of configuration and workflow identity."""

from __future__ import annotations

import os
from collections.abc import Collection, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

# The launcher is often not this process: a CI job or a wrapper script starts the
# benchmark and is the only thing that knows which revision it checked out. These
# name the same fields a caller passes to `Execution.start`, so provenance can
# cross a process boundary without bencher inferring any of it.
PROVENANCE_ENV = {
    "display_label": "BENCHER_DISPLAY_LABEL",
    "source_revision": "BENCHER_SOURCE_REVISION",
    "workflow": "BENCHER_WORKFLOW",
    "workflow_run": "BENCHER_WORKFLOW_RUN",
    "lane": "BENCHER_LANE",
    "attempt": "BENCHER_ATTEMPT",
    "reproduce_command": "BENCHER_REPRODUCE_COMMAND",
}

# A command longer than this is not one a reader will copy off a page, and every
# character of it is carried by report.json and rendered into the report. A
# launcher with more to say exports the name of a script instead.
REPRODUCE_COMMAND_LIMIT = 1024


def environment_provenance(
    env: Mapping[str, str] | None = None, *, supplied: Collection[str] = ()
) -> dict:
    """Read :data:`PROVENANCE_ENV` as keyword arguments for :meth:`Execution.start`.

    A variable that is unset, empty or blank is absent rather than "": a job
    template that exports a value it does not have must not attribute the
    execution to one. Provenance is reported, never checked -- an exported
    revision that no longer matches the checkout is the launcher's mistake to
    avoid, and is why a long-lived shell should not export these.

    A field named in *supplied* is not read at all, because the caller has
    already answered it.

    Raises:
        ValueError: If the attempt variable is read and does not hold a positive
            integer -- a misattributed retry is worse than a failed run -- or if
            the reproduce command variable is longer than
            :data:`REPRODUCE_COMMAND_LIMIT`.
    """
    source = os.environ if env is None else env
    provenance: dict = {}
    for field, name in PROVENANCE_ENV.items():
        if field in supplied:
            continue
        value = source.get(name, "").strip()
        if not value:
            continue
        if field == "reproduce_command" and len(value) > REPRODUCE_COMMAND_LIMIT:
            raise ValueError(f"{name} must be at most {REPRODUCE_COMMAND_LIMIT} characters")
        if field != "attempt":
            provenance[field] = value
            continue
        try:
            attempt = int(value)
        except ValueError:
            attempt = 0
        if attempt < 1:
            raise ValueError(f"{name} must be a positive integer, not {value!r}")
        provenance[field] = attempt
    return provenance


@dataclass(frozen=True)
class Execution:
    """Immutable provenance captured when measurement starts; never during rendering."""

    uuid: str
    executed_at: str
    display_label: str
    source_revision: str | None = None
    workflow: str | None = None
    workflow_run: str | None = None
    lane: str | None = None
    attempt: int | None = None
    reproduce_command: str | None = None
    """How to run this execution again, as the launcher wrote it.

    Bencher never composes this string and never runs it. It is opaque display
    text, reported beside the rest of the provenance so a reader of a published
    report can see how the run was started; nothing here parses it, shells it
    out, or checks that it still works. What it says is the launcher's business.
    """

    def __post_init__(self) -> None:
        for field in (
            "display_label",
            "source_revision",
            "workflow",
            "workflow_run",
            "lane",
            "reproduce_command",
        ):
            value = getattr(self, field)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"execution {field} must be a string")
        command = self.reproduce_command
        if command is not None and len(command) > REPRODUCE_COMMAND_LIMIT:
            raise ValueError(
                f"execution reproduce_command must be at most {REPRODUCE_COMMAND_LIMIT} characters"
            )
        if self.attempt is not None and (type(self.attempt) is not int or self.attempt < 1):
            raise ValueError("execution attempt must be a positive integer")
        if str(UUID(self.uuid)) != self.uuid:
            raise ValueError("execution UUID must use canonical form")
        timestamp = datetime.fromisoformat(self.executed_at)
        if timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0:
            raise ValueError("execution timestamp must be UTC")

    @classmethod
    def start(cls, **provenance) -> Execution:
        """Start a new execution using optional caller-supplied provenance.

        Resolve git metadata in the launcher before starting foreign threads;
        this function does not run subprocesses or infer a checkout revision.
        A launcher in another process supplies the same fields through
        :data:`PROVENANCE_ENV`; a field passed here leaves its variable unread,
        so an argument wins over an unusable value as well as a usable one.
        """
        timestamp = datetime.now(UTC)
        provenance = {**environment_provenance(supplied=provenance.keys()), **provenance}
        return cls(
            uuid=str(uuid4()),
            executed_at=timestamp.isoformat(),
            display_label=provenance.pop(
                "display_label", timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
            ),
            **provenance,
        )

    def to_dict(self) -> dict:
        """Return JSON-compatible provenance."""
        return asdict(self)


_CURRENT: ContextVar[Execution | None] = ContextVar("bencher_execution", default=None)


def current_execution() -> Execution:
    """Use the active bundle identity, or start an independent sweep execution."""
    return _CURRENT.get() or Execution.start()


@contextmanager
def execution_context(**provenance) -> Iterator[Execution]:
    """Group collected sweeps into one new execution, including across configurations."""
    execution = Execution.start(**provenance)
    token = _CURRENT.set(execution)
    try:
        yield execution
    finally:
        _CURRENT.reset(token)


@contextmanager
def execution_scope() -> Iterator[Execution]:
    """Start a runner execution unless its launcher already supplied one."""
    current = _CURRENT.get()
    if current is not None:
        yield current
    else:
        with execution_context() as execution:
            yield execution
