"""Keeping the execution a live pointer names from being reaped under an age policy.

A pointer is a redirect. The execution it names is a separate, immutable set of
objects under that execution's UUID, and under a backend Age-based Delete policy
the two age independently. Nothing about being pointed at makes an execution
young, so the redirect outlives what it redirects to and starts serving a URL
whose bytes are gone.

``renew_pointed_execution`` is the only thing that stops that: it reads the
pointer, lists the objects of the execution the pointer names, and resets the
storage age of every one of them. It renews the pointer object last, because the
pointer is under the same policy and can expire too -- and because an expired
pointer costs a link the next publication rewrites, while an expired execution
costs measurements nobody can take again.

Renewal extends the lifetime of what is stored; it does not prove the report is
complete. ``CompleteReportPublisher.verify`` does that, and it needs a receipt
that a scheduled maintenance pass does not have.
"""

from __future__ import annotations

from dataclasses import dataclass

from bencher.complete_report import safe_path
from bencher.object_store import (
    Absent,
    Conflict,
    ListFailed,
    ObjectInfo,
    ObjectStore,
    Present,
    ReadFailed,
    Renewed,
    Unsupported,
)
from bencher.publication_pointers import read_pointer
from bencher.publishing import http_base

MANIFEST = "report.json"


@dataclass(frozen=True)
class Refusal:
    """One object whose lifetime could not be extended, and why."""

    key: str
    reason: str


@dataclass(frozen=True)
class ExecutionRenewed:
    """Every object of the pointed-at execution, and the pointer, was renewed."""

    target: str
    prefix: str
    keys: tuple[str, ...]
    expires_at: float | None


@dataclass(frozen=True)
class RenewalIncomplete:
    """Some objects were renewed and at least one was refused.

    This is the outcome a caller must act on. A report page missing one asset is
    a broken report page, so a partial renewal is not a smaller success: the
    execution still expires at the oldest object's age, and the ``refused`` keys
    say which ones a human or a retry has to deal with.
    """

    target: str
    prefix: str
    renewed: tuple[str, ...]
    refused: tuple[Refusal, ...]


@dataclass(frozen=True)
class RenewalUnsupported:
    """The store has no expiry model, so no object of it can be renewed.

    A deployment whose storage has no age policy is a legitimate one -- there is
    nothing to keep alive because nothing is being reaped. Callers must tell this
    apart from a failure and do nothing about it.
    """

    reason: str
    target: str | None = None


@dataclass(frozen=True)
class NothingPointedAt:
    """The pointer key names no object, so no execution is current yet."""

    reason: str


@dataclass(frozen=True)
class PointerMoved:
    """The renewal finished, and by then the pointer named another execution.

    The execution that was renewed is the one the pointer named when the pass
    started. Whatever moved the pointer published the execution it now names, so
    that execution's objects were written or verified by that publication and are
    the youngest in the store. There is nothing to chase here; the next pass
    covers the new one.
    """

    renewed: str
    current: str


@dataclass(frozen=True)
class RenewalFailed:
    """Nothing could be renewed, because the pointer or its execution is unusable."""

    reason: str
    key: str | None = None


RenewalOutcome = (
    ExecutionRenewed
    | RenewalIncomplete
    | RenewalUnsupported
    | NothingPointedAt
    | PointerMoved
    | RenewalFailed
)


def execution_prefix(target: str, http_root: str, storage_root: str) -> str | None:
    """Return the storage prefix a served report URL names, or None if it is foreign.

    Storage and serving are independent namespaces, and only the publisher's two
    roots relate them: a report URL is ``<http_root>/<uuid>/<entry page>`` and its
    objects are ``<storage_root>/<uuid>/...``. A target under another serving root
    belongs to another deployment and this one must not renew objects for it.
    """
    base = f"{http_base(http_root)}/"
    if not target.startswith(base):
        return None
    uuid = target[len(base) :].split("/", 1)[0]
    if not uuid:
        return None
    try:
        safe_path(uuid)
    except ValueError:
        return None
    return f"{storage_root}/{uuid}"


def _inventory(store: ObjectStore, prefix: str) -> tuple[ObjectInfo, ...] | RenewalFailed:
    """List every object of one execution, following the listing's continuations.

    A listing is not a snapshot, but a published execution is immutable and
    complete before any pointer names it, so its inventory cannot grow underneath
    this pass.
    """
    items: list[ObjectInfo] = []
    token: str | None = None
    while True:
        listed = store.list(prefix=f"{prefix}/", token=token)
        if isinstance(listed, ListFailed):
            return RenewalFailed(listed.reason, prefix)
        items.extend(listed.items)
        if listed.complete:
            return tuple(items)
        token = listed.next_token


