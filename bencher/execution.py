"""Collection-time identity, independent of configuration and workflow identity."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4


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

    def __post_init__(self) -> None:
        for field in ("display_label", "source_revision", "workflow", "workflow_run", "lane"):
            value = getattr(self, field)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"execution {field} must be a string")
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
        """
        timestamp = datetime.now(UTC)
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