def _renew_one(
    store: ObjectStore, key: str, version: str, attempts: int
) -> Renewed | Unsupported | Refusal:
    """Renew one object, rereading its version when a concurrent write conflicts.

    ``Conflict`` means the version this pass observed is no longer the current
    one. Replaying it would prove nothing, so the object is reread and renewed at
    the version it now has, within a bounded budget.
    """
    for _ in range(attempts):
        outcome = store.renew(key, version)
        if isinstance(outcome, (Renewed, Unsupported)):
            return outcome
        if isinstance(outcome, Absent):
            return Refusal(key, "object is absent; its lifetime has already run out")
        if not isinstance(outcome, Conflict):
            return Refusal(key, outcome.reason)
        current = store.read(key)
        if isinstance(current, ReadFailed):
            return Refusal(key, current.reason)
        if not isinstance(current, Present):
            return Refusal(key, "object is absent; its lifetime has already run out")
        version = current.version
    return Refusal(key, "renewal kept conflicting with a concurrent write")


def renew_pointed_execution(  # pylint: disable=too-many-return-statements,too-many-locals
    store: ObjectStore,
    pointer_key: str,
    storage_root: str,
    http_root: str,
    *,
    attempts: int = 3,
) -> RenewalOutcome:
    """Extend the lifetime of the execution *pointer_key* currently names.

    Report callers should use ``CompleteReportPublisher.renew``, which supplies
    the two roots it already holds.

    Args:
        store: The store holding both the pointer and the execution.
        pointer_key: The object key of the redirect.
        storage_root: The publisher's object-key root, without the UUID.
        http_root: The publisher's serving root, without the UUID.
        attempts: How many times one object may be reread after a conflict.

    Returns:
        One of ``ExecutionRenewed``, ``RenewalIncomplete``, ``RenewalUnsupported``,
        ``NothingPointedAt``, ``PointerMoved`` or ``RenewalFailed``. Only
        ``RenewalIncomplete`` and ``RenewalFailed`` ask the caller to do anything.

    Raises:
        ValueError: If a key is not a safe relative object key, the serving root
            is not an absolute http(s) URL, or *attempts* is not positive.
    """
    safe_path(pointer_key)
    safe_path(storage_root)
    if attempts < 1:
        raise ValueError("renewal attempts must be positive")
    pointer = store.read(pointer_key)
    if isinstance(pointer, ReadFailed):
        return RenewalFailed(pointer.reason, pointer_key)
    if isinstance(pointer, Absent):
        return NothingPointedAt("no pointer is published at this key")
    try:
        target = read_pointer(pointer.data).target
    except (ValueError, KeyError, TypeError) as exc:
        return RenewalFailed(f"invalid pointer: {exc}", pointer_key)
    prefix = execution_prefix(target, http_root, storage_root)
    if prefix is None:
        return RenewalFailed(f"pointer names {target}, which is not served from here", pointer_key)
    inventory = _inventory(store, prefix)
    if isinstance(inventory, RenewalFailed):
        return inventory
    if f"{prefix}/{MANIFEST}" not in {item.key for item in inventory}:
        # Whatever else is left, an execution without its manifest is a report
        # page that can no longer be served or verified.
        return RenewalFailed("the pointed-at execution has no manifest", f"{prefix}/{MANIFEST}")
    renewed: list[str] = []
    refused: list[Refusal] = []
    expiries: list[float] = []
    for key, version in [(item.key, item.version) for item in inventory] + [
        (pointer_key, pointer.version)
    ]:
        outcome = _renew_one(store, key, version, attempts)
        if isinstance(outcome, Unsupported):
            # Renewal is a property of the store, not of one object, so the
            # first Unsupported answers for all of them.
            return RenewalUnsupported(outcome.reason, target)
        if isinstance(outcome, Refusal):
            refused.append(outcome)
            continue
        renewed.append(key)
        if outcome.expires_at is not None:
            expiries.append(outcome.expires_at)
    if refused:
        return RenewalIncomplete(target, prefix, tuple(renewed), tuple(refused))
    # A reread that fails says nothing about the renewal, which is already done.
    after = store.read(pointer_key)
    if isinstance(after, Present):
        try:
            current = read_pointer(after.data).target
        except (ValueError, KeyError, TypeError):
            current = target
        if current != target:
            return PointerMoved(target, current)
    return ExecutionRenewed(target, prefix, tuple(renewed), min(expiries) if expiries else None)
